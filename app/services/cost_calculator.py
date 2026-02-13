"""Cost calculation service for recipes and menu items."""

from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ingredient import DistIngredient, Ingredient, PriceHistory
from app.models.distributor import Distributor
from app.models.recipe import Recipe, RecipeIngredient, RecipeComponent
from app.schemas.recipe import IngredientCostBreakdown, RecipeCostBreakdown


def get_all_raw_ingredient_prices_batch(
    db: Session,
) -> dict[UUID, tuple[Decimal, str]]:
    """
    Get the best (lowest) most recent price per base unit for ALL raw ingredients.

    Returns a dict of {ingredient_id: (price_per_base_unit_cents, distributor_name)}
    This is optimized to run in a single query instead of N queries.
    """
    # Subquery for latest price per dist_ingredient
    price_subq = (
        db.query(
            PriceHistory.dist_ingredient_id,
            func.max(PriceHistory.effective_date).label("max_date"),
        )
        .group_by(PriceHistory.dist_ingredient_id)
        .subquery()
    )

    # Get all dist_ingredients with latest prices in one query
    results = (
        db.query(
            DistIngredient.ingredient_id,
            Distributor.name.label("distributor_name"),
            PriceHistory.price_cents,
            DistIngredient.grams_per_unit,
        )
        .join(Distributor, DistIngredient.distributor_id == Distributor.id)
        .join(
            price_subq,
            DistIngredient.id == price_subq.c.dist_ingredient_id,
        )
        .join(
            PriceHistory,
            (DistIngredient.id == PriceHistory.dist_ingredient_id)
            & (PriceHistory.effective_date == price_subq.c.max_date),
        )
        .filter(DistIngredient.ingredient_id != None)
        .filter(DistIngredient.is_active == True)
        .filter(DistIngredient.grams_per_unit != None)
        .filter(DistIngredient.grams_per_unit > 0)
        .all()
    )

    # Group by ingredient_id and find lowest price per base unit
    prices_by_ingredient: dict[UUID, list[tuple[Decimal, str]]] = {}
    for row in results:
        ingredient_id = row.ingredient_id
        price_per_base = Decimal(str(row.price_cents)) / Decimal(str(row.grams_per_unit))

        if ingredient_id not in prices_by_ingredient:
            prices_by_ingredient[ingredient_id] = []
        prices_by_ingredient[ingredient_id].append((price_per_base, row.distributor_name))

    # Return the best (lowest) price for each ingredient
    best_prices: dict[UUID, tuple[Decimal, str]] = {}
    for ing_id, price_list in prices_by_ingredient.items():
        # Sort by price and take lowest
        price_list.sort(key=lambda x: x[0])
        best_prices[ing_id] = price_list[0]

    return best_prices


def get_ingredient_best_price(
    db: Session,
    ingredient_id: UUID,
    pricing_mode: Literal["recent", "average"] = "recent",
    average_days: int = 30,
    _calculating_recipes: set[UUID] | None = None,
) -> tuple[Decimal | None, str | None]:
    """
    Get the best price per base unit for an ingredient.

    For component ingredients (with source_recipe_id), calculates price from recipe cost.
    For raw ingredients, returns the best distributor price.

    Returns:
        Tuple of (price_per_base_unit_cents, source_name) or (None, None) if no price.
        source_name is distributor name for raw, "From Recipe" for components.
    """
    # Check if this is a component ingredient with a source recipe
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        return None, None

    if ingredient.source_recipe_id:
        return _get_component_price(
            db, ingredient, pricing_mode, average_days, _calculating_recipes
        )

    # Raw ingredient - get from distributor prices
    if pricing_mode == "recent":
        return _get_recent_best_price(db, ingredient_id)
    else:
        return _get_average_best_price(db, ingredient_id, average_days)


