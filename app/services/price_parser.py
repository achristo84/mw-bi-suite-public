"""Price parsing service using Claude Haiku for extracting pricing from various sources."""

import base64
import json
import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from anthropic import Anthropic

logger = logging.getLogger(__name__)

# System distributor UUID for one-off purchases
ONEOFF_DISTRIBUTOR_ID = "00000000-0000-0000-0000-000000000001"


@dataclass
class ParsedPriceItem:
    """A single parsed price item."""
    description: str
    sku: Optional[str]
    pack_size: Optional[str]  # e.g., "12", "4x5lb"
    pack_unit: Optional[str]  # e.g., "case", "bag"
    unit_contents: Optional[float]  # e.g., 16 (oz per unit)
    unit_contents_unit: Optional[str]  # e.g., "oz", "lb", "gal"
    price_cents: int
    price_type: str  # "case" or "unit"
    total_base_units: Optional[float]  # Calculated total in g/ml/each
    base_unit: Optional[str]  # "g", "ml", "each"
    price_per_base_unit_cents: Optional[float]
    raw_text: str
    confidence: float


@dataclass
class ParseResult:
    """Result of parsing price content."""
    items: list[ParsedPriceItem]
    detected_distributor: Optional[str]
    document_date: Optional[str]
    raw_response: str
    prompt_used: str = ""  # The prompt that was used for parsing


def _get_anthropic_client() -> Anthropic:
    """Get Anthropic client with API key from environment or Secret Manager."""
    from app.config import get_settings

    api_key = get_settings().ANTHROPIC_API_KEY
    if not api_key:
        # Try to get from Secret Manager
        try:
            from google.cloud import secretmanager
            client = secretmanager.SecretManagerServiceClient()
            project_id = get_settings().GCP_PROJECT_ID
            name = f"projects/{project_id}/secrets/anthropic-api-key/versions/latest"
            response = client.access_secret_version(request={"name": name})
            api_key = response.payload.data.decode("UTF-8")
        except Exception as e:
            logger.warning(f"Could not get API key from Secret Manager: {e}")
            raise ValueError("ANTHROPIC_API_KEY not set and Secret Manager unavailable")

    return Anthropic(api_key=api_key)


def _extract_email_body(content: str) -> str:
    """Extract the body from an email with headers (Gmail format)."""
    # Check if this looks like an email with headers
    if not any(h in content[:500] for h in ['From:', 'Subject:', 'Delivered-To:', 'Received:']):
        return content

    # Split on double newline to separate headers from body
    parts = re.split(r'\n\n|\r\n\r\n', content, maxsplit=1)
    if len(parts) > 1:
        body = parts[1]
    else:
        body = content

    # Check for base64 encoded content
    if 'Content-Transfer-Encoding: base64' in content:
        # Try to find and decode base64 section
        base64_match = re.search(r'Content-Transfer-Encoding: base64\s*\n\n([A-Za-z0-9+/=\s]+)', content)
        if base64_match:
            try:
                encoded = base64_match.group(1).replace('\n', '').replace('\r', '')
                body = base64.b64decode(encoded).decode('utf-8', errors='ignore')
            except Exception:
                pass

    return body


# Default price parsing prompt template
DEFAULT_PRICE_PARSE_PROMPT = """You are a pricing data extraction assistant. Extract all product line items with pricing from this content.

For each item found, extract:
1. description: Product name/description
2. sku: SKU or product code (if present)
3. pack_size: Number of units per case/pack (e.g., "12", "4")
4. pack_unit: What the pack is called (e.g., "case", "bag", "box")
5. unit_contents: Size of each unit (e.g., 16 for "16oz bottles")
6. unit_contents_unit: Unit of measure for contents (oz, lb, gal, L, kg, g, each, etc.)
7. price_cents: Price in cents (e.g., $15.99 = 1599)
8. price_type: "case" if price is for the whole case/pack, "unit" if per-unit price
9. raw_text: The original text this was extracted from

Also extract:
- detected_distributor: The distributor name if identifiable
- document_date: Date of the document if present (YYYY-MM-DD format)

Return JSON in this exact format:
{
  "items": [
    {
      "description": "Whole Milk",
      "sku": "12345",
      "pack_size": "4",
      "pack_unit": "case",
      "unit_contents": 1,
      "unit_contents_unit": "gal",
      "price_cents": 1599,
      "price_type": "case",
      "raw_text": "Whole Milk 4/1GAL $15.99",
      "match_score": 0.85
    }
  ],
  "detected_distributor": "Valley Foods",
  "document_date": "2024-12-15"
}

Important:
- Extract ALL items you can find, not just the first one
- If pack_size is not specified, assume 1
- If you can't determine a field, use null
- match_score should be 0.0-1.0 based on how well the item matches the ingredient context (if provided)
- Be thorough - this is financial data and accuracy matters

Return ONLY valid JSON, no explanation or markdown."""


def get_default_price_prompt() -> str:
    """Get the default price parsing prompt."""
    return DEFAULT_PRICE_PARSE_PROMPT


