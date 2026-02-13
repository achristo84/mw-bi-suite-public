"""Order Builder API endpoints.

Manages cart building - assigning order list items to specific
distributors and quantities, then finalizing into orders.
"""
from datetime import datetime, date, timedelta
from typing import Optional
from uuid import UUID
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    OrderListItem,
    OrderListItemAssignment,
    Order,
    OrderLine,
    Distributor,
    DistIngredient,
    PriceHistory,
)
from app.schemas.order_hub import (
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentResponse,
    AssignmentWithDetails,
    CartItem,
    DistributorCart,
    OrderBuilderSummary,
    FinalizeRequest,
    FinalizeResponse,
    OrderWithDetails,
    CopyListItem,
    CopyListResponse,
)

router = APIRouter(prefix="/order-builder", tags=["order-builder"])


@router.post("/assign", response_model=AssignmentWithDetails, status_code=201)
def create_assignment(
    data: AssignmentCreate,
    db: Session = Depends(get_db),
):
    """Assign an order list item to a specific distributor SKU.

    This adds the item to the cart for that distributor.

    Either dist_ingredient_id OR (distributor_id + sku) must be provided.
    If dist_ingredient_id is not provided, the system will look up or create
    a dist_ingredient from the search result data.
    """
    # Validate order list item exists and is pending
    order_list_item = db.query(OrderListItem).filter(
        OrderListItem.id == data.order_list_item_id,
    ).first()

    if not order_list_item:
        raise HTTPException(status_code=404, detail="Order list item not found")

    if order_list_item.status != OrderListItem.STATUS_PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Order list item is {order_list_item.status}, not pending",
        )

    # Get or create dist_ingredient
    dist_ingredient = None

    if data.dist_ingredient_id:
        # Option 1: Use existing dist_ingredient_id
        dist_ingredient = db.query(DistIngredient).options(
            joinedload(DistIngredient.distributor),
        ).filter(
            DistIngredient.id == data.dist_ingredient_id,
        ).first()

        if not dist_ingredient:
            raise HTTPException(status_code=404, detail="Distributor ingredient not found")

    elif data.distributor_id and data.sku:
        # Option 2: Find or create from search result data
        distributor = db.query(Distributor).filter(
            Distributor.id == data.distributor_id,
        ).first()

        if not distributor:
            raise HTTPException(status_code=404, detail="Distributor not found")

        # Try to find existing by distributor + sku
        dist_ingredient = db.query(DistIngredient).options(
            joinedload(DistIngredient.distributor),
        ).filter(
            DistIngredient.distributor_id == data.distributor_id,
            DistIngredient.sku == data.sku,
        ).first()

        if not dist_ingredient:
            # Create new dist_ingredient from search result
            dist_ingredient = DistIngredient(
                id=uuid.uuid4(),
                distributor_id=data.distributor_id,
                sku=data.sku,
                description=data.description or data.sku,
                pack_size=None,  # Parse from pack_size string if needed
                pack_unit=data.pack_unit,
                is_active=True,
            )
            dist_ingredient.distributor = distributor
            db.add(dist_ingredient)
            db.flush()

        # Record price if provided
        if data.price_cents is not None:
            from datetime import date as date_type
            price_entry = PriceHistory(
                id=uuid.uuid4(),
                dist_ingredient_id=dist_ingredient.id,
                price_cents=data.price_cents,
                effective_date=date_type.today(),
                source="order_hub_search",
            )
            db.add(price_entry)

    else:
        raise HTTPException(
            status_code=400,
            detail="Either dist_ingredient_id or (distributor_id + sku) must be provided",
        )

    # Create assignment
    assignment = OrderListItemAssignment(
        id=uuid.uuid4(),
        order_list_item_id=data.order_list_item_id,
        dist_ingredient_id=dist_ingredient.id,
        quantity=data.quantity,
    )

    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    # Get price - prefer provided price (from search), fall back to database
    price = data.price_cents if data.price_cents is not None else _get_latest_price(db, dist_ingredient.id)

    return AssignmentWithDetails(
        id=assignment.id,
        order_list_item_id=assignment.order_list_item_id,
        dist_ingredient_id=assignment.dist_ingredient_id,
        quantity=assignment.quantity,
        order_id=assignment.order_id,
        created_at=assignment.created_at,
        distributor_id=dist_ingredient.distributor_id,
        distributor_name=dist_ingredient.distributor.name,
        sku=dist_ingredient.sku,
        description=dist_ingredient.description,
        pack_size=dist_ingredient.pack_size,
        pack_unit=dist_ingredient.pack_unit,
        unit_price_cents=price,
        extended_price_cents=price * data.quantity if price else None,
    )


