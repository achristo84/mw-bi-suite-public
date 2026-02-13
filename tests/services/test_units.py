"""Tests for app/services/units.py - unit conversion engine and pack size parsing."""
from decimal import Decimal

import pytest

from app.services.units import (
    BaseUnit,
    PackInfo,
    calculate_price_per_base_unit,
    convert_count_to_each,
    convert_to_base_unit,
    convert_volume_to_ml,
    convert_weight_to_grams,
    format_price_per_unit,
    get_unit_type,
    normalize_unit,
    parse_pack_description,
    suggest_category,
)


# ============================================================================
# normalize_unit
# ============================================================================


class TestNormalizeUnit:
    def test_lowercase(self):
        assert normalize_unit("LB") == "lb"

    def test_strip_whitespace(self):
        assert normalize_unit("  oz  ") == "oz"

    def test_replace_hyphens(self):
        assert normalize_unit("fl-oz") == "fl oz"

    def test_replace_underscores(self):
        assert normalize_unit("fl_oz") == "fl oz"

    def test_combined(self):
        assert normalize_unit("  FL_OZ  ") == "fl oz"


# ============================================================================
# get_unit_type
# ============================================================================


class TestGetUnitType:
    @pytest.mark.parametrize(
        "unit",
        ["g", "gram", "grams", "kg", "kilogram", "kilograms", "oz", "ounce", "ounces",
         "lb", "lbs", "pound", "pounds", "#"],
    )
    def test_weight_units(self, unit):
        assert get_unit_type(unit) == BaseUnit.GRAM

    @pytest.mark.parametrize(
        "unit",
        ["ml", "milliliter", "milliliters", "l", "liter", "liters", "litre", "litres",
         "fl oz", "fl_oz", "floz", "cup", "cups", "pt", "pint", "qt", "quart",
         "gal", "gallon", "gallons", "tbsp", "tablespoon", "tsp", "teaspoon"],
    )
    def test_volume_units(self, unit):
        assert get_unit_type(unit) == BaseUnit.MILLILITER

    @pytest.mark.parametrize(
        "unit",
        ["ea", "each", "ct", "count", "pc", "piece", "pieces", "unit", "units",
         "dz", "doz", "dozen"],
    )
    def test_count_units(self, unit):
        assert get_unit_type(unit) == BaseUnit.EACH

    def test_unknown_unit(self):
        assert get_unit_type("bushel") is None

    def test_case_insensitive(self):
        assert get_unit_type("LB") == BaseUnit.GRAM
        assert get_unit_type("Gallon") == BaseUnit.MILLILITER
        assert get_unit_type("EACH") == BaseUnit.EACH


# ============================================================================
# convert_to_base_unit
# ============================================================================


class TestConvertToBaseUnit:
    def test_grams_to_grams(self):
        result = convert_to_base_unit(Decimal("100"), "g", BaseUnit.GRAM)
        assert result == Decimal("100")

    def test_pounds_to_grams(self):
        result = convert_to_base_unit(Decimal("1"), "lb", BaseUnit.GRAM)
        assert result == Decimal("453.592")

    def test_ounces_to_grams(self):
        result = convert_to_base_unit(Decimal("1"), "oz", BaseUnit.GRAM)
        assert result == Decimal("28.3495")

    def test_kg_to_grams(self):
        result = convert_to_base_unit(Decimal("2"), "kg", BaseUnit.GRAM)
        assert result == Decimal("2000")

    def test_gallons_to_ml(self):
        result = convert_to_base_unit(Decimal("1"), "gal", BaseUnit.MILLILITER)
        assert result == Decimal("3785.41")

    def test_cups_to_ml(self):
        result = convert_to_base_unit(Decimal("2"), "cup", BaseUnit.MILLILITER)
        assert result == Decimal("2") * Decimal("236.588")

    def test_dozen_to_each(self):
        result = convert_to_base_unit(Decimal("1"), "dozen", BaseUnit.EACH)
        assert result == Decimal("12")

    def test_wrong_unit_type_raises(self):
        with pytest.raises(ValueError, match="not a weight unit"):
            convert_to_base_unit(Decimal("1"), "gal", BaseUnit.GRAM)

    def test_volume_unit_as_weight_raises(self):
        with pytest.raises(ValueError, match="not a volume unit"):
            convert_to_base_unit(Decimal("1"), "lb", BaseUnit.MILLILITER)

    def test_weight_unit_as_count_raises(self):
        with pytest.raises(ValueError, match="not a count unit"):
            convert_to_base_unit(Decimal("1"), "lb", BaseUnit.EACH)


