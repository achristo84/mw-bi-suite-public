#!/usr/bin/env python3
"""Test the unit conversion engine with real-world examples."""

from decimal import Decimal
from app.services.units import (
    convert_weight_to_grams,
    convert_volume_to_ml,
    convert_count_to_each,
    parse_pack_description,
    calculate_price_per_base_unit,
    format_price_per_unit,
    get_unit_type,
    BaseUnit,
)


def test_weight_conversions():
    """Test weight unit conversions."""
    print("\n=== Weight Conversions ===")

    tests = [
        (1, "lb", 453.592),
        (36, "lb", 16329.312),  # 36/1LB case of butter
        (10, "kg", 10000),
        (16, "oz", 453.592),  # 1 lb in oz
        (1, "#", 453.592),  # Pound symbol
    ]

    for qty, unit, expected in tests:
        result = convert_weight_to_grams(Decimal(str(qty)), unit)
        status = "✓" if abs(float(result) - expected) < 0.01 else "✗"
        print(f"  {status} {qty} {unit} = {result:.2f}g (expected {expected:.2f}g)")


def test_volume_conversions():
    """Test volume unit conversions."""
    print("\n=== Volume Conversions ===")

    tests = [
        (1, "gallon", 3785.41),
        (4, "gal", 15141.64),  # 4/1GAL case
        (1, "quart", 946.353),
        (1, "cup", 236.588),
        (1, "fl oz", 29.5735),
    ]

    for qty, unit, expected in tests:
        result = convert_volume_to_ml(Decimal(str(qty)), unit)
        status = "✓" if abs(float(result) - expected) < 0.01 else "✗"
        print(f"  {status} {qty} {unit} = {result:.2f}ml (expected {expected:.2f}ml)")


def test_count_conversions():
    """Test count unit conversions."""
    print("\n=== Count Conversions ===")

    tests = [
        (15, "dozen", 180),  # 15 dozen eggs
        (1, "dz", 12),
        (24, "ea", 24),
        (1, "each", 1),
    ]

    for qty, unit, expected in tests:
        result = convert_count_to_each(Decimal(str(qty)), unit)
        status = "✓" if float(result) == expected else "✗"
        print(f"  {status} {qty} {unit} = {result} each (expected {expected})")


def test_pack_parsing():
    """Test pack size parsing from invoice descriptions."""
    print("\n=== Pack Size Parsing ===")

    tests = [
        # (description, expected_pack_qty, expected_unit_qty, expected_unit, expected_total_base)
        ("BUTTER AA 36/1LB CS", 36, 1, "LB", 16329.312),
        ("HEAVY CREAM 4/1GAL", 4, 1, "GAL", 15141.64),
        ("EGGS LARGE 15DZ", 15, 12, "each", 180),
        ("ALL PURPOSE FLOUR 50LB", 1, 50, "LB", 22679.6),
        ("MILK 6/1GAL CS", 6, 1, "GAL", 22712.46),
        ("OLIVE OIL 4/1GAL", 4, 1, "GAL", 15141.64),
        ("SUGAR GRANULATED 25LB", 1, 25, "LB", 11339.8),
    ]

    for desc, exp_pack, exp_unit_qty, exp_unit, exp_total in tests:
        result = parse_pack_description(desc)
        if result:
            pack_match = float(result.pack_quantity) == exp_pack
            unit_qty_match = float(result.unit_quantity) == exp_unit_qty
            total_match = abs(float(result.total_base_units or 0) - exp_total) < 1

            status = "✓" if (pack_match and unit_qty_match and total_match) else "✗"
            print(f"  {status} '{desc}'")
            print(f"      → {result.pack_quantity}×{result.unit_quantity}{result.unit} = {result.total_base_units:.2f} {result.base_unit.value}")
        else:
            print(f"  ✗ '{desc}' - Failed to parse")


def test_price_calculations():
    """Test price per base unit calculations."""
    print("\n=== Price Per Base Unit ===")

    tests = [
        # (description, price_cents, expected_price_per_base)
        ("BUTTER AA 36/1LB CS", 14256, 0.873),  # $142.56 / 16329g = $0.00873/g
        ("HEAVY CREAM 4/1GAL", 1180, 0.078),  # $11.80 / 15141ml = $0.00078/ml
        ("EGGS LARGE 15DZ", 3200, 17.78),  # $32.00 / 180 = $0.178/each
    ]

    for desc, price_cents, expected_per_base in tests:
        pack_info = parse_pack_description(desc)
        if pack_info:
            price_per_base = calculate_price_per_base_unit(price_cents, pack_info)
            if price_per_base:
                formatted = format_price_per_unit(price_per_base, pack_info.base_unit)
                # Compare with some tolerance for rounding
                status = "✓" if abs(float(price_per_base) - expected_per_base) < 0.1 else "~"
                print(f"  {status} '{desc}' @ ${price_cents/100:.2f}")
                print(f"      → {formatted} (expected ~${expected_per_base/100:.4f}/{pack_info.base_unit.value})")


def test_unit_type_detection():
    """Test unit type detection."""
    print("\n=== Unit Type Detection ===")

    tests = [
        ("lb", BaseUnit.GRAM),
        ("oz", BaseUnit.GRAM),
        ("kg", BaseUnit.GRAM),
        ("gallon", BaseUnit.MILLILITER),
        ("ml", BaseUnit.MILLILITER),
        ("each", BaseUnit.EACH),
        ("dozen", BaseUnit.EACH),
    ]

    for unit, expected_type in tests:
        result = get_unit_type(unit)
        status = "✓" if result == expected_type else "✗"
        print(f"  {status} '{unit}' → {result} (expected {expected_type})")


if __name__ == "__main__":
    print("=" * 50)
    print("Unit Conversion Engine Tests")
    print("=" * 50)

    test_weight_conversions()
    test_volume_conversions()
    test_count_conversions()
    test_pack_parsing()
    test_price_calculations()
    test_unit_type_detection()

    print("\n" + "=" * 50)
    print("Tests complete!")
    print("=" * 50)
