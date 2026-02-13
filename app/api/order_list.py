"""Order List API endpoints.

Manages the shared "need to order" list where staff can add items
that need to be ordered. This is the digital whiteboard for the team.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    OrderListItem,
    OrderListItemAssignment,
    Order,
    OrderLine,
    Ingredient,
    DistIngredient,
    Distributor,
)
from app.schemas.order_hub import (
    OrderListItemCreate,
    OrderListItemUpdate,
    OrderListItemResponse,
    OrderListItemWithDetails,
    OrderListItemList,
    OrderHistoryEntry,
    OrderHistoryResponse,
)

router = APIRouter(prefix="/order-list", tags=["order-list"])


@router.get("", response_model=OrderListItemList)
def list_order_list_items(
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    """List all items in the order list.

    Optionally filter by status: pending, ordered, received
    """
    query = db.query(OrderListItem).options(
        joinedload(OrderListItem.ingredient),
        joinedload(OrderListItem.assignments).joinedload(
            OrderListItemAssignment.order
        ).joinedload(Order.distributor),
    )

    if status:
        query = query.filter(OrderListItem.status == status)

    query = query.order_by(
        desc(OrderListItem.status == OrderListItem.STATUS_PENDING),
        desc(OrderListItem.created_at),
    )

    items = query.all()

    # Build response with details
    result_items = []
    for item in items:
        # Get last ordered info from assignments
        last_order_info = _get_last_order_info(item)

        result_items.append(
            OrderListItemWithDetails(
                id=item.id,
                name=item.name,
                quantity=item.quantity,
                notes=item.notes,
                ingredient_id=item.ingredient_id,
                status=item.status,
                created_by=item.created_by,
                created_at=item.created_at,
                updated_at=item.updated_at,
                ingredient_name=item.ingredient.name if item.ingredient else None,
                assignments_count=len(item.assignments),
                last_ordered_at=last_order_info.get("ordered_at"),
                last_ordered_distributor=last_order_info.get("distributor_name"),
                last_ordered_price_cents=last_order_info.get("price_cents"),
            )
        )

    return OrderListItemList(items=result_items, count=len(result_items))


def _get_last_order_info(item: OrderListItem) -> dict:
    """Get info about the last time this item was ordered."""
    for assignment in sorted(
        item.assignments,
        key=lambda a: a.order.submitted_at if a.order and a.order.submitted_at else datetime.min,
        reverse=True,
    ):
        if assignment.order and assignment.order.submitted_at:
            return {
                "ordered_at": assignment.order.submitted_at,
                "distributor_name": assignment.order.distributor.name if assignment.order.distributor else None,
                "price_cents": None,  # Not tracked at order level yet
            }
    return {}


@router.get("/{item_id}", response_model=OrderListItemWithDetails)
def get_order_list_item(
    item_id: UUID,
    db: Session = Depends(get_db),
):
    """Get a single order list item by ID."""
    item = db.query(OrderListItem).options(
        joinedload(OrderListItem.ingredient),
        joinedload(OrderListItem.assignments),
    ).filter(OrderListItem.id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Order list item not found")

    last_order_info = _get_last_order_info(item)

    return OrderListItemWithDetails(
        id=item.id,
        name=item.name,
        quantity=item.quantity,
        notes=item.notes,
        ingredient_id=item.ingredient_id,
        status=item.status,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
        ingredient_name=item.ingredient.name if item.ingredient else None,
        assignments_count=len(item.assignments),
        last_ordered_at=last_order_info.get("ordered_at"),
        last_ordered_distributor=last_order_info.get("distributor_name"),
        last_ordered_price_cents=last_order_info.get("price_cents"),
    )


@router.post("", response_model=OrderListItemResponse, status_code=201)
def create_order_list_item(
    data: OrderListItemCreate,
    db: Session = Depends(get_db),
):
    """Add a new item to the order list."""
    # Check for existing pending item with same name (case-insensitive) and no assignments
    existing = db.query(OrderListItem).filter(
        func.lower(OrderListItem.name) == func.lower(data.name),
        OrderListItem.status == OrderListItem.STATUS_PENDING,
    ).first()

    if existing:
        # Count assignments for this item
        assignment_count = db.query(OrderListItemAssignment).filter(
            OrderListItemAssignment.order_list_item_id == existing.id
        ).count()

        if assignment_count == 0:
            raise HTTPException(
                status_code=409,
                detail=f"'{existing.name}' is already on the list"
            )

    # Validate ingredient_id if provided
    if data.ingredient_id:
        ingredient = db.query(Ingredient).filter(
            Ingredient.id == data.ingredient_id
        ).first()
        if not ingredient:
            raise HTTPException(status_code=400, detail="Ingredient not found")

    item = OrderListItem(
        id=uuid.uuid4(),
        name=data.name,
        quantity=data.quantity,
        notes=data.notes,
        ingredient_id=data.ingredient_id,
        status=OrderListItem.STATUS_PENDING,
        created_by=data.created_by,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return OrderListItemResponse.model_validate(item)


@router.patch("/{item_id}", response_model=OrderListItemResponse)
def update_order_list_item(
    item_id: UUID,
    data: OrderListItemUpdate,
    db: Session = Depends(get_db),
):
    """Update an order list item."""
    item = db.query(OrderListItem).filter(
        OrderListItem.id == item_id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Order list item not found")

    # Validate ingredient_id if being updated
    if data.ingredient_id is not None:
        if data.ingredient_id:
            ingredient = db.query(Ingredient).filter(
                Ingredient.id == data.ingredient_id
            ).first()
            if not ingredient:
                raise HTTPException(status_code=400, detail="Ingredient not found")

    # Apply updates
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)

    return OrderListItemResponse.model_validate(item)


@router.delete("/{item_id}", status_code=204)
def delete_order_list_item(
    item_id: UUID,
    db: Session = Depends(get_db),
):
    """Remove an item from the order list.

    This also deletes any assignments for this item.
    """
    item = db.query(OrderListItem).filter(
        OrderListItem.id == item_id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Order list item not found")

    # Cascade delete will handle assignments
    db.delete(item)
    db.commit()

    return None


@router.get("/{item_id}/history", response_model=OrderHistoryResponse)
def get_order_history(
    item_id: UUID,
    db: Session = Depends(get_db),
):
    """Get order history for an item.

    Shows past orders, prices, and distributors for this item.
    If the item is linked to an ingredient, also shows orders
    for that ingredient from any order list item.
    """
    item = db.query(OrderListItem).filter(
        OrderListItem.id == item_id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Order list item not found")

    entries = []

    # Get history from this item's assignments
    assignments = db.query(OrderListItemAssignment).options(
        joinedload(OrderListItemAssignment.order).joinedload(Order.distributor),
        joinedload(OrderListItemAssignment.dist_ingredient),
    ).filter(
        OrderListItemAssignment.order_list_item_id == item_id,
        OrderListItemAssignment.order_id.isnot(None),
    ).all()

    for assignment in assignments:
        if assignment.order:
            entries.append(
                OrderHistoryEntry(
                    order_id=assignment.order.id,
                    order_date=assignment.order.submitted_at or assignment.order.created_at,
                    distributor_name=assignment.order.distributor.name,
                    sku=assignment.dist_ingredient.sku if assignment.dist_ingredient else None,
                    description=assignment.dist_ingredient.description if assignment.dist_ingredient else item.name,
                    quantity=assignment.quantity,
                    price_cents=0,  # Not tracked at assignment level yet
                    status=assignment.order.status,
                )
            )

    # If linked to an ingredient, also get order line history
    if item.ingredient_id:
        order_lines = db.query(OrderLine).join(
            DistIngredient
        ).join(
            Order
        ).join(
            Distributor
        ).filter(
            DistIngredient.ingredient_id == item.ingredient_id,
        ).order_by(desc(Order.created_at)).limit(20).all()

        for line in order_lines:
            entries.append(
                OrderHistoryEntry(
                    order_id=line.order.id,
                    order_date=line.order.submitted_at or line.order.created_at,
                    distributor_name=line.order.distributor.name,
                    sku=line.dist_ingredient.sku,
                    description=line.dist_ingredient.description,
                    quantity=int(line.quantity),
                    price_cents=line.expected_price_cents or 0,
                    status=line.order.status,
                )
            )

    # Sort by date descending and dedupe
    seen = set()
    unique_entries = []
    for entry in sorted(entries, key=lambda e: e.order_date, reverse=True):
        key = (entry.order_id, entry.sku)
        if key not in seen:
            seen.add(key)
            unique_entries.append(entry)

    return OrderHistoryResponse(
        item_name=item.name,
        entries=unique_entries[:50],  # Limit to 50 entries
        count=len(unique_entries),
    )


@router.post("/{item_id}/link-ingredient", response_model=OrderListItemResponse)
def link_to_ingredient(
    item_id: UUID,
    ingredient_id: UUID,
    db: Session = Depends(get_db),
):
    """Link an order list item to a canonical ingredient.

    This enables richer history tracking and suggestions.
    """
    item = db.query(OrderListItem).filter(
        OrderListItem.id == item_id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Order list item not found")

    ingredient = db.query(Ingredient).filter(
        Ingredient.id == ingredient_id
    ).first()

    if not ingredient:
        raise HTTPException(status_code=400, detail="Ingredient not found")

    item.ingredient_id = ingredient_id
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)

    return OrderListItemResponse.model_validate(item)
