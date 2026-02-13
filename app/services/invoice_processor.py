"""Invoice processing service - orchestrates parsing and database storage."""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Invoice, InvoiceLine, EmailMessage
from app.services.invoice_parser import get_invoice_parser, ParsedInvoice

logger = logging.getLogger(__name__)

# Confidence thresholds for review workflow
CONFIDENCE_AUTO_APPROVE = 0.9  # ≥0.9: auto-approve
CONFIDENCE_QUICK_REVIEW = 0.7  # 0.7-0.9: quick review needed
# <0.7: full review needed


class InvoiceProcessor:
    """Processes parsed invoices and stores them in the database."""

    def __init__(self, db: Session):
        self.db = db
        self.parser = get_invoice_parser()

    def process_email_pdf(
        self,
        email_message: EmailMessage,
        pdf_gcs_path: str,
        distributor_id: UUID,
    ) -> Optional[Invoice]:
        """
        Parse a PDF from an email and create invoice records.

        Args:
            email_message: The EmailMessage record
            pdf_gcs_path: GCS path to the PDF
            distributor_id: UUID of the distributor

        Returns:
            Created Invoice or None if parsing failed
        """
        try:
            # Parse the invoice
            logger.info(f"Parsing invoice from {pdf_gcs_path}")
            parsed = self.parser.parse_invoice_from_gcs(pdf_gcs_path)

            # Create the invoice record
            invoice = self._create_invoice(parsed, distributor_id, pdf_gcs_path)

            # Link email to invoice
            email_message.invoice_id = invoice.id
            email_message.status = EmailMessage.STATUS_PROCESSED
            email_message.processed_at = datetime.utcnow()

            self.db.commit()
            logger.info(f"Created invoice {invoice.invoice_number} with {len(invoice.lines)} lines")
            return invoice

        except Exception as e:
            logger.error(f"Failed to process invoice from {pdf_gcs_path}: {e}")
            email_message.status = EmailMessage.STATUS_FAILED
            email_message.error_message = str(e)[:1000]
            self.db.commit()
            raise

    def process_pdf_directly(
        self,
        pdf_gcs_path: str,
        distributor_id: UUID,
    ) -> Invoice:
        """
        Parse a PDF directly (without email context).

        Args:
            pdf_gcs_path: GCS path to the PDF
            distributor_id: UUID of the distributor

        Returns:
            Created Invoice
        """
        logger.info(f"Parsing invoice from {pdf_gcs_path}")
        parsed = self.parser.parse_invoice_from_gcs(pdf_gcs_path)
        invoice = self._create_invoice(parsed, distributor_id, pdf_gcs_path)
        self.db.commit()
        logger.info(f"Created invoice {invoice.invoice_number} with {len(invoice.lines)} lines")
        return invoice

    def process_local_pdf(
        self,
        pdf_path: str,
        distributor_id: UUID,
    ) -> Invoice:
        """
        Parse a local PDF file (for testing).

        Args:
            pdf_path: Local file path to the PDF
            distributor_id: UUID of the distributor

        Returns:
            Created Invoice
        """
        logger.info(f"Parsing local invoice from {pdf_path}")

        with open(pdf_path, "rb") as f:
            pdf_content = f.read()

        parsed = self.parser.parse_invoice(pdf_content)
        invoice = self._create_invoice(parsed, distributor_id, pdf_path)
        self.db.commit()
        logger.info(f"Created invoice {invoice.invoice_number} with {len(invoice.lines)} lines")
        return invoice

    def _create_invoice(
        self,
        parsed: ParsedInvoice,
        distributor_id: UUID,
        pdf_path: str,
    ) -> Invoice:
        """Create Invoice and InvoiceLine records from parsed data."""

        # Create the invoice
        invoice = Invoice(
            distributor_id=distributor_id,
            invoice_number=parsed.invoice_number,
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
            raw_text=parsed.raw_response,  # Store for debugging/search
            parsed_at=datetime.utcnow(),
            parse_confidence=Decimal(str(parsed.confidence)),
        )
        self.db.add(invoice)
        self.db.flush()  # Get the invoice ID

        # Create line items
        # First pass: create all product lines and build SKU -> line mapping
        sku_to_line: dict[str, InvoiceLine] = {}

        for item in parsed.line_items:
            line_type = item.get("line_type", "product")

            # Skip credits on first pass
            if line_type == "credit":
                continue

            quantity = Decimal(str(item["quantity"])) if item.get("quantity") else None
            extended_price_cents = item.get("extended_price_cents")
            unit_price_cents = item.get("unit_price_cents")

            # Recalculate unit_price from extended/quantity for accuracy
            if quantity and extended_price_cents and quantity > 0:
                unit_price_cents = round(extended_price_cents / float(quantity))

            line = InvoiceLine(
                invoice_id=invoice.id,
                raw_description=item.get("raw_description", "Unknown item"),
                raw_sku=item.get("raw_sku"),
                quantity_ordered=Decimal(str(item["quantity_ordered"])) if item.get("quantity_ordered") else None,
                quantity=quantity,
                unit=item.get("unit"),
                unit_price_cents=unit_price_cents,
                extended_price_cents=extended_price_cents,
                is_taxable=item.get("is_taxable", False),
                line_type=line_type,
            )
            self.db.add(line)

            # Track by SKU for credit linking
            if item.get("raw_sku"):
                sku_to_line[item["raw_sku"]] = line

        self.db.flush()  # Get line IDs

        # Second pass: create credit lines and link to parents
        for item in parsed.line_items:
            if item.get("line_type") != "credit":
                continue

            parent_sku = item.get("parent_sku")
            parent_line = sku_to_line.get(parent_sku) if parent_sku else None

            quantity = Decimal(str(item["quantity"])) if item.get("quantity") else None
            extended_price_cents = item.get("extended_price_cents")  # Should be negative
            unit_price_cents = item.get("unit_price_cents")

            # Recalculate unit_price from extended/quantity for accuracy
            if quantity and extended_price_cents and quantity > 0:
                unit_price_cents = round(extended_price_cents / float(quantity))

            line = InvoiceLine(
                invoice_id=invoice.id,
                raw_description=item.get("raw_description", "Credit"),
                raw_sku=item.get("raw_sku"),
                quantity=quantity,
                unit=item.get("unit"),
                unit_price_cents=unit_price_cents,
                extended_price_cents=extended_price_cents,
                is_taxable=item.get("is_taxable", False),
                line_type="credit",
                parent_line_id=parent_line.id if parent_line else None,
            )
            self.db.add(line)

        return invoice

    def get_review_status(self, confidence: float) -> str:
        """Determine review status based on confidence score."""
        if confidence >= CONFIDENCE_AUTO_APPROVE:
            return "auto_approved"
        elif confidence >= CONFIDENCE_QUICK_REVIEW:
            return "quick_review"
        else:
            return "full_review"


def process_invoice_from_gcs(
    db: Session,
    pdf_gcs_path: str,
    distributor_id: UUID,
) -> Invoice:
    """Convenience function to process an invoice from GCS."""
    processor = InvoiceProcessor(db)
    return processor.process_pdf_directly(pdf_gcs_path, distributor_id)
