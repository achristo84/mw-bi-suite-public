"""Unit conversion engine for normalizing ingredient quantities.

Handles conversion between various units and base units:
- Weight: grams (g)
- Volume: milliliters (ml)
- Count: each

Also includes pack size parsing to extract quantities from invoice descriptions
like "36/1LB" or "4/1GAL".
"""
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple
from enum import Enum


class BaseUnit(str, Enum):
    """Base units for ingredient storage."""
    GRAM = "g"
    MILLILITER = "ml"
    EACH = "each"


# Weight conversions to grams
WEIGHT_TO_GRAMS: dict[str, Decimal] = {
    # Metric
    "g": Decimal("1"),
    "gram": Decimal("1"),
    "grams": Decimal("1"),
    "kg": Decimal("1000"),
    "kilogram": Decimal("1000"),
    "kilograms": Decimal("1000"),
    # Imperial
    "oz": Decimal("28.3495"),
    "ounce": Decimal("28.3495"),
    "ounces": Decimal("28.3495"),
    "lb": Decimal("453.592"),
    "lbs": Decimal("453.592"),
    "pound": Decimal("453.592"),
    "pounds": Decimal("453.592"),
    "#": Decimal("453.592"),  # Pound symbol often used in food service
}

# Volume conversions to milliliters
VOLUME_TO_ML: dict[str, Decimal] = {
    # Metric
    "ml": Decimal("1"),
    "milliliter": Decimal("1"),
    "milliliters": Decimal("1"),
    "l": Decimal("1000"),
    "liter": Decimal("1000"),
    "liters": Decimal("1000"),
    "litre": Decimal("1000"),
    "litres": Decimal("1000"),
    # US customary
    "fl oz": Decimal("29.5735"),
    "fl_oz": Decimal("29.5735"),
    "floz": Decimal("29.5735"),
    "fluid ounce": Decimal("29.5735"),
    "fluid ounces": Decimal("29.5735"),
    "cup": Decimal("236.588"),
    "cups": Decimal("236.588"),
    "c": Decimal("236.588"),
    "pt": Decimal("473.176"),
    "pint": Decimal("473.176"),
    "pints": Decimal("473.176"),
    "qt": Decimal("946.353"),
    "quart": Decimal("946.353"),
    "quarts": Decimal("946.353"),
    "gal": Decimal("3785.41"),
    "gallon": Decimal("3785.41"),
    "gallons": Decimal("3785.41"),
    # Tablespoons and teaspoons
    "tbsp": Decimal("14.7868"),
    "tablespoon": Decimal("14.7868"),
    "tablespoons": Decimal("14.7868"),
    "tsp": Decimal("4.92892"),
    "teaspoon": Decimal("4.92892"),
    "teaspoons": Decimal("4.92892"),
}

# Count-based units (convert to "each")
COUNT_UNITS: dict[str, Decimal] = {
    "ea": Decimal("1"),
    "each": Decimal("1"),
    "ct": Decimal("1"),
    "count": Decimal("1"),
    "pc": Decimal("1"),
    "piece": Decimal("1"),
    "pieces": Decimal("1"),
    "unit": Decimal("1"),
    "units": Decimal("1"),
    "dz": Decimal("12"),
    "doz": Decimal("12"),
    "dozen": Decimal("12"),
}

# Common case/pack units that need special handling
CASE_UNITS = {"cs", "case", "cases", "pk", "pack", "packs", "bx", "box", "boxes", "ct", "carton", "cartons"}


def normalize_unit(unit: str) -> str:
    """Normalize unit string for lookup.

    Args:
        unit: Raw unit string from invoice

    Returns:
        Normalized lowercase unit string
    """
    return unit.lower().strip().replace("-", " ").replace("_", " ")


def get_unit_type(unit: str) -> Optional[BaseUnit]:
    """Determine the base unit type for a given unit.

    Args:
        unit: Unit string to classify

    Returns:
        BaseUnit enum or None if unknown
    """
    normalized = normalize_unit(unit)

    if normalized in WEIGHT_TO_GRAMS:
        return BaseUnit.GRAM
    if normalized in VOLUME_TO_ML:
        return BaseUnit.MILLILITER
    if normalized in COUNT_UNITS:
        return BaseUnit.EACH

    return None