def _get_component_price(
    db: Session,
    ingredient: Ingredient,
    pricing_mode: Literal["recent", "average"] = "recent",
    average_days: int = 30,
    _calculating_recipes: set[UUID] | None = None,
) -> tuple[Decimal | None, str | None]:
    """
    Get price for a component ingredient from its source recipe.

    Price per base unit = recipe_total_cost / (yield_quantity * base_units_per_yield)

    For example, Cold Brew recipe yields 1000ml, costs $2.91
    Cold Brew ingredient (base_unit=ml) price = $2.91 / 1000 = $0.00291/ml
    """
    # Cycle detection - tracks which component ingredient recipes we're calculating
    # to prevent A→B→A loops where A and B are both component ingredients
    if _calculating_recipes is None:
        _calculating_recipes = set()

    if ingredient.source_recipe_id in _calculating_recipes:
        # Circular reference - can't calculate
        return None, None

    # Get the source recipe
    recipe = (
        db.query(Recipe)
        .filter(Recipe.id == ingredient.source_recipe_id)
        .first()
    )

    if not recipe:
        return None, None

    # Add to tracking set AFTER we've gotten the recipe but BEFORE recursing
    # This set is for ingredient-level cycle detection, not recipe sub-component detection
    _calculating_recipes.add(ingredient.source_recipe_id)

    # Calculate recipe cost
    # Pass None for _visited_recipes - let calculate_recipe_cost manage its own cycle detection
    # for sub-recipes (components). Our _calculating_recipes handles ingredient-level cycles.
    try:
        cost_breakdown = calculate_recipe_cost(
            db,
            recipe.id,
            pricing_mode,
            average_days,
            None,  # Fresh cycle detection for sub-recipes
        )
    except ValueError:
        # Circular reference or other error
        return None, None

    if cost_breakdown.total_cost_cents == 0 and cost_breakdown.has_unpriced_ingredients:
        # Recipe has no priced ingredients
        return None, None

    # Calculate price per gram
    # Priority: use yield_weight_grams if set (most accurate for cooked items)
    # Fallback: use yield_quantity if yield_unit is 'g' or 'ml'

    if recipe.yield_weight_grams and recipe.yield_weight_grams > 0:
        # Use explicit yield weight (accounts for evaporation, etc.)
        price_per_base = Decimal(str(cost_breakdown.total_cost_cents)) / Decimal(str(recipe.yield_weight_grams))
        return price_per_base, f"Recipe: {recipe.name}"

    # Fallback: use yield_quantity if it's in base units
    if recipe.yield_unit in ('g', 'ml', 'each'):
        if recipe.yield_quantity and recipe.yield_quantity > 0:
            price_per_base = Decimal(str(cost_breakdown.total_cost_cents)) / Decimal(str(recipe.yield_quantity))
            return price_per_base, f"Recipe: {recipe.name}"

    # Can't calculate - yield is in non-base units without yield_weight_grams
    return None, None


def _get_recent_best_price(
    db: Session,
    ingredient_id: UUID,
) -> tuple[Decimal | None, str | None]:
    """Get the best (lowest) most recent price per base unit."""

    # Subquery for latest price per dist_ingredient
    price_subq = (
        db.query(
            PriceHistory.dist_ingredient_id,
            func.max(PriceHistory.effective_date).label("max_date"),
        )
        .group_by(PriceHistory.dist_ingredient_id)
        .subquery()
    )

    # Get all dist_ingredients for this ingredient with latest prices
    results = (
        db.query(
            DistIngredient,
            Distributor.name.label("distributor_name"),
            PriceHistory.price_cents,
        )
        .join(Distributor, DistIngredient.distributor_id == Distributor.id)
        .join(
            price_subq,
            DistIngredient.id == price_subq.c.dist_ingredient_id,
        )
        .join(
            PriceHistory,
            (DistIngredient.id == PriceHistory.dist_ingredient_id)
            & (PriceHistory.effective_date == price_subq.c.max_date),
        )
        .filter(DistIngredient.ingredient_id == ingredient_id)
        .filter(DistIngredient.is_active == True)
        .filter(DistIngredient.grams_per_unit != None)
        .filter(DistIngredient.grams_per_unit > 0)
        .all()
    )

    if not results:
        return None, None

    # Calculate price per base unit for each and find the best
    best_price = None
    best_distributor = None

    for di, dist_name, price_cents in results:
        if price_cents is None or di.grams_per_unit is None:
            continue

        price_per_base = Decimal(str(price_cents)) / Decimal(str(di.grams_per_unit))

        if best_price is None or price_per_base < best_price:
            best_price = price_per_base
            best_distributor = dist_name

    return best_price, best_distributor


def _get_average_best_price(
    db: Session,
    ingredient_id: UUID,
    days: int = 30,
) -> tuple[Decimal | None, str | None]:
    """Get the average price per base unit over the last N days."""
    from datetime import date, timedelta

    cutoff_date = date.today() - timedelta(days=days)

    # Get all prices in the date range grouped by dist_ingredient
    results = (
        db.query(
            DistIngredient,
            Distributor.name.label("distributor_name"),
            func.avg(PriceHistory.price_cents).label("avg_price"),
        )
        .join(Distributor, DistIngredient.distributor_id == Distributor.id)
        .join(PriceHistory, DistIngredient.id == PriceHistory.dist_ingredient_id)
        .filter(DistIngredient.ingredient_id == ingredient_id)
        .filter(DistIngredient.is_active == True)
        .filter(DistIngredient.grams_per_unit != None)
        .filter(DistIngredient.grams_per_unit > 0)
        .filter(PriceHistory.effective_date >= cutoff_date)
        .group_by(DistIngredient.id, Distributor.name)
        .all()
    )

    if not results:
        # Fall back to most recent if no prices in range
        return _get_recent_best_price(db, ingredient_id)

    # Calculate price per base unit for each and find the best
    best_price = None
    best_distributor = None

    for di, dist_name, avg_price in results:
        if avg_price is None or di.grams_per_unit is None:
            continue

        price_per_base = Decimal(str(avg_price)) / Decimal(str(di.grams_per_unit))

        if best_price is None or price_per_base < best_price:
            best_price = price_per_base
            best_distributor = dist_name

    return best_price, best_distributor


