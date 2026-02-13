"""Invoice management API endpoints."""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload
from google.cloud import storage

from app.database import get_db
from app.models import Invoice, InvoiceLine, Distributor
from app.models.ingredient import DistIngredient, Ingredient, PriceHistory
from app.services.invoice_parser import get_invoice_parser
from app.services.price_pipeline import process_approved_invoice

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["invoices"])

from app.config import get_settings

_settings = get_settings()
PROJECT_ID = _settings.GCP_PROJECT_ID
BUCKET_NAME = _settings.GCS_BUCKET_NAME


# Pydantic schemas
class InvoiceLineResponse(BaseModel):
    id: UUID
    invoice_id: UUID
    raw_description: str
    raw_sku: Optional[str]
    quantity_ordered: Optional[float]
    quantity: Optional[float]
    unit: Optional[str]
    unit_price_cents: Optional[int]
    extended_price_cents: Optional[int]
    is_taxable: bool
    line_type: str
    parent_line_id: Optional[UUID]
    line_status: str = "pending"  # pending, confirmed, removed

    class Config:
        from_attributes = True


class DistributorResponse(BaseModel):
    id: UUID
    name: str
    invoice_email: Optional[str]
    filename_pattern: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    id: UUID
    distributor_id: UUID
    distributor: Optional[DistributorResponse]
    invoice_number: str
    invoice_date: str
    delivery_date: Optional[str]
    due_date: Optional[str]
    account_number: Optional[str]
    sales_rep_name: Optional[str]
    sales_order_number: Optional[str]
    subtotal_cents: Optional[int]
    tax_cents: Optional[int]
    total_cents: int
    pdf_path: Optional[str]
    parse_confidence: Optional[float]
    parsed_at: Optional[str]
    reviewed_by: Optional[str]
    reviewed_at: Optional[str]
    paid_at: Optional[str]
    source: str
    review_status: str
    lines: Optional[list[InvoiceLineResponse]]
    created_at: str

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_dates(cls, invoice: Invoice, include_lines: bool = False):
        data = {
            "id": invoice.id,
            "distributor_id": invoice.distributor_id,
            "distributor": invoice.distributor,
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
            "delivery_date": invoice.delivery_date.isoformat() if invoice.delivery_date else None,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "account_number": invoice.account_number,
            "sales_rep_name": invoice.sales_rep_name,
            "sales_order_number": invoice.sales_order_number,
            "subtotal_cents": invoice.subtotal_cents,
            "tax_cents": invoice.tax_cents,
            "total_cents": invoice.total_cents,
            "pdf_path": invoice.pdf_path,
            "parse_confidence": float(invoice.parse_confidence) if invoice.parse_confidence else None,
            "parsed_at": invoice.parsed_at.isoformat() if invoice.parsed_at else None,
            "reviewed_by": invoice.reviewed_by,
            "reviewed_at": invoice.reviewed_at.isoformat() if invoice.reviewed_at else None,
            "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
            "source": invoice.source or "email",
            "review_status": invoice.review_status or "pending",
            "lines": invoice.lines if include_lines else None,
            "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        }
        return cls(**data)


class InvoiceListResponse(BaseModel):
    invoices: list[InvoiceResponse]
    total: int
    page: int
    limit: int


class InvoiceLineStats(BaseModel):
    """Stats about invoice line mapping status."""
    total_lines: int
    mapped_lines: int  # Has dist_ingredient with ingredient_id
    unmapped_lines: int  # No dist_ingredient or null ingredient_id
    priced_lines: int  # Has price_history entries


class InvoiceWithStats(BaseModel):
    """Invoice with line mapping statistics."""
    id: UUID
    distributor_id: UUID
    distributor_name: str
    invoice_number: str
    invoice_date: str
    total_cents: int
    review_status: str
    source: str
    stats: InvoiceLineStats

    class Config:
        from_attributes = True


class InvoiceWithStatsResponse(BaseModel):
    """Response for invoices with stats endpoint."""
    invoices: list[InvoiceWithStats]
    total: int


class InvoiceLineForPricing(BaseModel):
    """Invoice line with mapping status for pricing UI."""
    id: UUID
    invoice_id: UUID
    raw_description: str
    raw_sku: Optional[str]
    quantity: Optional[float]
    unit: Optional[str]
    unit_price_cents: Optional[int]
    extended_price_cents: Optional[int]
    dist_ingredient_id: Optional[UUID]
    mapped_ingredient_id: Optional[UUID]
    mapped_ingredient_name: Optional[str]
    # Color coding: 'green' (mapped to this ingredient), 'yellow' (unmapped),
    # 'grey' (mapped to different ingredient), 'orange' (mapped but unpriced)
    status: str
    has_price: bool

    class Config:
        from_attributes = True


class InvoiceLinesForPricingResponse(BaseModel):
    """Response for invoice lines for pricing."""
    invoice_id: UUID
    invoice_number: str
    distributor_name: str
    invoice_date: str
    lines: list[InvoiceLineForPricing]


class InvoiceLineUpdate(BaseModel):
    raw_description: Optional[str] = None
    raw_sku: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price_cents: Optional[int] = None
    extended_price_cents: Optional[int] = None


class ManualInvoiceCreate(BaseModel):
    distributor_id: UUID
    invoice_number: str
    invoice_date: str
    total_cents: int
    subtotal_cents: Optional[int] = None
    tax_cents: Optional[int] = None
    lines: list[dict]


class RejectRequest(BaseModel):
    reason: Optional[str] = None


# Routes
@router.get("", response_model=InvoiceListResponse)
def list_invoices(
    status: Optional[str] = None,
    distributor_id: Optional[UUID] = None,
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List invoices with optional filtering."""
    query = select(Invoice).options(joinedload(Invoice.distributor))

    # Filter by review status
    if status and status != "all":
        query = query.where(Invoice.review_status == status)

    # Filter by distributor
    if distributor_id:
        query = query.where(Invoice.distributor_id == distributor_id)

    # Order by date descending
    query = query.order_by(Invoice.invoice_date.desc(), Invoice.created_at.desc())

    # Get total count
    count_query = select(func.count(Invoice.id))
    if status and status != "all":
        count_query = count_query.where(Invoice.review_status == status)
    if distributor_id:
        count_query = count_query.where(Invoice.distributor_id == distributor_id)
    total = db.execute(count_query).scalar() or 0

    # Paginate
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    result = db.execute(query)
    invoices = result.scalars().unique().all()

    return InvoiceListResponse(
        invoices=[InvoiceResponse.from_orm_with_dates(inv) for inv in invoices],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/with-stats", response_model=InvoiceWithStatsResponse)
def list_invoices_with_stats(
    distributor_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
):
    """
    List all invoices with line mapping statistics.

    Used by the pricing modal to show which invoices have items to price.
    """
    # Base query for invoices
    query = (
        select(Invoice, Distributor.name.label("distributor_name"))
        .join(Distributor, Invoice.distributor_id == Distributor.id)
        .order_by(Invoice.invoice_date.desc())
    )

    if distributor_id:
        query = query.where(Invoice.distributor_id == distributor_id)

    result = db.execute(query)
    invoice_rows = result.all()

    invoices_with_stats = []

    for invoice, dist_name in invoice_rows:
        # Get line stats for this invoice
        lines = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice.id).all()

        total_lines = len(lines)
        mapped_lines = 0
        priced_lines = 0

        for line in lines:
            if line.dist_ingredient_id:
                # Check if dist_ingredient is mapped to a canonical ingredient
                di = db.query(DistIngredient).filter(DistIngredient.id == line.dist_ingredient_id).first()
                if di and di.ingredient_id:
                    mapped_lines += 1
                    # Check if it has any price history
                    has_price = db.query(PriceHistory).filter(
                        PriceHistory.dist_ingredient_id == di.id
                    ).first() is not None
                    if has_price:
                        priced_lines += 1

        unmapped_lines = total_lines - mapped_lines

        invoices_with_stats.append(InvoiceWithStats(
            id=invoice.id,
            distributor_id=invoice.distributor_id,
            distributor_name=dist_name,
            invoice_number=invoice.invoice_number,
            invoice_date=invoice.invoice_date.isoformat() if invoice.invoice_date else "",
            total_cents=invoice.total_cents,
            review_status=invoice.review_status or "pending",
            source=invoice.source or "email",
            stats=InvoiceLineStats(
                total_lines=total_lines,
                mapped_lines=mapped_lines,
                unmapped_lines=unmapped_lines,
                priced_lines=priced_lines,
            )
        ))

    return InvoiceWithStatsResponse(
        invoices=invoices_with_stats,
        total=len(invoices_with_stats),
    )


@router.get("/{invoice_id}/lines-for-pricing/{ingredient_id}", response_model=InvoiceLinesForPricingResponse)
def get_invoice_lines_for_pricing(
    invoice_id: UUID,
    ingredient_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get invoice lines with mapping status for pricing a specific ingredient.

    Returns color-coded status for each line:
    - 'green': Already mapped to this ingredient and has price
    - 'orange': Mapped to this ingredient but no price
    - 'yellow': Unmapped (can be mapped to this ingredient)
    - 'grey': Mapped to a different ingredient
    """
    # Get invoice with distributor
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.distributor))
        .filter(Invoice.id == invoice_id)
        .first()
    )

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Get all lines for this invoice
    lines = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == invoice_id).all()

    result_lines = []

    for line in lines:
        # Skip credits and fees
        if line.line_type in ('credit', 'fee'):
            continue

        mapped_ingredient_id = None
        mapped_ingredient_name = None
        status = 'yellow'  # Default: unmapped
        has_price = False

        if line.dist_ingredient_id:
            di = (
                db.query(DistIngredient)
                .options(joinedload(DistIngredient.ingredient))
                .filter(DistIngredient.id == line.dist_ingredient_id)
                .first()
            )

            if di and di.ingredient_id:
                mapped_ingredient_id = di.ingredient_id
                mapped_ingredient_name = di.ingredient.name if di.ingredient else None

                # Check if has price
                has_price = db.query(PriceHistory).filter(
                    PriceHistory.dist_ingredient_id == di.id
                ).first() is not None

                if str(di.ingredient_id) == str(ingredient_id):
                    # Mapped to THIS ingredient
                    status = 'green' if has_price else 'orange'
                else:
                    # Mapped to DIFFERENT ingredient
                    status = 'grey'

        result_lines.append(InvoiceLineForPricing(
            id=line.id,
            invoice_id=line.invoice_id,
            raw_description=line.raw_description,
            raw_sku=line.raw_sku,
            quantity=float(line.quantity) if line.quantity else None,
            unit=line.unit,
            unit_price_cents=line.unit_price_cents,
            extended_price_cents=line.extended_price_cents,
            dist_ingredient_id=line.dist_ingredient_id,
            mapped_ingredient_id=mapped_ingredient_id,
            mapped_ingredient_name=mapped_ingredient_name,
            status=status,
            has_price=has_price,
        ))

    return InvoiceLinesForPricingResponse(
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        distributor_name=invoice.distributor.name if invoice.distributor else "Unknown",
        invoice_date=invoice.invoice_date.isoformat() if invoice.invoice_date else "",
        lines=result_lines,
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(invoice_id: UUID, db: Session = Depends(get_db)):
    """Get a single invoice with all line items."""
    result = db.execute(
        select(Invoice)
        .options(joinedload(Invoice.distributor), joinedload(Invoice.lines))
        .where(Invoice.id == invoice_id)
    )
    invoice = result.scalars().unique().first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return InvoiceResponse.from_orm_with_dates(invoice, include_lines=True)


@router.post("/{invoice_id}/approve", response_model=InvoiceResponse)
def approve_invoice(invoice_id: UUID, db: Session = Depends(get_db)):
    """Approve an invoice and populate price_history."""
    # Load invoice with lines for price pipeline
    result = db.execute(
        select(Invoice)
        .options(joinedload(Invoice.lines))
        .where(Invoice.id == invoice_id)
    )
    invoice = result.scalars().unique().first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice.review_status = Invoice.REVIEW_APPROVED
    invoice.reviewed_at = datetime.utcnow()
    invoice.reviewed_by = "owner"  # Single-user system, no auth required

    # Process price pipeline - extract prices and create price_history entries
    try:
        pipeline_result = process_approved_invoice(db, invoice)
        logger.info(
            f"Invoice {invoice.invoice_number} approved. "
            f"Price pipeline: {pipeline_result['prices_created']} prices created, "
            f"{pipeline_result['dist_ingredients_created']} ingredients created"
        )
        if pipeline_result["errors"]:
            logger.warning(f"Price pipeline errors: {pipeline_result['errors']}")
    except Exception as e:
        logger.error(f"Price pipeline failed for invoice {invoice.invoice_number}: {e}")
        # Don't fail the approval if price pipeline fails

    db.commit()
    db.refresh(invoice)

    return InvoiceResponse.from_orm_with_dates(invoice)


@router.post("/{invoice_id}/reject", response_model=InvoiceResponse)
def reject_invoice(
    invoice_id: UUID,
    request: RejectRequest,
    db: Session = Depends(get_db),
):
    """Reject an invoice."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice.review_status = Invoice.REVIEW_REJECTED
    invoice.reviewed_at = datetime.utcnow()
    invoice.reviewed_by = "owner"  # Single-user system, no auth required

    db.commit()
    db.refresh(invoice)

    return InvoiceResponse.from_orm_with_dates(invoice)


@router.delete("/{invoice_id}")
def delete_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete an invoice and all its line items.

    This is a hard delete - use for re-parsing invoices that were parsed incorrectly.
    """
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Delete all line items first
    for line in invoice.lines:
        db.delete(line)

    # Delete the invoice
    db.delete(invoice)
    db.commit()

    return {"status": "deleted", "invoice_id": str(invoice_id)}


@router.patch("/{invoice_id}/lines/{line_id}", response_model=InvoiceResponse)
def update_invoice_line(
    invoice_id: UUID,
    line_id: UUID,
    update: InvoiceLineUpdate,
    db: Session = Depends(get_db),
):
    """Update an invoice line item."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    line = db.get(InvoiceLine, line_id)
    if not line or line.invoice_id != invoice_id:
        raise HTTPException(status_code=404, detail="Line item not found")

    # Update fields
    if update.raw_description is not None:
        line.raw_description = update.raw_description
    if update.raw_sku is not None:
        line.raw_sku = update.raw_sku
    if update.quantity is not None:
        line.quantity = Decimal(str(update.quantity))
    if update.unit is not None:
        line.unit = update.unit
    if update.unit_price_cents is not None:
        line.unit_price_cents = update.unit_price_cents
    if update.extended_price_cents is not None:
        line.extended_price_cents = update.extended_price_cents

    db.commit()

    # Reload invoice with lines
    db.refresh(invoice)
    result = db.execute(
        select(Invoice)
        .options(joinedload(Invoice.lines))
        .where(Invoice.id == invoice_id)
    )
    invoice = result.scalars().unique().first()

    return InvoiceResponse.from_orm_with_dates(invoice, include_lines=True)


class MapLineRequest(BaseModel):
    """Request to map an invoice line to an ingredient."""
    ingredient_id: UUID
    grams_per_unit: Optional[float] = None  # If provided, sets the conversion factor


class MapLineResponse(BaseModel):
    """Response from mapping an invoice line."""
    success: bool
    dist_ingredient_id: UUID
    ingredient_id: UUID
    ingredient_name: str


@router.post("/{invoice_id}/lines/{line_id}/map-ingredient", response_model=MapLineResponse)
def map_invoice_line_to_ingredient(
    invoice_id: UUID,
    line_id: UUID,
    data: MapLineRequest,
    db: Session = Depends(get_db),
):
    """Map an invoice line to a canonical ingredient.

    Creates or updates a dist_ingredient linked to the ingredient.
    If grams_per_unit is provided, also sets the conversion factor.
    """
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    line = db.get(InvoiceLine, line_id)
    if not line or line.invoice_id != invoice_id:
        raise HTTPException(status_code=404, detail="Line item not found")

    # Get the ingredient
    ingredient = db.query(Ingredient).filter(Ingredient.id == data.ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    # Check if line already has a dist_ingredient
    if line.dist_ingredient_id:
        di = db.get(DistIngredient, line.dist_ingredient_id)
        if di:
            # Update existing dist_ingredient
            di.ingredient_id = data.ingredient_id
            if data.grams_per_unit is not None:
                di.grams_per_unit = Decimal(str(data.grams_per_unit))
            db.commit()
            db.refresh(di)
            return MapLineResponse(
                success=True,
                dist_ingredient_id=di.id,
                ingredient_id=ingredient.id,
                ingredient_name=ingredient.name,
            )

    # Create new dist_ingredient
    di = DistIngredient(
        distributor_id=invoice.distributor_id,
        ingredient_id=data.ingredient_id,
        sku=line.raw_sku,
        description=line.raw_description[:255] if line.raw_description else "Unknown",
        is_active=True,
    )
    if data.grams_per_unit is not None:
        di.grams_per_unit = Decimal(str(data.grams_per_unit))

    db.add(di)
    db.flush()

    # Link line to dist_ingredient
    line.dist_ingredient_id = di.id
    db.commit()

    return MapLineResponse(
        success=True,
        dist_ingredient_id=di.id,
        ingredient_id=ingredient.id,
        ingredient_name=ingredient.name,
    )


@router.post("/{invoice_id}/lines/{line_id}/confirm")
def confirm_invoice_line(
    invoice_id: UUID,
    line_id: UUID,
    db: Session = Depends(get_db),
):
    """Mark an invoice line as confirmed/verified."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    line = db.get(InvoiceLine, line_id)
    if not line or line.invoice_id != invoice_id:
        raise HTTPException(status_code=404, detail="Line item not found")

    line.line_status = InvoiceLine.LINE_CONFIRMED
    db.commit()

    return {"success": True, "line_id": str(line_id), "status": "confirmed"}


@router.post("/{invoice_id}/lines/{line_id}/remove")
def remove_invoice_line(
    invoice_id: UUID,
    line_id: UUID,
    db: Session = Depends(get_db),
):
    """Mark an invoice line as removed (item didn't arrive or was returned)."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    line = db.get(InvoiceLine, line_id)
    if not line or line.invoice_id != invoice_id:
        raise HTTPException(status_code=404, detail="Line item not found")

    line.line_status = InvoiceLine.LINE_REMOVED
    db.commit()

    return {"success": True, "line_id": str(line_id), "status": "removed"}


@router.post("/{invoice_id}/lines/{line_id}/reset-status")
def reset_invoice_line_status(
    invoice_id: UUID,
    line_id: UUID,
    db: Session = Depends(get_db),
):
    """Reset an invoice line status back to pending."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    line = db.get(InvoiceLine, line_id)
    if not line or line.invoice_id != invoice_id:
        raise HTTPException(status_code=404, detail="Line item not found")

    line.line_status = InvoiceLine.LINE_PENDING
    db.commit()

    return {"success": True, "line_id": str(line_id), "status": "pending"}


@router.post("/{invoice_id}/reparse", response_model=InvoiceResponse)
def reparse_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete line items and re-parse the invoice PDF.

    Useful when the initial parse was incorrect.
    """
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if not invoice.pdf_path:
        raise HTTPException(status_code=400, detail="No PDF available to re-parse")

    # Delete existing line items
    for line in invoice.lines:
        db.delete(line)
    db.flush()

    # Re-parse the document (PDF or image)
    try:
        parser = get_invoice_parser()

        # Detect file type from path
        path_lower = invoice.pdf_path.lower()
        if any(path_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
            # It's an image - download and parse as image
            image_content = parser.download_pdf_from_gcs(invoice.pdf_path)
            # Determine media type
            if path_lower.endswith('.png'):
                media_type = 'image/png'
            elif path_lower.endswith('.gif'):
                media_type = 'image/gif'
            elif path_lower.endswith('.webp'):
                media_type = 'image/webp'
            else:
                media_type = 'image/jpeg'
            parsed = parser.parse_invoice_from_image(image_content, media_type)
        else:
            # It's a PDF
            parsed = parser.parse_invoice_from_gcs(invoice.pdf_path)

        # Update invoice with new parsed data
        invoice.invoice_number = parsed.invoice_number
        invoice.invoice_date = parsed.invoice_date
        invoice.delivery_date = parsed.delivery_date
        invoice.due_date = parsed.due_date
        invoice.account_number = parsed.account_number
        invoice.sales_rep_name = parsed.sales_rep_name
        invoice.sales_order_number = parsed.sales_order_number
        invoice.subtotal_cents = parsed.subtotal_cents
        invoice.tax_cents = parsed.tax_cents
        invoice.total_cents = parsed.total_cents
        invoice.parse_confidence = parsed.confidence
        invoice.parsed_at = datetime.utcnow()
        invoice.review_status = Invoice.REVIEW_PENDING
        invoice.reviewed_at = None
        invoice.reviewed_by = None

        # Create new line items
        for item in parsed.line_items:
            quantity = item.get("quantity")
            extended_price_cents = item.get("extended_price_cents")
            unit_price_cents = item.get("unit_price_cents")

            # Recalculate unit_price from extended/quantity for accuracy
            # Claude sometimes extracts unit_price incorrectly from invoices
            if quantity and extended_price_cents and quantity > 0:
                unit_price_cents = round(extended_price_cents / quantity)

            line = InvoiceLine(
                invoice_id=invoice.id,
                raw_description=item.get("raw_description", "")[:255],
                raw_sku=item.get("raw_sku"),
                quantity_ordered=item.get("quantity_ordered"),
                quantity=quantity,
                unit=item.get("unit"),
                unit_price_cents=unit_price_cents,
                extended_price_cents=extended_price_cents,
                is_taxable=item.get("is_taxable", False),
                line_type=item.get("line_type", "product"),
                line_status=InvoiceLine.LINE_PENDING,
            )
            db.add(line)

        db.commit()
        db.refresh(invoice)

        return InvoiceResponse.from_orm_with_dates(invoice)

    except Exception as e:
        logger.error(f"Failed to re-parse invoice: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Re-parse failed: {str(e)}")


class ReparsePreviewRequest(BaseModel):
    """Request for reparse preview with optional custom prompt."""
    custom_prompt: Optional[str] = None


class ParsedLineItem(BaseModel):
    """A single parsed line item (preview only, not saved)."""
    raw_description: str
    raw_sku: Optional[str] = None
    quantity_ordered: Optional[float] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price_cents: Optional[int] = None
    extended_price_cents: Optional[int] = None
    is_taxable: bool = False
    line_type: str = "product"


class ReparsePreviewResponse(BaseModel):
    """Response from reparse preview - shows what would be parsed."""
    invoice_number: str
    invoice_date: Optional[str] = None
    total_cents: int
    confidence: float
    line_items: list[ParsedLineItem]
    prompt_used: str


@router.post("/{invoice_id}/reparse-preview", response_model=ReparsePreviewResponse)
def reparse_invoice_preview(
    invoice_id: UUID,
    request: ReparsePreviewRequest,
    db: Session = Depends(get_db),
):
    """Preview re-parsing an invoice with an optional custom prompt.

    This does NOT save anything - it just shows what the parse result would be.
    Use this for the prompt editor modal to let users test prompts.
    """
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if not invoice.pdf_path:
        raise HTTPException(status_code=400, detail="No PDF available to re-parse")

    # Get custom prompt for this distributor if not provided
    custom_prompt = request.custom_prompt
    if custom_prompt is None and invoice.distributor_id:
        distributor = db.get(Distributor, invoice.distributor_id)
        if distributor:
            # Determine which prompt to use based on file type
            path_lower = invoice.pdf_path.lower()
            if any(path_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                custom_prompt = distributor.parsing_prompt_screenshot
            else:
                custom_prompt = distributor.parsing_prompt_pdf

    try:
        parser = get_invoice_parser()

        # Detect file type from path
        path_lower = invoice.pdf_path.lower()
        if any(path_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
            # It's an image
            image_content = parser.download_pdf_from_gcs(invoice.pdf_path)
            if path_lower.endswith('.png'):
                media_type = 'image/png'
            elif path_lower.endswith('.gif'):
                media_type = 'image/gif'
            elif path_lower.endswith('.webp'):
                media_type = 'image/webp'
            else:
                media_type = 'image/jpeg'
            parsed = parser.parse_invoice_from_image(image_content, media_type, custom_prompt)
        else:
            # It's a PDF
            parsed = parser.parse_invoice_from_gcs(invoice.pdf_path, custom_prompt)

        # Convert to response (without saving)
        line_items = []
        for item in parsed.line_items:
            quantity = item.get("quantity")
            extended_price_cents = item.get("extended_price_cents")
            unit_price_cents = item.get("unit_price_cents")

            # Recalculate unit_price from extended/quantity for accuracy
            if quantity and extended_price_cents and quantity > 0:
                unit_price_cents = round(extended_price_cents / quantity)

            line_items.append(ParsedLineItem(
                raw_description=item.get("raw_description", "")[:255],
                raw_sku=item.get("raw_sku"),
                quantity_ordered=item.get("quantity_ordered"),
                quantity=quantity,
                unit=item.get("unit"),
                unit_price_cents=unit_price_cents,
                extended_price_cents=extended_price_cents,
                is_taxable=item.get("is_taxable", False),
                line_type=item.get("line_type", "product"),
            ))

        return ReparsePreviewResponse(
            invoice_number=parsed.invoice_number,
            invoice_date=parsed.invoice_date.isoformat() if parsed.invoice_date else None,
            total_cents=parsed.total_cents,
            confidence=parsed.confidence,
            line_items=line_items,
            prompt_used=parsed.prompt_used,
        )

    except Exception as e:
        logger.error(f"Failed to preview re-parse invoice: {e}")
        raise HTTPException(status_code=500, detail=f"Re-parse preview failed: {str(e)}")


@router.get("/{invoice_id}/pdf")
def get_invoice_pdf(invoice_id: UUID, db: Session = Depends(get_db)):
    """Get the PDF for an invoice."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if not invoice.pdf_path:
        raise HTTPException(status_code=404, detail="No PDF available")

    # Get PDF from Cloud Storage
    try:
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)

        # Handle both gs:// URLs and plain paths
        path = invoice.pdf_path
        if path.startswith("gs://"):
            path = path.replace(f"gs://{BUCKET_NAME}/", "")

        blob = bucket.blob(path)
        content = blob.download_as_bytes()

        return StreamingResponse(
            iter([content]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{invoice.invoice_number}.pdf"'
            },
        )
    except Exception as e:
        logger.error(f"Failed to get PDF: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve PDF")


