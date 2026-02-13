"""Tests for app/services/cost_calculator.py - recipe cost calculation."""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.models.ingredient import DistIngredient, Ingredient, PriceHistory
from app.models.recipe import Recipe, RecipeComponent, RecipeIngredient
from app.services.cost_calculator import (
    calculate_recipe_cost,
    get_all_raw_ingredient_prices_batch,
    get_ingredient_best_price,
)


# ============================================================================
# get_ingredient_best_price - raw ingredients
# ============================================================================


class TestGetIngredientBestPriceRaw:
    """Test best price lookup for raw ingredients (not component)."""

    def test_single_distributor_price(
        self, db, distributor_factory, ingredient_factory,
        dist_ingredient_factory, price_factory,
    ):
        dist = distributor_factory(name="Supplier A")
        ing = ingredient_factory(name="Butter", base_unit="g")
        di = dist_ingredient_factory(
            distributor=dist, ingredient=ing,
            grams_per_unit=Decimal("453.592"),
        )
        price_factory(dist_ingredient=di, price_cents=500)

        price, source = get_ingredient_best_price(db, ing.id)
        assert price is not None
        assert source == "Supplier A"
        expected = Decimal("500") / Decimal("453.592")
        assert abs(price - expected) < Decimal("0.001")

    def test_picks_lowest_price_across_distributors(
        self, db, distributor_factory, ingredient_factory,
        dist_ingredient_factory, price_factory,
    ):
        dist_a = distributor_factory(name="Expensive Supplier")
        dist_b = distributor_factory(name="Cheap Supplier")
        ing = ingredient_factory(name="Flour", base_unit="g")

        di_a = dist_ingredient_factory(
            distributor=dist_a, ingredient=ing, sku="A-001",
            grams_per_unit=Decimal("1000"),
        )
        di_b = dist_ingredient_factory(
            distributor=dist_b, ingredient=ing, sku="B-001",
            grams_per_unit=Decimal("1000"),
        )

        price_factory(dist_ingredient=di_a, price_cents=2000)
        price_factory(dist_ingredient=di_b, price_cents=1500)

        price, source = get_ingredient_best_price(db, ing.id)
        assert source == "Cheap Supplier"
        expected = Decimal("1500") / Decimal("1000")
        assert abs(price - expected) < Decimal("0.001")

    def test_no_prices_returns_none(self, db, ingredient_factory):
        ing = ingredient_factory(name="No Prices")
        price, source = get_ingredient_best_price(db, ing.id)
        assert price is None
        assert source is None

    def test_ingredient_not_found_returns_none(self, db):
        fake_id = uuid.uuid4()
        price, source = get_ingredient_best_price(db, fake_id)
        assert price is None
        assert source is None

    def test_inactive_dist_ingredient_excluded(
        self, db, distributor_factory, ingredient_factory,
        dist_ingredient_factory, price_factory,
    ):
        dist = distributor_factory(name="Supplier")
        ing = ingredient_factory(name="Inactive Item")
        di = dist_ingredient_factory(
            distributor=dist, ingredient=ing,
            grams_per_unit=Decimal("100"), is_active=False,
        )
        price_factory(dist_ingredient=di, price_cents=500)

        price, source = get_ingredient_best_price(db, ing.id)
        assert price is None

    def test_zero_grams_per_unit_excluded(
        self, db, distributor_factory, ingredient_factory,
        dist_ingredient_factory, price_factory,
    ):
        dist = distributor_factory(name="Supplier")
        ing = ingredient_factory(name="Zero GPU")
        di = dist_ingredient_factory(
            distributor=dist, ingredient=ing,
            grams_per_unit=Decimal("0"),
        )
        price_factory(dist_ingredient=di, price_cents=500)

        price, source = get_ingredient_best_price(db, ing.id)
        assert price is None

    def test_uses_most_recent_price(
        self, db, distributor_factory, ingredient_factory,
        dist_ingredient_factory, price_factory,
    ):
        dist = distributor_factory(name="Supplier")
        ing = ingredient_factory(name="Recent Price Test")
        di = dist_ingredient_factory(
            distributor=dist, ingredient=ing,
            grams_per_unit=Decimal("1000"),
        )

        # Older price
        price_factory(
            dist_ingredient=di, price_cents=2000,
            effective_date=date.today() - timedelta(days=30),
        )
        # Newer price
        price_factory(
            dist_ingredient=di, price_cents=1800,
            effective_date=date.today(),
        )

        price, source = get_ingredient_best_price(db, ing.id)
        expected = Decimal("1800") / Decimal("1000")
        assert abs(price - expected) < Decimal("0.001")


