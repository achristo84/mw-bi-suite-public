"""Cost calculation service for recipes and menu items."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.ingredient import DistIngredient, Ingredient, PriceHistory
from app.models.distributor import Distributor
from app.models.recipe import Recipe, RecipeIngredient, RecipeComponent, MenuItem, MenuItemPackaging
from app.schemas.recipe import (
    IngredientCostBreakdown,
    RecipeCostBreakdown,
    MenuItemCostBreakdown,
    PackagingCostItem,
    MenuItemAnalysis,
    MenuAnalyzerResponse,
    MenuAnalyzerSummary,
    CategorySummary,
    PriceMoverResponse,
    IngredientMover,
    ItemMover,
    AffectedMenuItem,
)


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


# ============================================================================
# Menu Item Cost Calculation
# ============================================================================


def _get_margin_status(food_cost_percent: Decimal) -> str:
    """Return margin health status based on food cost percentage."""
    if food_cost_percent < 30:
        return "healthy"
    elif food_cost_percent <= 35:
        return "warning"
    else:
        return "danger"


def calculate_menu_item_cost(
    db: Session,
    menu_item_id: UUID,
    pricing_mode: Literal["recent", "average"] = "recent",
    average_days: int = 30,
) -> MenuItemCostBreakdown:
    """
    Calculate cost breakdown for a single menu item.

    Combines recipe cost (scaled by portion_of_recipe) with packaging costs.
    """
    menu_item = (
        db.query(MenuItem)
        .options(
            joinedload(MenuItem.recipe),
            joinedload(MenuItem.packaging).joinedload(MenuItemPackaging.ingredient),
        )
        .filter(MenuItem.id == menu_item_id)
        .first()
    )

    if not menu_item:
        raise ValueError(f"Menu item {menu_item_id} not found")

    # Calculate recipe cost
    recipe_cost_cents = 0
    recipe_cost_breakdown = None
    has_unpriced = False

    if menu_item.recipe_id:
        try:
            recipe_breakdown = calculate_recipe_cost(
                db, menu_item.recipe_id, pricing_mode, average_days
            )
            recipe_cost_breakdown = recipe_breakdown
            # Scale by portion_of_recipe
            recipe_cost_cents = int(
                Decimal(str(recipe_breakdown.total_cost_cents))
                * Decimal(str(menu_item.portion_of_recipe))
            )
            has_unpriced = recipe_breakdown.has_unpriced_ingredients
        except ValueError:
            pass

    # Calculate packaging cost
    packaging_cost_cents = 0
    packaging_breakdown = []

    for pkg in menu_item.packaging:
        price_per_base, _ = get_ingredient_best_price(
            db, pkg.ingredient_id, pricing_mode, average_days
        )

        pkg_cost = None
        pkg_has_price = price_per_base is not None

        if pkg_has_price:
            # cost = price_per_base_unit * quantity * usage_rate
            pkg_cost = int(
                price_per_base
                * Decimal(str(pkg.quantity))
                * Decimal(str(pkg.usage_rate))
            )
            packaging_cost_cents += pkg_cost

        packaging_breakdown.append(PackagingCostItem(
            ingredient_id=pkg.ingredient_id,
            ingredient_name=pkg.ingredient.name if pkg.ingredient else "Unknown",
            quantity=pkg.quantity,
            usage_rate=pkg.usage_rate,
            price_per_unit_cents=price_per_base,
            cost_cents=pkg_cost,
            has_price=pkg_has_price,
        ))

    total_cost = recipe_cost_cents + packaging_cost_cents
    gross_margin = menu_item.menu_price_cents - total_cost

    food_cost_pct = Decimal("0")
    if menu_item.menu_price_cents > 0:
        food_cost_pct = (
            Decimal(str(total_cost)) / Decimal(str(menu_item.menu_price_cents)) * 100
        )

    return MenuItemCostBreakdown(
        menu_item_id=menu_item.id,
        name=menu_item.name,
        menu_price_cents=menu_item.menu_price_cents,
        recipe_cost_cents=recipe_cost_cents,
        packaging_cost_cents=packaging_cost_cents,
        total_cost_cents=total_cost,
        gross_margin_cents=gross_margin,
        food_cost_percent=food_cost_pct.quantize(Decimal("0.1")),
        recipe_cost_breakdown=recipe_cost_breakdown,
        packaging_breakdown=packaging_breakdown,
        has_unpriced_ingredients=has_unpriced,
        margin_status=_get_margin_status(food_cost_pct),
    )


def calculate_all_menu_item_costs(
    db: Session,
    pricing_mode: Literal["recent", "average"] = "recent",
    average_days: int = 30,
    category: str | None = None,
    active_only: bool = True,
) -> MenuAnalyzerResponse:
    """
    Calculate costs for all menu items and return analyzer response with summary.
    """
    query = db.query(MenuItem).options(
        joinedload(MenuItem.recipe),
        joinedload(MenuItem.packaging).joinedload(MenuItemPackaging.ingredient),
    )
    if active_only:
        query = query.filter(MenuItem.is_active == True)
    if category:
        query = query.filter(MenuItem.category == category)

    menu_items = query.order_by(MenuItem.category, MenuItem.name).all()

    # Pre-fetch all raw ingredient prices in batch for efficiency
    batch_prices = get_all_raw_ingredient_prices_batch(db)

    items: list[MenuItemAnalysis] = []
    total_food_cost = Decimal("0")
    healthy_count = 0
    warning_count = 0
    danger_count = 0
    by_category: dict[str, dict] = {}

    for mi in menu_items:
        # Calculate recipe cost
        recipe_cost_cents = 0
        has_unpriced = False
        recipe_name = mi.recipe.name if mi.recipe else None

        if mi.recipe_id:
            try:
                recipe_breakdown = calculate_recipe_cost(
                    db, mi.recipe_id, pricing_mode, average_days
                )
                recipe_cost_cents = int(
                    Decimal(str(recipe_breakdown.total_cost_cents))
                    * Decimal(str(mi.portion_of_recipe))
                )
                has_unpriced = recipe_breakdown.has_unpriced_ingredients
            except ValueError:
                pass

        # Packaging cost
        packaging_cost = 0
        for pkg in mi.packaging:
            price_per_base, _ = get_ingredient_best_price(
                db, pkg.ingredient_id, pricing_mode, average_days
            )
            if price_per_base is not None:
                packaging_cost += int(
                    price_per_base
                    * Decimal(str(pkg.quantity))
                    * Decimal(str(pkg.usage_rate))
                )

        total_cost = recipe_cost_cents + packaging_cost
        gross_margin = mi.menu_price_cents - total_cost

        food_cost_pct = Decimal("0")
        if mi.menu_price_cents > 0:
            food_cost_pct = (
                Decimal(str(total_cost)) / Decimal(str(mi.menu_price_cents)) * 100
            )

        margin_status = _get_margin_status(food_cost_pct)

        items.append(MenuItemAnalysis(
            id=mi.id,
            name=mi.name,
            category=mi.category,
            menu_price_cents=mi.menu_price_cents,
            total_cost_cents=total_cost,
            food_cost_percent=food_cost_pct.quantize(Decimal("0.1")),
            gross_margin_cents=gross_margin,
            margin_status=margin_status,
            recipe_name=recipe_name,
            portion_of_recipe=mi.portion_of_recipe,
            has_unpriced_ingredients=has_unpriced,
        ))

        # Accumulate summary
        total_food_cost += food_cost_pct
        if margin_status == "healthy":
            healthy_count += 1
        elif margin_status == "warning":
            warning_count += 1
        else:
            danger_count += 1

        # Per-category
        cat = mi.category or "uncategorized"
        if cat not in by_category:
            by_category[cat] = {
                "total_items": 0,
                "total_food_cost": Decimal("0"),
                "healthy": 0,
                "warning": 0,
                "danger": 0,
            }
        by_category[cat]["total_items"] += 1
        by_category[cat]["total_food_cost"] += food_cost_pct
        by_category[cat][margin_status] += 1

    # Build summary
    total_items = len(items)
    avg_food_cost = (
        (total_food_cost / total_items).quantize(Decimal("0.1"))
        if total_items > 0
        else Decimal("0")
    )

    cat_summaries = {}
    for cat, data in by_category.items():
        cat_avg = (
            (data["total_food_cost"] / data["total_items"]).quantize(Decimal("0.1"))
            if data["total_items"] > 0
            else Decimal("0")
        )
        cat_summaries[cat] = CategorySummary(
            total_items=data["total_items"],
            avg_food_cost_percent=cat_avg,
            healthy_count=data["healthy"],
            warning_count=data["warning"],
            danger_count=data["danger"],
        )

    return MenuAnalyzerResponse(
        items=items,
        summary=MenuAnalyzerSummary(
            total_items=total_items,
            avg_food_cost_percent=avg_food_cost,
            healthy_count=healthy_count,
            warning_count=warning_count,
            danger_count=danger_count,
            by_category=cat_summaries,
        ),
    )


# ============================================================================
# Price Movement Tracking
# ============================================================================


def get_price_movements(
    db: Session,
    days_back: int = 7,
    pricing_mode: Literal["recent", "average"] = "recent",
    average_days: int = 30,
) -> PriceMoverResponse:
    """
    Find ingredients with the biggest price changes over the last N days,
    and the menu items they affect.
    """
    cutoff = date.today() - timedelta(days=days_back)

    # Get ingredients that have at least 2 price points (one before cutoff, one after)
    # First: latest price before the cutoff for each ingredient
    old_price_subq = (
        db.query(
            DistIngredient.ingredient_id,
            func.max(PriceHistory.effective_date).label("max_old_date"),
        )
        .join(PriceHistory, DistIngredient.id == PriceHistory.dist_ingredient_id)
        .filter(PriceHistory.effective_date < cutoff)
        .filter(DistIngredient.ingredient_id != None)
        .filter(DistIngredient.is_active == True)
        .filter(DistIngredient.grams_per_unit != None)
        .filter(DistIngredient.grams_per_unit > 0)
        .group_by(DistIngredient.ingredient_id)
        .subquery()
    )

    # Get old prices
    old_prices_raw = (
        db.query(
            DistIngredient.ingredient_id,
            Ingredient.name.label("ingredient_name"),
            PriceHistory.price_cents,
            DistIngredient.grams_per_unit,
        )
        .join(Ingredient, DistIngredient.ingredient_id == Ingredient.id)
        .join(old_price_subq, DistIngredient.ingredient_id == old_price_subq.c.ingredient_id)
        .join(
            PriceHistory,
            (DistIngredient.id == PriceHistory.dist_ingredient_id)
            & (PriceHistory.effective_date == old_price_subq.c.max_old_date),
        )
        .filter(DistIngredient.is_active == True)
        .filter(DistIngredient.grams_per_unit != None)
        .filter(DistIngredient.grams_per_unit > 0)
        .all()
    )

    # Build best old price per ingredient
    old_best: dict[UUID, tuple[Decimal, str]] = {}
    for row in old_prices_raw:
        ppb = Decimal(str(row.price_cents)) / Decimal(str(row.grams_per_unit))
        if row.ingredient_id not in old_best or ppb < old_best[row.ingredient_id][0]:
            old_best[row.ingredient_id] = (ppb, row.ingredient_name)

    # Get current best prices
    new_best = get_all_raw_ingredient_prices_batch(db)

    # Find movers: ingredients present in both old and new
    ingredient_movers: list[IngredientMover] = []
    for ing_id, (old_ppb, ing_name) in old_best.items():
        if ing_id not in new_best:
            continue
        new_ppb, _ = new_best[ing_id]

        if old_ppb == 0:
            continue

        change_pct = ((new_ppb - old_ppb) / old_ppb * 100).quantize(Decimal("0.1"))

        # Only include if change is meaningful (>1%)
        if abs(change_pct) < 1:
            continue

        ingredient_movers.append(IngredientMover(
            ingredient_id=ing_id,
            ingredient_name=ing_name,
            old_price_per_unit=old_ppb.quantize(Decimal("0.0001")),
            new_price_per_unit=new_ppb.quantize(Decimal("0.0001")),
            change_percent=change_pct,
            affected_items=[],  # Populated below
        ))

    # Sort by absolute change percent descending
    ingredient_movers.sort(key=lambda m: abs(m.change_percent or 0), reverse=True)

    # Find affected menu items for each mover
    if ingredient_movers:
        mover_ids = {m.ingredient_id for m in ingredient_movers}

        # Get all menu items with recipes that use these ingredients
        recipe_ingredients = (
            db.query(
                RecipeIngredient.ingredient_id,
                RecipeIngredient.quantity_grams,
                RecipeIngredient.recipe_id,
                MenuItem.id.label("menu_item_id"),
                MenuItem.name.label("menu_item_name"),
                MenuItem.portion_of_recipe,
                MenuItem.menu_price_cents,
            )
            .join(Recipe, RecipeIngredient.recipe_id == Recipe.id)
            .join(MenuItem, MenuItem.recipe_id == Recipe.id)
            .filter(RecipeIngredient.ingredient_id.in_(mover_ids))
            .filter(MenuItem.is_active == True)
            .all()
        )

        # Map ingredient_id -> list of affected items with cost impact
        affected_map: dict[UUID, list[AffectedMenuItem]] = {}
        for row in recipe_ingredients:
            if row.ingredient_id not in affected_map:
                affected_map[row.ingredient_id] = []

            old_ppb = old_best[row.ingredient_id][0]
            new_ppb_val = new_best[row.ingredient_id][0]
            qty = Decimal(str(row.quantity_grams))
            portion = Decimal(str(row.portion_of_recipe))

            old_cost = int(qty * old_ppb * portion)
            new_cost = int(qty * new_ppb_val * portion)
            impact = new_cost - old_cost

            affected_map[row.ingredient_id].append(AffectedMenuItem(
                name=row.menu_item_name,
                cost_impact_cents=impact,
            ))

        for mover in ingredient_movers:
            mover.affected_items = affected_map.get(mover.ingredient_id, [])

    # Item movers: menu items with the biggest total cost changes
    # We compute this from the ingredient movers data
    item_cost_changes: dict[str, dict] = {}
    for mover in ingredient_movers:
        for affected in mover.affected_items:
            key = affected.name
            if key not in item_cost_changes:
                item_cost_changes[key] = {"total_impact": 0, "name": affected.name}
            item_cost_changes[key]["total_impact"] += affected.cost_impact_cents

    # Get current costs for the affected menu items to build ItemMover list
    item_movers: list[ItemMover] = []
    if item_cost_changes:
        affected_names = list(item_cost_changes.keys())
        affected_items = (
            db.query(MenuItem)
            .filter(MenuItem.name.in_(affected_names))
            .filter(MenuItem.is_active == True)
            .all()
        )
        for mi in affected_items:
            impact = item_cost_changes.get(mi.name, {}).get("total_impact", 0)
            if impact == 0:
                continue

            # Get current cost
            try:
                cost_breakdown = calculate_menu_item_cost(
                    db, mi.id, pricing_mode, average_days
                )
                new_total = cost_breakdown.total_cost_cents
                old_total = new_total - impact
                new_fcp = cost_breakdown.food_cost_percent
            except ValueError:
                continue

            item_movers.append(ItemMover(
                menu_item_id=mi.id,
                menu_item_name=mi.name,
                old_total_cost=old_total,
                new_total_cost=new_total,
                cost_change_cents=impact,
                new_food_cost_percent=new_fcp,
            ))

        # Sort by absolute cost change
        item_movers.sort(key=lambda m: abs(m.cost_change_cents), reverse=True)

    return PriceMoverResponse(
        period_days=days_back,
        ingredient_movers=ingredient_movers[:20],  # Top 20
        item_movers=item_movers[:20],
    )