@router.patch("/assign/{assignment_id}", response_model=AssignmentWithDetails)
def update_assignment(
    assignment_id: UUID,
    data: AssignmentUpdate,
    db: Session = Depends(get_db),
):
    """Update an assignment (change quantity or move to different SKU)."""
    assignment = db.query(OrderListItemAssignment).filter(
        OrderListItemAssignment.id == assignment_id,
    ).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if assignment.order_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot modify assignment - already linked to an order",
        )

    # Update quantity if provided
    if data.quantity is not None:
        assignment.quantity = data.quantity

    # Update dist_ingredient if provided (move to different distributor)
    if data.dist_ingredient_id is not None:
        dist_ingredient = db.query(DistIngredient).filter(
            DistIngredient.id == data.dist_ingredient_id,
        ).first()

        if not dist_ingredient:
            raise HTTPException(status_code=404, detail="Distributor ingredient not found")

        assignment.dist_ingredient_id = data.dist_ingredient_id

    db.commit()
    db.refresh(assignment)

    # Load relationships for response
    assignment = db.query(OrderListItemAssignment).options(
        joinedload(OrderListItemAssignment.dist_ingredient).joinedload(
            DistIngredient.distributor
        ),
    ).filter(
        OrderListItemAssignment.id == assignment_id,
    ).first()

    price = _get_latest_price(db, assignment.dist_ingredient_id)

    return AssignmentWithDetails(
        id=assignment.id,
        order_list_item_id=assignment.order_list_item_id,
        dist_ingredient_id=assignment.dist_ingredient_id,
        quantity=assignment.quantity,
        order_id=assignment.order_id,
        created_at=assignment.created_at,
        distributor_id=assignment.dist_ingredient.distributor_id,
        distributor_name=assignment.dist_ingredient.distributor.name,
        sku=assignment.dist_ingredient.sku,
        description=assignment.dist_ingredient.description,
        pack_size=assignment.dist_ingredient.pack_size,
        pack_unit=assignment.dist_ingredient.pack_unit,
        unit_price_cents=price,
        extended_price_cents=price * assignment.quantity if price else None,
    )


@router.delete("/assign/{assignment_id}", status_code=204)
def delete_assignment(
    assignment_id: UUID,
    db: Session = Depends(get_db),
):
    """Remove an assignment (remove item from distributor cart)."""
    assignment = db.query(OrderListItemAssignment).filter(
        OrderListItemAssignment.id == assignment_id,
    ).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if assignment.order_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete assignment - already linked to an order",
        )

    db.delete(assignment)
    db.commit()

    return None