def calculate_recipe_cost(
    db: Session,
    recipe_id: UUID,
    pricing_mode: Literal["recent", "average"] = "recent",
    average_days: int = 30,
    _visited_recipes: set[UUID] | None = None,
) -> RecipeCostBreakdown:
    """
    Calculate the full cost breakdown for a recipe.

    Handles sub-recipes (components) recursively with cycle detection.
    """
    # Cycle detection for sub-recipes
    if _visited_recipes is None:
        _visited_recipes = set()

    if recipe_id in _visited_recipes:
        raise ValueError(f"Circular recipe reference detected for recipe {recipe_id}")

    _visited_recipes.add(recipe_id)

    # Get recipe with ingredients
    recipe = (
        db.query(Recipe)
        .filter(Recipe.id == recipe_id)
        .first()
    )

    if not recipe:
        raise ValueError(f"Recipe {recipe_id} not found")

    # Get recipe ingredients with ingredient details
    recipe_ingredients = (
        db.query(RecipeIngredient, Ingredient)
        .join(Ingredient, RecipeIngredient.ingredient_id == Ingredient.id)
        .filter(RecipeIngredient.recipe_id == recipe_id)
        .all()
    )

    # Calculate ingredient costs
    ingredient_breakdowns = []
    total_ingredient_cost = 0
    unpriced_count = 0

    for ri, ingredient in recipe_ingredients:
        price_per_base, distributor_name = get_ingredient_best_price(
            db, ingredient.id, pricing_mode, average_days
        )

        cost_cents = None
        has_price = price_per_base is not None

        if has_price:
            # quantity_grams is in base units (g, ml, or each)
            cost_cents = int(Decimal(str(ri.quantity_grams)) * price_per_base)
            total_ingredient_cost += cost_cents
        else:
            unpriced_count += 1

        ingredient_breakdowns.append(IngredientCostBreakdown(
            ingredient_id=ingredient.id,
            ingredient_name=ingredient.name,
            ingredient_base_unit=ingredient.base_unit,
            quantity_grams=ri.quantity_grams,
            price_per_base_unit_cents=price_per_base,
            cost_cents=cost_cents,
            distributor_name=distributor_name,
            has_price=has_price,
        ))

    # Get recipe components (sub-recipes)
    components = (
        db.query(RecipeComponent)
        .filter(RecipeComponent.recipe_id == recipe_id)
        .all()
    )

    # Calculate component costs recursively
    component_breakdowns = []
    total_component_cost = 0

    for component in components:
        component_cost = calculate_recipe_cost(
            db,
            component.component_recipe_id,
            pricing_mode,
            average_days,
            _visited_recipes.copy(),  # Copy to allow parallel branches
        )

        # Scale by quantity (portion of component recipe needed)
        # component.quantity is how many "yield units" of the component we need
        # cost_per_unit_cents is cost for 1 yield unit
        scaled_cost = int(Decimal(str(component.quantity)) * component_cost.cost_per_unit_cents)

        # Update the component breakdown with scaled values
        component_cost.total_cost_cents = scaled_cost

        component_breakdowns.append(component_cost)
        total_component_cost += scaled_cost

        # Propagate unpriced count
        if component_cost.has_unpriced_ingredients:
            unpriced_count += component_cost.unpriced_count

    # Calculate totals
    total_cost = total_ingredient_cost + total_component_cost

    # Cost per yield unit
    cost_per_unit = Decimal("0")
    if recipe.yield_quantity and recipe.yield_quantity > 0:
        cost_per_unit = Decimal(str(total_cost)) / Decimal(str(recipe.yield_quantity))

    # Cost per gram (for component pricing)
    cost_per_gram = None
    if recipe.yield_weight_grams and recipe.yield_weight_grams > 0:
        # Use explicit yield weight
        cost_per_gram = Decimal(str(total_cost)) / Decimal(str(recipe.yield_weight_grams))
    elif recipe.yield_unit in ('g', 'ml', 'each') and recipe.yield_quantity and recipe.yield_quantity > 0:
        # Yield is in base units
        cost_per_gram = cost_per_unit

    return RecipeCostBreakdown(
        recipe_id=recipe.id,
        recipe_name=recipe.name,
        yield_quantity=recipe.yield_quantity,
        yield_unit=recipe.yield_unit,
        yield_weight_grams=recipe.yield_weight_grams,
        ingredients=ingredient_breakdowns,
        components=component_breakdowns,
        total_ingredient_cost_cents=total_ingredient_cost,
        total_component_cost_cents=total_component_cost,
        total_cost_cents=total_cost,
        cost_per_unit_cents=cost_per_unit,
        cost_per_gram_cents=cost_per_gram,
        has_unpriced_ingredients=unpriced_count > 0,
        unpriced_count=unpriced_count,
    )