# ============================================================================
# Convenience conversion functions
# ============================================================================


class TestConvertWeightToGrams:
    def test_pounds(self):
        assert convert_weight_to_grams(Decimal("1"), "lb") == Decimal("453.592")

    def test_ounces(self):
        assert convert_weight_to_grams(Decimal("16"), "oz") == Decimal("16") * Decimal("28.3495")

    def test_invalid_unit(self):
        with pytest.raises(ValueError):
            convert_weight_to_grams(Decimal("1"), "gal")


class TestConvertVolumeToMl:
    def test_liters(self):
        assert convert_volume_to_ml(Decimal("1"), "l") == Decimal("1000")

    def test_quarts(self):
        assert convert_volume_to_ml(Decimal("1"), "qt") == Decimal("946.353")

    def test_invalid_unit(self):
        with pytest.raises(ValueError):
            convert_volume_to_ml(Decimal("1"), "lb")


class TestConvertCountToEach:
    def test_dozen(self):
        assert convert_count_to_each(Decimal("1"), "dozen") == Decimal("12")

    def test_each(self):
        assert convert_count_to_each(Decimal("5"), "ea") == Decimal("5")

    def test_invalid_unit(self):
        with pytest.raises(ValueError):
            convert_count_to_each(Decimal("1"), "lb")


# ============================================================================
# parse_pack_description
# ============================================================================


