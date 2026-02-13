"""Email ingestion processor for invoice emails."""
import logging
import re
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Distributor, EmailMessage, Invoice
from app.services.gmail_service import get_gmail_service
from app.services.invoice_parser import get_invoice_parser

logger = logging.getLogger(__name__)

# Filename patterns to distinguish distributors sharing the same email.
# Maps (sender_email, filename_pattern) -> distributor_name.
# Configure these patterns based on your distributor email setup.
# Example: two distributors sharing the same platform email can be
# disambiguated by invoice filename prefixes.
FILENAME_PATTERNS: dict[str, list[tuple[str, str]]] = {
    # Add patterns like:
    # 'invoices@distributor.com': [
    #     (r'prefix_a_', 'Distributor A'),
    #     (r'prefix_b_', 'Distributor B'),
    # ]
}


class EmailIngestionProcessor:
    """Processes incoming invoice emails from Gmail."""

    def __init__(self, db: Session, parse_invoices: bool = True):
        self.db = db
        self.gmail = get_gmail_service()
        self.parse_invoices = parse_invoices
        self._parser = None
        self._distributor_cache: dict[str, UUID] = {}  # name -> id cache

    @property
    def parser(self):
        """Lazy-load the invoice parser."""
        if self._parser is None and self.parse_invoices:
            self._parser = get_invoice_parser()
        return self._parser

    def get_distributor_emails(self) -> dict[str, list[UUID]]:
        """
        Get mapping of invoice email addresses to distributor IDs.

        Note: Multiple distributors can share the same invoice_email
        (e.g., multiple distributors may share the same sender email)

        Returns:
            Dict mapping email address (lowercase) -> list of distributor_ids
        """
        result = self.db.execute(
            select(Distributor.id, Distributor.name, Distributor.invoice_email)
            .where(Distributor.invoice_email.isnot(None))
            .where(Distributor.is_active == True)
        )

        email_to_distributors: dict[str, list[UUID]] = {}
        for row in result:
            if row.invoice_email:
                email = row.invoice_email.lower()
                if email not in email_to_distributors:
                    email_to_distributors[email] = []
                email_to_distributors[email].append(row.id)
                # Cache name -> id for filename pattern matching
                self._distributor_cache[row.name] = row.id

        return email_to_distributors

    def _get_distributor_by_name(self, name: str) -> Optional[UUID]:
        """Get distributor ID by name (uses cache)."""
        if name in self._distributor_cache:
            return self._distributor_cache[name]

        result = self.db.execute(
            select(Distributor.id).where(Distributor.name == name)
        )
        dist_id = result.scalar()
        if dist_id:
            self._distributor_cache[name] = dist_id
        return dist_id

    def _resolve_distributor_from_filename(
        self,
        from_address: str,
        pdf_filename: str,
        distributor_ids: list[UUID]
    ) -> Optional[UUID]:
        """
        Resolve which distributor a PDF belongs to based on filename patterns.

        Used when multiple distributors share the same invoice email.
        """
        # If only one distributor uses this email, no ambiguity
        if len(distributor_ids) == 1:
            return distributor_ids[0]

        # Check filename patterns for this sender
        patterns = FILENAME_PATTERNS.get(from_address.lower(), [])
        for pattern, distributor_name in patterns:
            if re.search(pattern, pdf_filename, re.IGNORECASE):
                dist_id = self._get_distributor_by_name(distributor_name)
                if dist_id:
                    logger.info(f"Matched '{pdf_filename}' to {distributor_name} via pattern '{pattern}'")
                    return dist_id

        # No pattern matched - return first distributor as fallback
        logger.warning(f"Could not determine distributor for '{pdf_filename}' from {from_address}")
        return distributor_ids[0] if distributor_ids else None

    def is_already_processed(self, gmail_message_id: str) -> bool:
        """Check if we've already processed this email."""
        result = self.db.execute(
            select(EmailMessage.id)
            .where(EmailMessage.gmail_message_id == gmail_message_id)
        )
        return result.scalar() is not None

    def process_new_emails(
        self,
        lookback_days: int = 7,
        max_emails: int = 50
    ) -> dict:
        """
        Main entry point: fetch and process new invoice emails.

        Args:
            lookback_days: How far back to search for emails
            max_emails: Maximum emails to process in one run

        Returns:
            Summary dict with counts of processed, skipped, failed
        """
        stats = {
            'searched': 0,
            'already_processed': 0,
            'new_processed': 0,
            'invoices_created': 0,
            'parse_failed': 0,
            'failed': 0,
            'no_pdf': 0,
            'unknown_sender': 0
        }

        # Get known distributor email addresses
        distributor_emails = self.get_distributor_emails()
        sender_addresses = list(set(distributor_emails.keys())) if distributor_emails else None

        logger.info(f"Known distributor emails: {sender_addresses}")

        # Search for invoice emails
        after_date = datetime.utcnow() - timedelta(days=lookback_days)

        try:
            messages = self.gmail.search_invoice_emails(
                sender_addresses=sender_addresses,
                after_date=after_date,
                max_results=max_emails
            )
        except Exception as e:
            logger.error(f"Failed to search emails: {e}")
            return {'error': str(e)}

        stats['searched'] = len(messages)

        for msg in messages:
            gmail_id = msg['id']

            # Skip if already processed
            if self.is_already_processed(gmail_id):
                stats['already_processed'] += 1
                continue

            try:
                result = self._process_single_email(gmail_id, distributor_emails)
                if result['status'] == 'processed':
                    stats['new_processed'] += 1
                    stats['invoices_created'] += result.get('invoices_created', 0)
                    stats['parse_failed'] += result.get('parse_failed', 0)
                elif result['status'] == 'no_pdf':
                    stats['no_pdf'] += 1
                elif result['status'] == 'unknown_sender':
                    stats['unknown_sender'] += 1

            except Exception as e:
                logger.error(f"Failed to process email {gmail_id}: {e}")
                stats['failed'] += 1
                # Record the failure
                self._record_failed_email(gmail_id, str(e))

        logger.info(f"Email ingestion complete: {stats}")
        return stats

    def _process_single_email(
        self,
        gmail_message_id: str,
        distributor_emails: dict[str, list[UUID]]
    ) -> dict:
        """
        Process a single email.

        Returns:
            Dict with 'status' and optional counts:
            - status: 'processed', 'no_pdf', 'unknown_sender'
            - invoices_created: number of invoices parsed
            - parse_failed: number of PDFs that failed to parse
        """
        # Get full message details
        details = self.gmail.get_message_details(gmail_message_id)

        # Match sender to potential distributors
        from_address = details['from_address']
        distributor_ids = distributor_emails.get(from_address, [])

        # Find PDF attachments
        pdf_attachments = [
            a for a in details['attachments']
            if a['mimeType'] == 'application/pdf' or a['filename'].lower().endswith('.pdf')
        ]

        if not pdf_attachments:
            # Record email but mark as ignored (no PDF)
            self._record_email(
                details,
                distributor_id=distributor_ids[0] if distributor_ids else None,
                status=EmailMessage.STATUS_IGNORED,
                error_message="No PDF attachments found"
            )
            self.db.commit()
            return {'status': 'no_pdf'}

        if not distributor_ids:
            # Record email from unknown sender for manual review
            self._record_email(
                details,
                distributor_id=None,
                status=EmailMessage.STATUS_PENDING,
                error_message=f"Unknown sender: {from_address}"
            )
            self.db.commit()
            return {'status': 'unknown_sender'}

        # Process each PDF attachment
        # Note: Each PDF may belong to a different distributor on the same platform
        pdf_results = []  # List of (gcs_path, dist_id, pdf_content)
        resolved_distributor_id = None

        for attachment in pdf_attachments:
            # Resolve distributor from filename if multiple possibilities
            dist_id = self._resolve_distributor_from_filename(
                from_address,
                attachment['filename'],
                distributor_ids
            )

            # Use the first resolved distributor for the email record
            if resolved_distributor_id is None:
                resolved_distributor_id = dist_id

            pdf_content = self.gmail.download_attachment(
                gmail_message_id,
                attachment['attachmentId']
            )

            # Generate storage path
            date_prefix = details['date'].strftime("%Y/%m")
            safe_filename = self._sanitize_filename(attachment['filename'])
            storage_path = f"invoices/{date_prefix}/{gmail_message_id}_{safe_filename}"

            gcs_path = self.gmail.upload_to_storage(pdf_content, storage_path)
            pdf_results.append((gcs_path, dist_id, pdf_content))

        # Record the email first
        email_msg = self._record_email(
            details,
            distributor_id=resolved_distributor_id,
            status=EmailMessage.STATUS_PROCESSING,
            pdf_paths=[r[0] for r in pdf_results]
        )

        # Parse each PDF and create invoices
        invoices_created = 0
        parse_failed = 0
        created_invoices = []

        if self.parse_invoices and self.parser:
            for gcs_path, dist_id, pdf_content in pdf_results:
                try:
                    invoice = self._parse_and_create_invoice(
                        pdf_content, gcs_path, dist_id
                    )
                    if invoice:
                        created_invoices.append(invoice)
                        invoices_created += 1
                        logger.info(f"Created invoice {invoice.invoice_number} from {gcs_path}")
                except Exception as e:
                    logger.error(f"Failed to parse invoice from {gcs_path}: {e}")
                    parse_failed += 1

        # Update email status and link to first invoice
        email_msg.status = EmailMessage.STATUS_PROCESSED
        email_msg.processed_at = datetime.utcnow()
        if created_invoices:
            email_msg.invoice_id = created_invoices[0].id
        self.db.commit()

        logger.info(f"Processed email from {from_address}: {len(pdf_results)} PDFs, {invoices_created} invoices created")
        return {
            'status': 'processed',
            'invoices_created': invoices_created,
            'parse_failed': parse_failed
        }

    def _parse_and_create_invoice(
        self,
        pdf_content: bytes,
        gcs_path: str,
        distributor_id: UUID
    ) -> Optional[Invoice]:
        """Parse a PDF and create Invoice + InvoiceLine records."""
        from decimal import Decimal

        # Parse the invoice
        parsed = self.parser.parse_invoice(pdf_content)

        # Check for duplicate invoice number
        existing = self.db.execute(
            select(Invoice.id)
            .where(Invoice.distributor_id == distributor_id)
            .where(Invoice.invoice_number == parsed.invoice_number)
        ).scalar()

        if existing:
            logger.warning(f"Invoice {parsed.invoice_number} already exists for distributor, skipping")
            return None

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
            pdf_path=gcs_path,
            raw_text=parsed.raw_response,
            parsed_at=datetime.utcnow(),
            parse_confidence=Decimal(str(parsed.confidence)),
        )
        self.db.add(invoice)
        self.db.flush()

        # Create line items
        from app.models import InvoiceLine
        sku_to_line: dict[str, InvoiceLine] = {}

        # First pass: product and fee lines
        for item in parsed.line_items:
            line_type = item.get("line_type", "product")
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
            if item.get("raw_sku"):
                sku_to_line[item["raw_sku"]] = line

        self.db.flush()

        # Second pass: credit lines
        for item in parsed.line_items:
            if item.get("line_type") != "credit":
                continue

            parent_sku = item.get("parent_sku")
            parent_line = sku_to_line.get(parent_sku) if parent_sku else None

            quantity = Decimal(str(item["quantity"])) if item.get("quantity") else None
            extended_price_cents = item.get("extended_price_cents")
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

    def _record_email(
        self,
        details: dict,
        distributor_id: Optional[UUID],
        status: str,
        error_message: Optional[str] = None,
        pdf_paths: Optional[list[str]] = None
    ) -> EmailMessage:
        """Record an email message in the database."""
        email_msg = EmailMessage(
            gmail_message_id=details['id'],
            gmail_thread_id=details['threadId'],
            from_address=details['from_address'],
            subject=details['subject'][:500] if details['subject'] else None,
            received_at=details['date'],
            distributor_id=distributor_id,
            status=status,
            has_attachments=len(details['attachments']) > 0,
            attachment_count=len(details['attachments']),
            error_message=error_message,
            processed_at=datetime.utcnow() if status in (EmailMessage.STATUS_PROCESSED, EmailMessage.STATUS_IGNORED) else None
        )
        self.db.add(email_msg)
        self.db.flush()  # Get ID without committing
        return email_msg

    def _record_failed_email(self, gmail_message_id: str, error: str):
        """Record a failed email processing attempt."""
        try:
            details = self.gmail.get_message_details(gmail_message_id)
            self._record_email(
                details,
                distributor_id=None,
                status=EmailMessage.STATUS_FAILED,
                error_message=error[:1000]
            )
            self.db.commit()
        except Exception as e:
            # If we can't even get details, create minimal record
            email_msg = EmailMessage(
                gmail_message_id=gmail_message_id,
                from_address="unknown",
                received_at=datetime.utcnow(),
                status=EmailMessage.STATUS_FAILED,
                error_message=f"Failed to get details: {e}; Original error: {error}"[:1000]
            )
            self.db.add(email_msg)
            self.db.commit()

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for storage."""
        import re
        # Remove or replace problematic characters
        sanitized = re.sub(r'[^\w\-_\.]', '_', filename)
        # Limit length
        if len(sanitized) > 100:
            name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
            sanitized = name[:95] + '.' + ext if ext else name[:100]
        return sanitized


def run_email_ingestion(db: Session, lookback_days: int = 7) -> dict:
    """
    Convenience function to run email ingestion.

    Args:
        db: Database session
        lookback_days: How many days back to search

    Returns:
        Processing statistics dict
    """
    processor = EmailIngestionProcessor(db)
    return processor.process_new_emails(lookback_days=lookback_days)