# ============================================================================
# get_ingredient_best_price - component ingredients
# ============================================================================


class TestGetIngredientBestPriceComponent:
    """Test price lookup for component ingredients (derived from recipes)."""

    def test_component_price_from_recipe(
        self, db, distributor_factory, ingredient_factory,
        dist_ingredient_factory, price_factory,
        recipe_factory, recipe_ingredient_factory,
    ):
        """Component ingredient price = recipe cost / yield weight."""
        # Set up a raw ingredient with a known price
        dist = distributor_factory(name="Supplier")
        raw_ing = ingredient_factory(name="Sugar", base_unit="g")
        di = dist_ingredient_factory(
            distributor=dist, ingredient=raw_ing,
            grams_per_unit=Decimal("1000"),
        )
        price_factory(dist_ingredient=di, price_cents=500)  # 500 cents per 1000g

        # Create a recipe using that ingredient
        recipe = recipe_factory(
            name="Simple Syrup",
            yield_quantity=1000,
            yield_unit="ml",
            yield_weight_grams=Decimal("1200"),
        )
        recipe_ingredient_factory(recipe=recipe, ingredient=raw_ing, quantity_grams=500)

        # Create component ingredient linked to recipe
        component_ing = ingredient_factory(
            name="Simple Syrup",
            base_unit="ml",
            ingredient_type="component",
            source_recipe_id=recipe.id,
        )

        price, source = get_ingredient_best_price(db, component_ing.id)
        assert price is not None
        assert "Recipe" in source

        # Recipe cost: 500g of sugar at 0.5 cents/g = 250 cents
        # Price per gram: 250 / 1200 = ~0.2083 cents/g
        recipe_cost = Decimal("500") * Decimal("500") / Decimal("1000")
        expected = recipe_cost / Decimal("1200")
        assert abs(price - expected) < Decimal("0.01")

    def test_component_with_yield_unit_in_base_units(
        self, db, distributor_factory, ingredient_factory,
        dist_ingredient_factory, price_factory,
        recipe_factory, recipe_ingredient_factory,
    ):
        """Component ingredient with yield_unit in g (no yield_weight_grams needed)."""
        dist = distributor_factory(name="Supplier")
        raw_ing = ingredient_factory(name="Cocoa", base_unit="g")
        di = dist_ingredient_factory(
            distributor=dist, ingredient=raw_ing,
            grams_per_unit=Decimal("500"),
        )
        price_factory(dist_ingredient=di, price_cents=800)

        recipe = recipe_factory(
            name="Chocolate Sauce",
            yield_quantity=500,
            yield_unit="g",
        )
        recipe_ingredient_factory(recipe=recipe, ingredient=raw_ing, quantity_grams=200)

        component_ing = ingredient_factory(
            name="Chocolate Sauce",
            base_unit="g",
            ingredient_type="component",
            source_recipe_id=recipe.id,
        )

        price, source = get_ingredient_best_price(db, component_ing.id)
        assert price is not None

        # Recipe cost: 200g of cocoa at (800/500) = 1.6 cents/g = 320 cents
        # Price per g: 320 / 500 = 0.64 cents/g
        expected = (Decimal("200") * Decimal("800") / Decimal("500")) / Decimal("500")
        assert abs(price - expected) < Decimal("0.01")

    def test_circular_component_returns_zero_for_empty_recipe(
        self, db, ingredient_factory, recipe_factory,
    ):
        """Component from an empty recipe returns zero price (no ingredients to cost)."""
        recipe = recipe_factory(name="Empty Recipe", yield_quantity=100, yield_unit="g")

        component_ing = ingredient_factory(
            name="Empty Component",
            base_unit="g",
            ingredient_type="component",
            source_recipe_id=recipe.id,
        )

        # Empty recipe: total_cost=0, no unpriced ingredients
        # So price = 0 / 100 = 0 (not None)
        price, source = get_ingredient_best_price(db, component_ing.id)
        assert price == Decimal("0")
        assert "Recipe" in source


# ============================================================================
# get_all_raw_ingredient_prices_batch
# ============================================================================