@router.post("", response_model=InvoiceResponse)
def create_manual_invoice(
    data: ManualInvoiceCreate,
    db: Session = Depends(get_db),
):
    """Create a manual invoice entry."""
    # Verify distributor exists
    distributor = db.get(Distributor, data.distributor_id)
    if not distributor:
        raise HTTPException(status_code=404, detail="Distributor not found")

    # Create invoice
    invoice = Invoice(
        distributor_id=data.distributor_id,
        invoice_number=data.invoice_number,
        invoice_date=datetime.strptime(data.invoice_date, "%Y-%m-%d").date(),
        total_cents=data.total_cents,
        subtotal_cents=data.subtotal_cents,
        tax_cents=data.tax_cents,
        source=Invoice.SOURCE_MANUAL,
        review_status=Invoice.REVIEW_PENDING,
    )
    db.add(invoice)
    db.flush()

    # Create line items
    for line_data in data.lines:
        line = InvoiceLine(
            invoice_id=invoice.id,
            raw_description=line_data.get("raw_description", "Item"),
            raw_sku=line_data.get("raw_sku"),
            quantity=Decimal(str(line_data.get("quantity", 1))),
            unit_price_cents=line_data.get("unit_price_cents"),
            extended_price_cents=line_data.get("extended_price_cents"),
            line_type="product",
        )
        db.add(line)

    db.commit()
    db.refresh(invoice)

    return InvoiceResponse.from_orm_with_dates(invoice)