@router.get("/summary", response_model=OrderBuilderSummary)
def get_builder_summary(
    db: Session = Depends(get_db),
):
    """Get current state of all carts being built.

    Returns assignments grouped by distributor with totals
    and minimum order status.
    """
    # Get all pending assignments (not yet linked to orders)
    assignments = db.query(OrderListItemAssignment).options(
        joinedload(OrderListItemAssignment.order_list_item),
        joinedload(OrderListItemAssignment.dist_ingredient).joinedload(
            DistIngredient.distributor
        ),
    ).filter(
        OrderListItemAssignment.order_id.is_(None),
    ).all()

    # Group by distributor
    distributor_assignments: dict[UUID, list[OrderListItemAssignment]] = {}
    for assignment in assignments:
        dist_id = assignment.dist_ingredient.distributor_id
        if dist_id not in distributor_assignments:
            distributor_assignments[dist_id] = []
        distributor_assignments[dist_id].append(assignment)

    # Build carts
    carts = []
    total_items = 0
    total_cents = 0
    ready_count = 0

    for dist_id, dist_assignments in distributor_assignments.items():
        distributor = dist_assignments[0].dist_ingredient.distributor

        items = []
        subtotal = 0

        for assignment in dist_assignments:
            price = _get_latest_price(db, assignment.dist_ingredient_id)
            extended = price * assignment.quantity if price else 0

            items.append(CartItem(
                assignment_id=assignment.id,
                order_list_item_id=assignment.order_list_item_id,
                order_list_item_name=assignment.order_list_item.name,
                dist_ingredient_id=assignment.dist_ingredient_id,
                sku=assignment.dist_ingredient.sku,
                description=assignment.dist_ingredient.description,
                quantity=assignment.quantity,
                unit_price_cents=price,
                extended_price_cents=extended,
            ))

            subtotal += extended
            total_items += 1

        total_cents += subtotal

        # Check minimum order
        min_cents = distributor.minimum_order_cents or 0
        min_items = distributor.order_minimum_items
        meets_min_cents = subtotal >= min_cents
        meets_min_items = min_items is None or len(items) >= min_items
        meets_minimum = meets_min_cents and meets_min_items

        if meets_minimum:
            ready_count += 1

        # Calculate next delivery date
        next_delivery = _calculate_next_delivery(distributor)

        carts.append(DistributorCart(
            distributor_id=distributor.id,
            distributor_name=distributor.name,
            delivery_days=distributor.delivery_days,
            order_cutoff_time=(
                distributor.order_cutoff_time.isoformat()
                if distributor.order_cutoff_time else None
            ),
            next_delivery_date=next_delivery,
            minimum_order_cents=min_cents,
            order_minimum_items=min_items,
            items=items,
            subtotal_cents=subtotal,
            meets_minimum=meets_minimum,
            ordering_enabled=distributor.ordering_enabled,
        ))

    # Sort carts by name
    carts.sort(key=lambda c: c.distributor_name)

    return OrderBuilderSummary(
        carts=carts,
        total_items=total_items,
        total_cents=total_cents,
        ready_to_order=ready_count,
    )


def _get_latest_price(db: Session, dist_ingredient_id: UUID) -> Optional[int]:
    """Get the most recent price for a dist_ingredient."""
    price = db.query(PriceHistory).filter(
        PriceHistory.dist_ingredient_id == dist_ingredient_id,
    ).order_by(desc(PriceHistory.effective_date)).first()

    return price.price_cents if price else None


def _calculate_next_delivery(distributor: Distributor) -> Optional[date]:
    """Calculate the next delivery date for a distributor."""
    if not distributor.delivery_days:
        return None

    # Map day names to weekday numbers
    day_map = {
        "mon": 0, "monday": 0,
        "tue": 1, "tuesday": 1,
        "wed": 2, "wednesday": 2,
        "thu": 3, "thursday": 3,
        "fri": 4, "friday": 4,
        "sat": 5, "saturday": 5,
        "sun": 6, "sunday": 6,
    }

    delivery_weekdays = []
    for day in distributor.delivery_days:
        weekday = day_map.get(day.lower())
        if weekday is not None:
            delivery_weekdays.append(weekday)

    if not delivery_weekdays:
        return None

    today = date.today()
    current_weekday = today.weekday()

    # Find the next delivery day
    for i in range(1, 8):  # Check next 7 days
        check_date = today + timedelta(days=i)
        if check_date.weekday() in delivery_weekdays:
            # Check cutoff time
            if distributor.order_cutoff_hours:
                cutoff_date = check_date - timedelta(
                    hours=distributor.order_cutoff_hours
                )
                if datetime.now() > datetime.combine(cutoff_date, datetime.min.time()):
                    continue  # Past cutoff, try next delivery day
            return check_date

    return None


# Orders API

orders_router = APIRouter(prefix="/orders", tags=["orders"])


