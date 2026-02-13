"""Invoice parsing service using Claude Haiku vision."""
import base64
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

import anthropic
from google.cloud import secretmanager, storage

logger = logging.getLogger(__name__)

# GCP project - read from centralized config
from app.config import get_settings

_settings = get_settings()
PROJECT_ID = _settings.GCP_PROJECT_ID
BUCKET_NAME = _settings.GCS_BUCKET_NAME

# Parsing prompt for Claude
INVOICE_PARSE_PROMPT = """Analyze this invoice and extract all information into structured JSON.

Return ONLY valid JSON with this exact structure (no markdown, no explanation):
{
  "invoice_number": "string",
  "invoice_date": "YYYY-MM-DD",
  "delivery_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "account_number": "string or null",
  "sales_rep_name": "string or null",
  "sales_order_number": "string or null",
  "subtotal_cents": integer (dollars * 100),
  "tax_cents": integer (dollars * 100) or null,
  "total_cents": integer (dollars * 100),
  "line_items": [
    {
      "raw_sku": "item code/number or null",
      "raw_description": "full item description",
      "quantity_ordered": decimal or null,
      "quantity": decimal (quantity shipped/invoiced - the TOTAL COUNT of units),
      "unit": "string - the unit of measure (EA, OZ, LB, CS, CT, GAL, etc.)",
      "unit_price_cents": integer (price per unit * 100),
      "extended_price_cents": integer (line total * 100, negative for credits),
      "is_taxable": boolean,
      "line_type": "product" or "credit" or "fee",
      "parent_sku": "for credits, the SKU this credit applies to, or null"
    }
  ],
  "confidence": decimal 0.0-1.0 (your confidence in the overall parse accuracy)
}

CRITICAL - Understanding invoice quantity vs pack size:
Many invoices show TWO or THREE numbers that affect quantity:
1. QTY column (or "# OF", "ORDERED") - number of cases/packs ordered (e.g., 1, 2, 3)
2. Pack description - can be ONE multiplication (e.g., "9/1 Qt") or TWO (e.g., "4/2.5 Lb")

YOU MUST MULTIPLY ALL NUMBERS together to get the TOTAL quantity:
- Pattern "N/M UNIT" with QTY=Q: Total = Q × N × M
- Example: QTY=1, pack="9/1 Qt" → 1 × 9 × 1 = 9 quarts
- Example: QTY=2, pack="4/2.5 Lb" → 2 × 4 × 2.5 = 20 pounds

EXAMPLE 1 - Single case:
  Item: "Milk Half And Half" with pack "9/1 Qt"
  QTY column: 1
  Price: $28.21
  CORRECT: quantity = 1 × 9 × 1 = 9 QT, unit_price = $28.21 ÷ 9 = $3.13

EXAMPLE 2 - Multiple cases with compound pack:
  Item: "Cheese Cheddar" with pack "4/2.5 Lb"
  QTY column: 2
  Price per case: $75.50
  Extended: $151.00
  Pack means: 4 packages × 2.5 LB each = 10 LB per case
  CORRECT: quantity = 2 cases × 10 LB/case = 20 LB, unit_price = $151 ÷ 20 = $7.55/LB

Pack description patterns to recognize:
The pattern is: PACK_COUNT/UNIT_SIZE UNIT
- First number = how many units in the pack
- Second number = size of each unit
- Total quantity = PACK_COUNT × UNIT_SIZE

Examples where first number is the count:
- "9/1 Qt" = 9 × 1 quart = 9 quarts total
- "6/1 LB" = 6 × 1 pound = 6 pounds total
- "12/8 OZ" = 12 × 8 oz = 96 oz total

Examples where second number is larger (bulk items):
- "1/6 Lb" = 1 × 6 pounds = 6 pounds total (one 6-lb container)
- "1/50 Lb" = 1 × 50 pounds = 50 pounds total (one 50-lb bag)
- "1/8 Lb" = 1 × 8 pounds = 8 pounds total
- "2/5 Lb" = 2 × 5 pounds = 10 pounds total

Fractional units (three numbers):
- "9/1/2 Gal" = 9 × 0.5 gallon = 4.5 gallons total
- "6/1/2 GAL" = 6 × 0.5 gallon = 3 gallons total

IMPORTANT: "1/6 Lb" does NOT mean 1/6 of a pound (0.167 lb). It means 1 pack of 6 pounds = 6 LB total.

ALWAYS check: quantity × unit_price ≈ extended_price
If they don't match, you probably need to multiply by the pack count.

IMPORTANT - Unit extraction:
- Extract the unit of measure: QT (quart), GAL (gallon), LB (pound), OZ (ounce), EA (each), CS (case), CT (count)
- Normalize: "QUART" → "QT", "GALLON" → "GAL", "POUND" → "LB", "OUNCE" → "OZ"
- For pack descriptions like "9/1 Qt", the unit is "QT" (not "1 Qt")

Other important notes:
- Convert all dollar amounts to cents (multiply by 100)
- For credits/allowances (like "TRACS ALLOWANCE"), use negative extended_price_cents and line_type="credit"
- If a credit applies to a specific item, set parent_sku to that item's SKU
- Set is_taxable based on whether the item appears to be taxed (look for ** or tax indicators)
- Include ALL line items, including credits and fees
- Use null for fields you cannot determine
- Set confidence based on how clearly you can read and parse the invoice
"""