def convert_to_base_unit(quantity: Decimal, unit: str, target_base: BaseUnit) -> Optional[Decimal]:
    """Convert a quantity to its base unit.

    Args:
        quantity: Amount to convert
        unit: Source unit (e.g., "lb", "oz", "gallon")
        target_base: Target base unit type

    Returns:
        Converted quantity in base units, or None if conversion not possible

    Raises:
        ValueError: If unit type doesn't match target base
    """
    normalized = normalize_unit(unit)

    if target_base == BaseUnit.GRAM:
        if normalized in WEIGHT_TO_GRAMS:
            return quantity * WEIGHT_TO_GRAMS[normalized]
        raise ValueError(f"Cannot convert '{unit}' to grams - not a weight unit")

    elif target_base == BaseUnit.MILLILITER:
        if normalized in VOLUME_TO_ML:
            return quantity * VOLUME_TO_ML[normalized]
        raise ValueError(f"Cannot convert '{unit}' to milliliters - not a volume unit")

    elif target_base == BaseUnit.EACH:
        if normalized in COUNT_UNITS:
            return quantity * COUNT_UNITS[normalized]
        raise ValueError(f"Cannot convert '{unit}' to each - not a count unit")

    return None


def convert_weight_to_grams(quantity: Decimal, unit: str) -> Decimal:
    """Convert a weight quantity to grams.

    Args:
        quantity: Amount to convert
        unit: Source weight unit

    Returns:
        Quantity in grams

    Raises:
        ValueError: If unit is not a recognized weight unit
    """
    result = convert_to_base_unit(quantity, unit, BaseUnit.GRAM)
    if result is None:
        raise ValueError(f"Unknown weight unit: {unit}")
    return result


def convert_volume_to_ml(quantity: Decimal, unit: str) -> Decimal:
    """Convert a volume quantity to milliliters.

    Args:
        quantity: Amount to convert
        unit: Source volume unit

    Returns:
        Quantity in milliliters

    Raises:
        ValueError: If unit is not a recognized volume unit
    """
    result = convert_to_base_unit(quantity, unit, BaseUnit.MILLILITER)
    if result is None:
        raise ValueError(f"Unknown volume unit: {unit}")
    return result


def convert_count_to_each(quantity: Decimal, unit: str) -> Decimal:
    """Convert a count quantity to each.

    Args:
        quantity: Amount to convert
        unit: Source count unit

    Returns:
        Quantity in each

    Raises:
        ValueError: If unit is not a recognized count unit
    """
    result = convert_to_base_unit(quantity, unit, BaseUnit.EACH)
    if result is None:
        raise ValueError(f"Unknown count unit: {unit}")
    return result


# Pack size parsing patterns
# Note: Unit alternations ordered longest-first to prevent partial matches (GAL before G, etc.)
UNIT_PATTERN = r"GAL|GALLON|QT|QUART|PT|PINT|ML|LB|OZ|KG|G|L"

# Fraction pattern for "9/1/2GAL" = 9 × 0.5 gallon
# Format: pack_count / numerator / denominator + unit
FRACTION_PACK_PATTERN = re.compile(
    rf"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*({UNIT_PATTERN})", re.IGNORECASE
)

PACK_PATTERNS = [
    # "36/1LB" - 36 units of 1 lb each (no space before unit)
    re.compile(rf"(\d+)\s*/\s*(\d+\.?\d*)\s*({UNIT_PATTERN})", re.IGNORECASE),
    # "36/1 LB" - with space before unit
    re.compile(rf"(\d+)\s*/\s*(\d+\.?\d*)\s+({UNIT_PATTERN})", re.IGNORECASE),
    # "36X1LB" or "36 X 1LB" - alternate format
    re.compile(rf"(\d+)\s*[Xx]\s*(\d+\.?\d*)\s*({UNIT_PATTERN})", re.IGNORECASE),
    # "15DZ" or "15 DZ" - dozen count
    re.compile(r"(\d+)\s*(DZ|DOZ|DOZEN)", re.IGNORECASE),
    # "10LB CS" or "10 LB CASE" - weight case (standalone quantity+unit)
    re.compile(rf"(\d+\.?\d*)\s*({UNIT_PATTERN})\s*(CS|CASE|BX|BOX|PK|PACK)?", re.IGNORECASE),
    # "4CT" or "4 CT" - count
    re.compile(r"(\d+)\s*(CT|EA|PC|EACH)", re.IGNORECASE),
]


