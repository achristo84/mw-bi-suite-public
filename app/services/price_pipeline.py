"""Price pipeline - populates price_history from approved invoices."""
import logging
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Invoice, InvoiceLine, DistIngredient, PriceHistory

logger = logging.getLogger(__name__)


class PricePipelineService:
    """Service to extract prices from approved invoices and populate price_history."""

    def __init__(self, db: Session):
        self.db = db

    def process_invoice(self, invoice: Invoice) -> dict:
        """
        Process an approved invoice and create price_history entries.

        Returns a summary dict with counts:
        - lines_processed: number of product lines processed
        - prices_created: number of new price_history entries created
        - dist_ingredients_created: number of new dist_ingredient entries created
        - errors: list of error messages
        """
        if invoice.review_status != Invoice.REVIEW_APPROVED:
            raise ValueError(f"Invoice {invoice.invoice_number} is not approved")

        result = {
            "lines_processed": 0,
            "prices_created": 0,
            "dist_ingredients_created": 0,
            "errors": [],
        }

        # Get all product lines (not credits or fees)
        product_lines = [
            line for line in invoice.lines
            if line.line_type == "product" and line.raw_sku
        ]

        for line in product_lines:
            try:
                self._process_line(invoice, line, result)
            except Exception as e:
                error_msg = f"Failed to process line {line.raw_sku}: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)

        logger.info(
            f"Price pipeline processed invoice {invoice.invoice_number}: "
            f"{result['lines_processed']} lines, {result['prices_created']} prices, "
            f"{result['dist_ingredients_created']} new ingredients"
        )

        return result

    def _process_line(self, invoice: Invoice, line: InvoiceLine, result: dict):
        """Process a single invoice line and create price_history entry."""
        result["lines_processed"] += 1

        # Calculate effective price (list price + credits)
        effective_price_cents = self._calculate_effective_price(line)

        if effective_price_cents is None:
            result["errors"].append(f"SKU {line.raw_sku}: no price available")
            return

        # Calculate unit price
        quantity = float(line.quantity) if line.quantity else 1
        if quantity <= 0:
            result["errors"].append(f"SKU {line.raw_sku}: invalid quantity {quantity}")
            return

        effective_unit_price_cents = round(effective_price_cents / quantity)

        # Find or create dist_ingredient
        dist_ingredient = self._find_or_create_dist_ingredient(
            invoice.distributor_id,
            line.raw_sku,
            line.raw_description,
            line.unit,
            result,
        )

        if not dist_ingredient:
            result["errors"].append(f"SKU {line.raw_sku}: failed to find/create dist_ingredient")
            return

        # Link the invoice line to the dist_ingredient
        if line.dist_ingredient_id != dist_ingredient.id:
            line.dist_ingredient_id = dist_ingredient.id

        # Create price_history entry
        self._create_price_history(
            dist_ingredient_id=dist_ingredient.id,
            price_cents=effective_unit_price_cents,
            effective_date=invoice.invoice_date,
            invoice_number=invoice.invoice_number,
            result=result,
        )

    def _calculate_effective_price(self, line: InvoiceLine) -> Optional[int]:
        """
        Calculate effective price after credits.

        Credits are stored as separate lines with parent_line_id pointing
        to the product line, and negative extended_price_cents.
        """
        if line.extended_price_cents is None:
            return None

        # Start with list price
        effective_cents = line.extended_price_cents

        # Add any credits linked to this line (credits have negative amounts)
        for credit_line in line.credit_lines:
            if credit_line.extended_price_cents:
                effective_cents += credit_line.extended_price_cents

        return effective_cents

    def _find_or_create_dist_ingredient(
        self,
        distributor_id: UUID,
        sku: str,
        description: str,
        unit: Optional[str],
        result: dict,
    ) -> Optional[DistIngredient]:
        """
        Find existing dist_ingredient by (distributor_id, sku) or create new one.

        New dist_ingredients are created without an ingredient_id (unmapped),
        to be linked to canonical ingredients later.
        """
        # Look for existing
        existing = self.db.execute(
            select(DistIngredient)
            .where(DistIngredient.distributor_id == distributor_id)
            .where(DistIngredient.sku == sku)
        ).scalars().first()

        if existing:
            # Update description if we have a better one
            if description and len(description) > len(existing.description or ""):
                existing.description = description
            return existing

        # Create new
        dist_ingredient = DistIngredient(
            distributor_id=distributor_id,
            sku=sku,
            description=description or f"SKU {sku}",
            pack_unit=unit,  # Use parsed unit as pack_unit
            is_active=True,
            # ingredient_id left NULL - to be mapped later
        )
        self.db.add(dist_ingredient)
        self.db.flush()  # Get the ID

        result["dist_ingredients_created"] += 1
        logger.info(f"Created new dist_ingredient: {sku} - {description}")

        return dist_ingredient

    def _create_price_history(
        self,
        dist_ingredient_id: UUID,
        price_cents: int,
        effective_date: date,
        invoice_number: str,
        result: dict,
    ):
        """
        Create a price_history entry.

        Checks if we already have a price for this ingredient/date/source to
        avoid duplicates (e.g., if invoice is processed twice).
        """
        # Check for existing entry with same ingredient, date, and source_reference
        existing = self.db.execute(
            select(PriceHistory)
            .where(PriceHistory.dist_ingredient_id == dist_ingredient_id)
            .where(PriceHistory.effective_date == effective_date)
            .where(PriceHistory.source == "invoice")
            .where(PriceHistory.source_reference == invoice_number)
        ).scalars().first()

        if existing:
            # Update if price changed
            if existing.price_cents != price_cents:
                existing.price_cents = price_cents
                logger.info(f"Updated price_history for {invoice_number}: {price_cents}¢")
            return

        # Create new entry
        price_entry = PriceHistory(
            dist_ingredient_id=dist_ingredient_id,
            price_cents=price_cents,
            effective_date=effective_date,
            source="invoice",
            source_reference=invoice_number,
        )
        self.db.add(price_entry)
        result["prices_created"] += 1


def process_approved_invoice(db: Session, invoice: Invoice) -> dict:
    """Convenience function to process an approved invoice."""
    service = PricePipelineService(db)
    return service.process_invoice(invoice)