class TestParsePackDescription:
    def test_standard_slash_format(self):
        """36/1LB = 36 units of 1 lb each."""
        result = parse_pack_description("BUTTER AA 36/1LB CS")
        assert result is not None
        assert result.pack_quantity == Decimal("36")
        assert result.unit_quantity == Decimal("1")
        assert result.unit.upper() == "LB"
        assert result.base_unit == BaseUnit.GRAM
        expected_grams = Decimal("36") * Decimal("453.592")
        assert result.total_base_units == expected_grams

    def test_slash_with_space(self):
        """36/1 LB with space before unit."""
        result = parse_pack_description("36/1 LB")
        assert result is not None
        assert result.pack_quantity == Decimal("36")
        assert result.unit_quantity == Decimal("1")

    def test_gallon_format(self):
        """4/1GAL = 4 gallons."""
        result = parse_pack_description("MILK 4/1GAL")
        assert result is not None
        assert result.pack_quantity == Decimal("4")
        assert result.unit_quantity == Decimal("1")
        assert result.base_unit == BaseUnit.MILLILITER
        expected_ml = Decimal("4") * Decimal("3785.41")
        assert result.total_base_units == expected_ml

    def test_fraction_format(self):
        """9/1/2GAL = 9 units of 1/2 gallon each."""
        result = parse_pack_description("JUICE 9/1/2GAL")
        assert result is not None
        assert result.pack_quantity == Decimal("9")
        assert result.unit_quantity == Decimal("0.5")
        assert result.base_unit == BaseUnit.MILLILITER
        expected_ml = Decimal("9") * Decimal("0.5") * Decimal("3785.41")
        assert result.total_base_units == expected_ml

    def test_x_format(self):
        """4X5LB = 4 units of 5 lb each."""
        result = parse_pack_description("CHEESE 4X5LB")
        assert result is not None
        assert result.pack_quantity == Decimal("4")
        assert result.unit_quantity == Decimal("5")
        assert result.base_unit == BaseUnit.GRAM
        expected_grams = Decimal("20") * Decimal("453.592")
        assert result.total_base_units == expected_grams

    def test_dozen_format(self):
        """15DZ = 15 dozen = 180 each."""
        result = parse_pack_description("EGGS 15DZ")
        assert result is not None
        assert result.pack_quantity == Decimal("15")
        assert result.unit_quantity == Decimal("12")
        assert result.base_unit == BaseUnit.EACH
        assert result.total_base_units == Decimal("180")

    def test_weight_case_format(self):
        """10LB CS = 1 case of 10 lb."""
        result = parse_pack_description("FLOUR 10LB CS")
        assert result is not None
        assert result.pack_quantity == Decimal("1")
        assert result.unit_quantity == Decimal("10")
        assert result.base_unit == BaseUnit.GRAM
        expected_grams = Decimal("10") * Decimal("453.592")
        assert result.total_base_units == expected_grams

    def test_count_format(self):
        """4CT = 4 each."""
        result = parse_pack_description("NAPKINS 4CT")
        assert result is not None
        assert result.pack_quantity == Decimal("4")
        assert result.base_unit == BaseUnit.EACH

    def test_no_match(self):
        """Description with no recognizable pack pattern."""
        result = parse_pack_description("SOMETHING RANDOM")
        assert result is None

    def test_total_quantity_property(self):
        """PackInfo.total_quantity = pack_quantity * unit_quantity."""
        result = parse_pack_description("36/1LB")
        assert result is not None
        assert result.total_quantity == Decimal("36")

    def test_volume_slash_format(self):
        """6/1QT = 6 quarts."""
        result = parse_pack_description("CREAM 6/1QT")
        assert result is not None
        assert result.pack_quantity == Decimal("6")
        assert result.base_unit == BaseUnit.MILLILITER
        expected_ml = Decimal("6") * Decimal("946.353")
        assert result.total_base_units == expected_ml

    def test_case_insensitive(self):
        """Pack parsing should be case-insensitive."""
        result_upper = parse_pack_description("4/1GAL")
        result_lower = parse_pack_description("4/1gal")
        assert result_upper is not None
        assert result_lower is not None
        assert result_upper.total_base_units == result_lower.total_base_units

    def test_decimal_unit_quantity(self):
        """6/1.5LB = 6 units of 1.5 lb each."""
        result = parse_pack_description("BACON 6/1.5LB")
        assert result is not None
        assert result.pack_quantity == Decimal("6")
        assert result.unit_quantity == Decimal("1.5")
        expected_grams = Decimal("9") * Decimal("453.592")
        assert result.total_base_units == expected_grams


# ============================================================================
# calculate_price_per_base_unit
# ============================================================================


class TestCalculatePricePerBaseUnit:
    def test_basic_calculation(self):
        """$142.56 for 36/1LB butter = price per gram."""
        pack = parse_pack_description("36/1LB")
        assert pack is not None
        result = calculate_price_per_base_unit(14256, pack)
        assert result is not None
        # 14256 cents / (36 * 453.592 grams) = ~0.873 cents/gram
        expected = Decimal("14256") / (Decimal("36") * Decimal("453.592"))
        assert abs(result - expected) < Decimal("0.0001")

    def test_zero_base_units(self):
        """Should return None when total_base_units is zero."""
        pack = PackInfo(
            pack_quantity=Decimal("0"),
            unit_quantity=Decimal("1"),
            unit="lb",
            total_base_units=Decimal("0"),
            base_unit=BaseUnit.GRAM,
        )
        result = calculate_price_per_base_unit(1000, pack)
        assert result is None

    def test_none_base_units(self):
        """Should return None when total_base_units is None."""
        pack = PackInfo(
            pack_quantity=Decimal("1"),
            unit_quantity=Decimal("1"),
            unit="lb",
            total_base_units=None,
            base_unit=BaseUnit.GRAM,
        )
        result = calculate_price_per_base_unit(1000, pack)
        assert result is None