class PackInfo:
    """Parsed pack size information."""

    def __init__(
        self,
        pack_quantity: Decimal,
        unit_quantity: Decimal,
        unit: str,
        total_base_units: Optional[Decimal] = None,
        base_unit: Optional[BaseUnit] = None,
    ):
        self.pack_quantity = pack_quantity  # Number of units in pack (e.g., 36)
        self.unit_quantity = unit_quantity  # Size per unit (e.g., 1)
        self.unit = unit  # Unit type (e.g., "LB")
        self.total_base_units = total_base_units  # Total in base units (e.g., 16329 grams)
        self.base_unit = base_unit  # Base unit type

    @property
    def total_quantity(self) -> Decimal:
        """Total quantity in source units."""
        return self.pack_quantity * self.unit_quantity

    def __repr__(self):
        return f"PackInfo({self.pack_quantity} × {self.unit_quantity} {self.unit} = {self.total_base_units} {self.base_unit})"


def parse_pack_description(description: str) -> Optional[PackInfo]:
    """Extract pack configuration from a distributor description.

    Args:
        description: Product description (e.g., "BUTTER AA 36/1LB CS")

    Returns:
        PackInfo with parsed values, or None if no pattern matched

    Examples:
        "36/1LB" -> PackInfo(36, 1, "LB", 16329g, GRAM)
        "4/1GAL" -> PackInfo(4, 1, "GAL", 15141ml, MILLILITER)
        "9/1/2GAL" -> PackInfo(9, 0.5, "GAL", 17034ml, MILLILITER)
        "15DZ" -> PackInfo(15, 12, "each", 180, EACH)
        "10LB CS" -> PackInfo(1, 10, "LB", 4535.92g, GRAM)
    """
    description_upper = description.upper()

    # Check for fraction pattern first: "9/1/2GAL" = 9 × (1/2) gallon
    fraction_match = FRACTION_PACK_PATTERN.search(description_upper)
    if fraction_match:
        pack_qty = Decimal(fraction_match.group(1))
        numerator = Decimal(fraction_match.group(2))
        denominator = Decimal(fraction_match.group(3))
        unit = fraction_match.group(4)

        # unit_qty is the fraction (e.g., 1/2 = 0.5)
        unit_qty = numerator / denominator

        # Convert to base units
        normalized_unit = normalize_unit(unit)
        total_source = pack_qty * unit_qty

        if normalized_unit in WEIGHT_TO_GRAMS:
            total_base = total_source * WEIGHT_TO_GRAMS[normalized_unit]
            return PackInfo(pack_qty, unit_qty, unit, total_base, BaseUnit.GRAM)
        elif normalized_unit in VOLUME_TO_ML:
            total_base = total_source * VOLUME_TO_ML[normalized_unit]
            return PackInfo(pack_qty, unit_qty, unit, total_base, BaseUnit.MILLILITER)

    # Try each standard pattern
    for pattern in PACK_PATTERNS:
        match = pattern.search(description_upper)
        if match:
            groups = match.groups()

            # Handle different pattern formats
            if len(groups) == 2:
                # Dozen pattern: (count, DZ)
                if groups[1].upper() in ("DZ", "DOZ", "DOZEN"):
                    pack_qty = Decimal(groups[0])
                    unit_qty = Decimal("12")  # Convert dozen to each
                    unit = "each"
                    base_unit = BaseUnit.EACH
                    total = pack_qty * unit_qty
                    return PackInfo(pack_qty, unit_qty, unit, total, base_unit)
                # Count pattern: (count, CT/EA)
                else:
                    pack_qty = Decimal(groups[0])
                    unit_qty = Decimal("1")
                    unit = "each"
                    base_unit = BaseUnit.EACH
                    return PackInfo(pack_qty, unit_qty, unit, pack_qty, base_unit)

            elif len(groups) >= 3:
                # Standard patterns: (pack_count, unit_size, unit) or (unit_size, unit, case?)
                # Check if first number is pack count or unit size
                if "/" in match.group(0) or "X" in match.group(0).upper():
                    # Format: 36/1LB or 36X1LB
                    pack_qty = Decimal(groups[0])
                    unit_qty = Decimal(groups[1])
                    unit = groups[2]
                else:
                    # Format: 10LB CS (single weight/volume)
                    pack_qty = Decimal("1")
                    unit_qty = Decimal(groups[0])
                    unit = groups[1]

                # Convert to base units
                normalized_unit = normalize_unit(unit)
                total_source = pack_qty * unit_qty

                if normalized_unit in WEIGHT_TO_GRAMS:
                    total_base = total_source * WEIGHT_TO_GRAMS[normalized_unit]
                    return PackInfo(pack_qty, unit_qty, unit, total_base, BaseUnit.GRAM)

                elif normalized_unit in VOLUME_TO_ML:
                    total_base = total_source * VOLUME_TO_ML[normalized_unit]
                    return PackInfo(pack_qty, unit_qty, unit, total_base, BaseUnit.MILLILITER)

    return None