@router.post("/upload", response_model=InvoiceResponse)
async def upload_invoice(
    distributor_id: str = Form(...),
    file: Optional[UploadFile] = File(None),
    email_content: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Upload and parse an invoice (PDF, image, or email content)."""
    dist_uuid = UUID(distributor_id)

    # Verify distributor exists
    distributor = db.get(Distributor, dist_uuid)
    if not distributor:
        raise HTTPException(status_code=404, detail="Distributor not found")

    parser = get_invoice_parser()
    pdf_path = None

    # Supported image types
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
    IMAGE_MIME_TYPES = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }

    if file and file.filename:
        content = await file.read()
        filename_lower = file.filename.lower()
        file_ext = '.' + filename_lower.rsplit('.', 1)[-1] if '.' in filename_lower else ''

        # Also check content_type for clipboard pastes which may not have extension
        file_content_type = file.content_type or ''

        if file_ext == '.pdf' or file_content_type == 'application/pdf':
            # Parse PDF file
            parsed = parser.parse_invoice(content)
            content_type = "application/pdf"
        elif file_ext in IMAGE_EXTENSIONS or file_content_type.startswith('image/'):
            # Parse image file - use file's content_type if available, else derive from extension
            if file_content_type.startswith('image/'):
                media_type = file_content_type
            else:
                media_type = IMAGE_MIME_TYPES.get(file_ext, 'image/png')
            parsed = parser.parse_invoice_from_image(content, media_type)
            content_type = media_type
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Supported: PDF, PNG, JPG, JPEG, GIF, WEBP"
            )

        source = Invoice.SOURCE_UPLOAD

        # Upload file to storage
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        date_prefix = datetime.utcnow().strftime("%Y/%m")
        storage_path = f"invoices/{date_prefix}/upload_{datetime.utcnow().timestamp()}_{file.filename}"
        blob = bucket.blob(storage_path)
        blob.upload_from_string(content, content_type=content_type)
        pdf_path = f"gs://{BUCKET_NAME}/{storage_path}"

    elif email_content:
        # Parse email content
        parsed = parser.parse_invoice_from_text(email_content)
        source = Invoice.SOURCE_UPLOAD
        pdf_path = None

    else:
        raise HTTPException(status_code=400, detail="Provide either a file or email_content")

    # Generate fallback invoice number if not parsed
    invoice_number = parsed.invoice_number
    if not invoice_number:
        # Generate a unique invoice number based on timestamp
        invoice_number = f"UPLOAD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    # Create invoice
    invoice = Invoice(
        distributor_id=dist_uuid,
        invoice_number=invoice_number,
        invoice_date=parsed.invoice_date.date() if parsed.invoice_date else datetime.utcnow().date(),
        delivery_date=parsed.delivery_date.date() if parsed.delivery_date else None,
        due_date=parsed.due_date.date() if parsed.due_date else None,
        account_number=parsed.account_number,
        sales_rep_name=parsed.sales_rep_name,
        sales_order_number=parsed.sales_order_number,
        subtotal_cents=parsed.subtotal_cents,
        tax_cents=parsed.tax_cents,
        total_cents=parsed.total_cents,
        pdf_path=pdf_path,
        raw_text=parsed.raw_response,
        parsed_at=datetime.utcnow(),
        parse_confidence=Decimal(str(parsed.confidence)),
        source=source,
        review_status=Invoice.REVIEW_PENDING,
    )
    db.add(invoice)
    db.flush()

    # Create line items
    sku_to_line = {}
    for item in parsed.line_items:
        if item.get("line_type") == "credit":
            continue
        line = InvoiceLine(
            invoice_id=invoice.id,
            raw_description=item.get("raw_description", "Item"),
            raw_sku=item.get("raw_sku"),
            quantity=Decimal(str(item["quantity"])) if item.get("quantity") else None,
            unit=item.get("unit"),
            unit_price_cents=item.get("unit_price_cents"),
            extended_price_cents=item.get("extended_price_cents"),
            is_taxable=item.get("is_taxable", False),
            line_type=item.get("line_type", "product"),
        )
        db.add(line)
        if item.get("raw_sku"):
            sku_to_line[item["raw_sku"]] = line

    db.flush()

    # Add credit lines
    for item in parsed.line_items:
        if item.get("line_type") != "credit":
            continue
        parent_sku = item.get("parent_sku")
        parent_line = sku_to_line.get(parent_sku) if parent_sku else None
        line = InvoiceLine(
            invoice_id=invoice.id,
            raw_description=item.get("raw_description", "Credit"),
            raw_sku=item.get("raw_sku"),
            quantity=Decimal(str(item["quantity"])) if item.get("quantity") else None,
            unit=item.get("unit"),
            unit_price_cents=item.get("unit_price_cents"),
            extended_price_cents=item.get("extended_price_cents"),
            is_taxable=item.get("is_taxable", False),
            line_type="credit",
            parent_line_id=parent_line.id if parent_line else None,
        )
        db.add(line)

    db.commit()
    db.refresh(invoice)

    return InvoiceResponse.from_orm_with_dates(invoice)