def _build_parse_prompt(content_type: str, ingredient_context: Optional[dict] = None, custom_prompt: Optional[str] = None) -> str:
    """Build the prompt for Claude Haiku to parse pricing content.

    Args:
        content_type: Type of content being parsed (e.g., "image", "PDF document", "text")
        ingredient_context: Optional dict with ingredient info for matching
        custom_prompt: Optional custom prompt to use instead of default

    Returns:
        The prompt string to use
    """
    # If custom prompt provided, use it directly (with ingredient hint prepended if available)
    if custom_prompt:
        if ingredient_context:
            ingredient_hint = f"""The user is looking to price the ingredient: "{ingredient_context.get('name', 'Unknown')}"
Category: {ingredient_context.get('category', 'Unknown')}
Base unit: {ingredient_context.get('base_unit', 'g')}

When calculating match_score, consider how well each item matches this ingredient.

"""
            return ingredient_hint + custom_prompt
        return custom_prompt

    # Build default prompt with ingredient context
    ingredient_hint = ""
    if ingredient_context:
        ingredient_hint = f"""
The user is looking to price the ingredient: "{ingredient_context.get('name', 'Unknown')}"
Category: {ingredient_context.get('category', 'Unknown')}
Base unit: {ingredient_context.get('base_unit', 'g')}

When calculating match_score, consider how well each item matches this ingredient.
"""

    return f"""You are a pricing data extraction assistant. Extract all product line items with pricing from this {content_type}.

{ingredient_hint}

For each item found, extract:
1. description: Product name/description
2. sku: SKU or product code (if present)
3. pack_size: Number of units per case/pack (e.g., "12", "4")
4. pack_unit: What the pack is called (e.g., "case", "bag", "box")
5. unit_contents: Size of each unit (e.g., 16 for "16oz bottles")
6. unit_contents_unit: Unit of measure for contents (oz, lb, gal, L, kg, g, each, etc.)
7. price_cents: Price in cents (e.g., $15.99 = 1599)
8. price_type: "case" if price is for the whole case/pack, "unit" if per-unit price
9. raw_text: The original text this was extracted from

Also extract:
- detected_distributor: The distributor name if identifiable
- document_date: Date of the document if present (YYYY-MM-DD format)

Return JSON in this exact format:
{{
  "items": [
    {{
      "description": "Whole Milk",
      "sku": "12345",
      "pack_size": "4",
      "pack_unit": "case",
      "unit_contents": 1,
      "unit_contents_unit": "gal",
      "price_cents": 1599,
      "price_type": "case",
      "raw_text": "Whole Milk 4/1GAL $15.99",
      "match_score": 0.85
    }}
  ],
  "detected_distributor": "Valley Foods",
  "document_date": "2024-12-15"
}}

Important:
- Extract ALL items you can find, not just the first one
- If pack_size is not specified, assume 1
- If you can't determine a field, use null
- match_score should be 0.0-1.0 based on how well the item matches the ingredient context (if provided)
- Be thorough - this is financial data and accuracy matters

Return ONLY valid JSON, no explanation or markdown."""


# Unit conversion factors to base units (grams for weight, ml for volume)
UNIT_CONVERSIONS = {
    # Weight to grams
    "g": 1,
    "gram": 1,
    "grams": 1,
    "kg": 1000,
    "kilogram": 1000,
    "lb": 453.592,
    "lbs": 453.592,
    "pound": 453.592,
    "pounds": 453.592,
    "oz": 28.3495,
    "ounce": 28.3495,
    "ounces": 28.3495,
    # Volume to ml
    "ml": 1,
    "milliliter": 1,
    "l": 1000,
    "liter": 1000,
    "litre": 1000,
    "gal": 3785.41,
    "gallon": 3785.41,
    "gallons": 3785.41,
    "qt": 946.353,
    "quart": 946.353,
    "pt": 473.176,
    "pint": 473.176,
    "cup": 236.588,
    "fl oz": 29.5735,
    "floz": 29.5735,
    # Count
    "each": 1,
    "ea": 1,
    "ct": 1,
    "count": 1,
    "pc": 1,
    "piece": 1,
}

WEIGHT_UNITS = {"g", "gram", "grams", "kg", "kilogram", "lb", "lbs", "pound", "pounds", "oz", "ounce", "ounces"}
VOLUME_UNITS = {"ml", "milliliter", "l", "liter", "litre", "gal", "gallon", "gallons", "qt", "quart", "pt", "pint", "cup", "fl oz", "floz"}
COUNT_UNITS = {"each", "ea", "ct", "count", "pc", "piece"}