def calculate_price_per_base_unit(
    price_cents: int,
    pack_info: PackInfo,
) -> Optional[Decimal]:
    """Calculate price per base unit from pack price.

    Args:
        price_cents: Total price for the pack in cents
        pack_info: Parsed pack information

    Returns:
        Price per base unit in cents (Decimal for precision)

    Example:
        $142.56 for 36/1LB butter = $0.0087/gram
    """
    if pack_info.total_base_units is None or pack_info.total_base_units == 0:
        return None

    return Decimal(price_cents) / pack_info.total_base_units


def format_price_per_unit(price_per_base: Decimal, base_unit: BaseUnit) -> str:
    """Format a price per base unit for display.

    Args:
        price_per_base: Price in cents per base unit
        base_unit: The base unit type

    Returns:
        Formatted string like "$0.0087/g" or "$0.15/each"
    """
    # Convert cents to dollars
    price_dollars = price_per_base / Decimal("100")

    # Format with appropriate precision
    if price_dollars < Decimal("0.01"):
        formatted = f"${price_dollars:.4f}"
    elif price_dollars < Decimal("1"):
        formatted = f"${price_dollars:.3f}"
    else:
        formatted = f"${price_dollars:.2f}"

    return f"{formatted}/{base_unit.value}"


# Common ingredient categories
INGREDIENT_CATEGORIES = [
    "dairy",
    "produce",
    "protein",
    "dry_goods",
    "beverages",
    "coffee",
    "bakery",
    "frozen",
    "packaging",
    "cleaning",
    "other",
]


def suggest_category(ingredient_name: str) -> Optional[str]:
    """Suggest a category based on ingredient name.

    Simple keyword matching - not comprehensive, just a starting point.

    Args:
        ingredient_name: Name of the ingredient

    Returns:
        Suggested category or None
    """
    name_lower = ingredient_name.lower()

    # Dairy
    if any(word in name_lower for word in ["milk", "cream", "butter", "cheese", "yogurt", "half"]):
        return "dairy"

    # Produce
    if any(word in name_lower for word in ["onion", "garlic", "tomato", "lettuce", "carrot", "celery", "pepper", "herb", "lemon", "lime", "orange", "apple", "banana", "berry"]):
        return "produce"

    # Protein
    if any(word in name_lower for word in ["chicken", "beef", "pork", "fish", "salmon", "shrimp", "egg", "bacon", "sausage", "turkey"]):
        return "protein"

    # Coffee
    if any(word in name_lower for word in ["coffee", "espresso", "bean"]):
        return "coffee"

    # Bakery
    if any(word in name_lower for word in ["flour", "sugar", "yeast", "baking", "vanilla", "chocolate", "cocoa"]):
        return "bakery"

    # Beverages
    if any(word in name_lower for word in ["juice", "soda", "water", "tea", "syrup"]):
        return "beverages"

    # Packaging
    if any(word in name_lower for word in ["cup", "lid", "straw", "napkin", "sleeve", "bag", "box", "container", "wrap", "foil"]):
        return "packaging"

    # Dry goods
    if any(word in name_lower for word in ["rice", "pasta", "oil", "vinegar", "sauce", "spice", "salt", "pepper"]):
        return "dry_goods"

    return None