@orders_router.post("/finalize", response_model=FinalizeResponse)
def finalize_orders(
    data: FinalizeRequest,
    db: Session = Depends(get_db),
):
    """Finalize pending assignments into orders.

    Creates one order per distributor with all assigned items.
    """
    # Get pending assignments
    query = db.query(OrderListItemAssignment).options(
        joinedload(OrderListItemAssignment.order_list_item),
        joinedload(OrderListItemAssignment.dist_ingredient).joinedload(
            DistIngredient.distributor
        ),
    ).filter(
        OrderListItemAssignment.order_id.is_(None),
    )

    if data.distributor_ids:
        # Filter to specific distributors
        query = query.join(DistIngredient).filter(
            DistIngredient.distributor_id.in_(data.distributor_ids),
        )

    assignments = query.all()

    if not assignments:
        raise HTTPException(
            status_code=400,
            detail="No pending assignments to finalize",
        )

    # Group by distributor
    by_distributor: dict[UUID, list[OrderListItemAssignment]] = {}
    for assignment in assignments:
        dist_id = assignment.dist_ingredient.distributor_id
        if dist_id not in by_distributor:
            by_distributor[dist_id] = []
        by_distributor[dist_id].append(assignment)

    # Create orders
    orders = []
    total_items = 0
    total_cents = 0

    for dist_id, dist_assignments in by_distributor.items():
        distributor = dist_assignments[0].dist_ingredient.distributor

        # Calculate next delivery
        next_delivery = _calculate_next_delivery(distributor)

        # Create order
        order = Order(
            id=uuid.uuid4(),
            distributor_id=dist_id,
            status=Order.STATUS_DRAFT,
            expected_delivery=next_delivery,
        )
        db.add(order)
        db.flush()  # Get ID before creating lines

        # Create order lines and link assignments
        lines = []
        subtotal = 0

        for assignment in dist_assignments:
            price = _get_latest_price(db, assignment.dist_ingredient_id)
            extended = price * assignment.quantity if price else 0

            # Create order line
            line = OrderLine(
                id=uuid.uuid4(),
                order_id=order.id,
                dist_ingredient_id=assignment.dist_ingredient_id,
                quantity=assignment.quantity,
                expected_price_cents=price,
            )
            db.add(line)

            # Link assignment to order
            assignment.order_id = order.id

            # Update order list item status
            assignment.order_list_item.status = OrderListItem.STATUS_ORDERED
            assignment.order_list_item.updated_at = datetime.utcnow()

            lines.append(CartItem(
                assignment_id=assignment.id,
                order_list_item_id=assignment.order_list_item_id,
                order_list_item_name=assignment.order_list_item.name,
                dist_ingredient_id=assignment.dist_ingredient_id,
                sku=assignment.dist_ingredient.sku,
                description=assignment.dist_ingredient.description,
                quantity=assignment.quantity,
                unit_price_cents=price,
                extended_price_cents=extended,
            ))

            subtotal += extended
            total_items += 1

        total_cents += subtotal

        orders.append(OrderWithDetails(
            id=order.id,
            distributor_id=dist_id,
            distributor_name=distributor.name,
            status=order.status,
            submitted_at=order.submitted_at,
            expected_delivery=order.expected_delivery,
            confirmation_number=order.confirmation_number,
            notes=order.notes,
            created_at=order.created_at,
            updated_at=order.updated_at,
            lines=lines,
            subtotal_cents=subtotal,
        ))

    db.commit()

    return FinalizeResponse(
        orders=orders,
        items_ordered=total_items,
        total_cents=total_cents,
    )