def _calculate_base_units(item: dict) -> tuple[Optional[float], Optional[str]]:
    """Calculate total base units for an item."""
    pack_size = item.get("pack_size")
    unit_contents = item.get("unit_contents")
    unit_contents_unit = item.get("unit_contents_unit")

    if not unit_contents or not unit_contents_unit:
        return None, None

    # Normalize unit name
    unit_lower = unit_contents_unit.lower().strip()

    if unit_lower not in UNIT_CONVERSIONS:
        logger.warning(f"Unknown unit: {unit_contents_unit}")
        return None, None

    conversion = UNIT_CONVERSIONS[unit_lower]

    # Determine base unit type
    if unit_lower in WEIGHT_UNITS:
        base_unit = "g"
    elif unit_lower in VOLUME_UNITS:
        base_unit = "ml"
    else:
        base_unit = "each"

    # Calculate total base units
    try:
        pack_qty = float(pack_size) if pack_size else 1
        contents = float(unit_contents)
        total = pack_qty * contents * conversion
        return total, base_unit
    except (ValueError, TypeError):
        return None, None


def parse_price_content(
    content: bytes | str,
    content_type: str,
    ingredient_context: Optional[dict] = None,
    custom_prompt: Optional[str] = None,
) -> ParseResult:
    """
    Parse pricing content using Claude Haiku.

    Args:
        content: The content to parse (bytes for images/PDFs, str for text)
        content_type: MIME type or content type hint:
            - "image/png", "image/jpeg", etc. for images
            - "application/pdf" for PDFs
            - "text/plain" for plain text
            - "text/email" for email content (with headers)
        ingredient_context: Optional dict with ingredient info for fuzzy matching:
            - name: Ingredient name
            - category: Ingredient category
            - base_unit: Base unit (g, ml, each)
        custom_prompt: Optional custom prompt to use instead of default

    Returns:
        ParseResult with extracted items and prompt_used
    """
    client = _get_anthropic_client()

    messages = []
    prompt_used = ""

    if content_type.startswith("image/"):
        # Image content - use vision
        if isinstance(content, str):
            # Assume it's already base64 encoded
            image_data = content
        else:
            image_data = base64.b64encode(content).decode("utf-8")

        # Map content type to media type
        media_type = content_type
        if content_type == "image/jpg":
            media_type = "image/jpeg"

        prompt_used = _build_parse_prompt("image", ingredient_context, custom_prompt)
        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    }
                },
                {
                    "type": "text",
                    "text": prompt_used
                }
            ]
        }]

    elif content_type == "application/pdf":
        # PDF - use document understanding
        if isinstance(content, str):
            pdf_data = content
        else:
            pdf_data = base64.b64encode(content).decode("utf-8")

        prompt_used = _build_parse_prompt("PDF document", ingredient_context, custom_prompt)
        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_data,
                    }
                },
                {
                    "type": "text",
                    "text": prompt_used
                }
            ]
        }]

    else:
        # Text content (plain text or email)
        if isinstance(content, bytes):
            text_content = content.decode("utf-8", errors="ignore")
        else:
            text_content = content

        # Handle email format
        if content_type == "text/email":
            text_content = _extract_email_body(text_content)

        prompt_used = _build_parse_prompt('text', ingredient_context, custom_prompt)
        messages = [{
            "role": "user",
            "content": f"{prompt_used}\n\nContent to parse:\n{text_content}"
        }]

    # Call Claude Haiku
    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=4096,
            messages=messages,
        )

        raw_response = response.content[0].text

        # Parse JSON response
        # Try to extract JSON from response (in case there's extra text)
        json_match = re.search(r'\{[\s\S]*\}', raw_response)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            parsed = json.loads(raw_response)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from Haiku response: {e}")
        logger.error(f"Raw response: {raw_response[:500]}")
        return ParseResult(
            items=[],
            detected_distributor=None,
            document_date=None,
            raw_response=raw_response if 'raw_response' in dir() else str(e),
            prompt_used=prompt_used,
        )
    except Exception as e:
        logger.error(f"Error calling Claude Haiku: {e}")
        raise

    # Process items
    items = []
    for item_data in parsed.get("items", []):
        # Calculate base units
        total_base_units, base_unit = _calculate_base_units(item_data)

        # Calculate price per base unit
        price_per_base = None
        if total_base_units and total_base_units > 0:
            price_cents = item_data.get("price_cents", 0)
            price_per_base = price_cents / total_base_units

        items.append(ParsedPriceItem(
            description=item_data.get("description", ""),
            sku=item_data.get("sku"),
            pack_size=item_data.get("pack_size"),
            pack_unit=item_data.get("pack_unit"),
            unit_contents=item_data.get("unit_contents"),
            unit_contents_unit=item_data.get("unit_contents_unit"),
            price_cents=item_data.get("price_cents", 0),
            price_type=item_data.get("price_type", "unit"),
            total_base_units=total_base_units,
            base_unit=base_unit,
            price_per_base_unit_cents=price_per_base,
            raw_text=item_data.get("raw_text", ""),
            confidence=item_data.get("match_score", 0.5),
        ))

    return ParseResult(
        items=items,
        detected_distributor=parsed.get("detected_distributor"),
        document_date=parsed.get("document_date"),
        raw_response=raw_response,
        prompt_used=prompt_used,
    )