class TestGetAllRawIngredientPricesBatch:
    def test_returns_best_prices_for_multiple_ingredients(
        self, db, distributor_factory, ingredient_factory,
        dist_ingredient_factory, price_factory,
    ):
        dist = distributor_factory(name="Supplier")

        ing_a = ingredient_factory(name="Ingredient A", base_unit="g")
        di_a = dist_ingredient_factory(
            distributor=dist, ingredient=ing_a, sku="A-001",
            grams_per_unit=Decimal("1000"),
        )
        price_factory(dist_ingredient=di_a, price_cents=500)

        ing_b = ingredient_factory(name="Ingredient B", base_unit="ml")
        di_b = dist_ingredient_factory(
            distributor=dist, ingredient=ing_b, sku="B-001",
            grams_per_unit=Decimal("2000"),
        )
        price_factory(dist_ingredient=di_b, price_cents=800)

        result = get_all_raw_ingredient_prices_batch(db)

        assert ing_a.id in result
        assert ing_b.id in result

        price_a, name_a = result[ing_a.id]
        assert name_a == "Supplier"
        assert abs(price_a - Decimal("0.5")) < Decimal("0.001")

    def test_empty_db_returns_empty(self, db):
        result = get_all_raw_ingredient_prices_batch(db)
        assert result == {}


# ============================================================================
# calculate_recipe_cost
# ============================================================================