@dataclass
class ParsedInvoice:
    """Structured invoice data from parsing."""
    invoice_number: str
    invoice_date: datetime
    delivery_date: Optional[datetime]
    due_date: Optional[datetime]
    account_number: Optional[str]
    sales_rep_name: Optional[str]
    sales_order_number: Optional[str]
    subtotal_cents: Optional[int]
    tax_cents: Optional[int]
    total_cents: int
    line_items: list[dict]
    confidence: float
    raw_response: str  # Keep original for debugging
    prompt_used: str = ""  # The prompt that was used for parsing


class InvoiceParser:
    """Parses invoice PDFs using Claude Haiku vision."""

    def __init__(self):
        self._client: Optional[anthropic.Anthropic] = None
        self._storage_client: Optional[storage.Client] = None

    def _get_secret(self, secret_id: str) -> str:
        """Fetch a secret from Secret Manager."""
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8").strip()

    @property
    def client(self) -> anthropic.Anthropic:
        """Get Anthropic client (lazy initialization)."""
        if self._client is None:
            api_key = self._get_secret("anthropic-api-key")
            self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    @property
    def storage_client(self) -> storage.Client:
        """Get Cloud Storage client (lazy initialization)."""
        if self._storage_client is None:
            self._storage_client = storage.Client(project=PROJECT_ID)
        return self._storage_client

    def download_pdf_from_gcs(self, gcs_path: str) -> bytes:
        """Download PDF from Cloud Storage.

        Args:
            gcs_path: Full GCS path (gs://bucket/path) or just the path within bucket
        """
        # Handle both gs:// URLs and plain paths
        if gcs_path.startswith("gs://"):
            # Extract path after bucket name
            path = gcs_path.replace(f"gs://{BUCKET_NAME}/", "")
        else:
            path = gcs_path

        bucket = self.storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(path)
        return blob.download_as_bytes()

    def parse_invoice(self, pdf_content: bytes, custom_prompt: Optional[str] = None) -> ParsedInvoice:
        """Parse an invoice PDF using Claude Haiku.

        Args:
            pdf_content: Raw PDF bytes
            custom_prompt: Optional custom prompt to use instead of default

        Returns:
            ParsedInvoice with extracted data
        """
        # Encode PDF as base64
        pdf_base64 = base64.standard_b64encode(pdf_content).decode("utf-8")

        # Use custom prompt or default
        prompt = custom_prompt or INVOICE_PARSE_PROMPT

        logger.info("Sending invoice to Claude Haiku for parsing...")

        # Call Claude with the PDF
        message = self.client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        # Extract the response text
        response_text = message.content[0].text
        logger.debug(f"Claude response: {response_text}")

        # Parse JSON from response
        try:
            # Handle potential markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response was: {response_text}")
            raise ValueError(f"Claude returned invalid JSON: {e}")

        # Convert to ParsedInvoice
        return self._dict_to_parsed_invoice(data, response_text, prompt)

    def parse_invoice_from_gcs(self, gcs_path: str, custom_prompt: Optional[str] = None) -> ParsedInvoice:
        """Download and parse an invoice from Cloud Storage.

        Args:
            gcs_path: GCS path to the PDF
            custom_prompt: Optional custom prompt to use instead of default

        Returns:
            ParsedInvoice with extracted data
        """
        pdf_content = self.download_pdf_from_gcs(gcs_path)
        return self.parse_invoice(pdf_content, custom_prompt)

    def parse_invoice_from_image(self, image_content: bytes, media_type: str, custom_prompt: Optional[str] = None) -> ParsedInvoice:
        """Parse an invoice image using Claude Haiku.

        Args:
            image_content: Raw image bytes
            media_type: MIME type of the image (e.g., 'image/png', 'image/jpeg')
            custom_prompt: Optional custom prompt to use instead of default

        Returns:
            ParsedInvoice with extracted data
        """
        # Encode image as base64
        image_base64 = base64.standard_b64encode(image_content).decode("utf-8")

        # Use custom prompt or default
        prompt = custom_prompt or INVOICE_PARSE_PROMPT

        logger.info(f"Sending invoice image ({media_type}) to Claude Haiku for parsing...")

        # Call Claude with the image
        message = self.client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        # Extract the response text
        response_text = message.content[0].text
        logger.debug(f"Claude response: {response_text}")

        # Parse JSON from response
        try:
            # Handle potential markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response was: {response_text}")
            raise ValueError(f"Claude returned invalid JSON: {e}")

        # Convert to ParsedInvoice
        return self._dict_to_parsed_invoice(data, response_text, prompt)

    def parse_invoice_from_text(self, text_content: str, custom_prompt: Optional[str] = None) -> ParsedInvoice:
        """Parse invoice information from email body text.

        Args:
            text_content: Email body (HTML or plain text)
            custom_prompt: Optional custom prompt to use instead of default

        Returns:
            ParsedInvoice with extracted data
        """
        logger.info("Parsing invoice from email text...")

        # Use custom prompt or default
        prompt = custom_prompt or INVOICE_PARSE_PROMPT

        message = self.client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}\n\nEmail content to parse:\n\n{text_content}",
                }
            ],
        )

        response_text = message.content[0].text
        logger.debug(f"Claude response: {response_text}")

        try:
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise ValueError(f"Claude returned invalid JSON: {e}")

        return self._dict_to_parsed_invoice(data, response_text, prompt)

    def _dict_to_parsed_invoice(self, data: dict, raw_response: str, prompt_used: str = "") -> ParsedInvoice:
        """Convert parsed JSON dict to ParsedInvoice dataclass."""

        def parse_date(date_str: Optional[str]) -> Optional[datetime]:
            if not date_str:
                return None
            try:
                return datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                logger.warning(f"Could not parse date: {date_str}")
                return None

        return ParsedInvoice(
            invoice_number=data.get("invoice_number", "UNKNOWN"),
            invoice_date=parse_date(data.get("invoice_date")) or datetime.utcnow(),
            delivery_date=parse_date(data.get("delivery_date")),
            due_date=parse_date(data.get("due_date")),
            account_number=data.get("account_number"),
            sales_rep_name=data.get("sales_rep_name"),
            sales_order_number=data.get("sales_order_number"),
            subtotal_cents=data.get("subtotal_cents"),
            tax_cents=data.get("tax_cents"),
            total_cents=data.get("total_cents", 0),
            line_items=data.get("line_items", []),
            confidence=float(data.get("confidence", 0.5)),
            raw_response=raw_response,
            prompt_used=prompt_used,
        )


# Singleton instance
_parser: Optional[InvoiceParser] = None


def get_invoice_parser() -> InvoiceParser:
    """Get or create the invoice parser singleton."""
    global _parser
    if _parser is None:
        _parser = InvoiceParser()
    return _parser