@orders_router.get("", response_model=list[OrderWithDetails])
def list_orders(
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List orders with optional status filter."""
    query = db.query(Order).options(
        joinedload(Order.distributor),
        joinedload(Order.lines).joinedload(OrderLine.dist_ingredient),
        joinedload(Order.list_item_assignments).joinedload(
            OrderListItemAssignment.order_list_item
        ),
    )

    if status:
        query = query.filter(Order.status == status)

    query = query.order_by(desc(Order.created_at)).limit(limit)

    orders = query.all()

    result = []
    for order in orders:
        lines = []
        subtotal = 0

        for line in order.lines:
            extended = (
                line.expected_price_cents * int(line.quantity)
                if line.expected_price_cents else 0
            )

            # Try to find assignment for this line
            assignment = next(
                (a for a in order.list_item_assignments
                 if a.dist_ingredient_id == line.dist_ingredient_id),
                None,
            )

            lines.append(CartItem(
                assignment_id=assignment.id if assignment else uuid.uuid4(),
                order_list_item_id=assignment.order_list_item_id if assignment else uuid.uuid4(),
                order_list_item_name=(
                    assignment.order_list_item.name if assignment
                    else line.dist_ingredient.description
                ),
                dist_ingredient_id=line.dist_ingredient_id,
                sku=line.dist_ingredient.sku,
                description=line.dist_ingredient.description,
                quantity=int(line.quantity),
                unit_price_cents=line.expected_price_cents,
                extended_price_cents=extended,
            ))
            subtotal += extended

        result.append(OrderWithDetails(
            id=order.id,
            distributor_id=order.distributor_id,
            distributor_name=order.distributor.name,
            status=order.status,
            submitted_at=order.submitted_at,
            expected_delivery=order.expected_delivery,
            confirmation_number=order.confirmation_number,
            notes=order.notes,
            created_at=order.created_at,
            updated_at=order.updated_at,
            lines=lines,
            subtotal_cents=subtotal,
        ))

    return result


@orders_router.get("/{order_id}", response_model=OrderWithDetails)
def get_order(
    order_id: UUID,
    db: Session = Depends(get_db),
):
    """Get a single order with details."""
    order = db.query(Order).options(
        joinedload(Order.distributor),
        joinedload(Order.lines).joinedload(OrderLine.dist_ingredient),
        joinedload(Order.list_item_assignments).joinedload(
            OrderListItemAssignment.order_list_item
        ),
    ).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    lines = []
    subtotal = 0

    for line in order.lines:
        extended = (
            line.expected_price_cents * int(line.quantity)
            if line.expected_price_cents else 0
        )

        assignment = next(
            (a for a in order.list_item_assignments
             if a.dist_ingredient_id == line.dist_ingredient_id),
            None,
        )

        lines.append(CartItem(
            assignment_id=assignment.id if assignment else uuid.uuid4(),
            order_list_item_id=assignment.order_list_item_id if assignment else uuid.uuid4(),
            order_list_item_name=(
                assignment.order_list_item.name if assignment
                else line.dist_ingredient.description
            ),
            dist_ingredient_id=line.dist_ingredient_id,
            sku=line.dist_ingredient.sku,
            description=line.dist_ingredient.description,
            quantity=int(line.quantity),
            unit_price_cents=line.expected_price_cents,
            extended_price_cents=extended,
        ))
        subtotal += extended

    return OrderWithDetails(
        id=order.id,
        distributor_id=order.distributor_id,
        distributor_name=order.distributor.name,
        status=order.status,
        submitted_at=order.submitted_at,
        expected_delivery=order.expected_delivery,
        confirmation_number=order.confirmation_number,
        notes=order.notes,
        created_at=order.created_at,
        updated_at=order.updated_at,
        lines=lines,
        subtotal_cents=subtotal,
    )


@orders_router.patch("/{order_id}")
def update_order(
    order_id: UUID,
    status: Optional[str] = None,
    confirmation_number: Optional[str] = None,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Update order status or add notes."""
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if status:
        order.status = status
        if status == Order.STATUS_SUBMITTED:
            order.submitted_at = datetime.utcnow()

    if confirmation_number is not None:
        order.confirmation_number = confirmation_number

    if notes is not None:
        order.notes = notes

    order.updated_at = datetime.utcnow()
    db.commit()

    return {"status": "updated"}


@orders_router.get("/{order_id}/copy-list", response_model=CopyListResponse)
def get_copy_list(
    order_id: UUID,
    db: Session = Depends(get_db),
):
    """Get order formatted for copy-paste into distributor portal.

    Returns a formatted text list ready for manual order entry.
    """
    order = db.query(Order).options(
        joinedload(Order.distributor),
        joinedload(Order.lines).joinedload(OrderLine.dist_ingredient),
    ).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    items = []
    lines_text = []

    for line in order.lines:
        items.append(CopyListItem(
            sku=line.dist_ingredient.sku or "",
            description=line.dist_ingredient.description,
            quantity=int(line.quantity),
            notes=None,
        ))

        # Format for copy-paste
        lines_text.append(
            f"{line.dist_ingredient.sku or 'N/A'}\t{int(line.quantity)}\t{line.dist_ingredient.description}"
        )

    formatted = "\n".join(lines_text)

    return CopyListResponse(
        distributor_name=order.distributor.name,
        items=items,
        formatted_text=formatted,
    )
