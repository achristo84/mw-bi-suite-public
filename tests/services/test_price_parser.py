"""Tests for app/services/price_parser.py - price parsing helpers.

Only tests pure functions (_calculate_base_units, _extract_email_body, _build_parse_prompt).
The main parse_price_content function calls Claude API and is not unit-tested here.
"""
import pytest

from app.services.price_parser import (
    COUNT_UNITS,
    UNIT_CONVERSIONS,
    VOLUME_UNITS,
    WEIGHT_UNITS,
    _build_parse_prompt,
    _calculate_base_units,
    _extract_email_body,
    get_default_price_prompt,
)


# ============================================================================
# _calculate_base_units
# ============================================================================


class TestCalculateBaseUnits:
    def test_weight_conversion_lb(self):
        item = {"pack_size": "4", "unit_contents": 5, "unit_contents_unit": "lb"}
        total, base_unit = _calculate_base_units(item)
        assert base_unit == "g"
        assert abs(total - 4 * 5 * 453.592) < 0.01

    def test_weight_conversion_oz(self):
        item = {"pack_size": "12", "unit_contents": 16, "unit_contents_unit": "oz"}
        total, base_unit = _calculate_base_units(item)
        assert base_unit == "g"
        assert abs(total - 12 * 16 * 28.3495) < 0.01

    def test_weight_conversion_kg(self):
        item = {"pack_size": "1", "unit_contents": 2, "unit_contents_unit": "kg"}
        total, base_unit = _calculate_base_units(item)
        assert base_unit == "g"
        assert abs(total - 2000) < 0.01

    def test_volume_conversion_gal(self):
        item = {"pack_size": "4", "unit_contents": 1, "unit_contents_unit": "gal"}
        total, base_unit = _calculate_base_units(item)
        assert base_unit == "ml"
        assert abs(total - 4 * 3785.41) < 0.01

    def test_volume_conversion_qt(self):
        item = {"pack_size": "6", "unit_contents": 1, "unit_contents_unit": "qt"}
        total, base_unit = _calculate_base_units(item)
        assert base_unit == "ml"
        assert abs(total - 6 * 946.353) < 0.01

    def test_volume_conversion_liter(self):
        item = {"pack_size": "2", "unit_contents": 1, "unit_contents_unit": "liter"}
        total, base_unit = _calculate_base_units(item)
        assert base_unit == "ml"
        assert abs(total - 2000) < 0.01

    def test_count_conversion(self):
        item = {"pack_size": "10", "unit_contents": 1, "unit_contents_unit": "each"}
        total, base_unit = _calculate_base_units(item)
        assert base_unit == "each"
        assert total == 10

    def test_no_pack_size_defaults_to_one(self):
        item = {"unit_contents": 5, "unit_contents_unit": "lb"}
        total, base_unit = _calculate_base_units(item)
        assert base_unit == "g"
        assert abs(total - 5 * 453.592) < 0.01

    def test_missing_unit_contents_returns_none(self):
        item = {"pack_size": "4", "unit_contents_unit": "lb"}
        total, base_unit = _calculate_base_units(item)
        assert total is None
        assert base_unit is None

    def test_missing_unit_returns_none(self):
        item = {"pack_size": "4", "unit_contents": 5}
        total, base_unit = _calculate_base_units(item)
        assert total is None
        assert base_unit is None

    def test_unknown_unit_returns_none(self):
        item = {"pack_size": "4", "unit_contents": 5, "unit_contents_unit": "bushel"}
        total, base_unit = _calculate_base_units(item)
        assert total is None
        assert base_unit is None

    def test_case_insensitive_unit(self):
        item = {"pack_size": "1", "unit_contents": 1, "unit_contents_unit": "GAL"}
        total, base_unit = _calculate_base_units(item)
        assert base_unit == "ml"
        assert abs(total - 3785.41) < 0.01

    def test_unit_with_whitespace(self):
        item = {"pack_size": "1", "unit_contents": 1, "unit_contents_unit": " lb "}
        total, base_unit = _calculate_base_units(item)
        assert base_unit == "g"
        assert abs(total - 453.592) < 0.01

    def test_string_pack_size(self):
        """pack_size can come as string from JSON."""
        item = {"pack_size": "12", "unit_contents": 16, "unit_contents_unit": "oz"}
        total, base_unit = _calculate_base_units(item)
        assert total is not None
        assert total > 0

    def test_invalid_pack_size_returns_none(self):
        item = {"pack_size": "abc", "unit_contents": 5, "unit_contents_unit": "lb"}
        total, base_unit = _calculate_base_units(item)
        assert total is None
        assert base_unit is None

    def test_fl_oz_volume(self):
        item = {"pack_size": "24", "unit_contents": 12, "unit_contents_unit": "fl oz"}
        total, base_unit = _calculate_base_units(item)
        assert base_unit == "ml"
        assert abs(total - 24 * 12 * 29.5735) < 0.01