# ============================================================================
# format_price_per_unit
# ============================================================================


class TestFormatPricePerUnit:
    def test_tiny_price(self):
        """Very small per-gram price should show 4 decimal places."""
        # 0.87 cents per gram = $0.0087/g
        result = format_price_per_unit(Decimal("0.87"), BaseUnit.GRAM)
        assert result == "$0.0087/g"

    def test_medium_price(self):
        """Medium price shows 3 decimal places."""
        # 50 cents per ml = $0.500/ml
        result = format_price_per_unit(Decimal("50"), BaseUnit.MILLILITER)
        assert result == "$0.500/ml"

    def test_large_price(self):
        """Larger price shows 2 decimal places."""
        # 150 cents per each = $1.50/each
        result = format_price_per_unit(Decimal("150"), BaseUnit.EACH)
        assert result == "$1.50/each"

    def test_unit_suffix(self):
        """Unit suffix should use base_unit.value."""
        result = format_price_per_unit(Decimal("0.5"), BaseUnit.GRAM)
        assert result.endswith("/g")

        result = format_price_per_unit(Decimal("0.5"), BaseUnit.MILLILITER)
        assert result.endswith("/ml")


# ============================================================================
# suggest_category
# ============================================================================


class TestSuggestCategory:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Whole Milk", "dairy"),
            ("Heavy Cream", "dairy"),
            ("Butter", "dairy"),
            ("Cheddar Cheese", "dairy"),
            ("Yogurt", "dairy"),
        ],
    )
    def test_dairy(self, name, expected):
        assert suggest_category(name) == expected

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Yellow Onion", "produce"),
            ("Fresh Garlic", "produce"),
            ("Roma Tomato", "produce"),
            ("Green Pepper", "produce"),
            ("Lemon", "produce"),
        ],
    )
    def test_produce(self, name, expected):
        assert suggest_category(name) == expected

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Chicken Breast", "protein"),
            ("Ground Beef", "protein"),
            ("Atlantic Salmon", "protein"),
            ("Egg", "protein"),
            ("Bacon", "protein"),
        ],
    )
    def test_protein(self, name, expected):
        assert suggest_category(name) == expected

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Espresso Beans", "coffee"),
            ("Coffee Blend", "coffee"),
        ],
    )
    def test_coffee(self, name, expected):
        assert suggest_category(name) == expected

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("All Purpose Flour", "bakery"),
            ("Granulated Sugar", "bakery"),
            ("Vanilla Extract", "bakery"),
            ("Cocoa Powder", "bakery"),
        ],
    )
    def test_bakery(self, name, expected):
        assert suggest_category(name) == expected

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Apple Juice", "produce"),  # "apple" matches produce first
            ("Green Tea", "beverages"),
            ("Simple Syrup", "beverages"),
            ("Sparkling Water", "beverages"),
        ],
    )
    def test_beverages(self, name, expected):
        assert suggest_category(name) == expected

    def test_orange_juice_matches_produce_first(self):
        """'orange' is checked in produce before 'juice' in beverages."""
        assert suggest_category("Orange Juice") == "produce"

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("12oz Cup", "packaging"),
            ("Lid", "packaging"),
            ("Paper Bag", "packaging"),
            ("Straw", "packaging"),
        ],
    )
    def test_packaging(self, name, expected):
        assert suggest_category(name) == expected

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Jasmine Rice", "dry_goods"),
            ("Olive Oil", "dry_goods"),
            ("Balsamic Vinegar", "dry_goods"),
        ],
    )
    def test_dry_goods(self, name, expected):
        assert suggest_category(name) == expected

    def test_unknown_returns_none(self):
        assert suggest_category("Exotic Ingredient XYZ") is None

    def test_case_insensitive(self):
        assert suggest_category("WHOLE MILK") == "dairy"
        assert suggest_category("whole milk") == "dairy"
