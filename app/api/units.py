"""Units API for centralized unit conversion information."""

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.units import (
    WEIGHT_TO_GRAMS,
    VOLUME_TO_ML,
    COUNT_UNITS,
    parse_pack_description,
    BaseUnit,
)

router = APIRouter(prefix="/units", tags=["units"])


class UnitConversions(BaseModel):
    """Unit conversion factors."""
    weight: dict[str, float]  # unit -> grams
    volume: dict[str, float]  # unit -> ml
    count: dict[str, float]   # unit -> each
    base_units: list[str]


class ParsePackRequest(BaseModel):
    """Request to parse a pack description."""
    description: str


class ParsePackResponse(BaseModel):
    """Parsed pack information."""
    success: bool
    pack_count: Optional[float] = None
    unit_size: Optional[float] = None
    unit: Optional[str] = None
    total_base_units: Optional[float] = None
    base_unit: Optional[str] = None
    display: Optional[str] = None
    error: Optional[str] = None


@router.get("", response_model=UnitConversions)
def get_units():
    """Get all unit conversion factors.

    Returns a dictionary of unit types with conversion factors to base units:
    - weight: converts to grams (g)
    - volume: converts to milliliters (ml)
    - count: converts to each
    """
    # Convert Decimal to float for JSON serialization
    # Only include common/useful units (skip variants like "gram" vs "grams")
    weight = {
        "g": 1.0,
        "kg": 1000.0,
        "oz": 28.3495,
        "lb": 453.592,
    }

    volume = {
        "ml": 1.0,
        "L": 1000.0,
        "fl oz": 29.5735,
        "cup": 236.588,
        "pt": 473.176,
        "qt": 946.353,
        "gal": 3785.41,
        "tbsp": 14.7868,
        "tsp": 4.92892,
    }

    count = {
        "each": 1.0,
        "ea": 1.0,
        "ct": 1.0,
        "doz": 12.0,
        "dozen": 12.0,
    }

    return UnitConversions(
        weight=weight,
        volume=volume,
        count=count,
        base_units=["g", "ml", "each"],
    )


@router.post("/parse-pack", response_model=ParsePackResponse)
def parse_pack(request: ParsePackRequest):
    """Parse a pack description like '36/1LB' or '9/1/2GAL'.

    Returns the parsed pack information including:
    - pack_count: Number of units in pack
    - unit_size: Size per unit
    - unit: Unit type
    - total_base_units: Total in base units (g or ml)
    - base_unit: The base unit type
    - display: Human-readable format
    """
    description = request.description.strip()
    if not description:
        return ParsePackResponse(
            success=False,
            error="Empty description"
        )

    pack_info = parse_pack_description(description)

    if pack_info is None:
        return ParsePackResponse(
            success=False,
            error=f"Could not parse pack description: {description}"
        )

    # Format display string
    if pack_info.pack_quantity == 1:
        display = f"{pack_info.unit_quantity} {pack_info.unit}"
    else:
        display = f"{pack_info.pack_quantity} × {pack_info.unit_quantity} {pack_info.unit}"

    if pack_info.total_base_units:
        if pack_info.base_unit == BaseUnit.GRAM:
            if pack_info.total_base_units >= 1000:
                display += f" = {float(pack_info.total_base_units / 1000):.2f} kg"
            else:
                display += f" = {float(pack_info.total_base_units):.0f} g"
        elif pack_info.base_unit == BaseUnit.MILLILITER:
            if pack_info.total_base_units >= 1000:
                display += f" = {float(pack_info.total_base_units / 1000):.2f} L"
            else:
                display += f" = {float(pack_info.total_base_units):.0f} ml"
        else:
            display += f" = {int(pack_info.total_base_units)} each"

    return ParsePackResponse(
        success=True,
        pack_count=float(pack_info.pack_quantity),
        unit_size=float(pack_info.unit_quantity),
        unit=pack_info.unit,
        total_base_units=float(pack_info.total_base_units) if pack_info.total_base_units else None,
        base_unit=pack_info.base_unit.value if pack_info.base_unit else None,
        display=display,
    )