# ============================================================================
# _extract_email_body
# ============================================================================


class TestExtractEmailBody:
    def test_plain_text_passthrough(self):
        """Non-email text should pass through unchanged."""
        text = "Just some plain text with prices"
        assert _extract_email_body(text) == text

    def test_email_with_headers(self):
        """Should strip email headers and return body."""
        email = "From: vendor@example.com\nSubject: Price List\n\nHere are the prices:\nMilk $5.99"
        result = _extract_email_body(email)
        assert "Here are the prices" in result
        assert "Milk $5.99" in result

    def test_email_headers_detection(self):
        """Headers must be in first 500 chars to be detected."""
        text = "From: test@example.com\nSubject: Test\n\nBody content here"
        result = _extract_email_body(text)
        assert "Body content here" in result


# ============================================================================
# _build_parse_prompt
# ============================================================================


class TestBuildParsePrompt:
    def test_default_prompt_includes_content_type(self):
        prompt = _build_parse_prompt("image")
        assert "image" in prompt

    def test_default_prompt_includes_json_format(self):
        prompt = _build_parse_prompt("text")
        assert "JSON" in prompt
        assert "items" in prompt

    def test_ingredient_context_included(self):
        context = {"name": "Whole Milk", "category": "dairy", "base_unit": "ml"}
        prompt = _build_parse_prompt("text", ingredient_context=context)
        assert "Whole Milk" in prompt
        assert "dairy" in prompt

    def test_custom_prompt_used(self):
        custom = "Extract only dairy product prices."
        prompt = _build_parse_prompt("text", custom_prompt=custom)
        assert prompt == custom

    def test_custom_prompt_with_ingredient_context(self):
        custom = "Extract all items with pricing."
        context = {"name": "Butter", "category": "dairy", "base_unit": "g"}
        prompt = _build_parse_prompt("text", ingredient_context=context, custom_prompt=custom)
        assert "Butter" in prompt
        assert "Extract all items" in prompt

    def test_pdf_content_type(self):
        prompt = _build_parse_prompt("PDF document")
        assert "PDF document" in prompt


# ============================================================================
# get_default_price_prompt
# ============================================================================


class TestGetDefaultPricePrompt:
    def test_returns_non_empty_string(self):
        prompt = get_default_price_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_includes_json_format(self):
        prompt = get_default_price_prompt()
        assert "JSON" in prompt
        assert "items" in prompt
        assert "price_cents" in prompt


# ============================================================================
# Unit conversion constants sanity checks
# ============================================================================


class TestUnitConversions:
    def test_weight_units_map_to_positive_values(self):
        for unit in WEIGHT_UNITS:
            assert unit in UNIT_CONVERSIONS
            assert UNIT_CONVERSIONS[unit] > 0

    def test_volume_units_map_to_positive_values(self):
        for unit in VOLUME_UNITS:
            assert unit in UNIT_CONVERSIONS
            assert UNIT_CONVERSIONS[unit] > 0

    def test_count_units_map_to_positive_values(self):
        for unit in COUNT_UNITS:
            assert unit in UNIT_CONVERSIONS
            assert UNIT_CONVERSIONS[unit] > 0

    def test_pound_conversion_factor(self):
        assert abs(UNIT_CONVERSIONS["lb"] - 453.592) < 0.001

    def test_gallon_conversion_factor(self):
        assert abs(UNIT_CONVERSIONS["gal"] - 3785.41) < 0.01

    def test_no_overlap_between_unit_sets(self):
        """Weight, volume, and count unit sets should not overlap."""
        assert len(WEIGHT_UNITS & VOLUME_UNITS) == 0
        assert len(WEIGHT_UNITS & COUNT_UNITS) == 0
        assert len(VOLUME_UNITS & COUNT_UNITS) == 0