class TestCalculateRecipeCost:
    def test_simple_recipe_cost(
        self, db, distributor_factory, ingredient_factory,
        dist_ingredient_factory, price_factory,
        recipe_factory, recipe_ingredient_factory,
    ):
        """Recipe with one ingredient, straightforward cost."""
        dist = distributor_factory(name="Supplier")
        ing = ingredient_factory(name="Butter", base_unit="g")
        di = dist_ingredient_factory(
            distributor=dist, ingredient=ing,
            grams_per_unit=Decimal("453.592"),
        )
        price_factory(dist_ingredient=di, price_cents=599)  # $5.99 per lb

        recipe = recipe_factory(
            name="Butter Sauce",
            yield_quantity=10,
            yield_unit="servings",
        )
        recipe_ingredient_factory(recipe=recipe, ingredient=ing, quantity_grams=227)

        breakdown = calculate_recipe_cost(db, recipe.id)

        assert breakdown.recipe_name == "Butter Sauce"
        assert breakdown.yield_quantity == Decimal("10")
        assert len(breakdown.ingredients) == 1
        assert breakdown.ingredients[0].has_price is True
        assert breakdown.total_cost_cents > 0
        assert breakdown.has_unpriced_ingredients is False
        assert breakdown.unpriced_count == 0

        # Verify cost: 227g * (599 / 453.592) cents/g
        price_per_g = Decimal("599") / Decimal("453.592")
        expected_cost = int(Decimal("227") * price_per_g)
        assert breakdown.total_cost_cents == expected_cost

    def test_recipe_with_unpriced_ingredient(
        self, db, ingredient_factory,
        recipe_factory, recipe_ingredient_factory,
    ):
        """Recipe with an ingredient that has no price data."""
        ing = ingredient_factory(name="Rare Spice", base_unit="g")
        recipe = recipe_factory(name="Spiced Dish", yield_quantity=4, yield_unit="servings")
        recipe_ingredient_factory(recipe=recipe, ingredient=ing, quantity_grams=10)

        breakdown = calculate_recipe_cost(db, recipe.id)

        assert breakdown.has_unpriced_ingredients is True
        assert breakdown.unpriced_count == 1
        assert breakdown.ingredients[0].has_price is False
        assert breakdown.ingredients[0].cost_cents is None

    def test_recipe_not_found_raises(self, db):
        fake_id = uuid.uuid4()
        with pytest.raises(ValueError, match="not found"):
            calculate_recipe_cost(db, fake_id)

    def test_cost_per_unit(
        self, db, distributor_factory, ingredient_factory,
        dist_ingredient_factory, price_factory,
        recipe_factory, recipe_ingredient_factory,
    ):
        """cost_per_unit_cents = total_cost / yield_quantity."""
        dist = distributor_factory(name="Supplier")
        ing = ingredient_factory(name="Flour", base_unit="g")
        di = dist_ingredient_factory(
            distributor=dist, ingredient=ing,
            grams_per_unit=Decimal("1000"),
        )
        price_factory(dist_ingredient=di, price_cents=300)

        recipe = recipe_factory(
            name="Bread",
            yield_quantity=4,
            yield_unit="loaves",
        )
        recipe_ingredient_factory(recipe=recipe, ingredient=ing, quantity_grams=1000)

        breakdown = calculate_recipe_cost(db, recipe.id)

        # Total cost = 1000g * (300/1000) = 300 cents
        assert breakdown.total_cost_cents == 300
        # Cost per loaf = 300 / 4 = 75
        assert breakdown.cost_per_unit_cents == Decimal("75")

    def test_cost_per_gram_with_yield_weight(
        self, db, distributor_factory, ingredient_factory,
        dist_ingredient_factory, price_factory,
        recipe_factory, recipe_ingredient_factory,
    ):
        """cost_per_gram_cents calculated from yield_weight_grams."""
        dist = distributor_factory(name="Supplier")
        ing = ingredient_factory(name="Sugar", base_unit="g")
        di = dist_ingredient_factory(
            distributor=dist, ingredient=ing,
            grams_per_unit=Decimal("1000"),
        )
        price_factory(dist_ingredient=di, price_cents=200)

        recipe = recipe_factory(
            name="Caramel",
            yield_quantity=500,
            yield_unit="ml",
            yield_weight_grams=Decimal("600"),
        )
        recipe_ingredient_factory(recipe=recipe, ingredient=ing, quantity_grams=400)

        breakdown = calculate_recipe_cost(db, recipe.id)

        # Total cost = 400 * 200/1000 = 80 cents
        assert breakdown.total_cost_cents == 80
        # Cost per gram = 80 / 600 grams
        expected_cpg = Decimal("80") / Decimal("600")
        assert abs(breakdown.cost_per_gram_cents - expected_cpg) < Decimal("0.001")

    def test_cost_per_gram_with_base_yield_unit(
        self, db, distributor_factory, ingredient_factory,
        dist_ingredient_factory, price_factory,
        recipe_factory, recipe_ingredient_factory,
    ):
        """cost_per_gram_cents when yield_unit is a base unit (g, ml, each)."""
        dist = distributor_factory(name="Supplier")
        ing = ingredient_factory(name="Oats", base_unit="g")
        di = dist_ingredient_factory(
            distributor=dist, ingredient=ing,
            grams_per_unit=Decimal("1000"),
        )
        price_factory(dist_ingredient=di, price_cents=400)

        recipe = recipe_factory(
            name="Granola",
            yield_quantity=2000,
            yield_unit="g",
        )
        recipe_ingredient_factory(recipe=recipe, ingredient=ing, quantity_grams=1500)

        breakdown = calculate_recipe_cost(db, recipe.id)

        # Total cost = 1500 * 400/1000 = 600 cents
        assert breakdown.total_cost_cents == 600
        # cost_per_gram = cost_per_unit when yield is in base units
        expected = Decimal("600") / Decimal("2000")
        assert abs(breakdown.cost_per_gram_cents - expected) < Decimal("0.001")

    def test_circular_recipe_raises(self, db, recipe_factory):
        """Circular sub-recipe reference should raise ValueError."""
        recipe = recipe_factory(name="Self Referencing")

        # Manually create a component that references itself
        component = RecipeComponent(
            id=uuid.uuid4(),
            recipe_id=recipe.id,
            component_recipe_id=recipe.id,
            quantity=1,
        )
        db.add(component)
        db.flush()

        with pytest.raises(ValueError, match="Circular"):
            calculate_recipe_cost(db, recipe.id)

    def test_multiple_ingredients(
        self, db, distributor_factory, ingredient_factory,
        dist_ingredient_factory, price_factory,
        recipe_factory, recipe_ingredient_factory,
    ):
        """Recipe with multiple ingredients sums costs correctly."""
        dist = distributor_factory(name="Supplier")

        butter = ingredient_factory(name="Butter", base_unit="g")
        di_butter = dist_ingredient_factory(
            distributor=dist, ingredient=butter, sku="B-001",
            grams_per_unit=Decimal("453.592"),
        )
        price_factory(dist_ingredient=di_butter, price_cents=599)

        flour = ingredient_factory(name="AP Flour", base_unit="g")
        di_flour = dist_ingredient_factory(
            distributor=dist, ingredient=flour, sku="F-001",
            grams_per_unit=Decimal("2267.96"),  # 5lb bag
        )
        price_factory(dist_ingredient=di_flour, price_cents=350)

        recipe = recipe_factory(name="Pie Crust", yield_quantity=2, yield_unit="crusts")
        recipe_ingredient_factory(recipe=recipe, ingredient=butter, quantity_grams=227)
        recipe_ingredient_factory(recipe=recipe, ingredient=flour, quantity_grams=340)

        breakdown = calculate_recipe_cost(db, recipe.id)

        assert len(breakdown.ingredients) == 2
        assert breakdown.has_unpriced_ingredients is False

        # Verify individual costs
        butter_cost = int(Decimal("227") * Decimal("599") / Decimal("453.592"))
        flour_cost = int(Decimal("340") * Decimal("350") / Decimal("2267.96"))
        assert breakdown.total_cost_cents == butter_cost + flour_cost
