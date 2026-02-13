"""Ingredient CRUD endpoints."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.cost_calculator import get_ingredient_best_price, get_all_raw_ingredient_prices_batch
from app.models.ingredient import Ingredient, DistIngredient, PriceHistory
from app.models.recipe import Recipe
from app.schemas.ingredient import (
    IngredientCreate,
    IngredientUpdate,
    IngredientResponse,
    IngredientList,
    IngredientWithVariants,
    IngredientWithPrice,
    IngredientWithPriceList,
    DistIngredientCreate,
    DistIngredientUpdate,
    DistIngredientResponse,
    DistIngredientList,
    DistIngredientSummary,
    UnmappedDistIngredient,
    UnmappedDistIngredientList,
    MapDistIngredientRequest,
    CreateAndMapRequest,
    DistributorPrice,
    IngredientPriceComparison,
    PriceComparisonMatrix,
    PriceHistoryEntry,
    DistributorPriceHistory,
    IngredientPriceHistory,
    ManualPriceRequest,
    ManualPriceResponse,
    FromInvoicePriceRequest,
    FromInvoicePriceResponse,
    ParsePriceContentRequest,
    ParsePriceContentResponse,
    ParsedPriceItemResponse,
    SaveParsedPriceRequest,
    # New mapping view schemas
    SKUPriceEntry,
    MappedSKU,
    DistributorSKUGroup,
    IngredientMappingView,
    # Unified pricing schemas
    MultiUnitPricing,
    UnifiedPricingItem,
    UnifiedPricingResponse,
)
from app.models.distributor import Distributor
from app.services.units import (
    INGREDIENT_CATEGORIES,
    BaseUnit,
    parse_pack_description,
    suggest_category,
)

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


# ============================================================================
# Ingredient Endpoints
# ============================================================================


@router.get("", response_model=IngredientList)
def list_ingredients(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by name"),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    """List all canonical ingredients."""
    query = db.query(Ingredient)

    if not include_inactive:
        # Note: Ingredient model doesn't have is_active, but keeping for future
        pass

    if category:
        query = query.filter(Ingredient.category == category)

    if search:
        query = query.filter(Ingredient.name.ilike(f"%{search}%"))

    ingredients = query.order_by(Ingredient.category, Ingredient.name).all()
    return IngredientList(ingredients=ingredients, count=len(ingredients))


@router.get("/with-prices", response_model=IngredientWithPriceList)
def list_ingredients_with_prices(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by name"),
    unpriced_only: bool = Query(False, description="Only show unpriced ingredients"),
    db: Session = Depends(get_db),
):
    """List all canonical ingredients with their current best price."""
    query = db.query(Ingredient)

    if category:
        query = query.filter(Ingredient.category == category)

    if search:
        query = query.filter(Ingredient.name.ilike(f"%{search}%"))

    ingredients = query.order_by(Ingredient.category, Ingredient.name).all()

    # Get variant counts for all ingredients
    variant_counts = dict(
        db.query(DistIngredient.ingredient_id, func.count(DistIngredient.id))
        .filter(DistIngredient.ingredient_id != None)
        .filter(DistIngredient.is_active == True)
        .group_by(DistIngredient.ingredient_id)
        .all()
    )

    # Get source recipe names for component ingredients
    source_recipe_ids = [i.source_recipe_id for i in ingredients if i.source_recipe_id]
    source_recipe_names = {}
    if source_recipe_ids:
        recipes = db.query(Recipe.id, Recipe.name).filter(Recipe.id.in_(source_recipe_ids)).all()
        source_recipe_names = {r.id: r.name for r in recipes}

    # Batch fetch all ingredient prices in a single query (optimized)
    all_prices = get_all_raw_ingredient_prices_batch(db)

    # Build response with prices
    result = []
    for ingredient in ingredients:
        # Use batch-fetched price for raw ingredients
        if ingredient.source_recipe_id:
            # Component ingredient - need individual calculation (involves recipe costing)
            price_per_base, distributor_name = get_ingredient_best_price(db, ingredient.id)
        elif ingredient.id in all_prices:
            # Raw ingredient with price from batch query
            price_per_base, distributor_name = all_prices[ingredient.id]
        else:
            # No price available
            price_per_base, distributor_name = None, None

        has_price = price_per_base is not None
        variant_count = variant_counts.get(ingredient.id, 0)

        if unpriced_only and has_price:
            continue

        source_recipe_name = None
        if ingredient.source_recipe_id:
            source_recipe_name = source_recipe_names.get(ingredient.source_recipe_id)

        result.append(IngredientWithPrice(
            id=ingredient.id,
            name=ingredient.name,
            category=ingredient.category,
            base_unit=ingredient.base_unit,
            ingredient_type=ingredient.ingredient_type,
            source_recipe_id=ingredient.source_recipe_id,
            source_recipe_name=source_recipe_name,
            storage_type=ingredient.storage_type,
            shelf_life_days=ingredient.shelf_life_days,
            notes=ingredient.notes,
            par_level_base_units=ingredient.par_level_base_units,
            yield_factor=ingredient.yield_factor,
            created_at=ingredient.created_at,
            updated_at=ingredient.updated_at,
            current_price_per_base_unit_cents=price_per_base,
            best_distributor_name=distributor_name,
            has_price=has_price,
            variant_count=variant_count,
        ))

    return IngredientWithPriceList(ingredients=result, count=len(result))


@router.get("/categories", response_model=list[str])
def list_categories():
    """List available ingredient categories."""
    return INGREDIENT_CATEGORIES


@router.get("/unified-pricing", response_model=UnifiedPricingResponse)
def get_unified_pricing(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by name"),
    include_ingredients: bool = Query(True, description="Include regular ingredients"),
    include_components: bool = Query(True, description="Include component ingredients"),
    include_recipes: bool = Query(True, description="Include recipes"),
    db: Session = Depends(get_db),
):
    """Get unified pricing view for all ingredients and recipes.

    Returns prices in multiple units (g, oz, lb, fl oz, L) for easy comparison.
    Toggleable filters for ingredients, components, and recipes.
    """
    from decimal import Decimal
    from app.services.cost_calculator import (
        get_ingredient_best_price,
        get_all_raw_ingredient_prices_batch,
        calculate_recipe_cost,
    )

    # Unit conversion constants
    OZ_TO_G = Decimal("28.3495")
    LB_TO_G = Decimal("453.592")
    FL_OZ_TO_ML = Decimal("29.5735")
    L_TO_ML = Decimal("1000")

    items = []
    ingredient_count = 0
    recipe_count = 0
    component_count = 0

    # Get ingredients
    if include_ingredients or include_components:
        ing_query = db.query(Ingredient)
        if category:
            ing_query = ing_query.filter(Ingredient.category == category)
        if search:
            ing_query = ing_query.filter(Ingredient.name.ilike(f"%{search}%"))

        ingredients = ing_query.order_by(Ingredient.category, Ingredient.name).all()

        # Batch fetch prices for raw ingredients
        all_prices = get_all_raw_ingredient_prices_batch(db)

        # Get source recipe names for component ingredients
        source_recipe_ids = [i.source_recipe_id for i in ingredients if i.source_recipe_id]
        source_recipe_names = {}
        if source_recipe_ids:
            recipes = db.query(Recipe.id, Recipe.name).filter(Recipe.id.in_(source_recipe_ids)).all()
            source_recipe_names = {r.id: r.name for r in recipes}

        for ingredient in ingredients:
            is_component = ingredient.ingredient_type == "component" or ingredient.source_recipe_id

            # Filter based on toggles
            if is_component and not include_components:
                continue
            if not is_component and not include_ingredients:
                continue

            # Get price
            if ingredient.source_recipe_id:
                price_per_base, source_name = get_ingredient_best_price(db, ingredient.id)
            elif ingredient.id in all_prices:
                price_per_base, source_name = all_prices[ingredient.id]
            else:
                price_per_base, source_name = None, None

            # Calculate multi-unit pricing
            pricing = MultiUnitPricing()
            if price_per_base is not None:
                if ingredient.base_unit == "g":
                    pricing.per_g_cents = price_per_base
                    pricing.per_oz_cents = price_per_base * OZ_TO_G
                    pricing.per_lb_cents = price_per_base * LB_TO_G
                elif ingredient.base_unit == "ml":
                    pricing.per_ml_cents = price_per_base
                    pricing.per_fl_oz_cents = price_per_base * FL_OZ_TO_ML
                    pricing.per_l_cents = price_per_base * L_TO_ML
                elif ingredient.base_unit == "each":
                    pricing.per_each_cents = price_per_base

            source_recipe_name = None
            if ingredient.source_recipe_id:
                source_recipe_name = source_recipe_names.get(ingredient.source_recipe_id)

            item_type = "component" if is_component else "ingredient"
            if is_component:
                component_count += 1
            else:
                ingredient_count += 1

            items.append(UnifiedPricingItem(
                id=ingredient.id,
                name=ingredient.name,
                item_type=item_type,
                category=ingredient.category,
                base_unit=ingredient.base_unit,
                source=source_name,
                has_price=price_per_base is not None,
                pricing=pricing,
                source_recipe_id=ingredient.source_recipe_id,
                source_recipe_name=source_recipe_name,
            ))

    # Get recipes
    if include_recipes:
        recipe_query = db.query(Recipe).filter(Recipe.is_active == True)
        if search:
            recipe_query = recipe_query.filter(Recipe.name.ilike(f"%{search}%"))

        recipes = recipe_query.order_by(Recipe.name).all()

        for recipe in recipes:
            try:
                cost_breakdown = calculate_recipe_cost(db, recipe.id)
                total_cost = cost_breakdown.total_cost_cents
                has_price = total_cost > 0 or not cost_breakdown.has_unpriced_ingredients
                cost_per_unit = cost_breakdown.cost_per_unit_cents
                cost_per_gram = cost_breakdown.cost_per_gram_cents
            except ValueError:
                total_cost = 0
                has_price = False
                cost_per_unit = None
                cost_per_gram = None

            # Calculate multi-unit pricing from cost_per_gram
            pricing = MultiUnitPricing()
            if cost_per_gram is not None:
                # Recipe yields weight (or has yield_weight_grams)
                pricing.per_g_cents = cost_per_gram
                pricing.per_oz_cents = cost_per_gram * OZ_TO_G
                pricing.per_lb_cents = cost_per_gram * LB_TO_G

            recipe_count += 1

            items.append(UnifiedPricingItem(
                id=recipe.id,
                name=recipe.name,
                item_type="recipe",
                category=None,  # Recipes don't have categories yet
                base_unit="g" if recipe.yield_weight_grams else recipe.yield_unit,
                source="Recipe",
                has_price=has_price,
                pricing=pricing,
                yield_quantity=recipe.yield_quantity,
                yield_unit=recipe.yield_unit,
                yield_weight_grams=recipe.yield_weight_grams,
                cost_per_yield_cents=cost_per_unit,
            ))

    return UnifiedPricingResponse(
        items=items,
        count=len(items),
        ingredient_count=ingredient_count,
        recipe_count=recipe_count,
        component_count=component_count,
    )


@router.get("/{ingredient_id}", response_model=IngredientWithVariants)
def get_ingredient(
    ingredient_id: UUID,
    db: Session = Depends(get_db),
):
    """Get a single ingredient with its distributor variants."""
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    # Get variants with distributor names
    variants = []
    for di in ingredient.dist_ingredients:
        variant_dict = {
            "id": di.id,
            "distributor_id": di.distributor_id,
            "distributor_name": di.distributor.name if di.distributor else None,
            "sku": di.sku,
            "description": di.description,
            "pack_size": di.pack_size,
            "pack_unit": di.pack_unit,
            "is_active": di.is_active,
        }
        variants.append(DistIngredientSummary(**variant_dict))

    # Get source recipe name if this is a component ingredient
    source_recipe_name = None
    if ingredient.source_recipe_id:
        source_recipe = db.query(Recipe.name).filter(Recipe.id == ingredient.source_recipe_id).first()
        if source_recipe:
            source_recipe_name = source_recipe.name

    response = IngredientWithVariants.model_validate(ingredient)
    response.variants = variants
    response.source_recipe_name = source_recipe_name
    return response


@router.get("/{ingredient_id}/mapping-view", response_model=IngredientMappingView)
def get_ingredient_mapping_view(
    ingredient_id: UUID,
    history_limit: int = Query(10, description="Max price history entries per SKU"),
    db: Session = Depends(get_db),
):
    """Get ingredient with mapped SKUs grouped by distributor, including price history.

    Optimized for the ingredient-centric mapping workflow UI.
    Returns SKUs grouped by distributor with their price history including invoice references.
    """
    from decimal import Decimal
    from app.models.invoice import Invoice

    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    # Get all dist_ingredients for this ingredient with distributor info
    dist_ingredients = (
        db.query(DistIngredient, Distributor.name.label("distributor_name"))
        .join(Distributor, DistIngredient.distributor_id == Distributor.id)
        .filter(DistIngredient.ingredient_id == ingredient_id)
        .filter(DistIngredient.is_active == True)
        .order_by(Distributor.name, DistIngredient.description)
        .all()
    )

    # Get all price history for these dist_ingredients
    di_ids = [di.id for di, _ in dist_ingredients]
    price_histories = []
    if di_ids:
        price_histories = (
            db.query(PriceHistory)
            .filter(PriceHistory.dist_ingredient_id.in_(di_ids))
            .order_by(PriceHistory.effective_date.desc())
            .all()
        )

    # Group price histories by dist_ingredient_id
    price_by_di: dict[UUID, list[PriceHistory]] = {}
    for ph in price_histories:
        if ph.dist_ingredient_id not in price_by_di:
            price_by_di[ph.dist_ingredient_id] = []
        price_by_di[ph.dist_ingredient_id].append(ph)

    # Get invoice info for price history entries that came from invoices
    invoice_refs = {}
    invoice_sources = [
        ph for ph in price_histories
        if ph.source == "invoice" and ph.source_reference
    ]
    if invoice_sources:
        # Extract invoice numbers from source_reference (format: "Invoice #123")
        invoice_numbers = set()
        for ph in invoice_sources:
            if ph.source_reference and ph.source_reference.startswith("Invoice #"):
                inv_num = ph.source_reference.replace("Invoice #", "")
                invoice_numbers.add(inv_num)

        if invoice_numbers:
            invoices = (
                db.query(Invoice.id, Invoice.invoice_number)
                .filter(Invoice.invoice_number.in_(invoice_numbers))
                .all()
            )
            invoice_refs = {inv.invoice_number: inv.id for inv in invoices}

    # Group by distributor
    distributor_groups: dict[UUID, DistributorSKUGroup] = {}
    best_price = None
    best_dist_name = None

    for di, dist_name in dist_ingredients:
        if di.distributor_id not in distributor_groups:
            distributor_groups[di.distributor_id] = DistributorSKUGroup(
                distributor_id=di.distributor_id,
                distributor_name=dist_name,
                skus=[],
                sku_count=0,
            )

        # Build price history for this SKU
        di_prices = price_by_di.get(di.id, [])[:history_limit]
        price_entries = []
        latest_price = None
        latest_date = None

        for ph in di_prices:
            # Calculate price per base unit
            price_per_base = None
            if di.grams_per_unit and di.grams_per_unit > 0:
                price_per_base = Decimal(str(ph.price_cents)) / Decimal(str(di.grams_per_unit))

                # Track best price
                if best_price is None or price_per_base < best_price:
                    best_price = price_per_base
                    best_dist_name = dist_name

            # Get invoice ID if available
            invoice_id = None
            invoice_number = None
            if ph.source_reference and ph.source_reference.startswith("Invoice #"):
                invoice_number = ph.source_reference.replace("Invoice #", "")
                invoice_id = invoice_refs.get(invoice_number)

            price_entries.append(SKUPriceEntry(
                price_cents=ph.price_cents,
                price_per_base_unit_cents=price_per_base,
                effective_date=ph.effective_date,
                source=ph.source,
                invoice_number=invoice_number,
                invoice_id=invoice_id,
            ))

            # Track latest price
            if latest_price is None:
                latest_price = ph.price_cents
                latest_date = ph.effective_date

        sku = MappedSKU(
            id=di.id,
            sku=di.sku,
            description=di.description,
            pack_size=di.pack_size,
            pack_unit=di.pack_unit,
            grams_per_unit=di.grams_per_unit,
            is_active=di.is_active,
            price_history=price_entries,
            latest_price_cents=latest_price,
            latest_price_date=latest_date,
        )

        distributor_groups[di.distributor_id].skus.append(sku)
        distributor_groups[di.distributor_id].sku_count += 1

    # Build response
    groups = list(distributor_groups.values())
    total_skus = sum(g.sku_count for g in groups)

    return IngredientMappingView(
        id=ingredient.id,
        name=ingredient.name,
        category=ingredient.category,
        base_unit=ingredient.base_unit,
        distributor_groups=groups,
        total_mapped_skus=total_skus,
        has_price=best_price is not None,
        best_price_per_base_unit_cents=best_price,
        best_distributor_name=best_dist_name,
    )


@router.post("", response_model=IngredientResponse, status_code=201)
def create_ingredient(
    data: IngredientCreate,
    db: Session = Depends(get_db),
):
    """Create a new canonical ingredient."""
    # Validate base_unit
    valid_units = [bu.value for bu in BaseUnit]
    if data.base_unit not in valid_units:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid base_unit. Must be one of: {', '.join(valid_units)}",
        )

    # Validate category if provided
    if data.category and data.category not in INGREDIENT_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {', '.join(INGREDIENT_CATEGORIES)}",
        )

    # Check for duplicate name
    existing = db.query(Ingredient).filter(Ingredient.name == data.name).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Ingredient with name '{data.name}' already exists",
        )

    # Auto-suggest category if not provided
    ingredient_data = data.model_dump()
    if not ingredient_data.get("category"):
        suggested = suggest_category(data.name)
        if suggested:
            ingredient_data["category"] = suggested

    ingredient = Ingredient(**ingredient_data)
    db.add(ingredient)
    db.commit()
    db.refresh(ingredient)
    return ingredient


@router.patch("/{ingredient_id}", response_model=IngredientResponse)
def update_ingredient(
    ingredient_id: UUID,
    data: IngredientUpdate,
    db: Session = Depends(get_db),
):
    """Update an ingredient."""
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    update_data = data.model_dump(exclude_unset=True)

    # Validate base_unit if being updated
    if "base_unit" in update_data:
        valid_units = [bu.value for bu in BaseUnit]
        if update_data["base_unit"] not in valid_units:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid base_unit. Must be one of: {', '.join(valid_units)}",
            )

    # Validate category if being updated
    if "category" in update_data and update_data["category"]:
        if update_data["category"] not in INGREDIENT_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {', '.join(INGREDIENT_CATEGORIES)}",
            )

    # Check for duplicate name if being updated
    if "name" in update_data:
        existing = (
            db.query(Ingredient)
            .filter(Ingredient.name == update_data["name"], Ingredient.id != ingredient_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Ingredient with name '{update_data['name']}' already exists",
            )

    for field, value in update_data.items():
        setattr(ingredient, field, value)

    db.commit()
    db.refresh(ingredient)
    return ingredient


@router.delete("/{ingredient_id}", status_code=204)
def delete_ingredient(
    ingredient_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete an ingredient.

    Note: This will fail if the ingredient is used in recipes or has
    distributor variants. Unlink those first.
    """
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    # Check for usage in recipes
    if ingredient.recipe_ingredients:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete ingredient that is used in recipes. Remove from recipes first.",
        )

    # Check for distributor variants
    if ingredient.dist_ingredients:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete ingredient with distributor variants. Unlink variants first.",
        )

    db.delete(ingredient)
    db.commit()
    return None


# ============================================================================
# Dist Ingredient Endpoints
# ============================================================================


@router.get("/dist", response_model=DistIngredientList)
def list_dist_ingredients(
    distributor_id: Optional[UUID] = Query(None, description="Filter by distributor"),
    unmapped_only: bool = Query(False, description="Only show unmapped items"),
    search: Optional[str] = Query(None, description="Search by description or SKU"),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    """List distributor ingredients (SKUs)."""
    query = db.query(DistIngredient)

    if not include_inactive:
        query = query.filter(DistIngredient.is_active == True)

    if distributor_id:
        query = query.filter(DistIngredient.distributor_id == distributor_id)

    if unmapped_only:
        query = query.filter(DistIngredient.ingredient_id == None)

    if search:
        query = query.filter(
            (DistIngredient.description.ilike(f"%{search}%"))
            | (DistIngredient.sku.ilike(f"%{search}%"))
        )

    dist_ingredients = query.order_by(DistIngredient.description).all()
    return DistIngredientList(dist_ingredients=dist_ingredients, count=len(dist_ingredients))


@router.get("/dist/unmapped", response_model=UnmappedDistIngredientList)
def list_unmapped_dist_ingredients(
    distributor_id: Optional[UUID] = Query(None, description="Filter by distributor"),
    search: Optional[str] = Query(None, description="Search by description or SKU"),
    db: Session = Depends(get_db),
):
    """List unmapped distributor ingredients with rich context for mapping UI.

    Returns dist_ingredients that have no ingredient_id set, along with:
    - Distributor name
    - Parsed pack information (if parseable)
    - Last price from invoices
    """
    from sqlalchemy import func

    # Query unmapped dist_ingredients with distributor join
    query = (
        db.query(DistIngredient, Distributor.name.label("distributor_name"))
        .join(Distributor, DistIngredient.distributor_id == Distributor.id)
        .filter(DistIngredient.ingredient_id == None)
        .filter(DistIngredient.is_active == True)
    )

    if distributor_id:
        query = query.filter(DistIngredient.distributor_id == distributor_id)

    if search:
        query = query.filter(
            (DistIngredient.description.ilike(f"%{search}%"))
            | (DistIngredient.sku.ilike(f"%{search}%"))
        )

    results = query.order_by(Distributor.name, DistIngredient.description).all()

    # Get last prices for these dist_ingredients
    di_ids = [r[0].id for r in results]
    last_prices = {}
    if di_ids:
        # Subquery to get the latest price for each dist_ingredient
        price_subq = (
            db.query(
                PriceHistory.dist_ingredient_id,
                func.max(PriceHistory.effective_date).label("max_date"),
            )
            .filter(PriceHistory.dist_ingredient_id.in_(di_ids))
            .group_by(PriceHistory.dist_ingredient_id)
            .subquery()
        )

        prices = (
            db.query(PriceHistory)
            .join(
                price_subq,
                (PriceHistory.dist_ingredient_id == price_subq.c.dist_ingredient_id)
                & (PriceHistory.effective_date == price_subq.c.max_date),
            )
            .all()
        )

        for p in prices:
            last_prices[p.dist_ingredient_id] = (p.price_cents, p.effective_date)

    # Build response with parsed pack info
    items = []
    for di, distributor_name in results:
        # Try to parse pack info
        pack_info = parse_pack_description(di.description)

        item = UnmappedDistIngredient(
            id=di.id,
            distributor_id=di.distributor_id,
            distributor_name=distributor_name,
            sku=di.sku,
            description=di.description,
            pack_size=di.pack_size,
            pack_unit=di.pack_unit,
            grams_per_unit=di.grams_per_unit,
            parsed_pack_quantity=pack_info.pack_quantity if pack_info else None,
            parsed_unit_quantity=pack_info.unit_quantity if pack_info else None,
            parsed_unit=pack_info.unit if pack_info else None,
            parsed_total_base_units=pack_info.total_base_units if pack_info else None,
            parsed_base_unit=pack_info.base_unit.value if pack_info and pack_info.base_unit else None,
            last_price_cents=last_prices.get(di.id, (None, None))[0],
            last_price_date=last_prices.get(di.id, (None, None))[1],
            created_at=di.created_at,
        )
        items.append(item)

    return UnmappedDistIngredientList(items=items, count=len(items))


@router.get("/dist/{dist_ingredient_id}", response_model=DistIngredientResponse)
def get_dist_ingredient(
    dist_ingredient_id: UUID,
    db: Session = Depends(get_db),
):
    """Get a single distributor ingredient."""
    di = db.query(DistIngredient).filter(DistIngredient.id == dist_ingredient_id).first()
    if not di:
        raise HTTPException(status_code=404, detail="Distributor ingredient not found")
    return di


@router.post("/dist", response_model=DistIngredientResponse, status_code=201)
def create_dist_ingredient(
    data: DistIngredientCreate,
    db: Session = Depends(get_db),
):
    """Create a new distributor ingredient mapping."""
    # Check for duplicate SKU with same distributor
    if data.sku:
        existing = (
            db.query(DistIngredient)
            .filter(
                DistIngredient.distributor_id == data.distributor_id,
                DistIngredient.sku == data.sku,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"SKU '{data.sku}' already exists for this distributor",
            )

    # Try to auto-parse pack info from description
    di_data = data.model_dump()
    if not di_data.get("pack_size") or not di_data.get("grams_per_unit"):
        pack_info = parse_pack_description(data.description)
        if pack_info:
            if not di_data.get("pack_size"):
                di_data["pack_size"] = pack_info.pack_quantity
            if not di_data.get("pack_unit"):
                di_data["pack_unit"] = f"{pack_info.unit_quantity}{pack_info.unit}"
            if not di_data.get("grams_per_unit") and pack_info.total_base_units:
                # Store total base units per pack
                di_data["grams_per_unit"] = pack_info.total_base_units

    di = DistIngredient(**di_data)
    db.add(di)
    db.commit()
    db.refresh(di)
    return di


@router.patch("/dist/{dist_ingredient_id}", response_model=DistIngredientResponse)
def update_dist_ingredient(
    dist_ingredient_id: UUID,
    data: DistIngredientUpdate,
    db: Session = Depends(get_db),
):
    """Update a distributor ingredient."""
    di = db.query(DistIngredient).filter(DistIngredient.id == dist_ingredient_id).first()
    if not di:
        raise HTTPException(status_code=404, detail="Distributor ingredient not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(di, field, value)

    db.commit()
    db.refresh(di)
    return di


@router.post("/dist/{dist_ingredient_id}/recalculate", response_model=DistIngredientResponse)
def recalculate_dist_ingredient_base_units(
    dist_ingredient_id: UUID,
    db: Session = Depends(get_db),
):
    """Recalculate grams_per_unit from pack_size and pack_unit.

    Useful when pack info was set but grams_per_unit wasn't calculated.
    """
    from decimal import Decimal
    from app.services.units import WEIGHT_TO_GRAMS, VOLUME_TO_ML, normalize_unit
    import re

    di = db.query(DistIngredient).filter(DistIngredient.id == dist_ingredient_id).first()
    if not di:
        raise HTTPException(status_code=404, detail="Distributor ingredient not found")

    if not di.ingredient_id:
        raise HTTPException(status_code=400, detail="Distributor ingredient not mapped to an ingredient")

    ingredient = db.query(Ingredient).filter(Ingredient.id == di.ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=400, detail="Mapped ingredient not found")

    if not di.pack_unit:
        raise HTTPException(status_code=400, detail="No pack_unit set - cannot calculate")

    pack_unit = di.pack_unit
    pack_size = di.pack_size or Decimal("1")

    # Try to parse pack_unit for unit quantity (e.g., "1LB" -> 1, "LB")
    match = re.match(r"^(\d+\.?\d*)?\s*(.+)$", pack_unit.strip())
    if not match:
        raise HTTPException(status_code=400, detail=f"Cannot parse pack_unit: {pack_unit}")

    unit_qty_str, unit = match.groups()
    unit_qty = Decimal(unit_qty_str) if unit_qty_str else Decimal("1")
    normalized_unit = normalize_unit(unit)

    # Calculate total base units based on ingredient's base_unit
    if ingredient.base_unit == "g" and normalized_unit in WEIGHT_TO_GRAMS:
        total_base = pack_size * unit_qty * WEIGHT_TO_GRAMS[normalized_unit]
        di.grams_per_unit = total_base
    elif ingredient.base_unit == "ml" and normalized_unit in VOLUME_TO_ML:
        total_base = pack_size * unit_qty * VOLUME_TO_ML[normalized_unit]
        di.grams_per_unit = total_base
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot convert '{unit}' to {ingredient.base_unit}"
        )

    db.commit()
    db.refresh(di)
    return di


@router.post("/dist/{dist_ingredient_id}/map", response_model=DistIngredientResponse)
def map_dist_ingredient(
    dist_ingredient_id: UUID,
    ingredient_id: UUID,
    db: Session = Depends(get_db),
):
    """Map a distributor ingredient to a canonical ingredient."""
    di = db.query(DistIngredient).filter(DistIngredient.id == dist_ingredient_id).first()
    if not di:
        raise HTTPException(status_code=404, detail="Distributor ingredient not found")

    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    di.ingredient_id = ingredient_id
    db.commit()
    db.refresh(di)
    return di


@router.post("/dist/{dist_ingredient_id}/parse-pack", response_model=dict)
def parse_dist_ingredient_pack(
    dist_ingredient_id: UUID,
    db: Session = Depends(get_db),
):
    """Parse pack information from a distributor ingredient's description.

    Returns suggested pack_size, pack_unit, and grams_per_unit values.
    """
    di = db.query(DistIngredient).filter(DistIngredient.id == dist_ingredient_id).first()
    if not di:
        raise HTTPException(status_code=404, detail="Distributor ingredient not found")

    pack_info = parse_pack_description(di.description)
    if not pack_info:
        return {
            "parsed": False,
            "message": "Could not parse pack information from description",
            "description": di.description,
        }

    return {
        "parsed": True,
        "pack_quantity": float(pack_info.pack_quantity),
        "unit_quantity": float(pack_info.unit_quantity),
        "unit": pack_info.unit,
        "total_base_units": float(pack_info.total_base_units) if pack_info.total_base_units else None,
        "base_unit": pack_info.base_unit.value if pack_info.base_unit else None,
        "suggested_pack_size": float(pack_info.pack_quantity),
        "suggested_pack_unit": f"{pack_info.unit_quantity}{pack_info.unit}",
        "suggested_grams_per_unit": float(pack_info.total_base_units) if pack_info.total_base_units else None,
    }


# ============================================================================
# Enhanced Mapping Endpoints for UI
# ============================================================================


@router.post("/dist/{dist_ingredient_id}/map-with-details", response_model=DistIngredientResponse)
def map_dist_ingredient_with_details(
    dist_ingredient_id: UUID,
    data: MapDistIngredientRequest,
    db: Session = Depends(get_db),
):
    """Map a distributor ingredient to a canonical ingredient with pack details.

    This is the preferred mapping endpoint that also sets pack_size and grams_per_unit.
    Will auto-calculate grams_per_unit from pack_size/pack_unit if not provided.
    """
    from decimal import Decimal
    from app.services.units import WEIGHT_TO_GRAMS, VOLUME_TO_ML, normalize_unit

    di = db.query(DistIngredient).filter(DistIngredient.id == dist_ingredient_id).first()
    if not di:
        raise HTTPException(status_code=404, detail="Distributor ingredient not found")

    ingredient = db.query(Ingredient).filter(Ingredient.id == data.ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    # Update the mapping and pack info
    di.ingredient_id = data.ingredient_id
    if data.pack_size is not None:
        di.pack_size = data.pack_size
    if data.pack_unit is not None:
        di.pack_unit = data.pack_unit
    if data.grams_per_unit is not None:
        di.grams_per_unit = data.grams_per_unit

    # Auto-calculate grams_per_unit if not provided but we have pack info
    if di.grams_per_unit is None and di.pack_unit:
        pack_unit = di.pack_unit
        pack_size = di.pack_size or Decimal("1")

        # Try to parse pack_unit for unit quantity (e.g., "1LB" -> 1, "LB")
        import re
        match = re.match(r"^(\d+\.?\d*)?\s*(.+)$", pack_unit.strip())
        if match:
            unit_qty_str, unit = match.groups()
            unit_qty = Decimal(unit_qty_str) if unit_qty_str else Decimal("1")
            normalized_unit = normalize_unit(unit)

            # Calculate total base units based on ingredient's base_unit
            if ingredient.base_unit == "g" and normalized_unit in WEIGHT_TO_GRAMS:
                total_base = pack_size * unit_qty * WEIGHT_TO_GRAMS[normalized_unit]
                di.grams_per_unit = total_base
            elif ingredient.base_unit == "ml" and normalized_unit in VOLUME_TO_ML:
                total_base = pack_size * unit_qty * VOLUME_TO_ML[normalized_unit]
                di.grams_per_unit = total_base

    db.commit()
    db.refresh(di)
    return di


@router.post("/dist/{dist_ingredient_id}/create-and-map", response_model=DistIngredientResponse)
def create_ingredient_and_map(
    dist_ingredient_id: UUID,
    data: CreateAndMapRequest,
    db: Session = Depends(get_db),
):
    """Create a new canonical ingredient and map the distributor ingredient to it.

    Useful when the dist_ingredient doesn't match any existing canonical ingredient.
    """
    di = db.query(DistIngredient).filter(DistIngredient.id == dist_ingredient_id).first()
    if not di:
        raise HTTPException(status_code=404, detail="Distributor ingredient not found")

    # Validate base_unit
    valid_units = [bu.value for bu in BaseUnit]
    if data.ingredient_base_unit not in valid_units:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid base_unit. Must be one of: {', '.join(valid_units)}",
        )

    # Check for duplicate ingredient name
    existing = db.query(Ingredient).filter(Ingredient.name == data.ingredient_name).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Ingredient with name '{data.ingredient_name}' already exists. Use map-with-details instead.",
        )

    # Create the new ingredient
    ingredient = Ingredient(
        name=data.ingredient_name,
        category=data.ingredient_category or suggest_category(data.ingredient_name),
        base_unit=data.ingredient_base_unit,
    )
    db.add(ingredient)
    db.flush()  # Get the ID without committing

    # Update the dist_ingredient mapping
    di.ingredient_id = ingredient.id
    if data.pack_size is not None:
        di.pack_size = data.pack_size
    if data.pack_unit is not None:
        di.pack_unit = data.pack_unit
    if data.grams_per_unit is not None:
        di.grams_per_unit = data.grams_per_unit

    db.commit()
    db.refresh(di)
    return di


# ============================================================================
# Price Comparison Endpoints
# ============================================================================


def _calculate_price_per_base_unit(
    price_cents: int,
    grams_per_unit: float | None,
) -> float | None:
    """Calculate price per base unit (g/ml/each).

    For items sold by pack, grams_per_unit is the total base units per pack.
    Price per base unit = price_cents / grams_per_unit
    """
    if price_cents is None or grams_per_unit is None or grams_per_unit <= 0:
        return None
    return price_cents / grams_per_unit


@router.get("/prices/comparison", response_model=PriceComparisonMatrix)
def get_price_comparison_matrix(
    category: Optional[str] = Query(None, description="Filter by ingredient category"),
    distributor_id: Optional[UUID] = Query(None, description="Filter by distributor"),
    search: Optional[str] = Query(None, description="Search by ingredient name"),
    mapped_only: bool = Query(True, description="Only show ingredients with mapped variants"),
    db: Session = Depends(get_db),
):
    """Get price comparison matrix across all ingredients and distributors.

    Returns price per base unit for each ingredient variant, with best price highlighted.
    """
    from sqlalchemy import func
    from decimal import Decimal

    # Get all active distributors
    distributors = db.query(Distributor).filter(Distributor.is_active == True).all()
    distributor_dict = {d.id: d.name for d in distributors}

    # Build ingredient query
    query = db.query(Ingredient)
    if category:
        query = query.filter(Ingredient.category == category)
    if search:
        query = query.filter(Ingredient.name.ilike(f"%{search}%"))

    ingredients = query.order_by(Ingredient.category, Ingredient.name).all()

    # Get all dist_ingredients with latest prices
    # Subquery for latest price per dist_ingredient
    price_subq = (
        db.query(
            PriceHistory.dist_ingredient_id,
            func.max(PriceHistory.effective_date).label("max_date"),
        )
        .group_by(PriceHistory.dist_ingredient_id)
        .subquery()
    )

    # Join to get latest prices
    dist_ing_query = (
        db.query(
            DistIngredient,
            Distributor.name.label("distributor_name"),
            PriceHistory.price_cents,
            PriceHistory.effective_date,
        )
        .join(Distributor, DistIngredient.distributor_id == Distributor.id)
        .outerjoin(
            price_subq,
            DistIngredient.id == price_subq.c.dist_ingredient_id,
        )
        .outerjoin(
            PriceHistory,
            (DistIngredient.id == PriceHistory.dist_ingredient_id)
            & (PriceHistory.effective_date == price_subq.c.max_date),
        )
        .filter(DistIngredient.is_active == True)
        .filter(DistIngredient.ingredient_id != None)
    )

    if distributor_id:
        dist_ing_query = dist_ing_query.filter(DistIngredient.distributor_id == distributor_id)

    dist_ingredients = dist_ing_query.all()

    # Group dist_ingredients by ingredient_id
    ingredient_variants = {}
    for di, dist_name, price_cents, effective_date in dist_ingredients:
        if di.ingredient_id not in ingredient_variants:
            ingredient_variants[di.ingredient_id] = []

        price_per_base = None
        if price_cents and di.grams_per_unit:
            price_per_base = Decimal(str(price_cents)) / Decimal(str(di.grams_per_unit))

        ingredient_variants[di.ingredient_id].append({
            "dist_ingredient": di,
            "distributor_name": dist_name,
            "price_cents": price_cents,
            "effective_date": effective_date,
            "price_per_base_unit": price_per_base,
        })

    # Build comparison list
    comparisons = []
    total_potential_savings = 0

    for ingredient in ingredients:
        variants = ingredient_variants.get(ingredient.id, [])

        if mapped_only and not variants:
            continue

        # Calculate best price
        prices_per_base = [
            v["price_per_base_unit"]
            for v in variants
            if v["price_per_base_unit"] is not None
        ]

        best_price = min(prices_per_base) if prices_per_base else None
        worst_price = max(prices_per_base) if prices_per_base else None
        best_distributor_id = None

        # Calculate spread
        price_spread = None
        if best_price and worst_price and best_price > 0:
            price_spread = ((worst_price - best_price) / best_price) * 100

        # Build distributor prices
        dist_prices = []
        for v in variants:
            is_best = (
                v["price_per_base_unit"] is not None
                and best_price is not None
                and v["price_per_base_unit"] == best_price
            )
            if is_best:
                best_distributor_id = v["dist_ingredient"].distributor_id

            dist_prices.append(DistributorPrice(
                distributor_id=v["dist_ingredient"].distributor_id,
                distributor_name=v["distributor_name"],
                dist_ingredient_id=v["dist_ingredient"].id,
                sku=v["dist_ingredient"].sku,
                description=v["dist_ingredient"].description,
                pack_size=v["dist_ingredient"].pack_size,
                pack_unit=v["dist_ingredient"].pack_unit,
                grams_per_unit=v["dist_ingredient"].grams_per_unit,
                price_cents=v["price_cents"],
                price_per_base_unit_cents=v["price_per_base_unit"],
                effective_date=v["effective_date"],
                is_best_price=is_best,
            ))

        comparisons.append(IngredientPriceComparison(
            ingredient_id=ingredient.id,
            ingredient_name=ingredient.name,
            category=ingredient.category,
            base_unit=ingredient.base_unit,
            distributor_prices=dist_prices,
            best_price_per_base_unit=best_price,
            best_distributor_id=best_distributor_id,
            price_spread_percent=price_spread,
        ))

    return PriceComparisonMatrix(
        ingredients=comparisons,
        distributors=[{"id": str(d.id), "name": d.name} for d in distributors],
        count=len(comparisons),
        total_potential_savings_cents=total_potential_savings if total_potential_savings > 0 else None,
    )


@router.get("/{ingredient_id}/prices", response_model=IngredientPriceComparison)
def get_ingredient_prices(
    ingredient_id: UUID,
    db: Session = Depends(get_db),
):
    """Get price comparison for a single ingredient across all distributors."""
    from sqlalchemy import func
    from decimal import Decimal
    from app.services.cost_calculator import get_ingredient_best_price

    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    # For component ingredients, calculate price from source recipe
    if ingredient.source_recipe_id:
        price_per_base, source_name = get_ingredient_best_price(db, ingredient_id)

        if price_per_base is not None:
            # Return synthetic price from recipe
            return IngredientPriceComparison(
                ingredient_id=ingredient.id,
                ingredient_name=ingredient.name,
                category=ingredient.category,
                base_unit=ingredient.base_unit,
                distributor_prices=[
                    DistributorPrice(
                        distributor_id=None,
                        distributor_name=source_name or "From Recipe",
                        dist_ingredient_id=None,
                        sku=None,
                        description=f"Calculated from recipe cost",
                        pack_size=None,
                        pack_unit=None,
                        grams_per_unit=None,
                        price_cents=None,
                        price_per_base_unit_cents=price_per_base,
                        effective_date=None,
                        is_best_price=True,
                    )
                ],
                best_price_per_base_unit=price_per_base,
                best_distributor_id=None,
                price_spread_percent=None,
            )
        else:
            # Recipe has unpriced ingredients
            return IngredientPriceComparison(
                ingredient_id=ingredient.id,
                ingredient_name=ingredient.name,
                category=ingredient.category,
                base_unit=ingredient.base_unit,
                distributor_prices=[],
                best_price_per_base_unit=None,
                best_distributor_id=None,
                price_spread_percent=None,
            )

    # Get all dist_ingredients for this ingredient with latest prices
    price_subq = (
        db.query(
            PriceHistory.dist_ingredient_id,
            func.max(PriceHistory.effective_date).label("max_date"),
        )
        .group_by(PriceHistory.dist_ingredient_id)
        .subquery()
    )

    dist_ing_query = (
        db.query(
            DistIngredient,
            Distributor.name.label("distributor_name"),
            PriceHistory.price_cents,
            PriceHistory.effective_date,
        )
        .join(Distributor, DistIngredient.distributor_id == Distributor.id)
        .outerjoin(
            price_subq,
            DistIngredient.id == price_subq.c.dist_ingredient_id,
        )
        .outerjoin(
            PriceHistory,
            (DistIngredient.id == PriceHistory.dist_ingredient_id)
            & (PriceHistory.effective_date == price_subq.c.max_date),
        )
        .filter(DistIngredient.ingredient_id == ingredient_id)
        .filter(DistIngredient.is_active == True)
    )

    dist_ingredients = dist_ing_query.all()

    # Calculate prices
    prices_per_base = []
    dist_prices = []

    for di, dist_name, price_cents, effective_date in dist_ingredients:
        price_per_base = None
        if price_cents and di.grams_per_unit:
            price_per_base = Decimal(str(price_cents)) / Decimal(str(di.grams_per_unit))
            prices_per_base.append(price_per_base)

        dist_prices.append({
            "dist_ingredient": di,
            "distributor_name": dist_name,
            "price_cents": price_cents,
            "effective_date": effective_date,
            "price_per_base_unit": price_per_base,
        })

    best_price = min(prices_per_base) if prices_per_base else None
    worst_price = max(prices_per_base) if prices_per_base else None
    best_distributor_id = None

    price_spread = None
    if best_price and worst_price and best_price > 0:
        price_spread = ((worst_price - best_price) / best_price) * 100

    # Build response
    result_prices = []
    for v in dist_prices:
        is_best = (
            v["price_per_base_unit"] is not None
            and best_price is not None
            and v["price_per_base_unit"] == best_price
        )
        if is_best:
            best_distributor_id = v["dist_ingredient"].distributor_id

        result_prices.append(DistributorPrice(
            distributor_id=v["dist_ingredient"].distributor_id,
            distributor_name=v["distributor_name"],
            dist_ingredient_id=v["dist_ingredient"].id,
            sku=v["dist_ingredient"].sku,
            description=v["dist_ingredient"].description,
            pack_size=v["dist_ingredient"].pack_size,
            pack_unit=v["dist_ingredient"].pack_unit,
            grams_per_unit=v["dist_ingredient"].grams_per_unit,
            price_cents=v["price_cents"],
            price_per_base_unit_cents=v["price_per_base_unit"],
            effective_date=v["effective_date"],
            is_best_price=is_best,
        ))

    return IngredientPriceComparison(
        ingredient_id=ingredient.id,
        ingredient_name=ingredient.name,
        category=ingredient.category,
        base_unit=ingredient.base_unit,
        distributor_prices=result_prices,
        best_price_per_base_unit=best_price,
        best_distributor_id=best_distributor_id,
        price_spread_percent=price_spread,
    )


@router.post("/{ingredient_id}/prices/manual", response_model=ManualPriceResponse, status_code=201)
def add_manual_price(
    ingredient_id: UUID,
    data: ManualPriceRequest,
    db: Session = Depends(get_db),
):
    """Add a manual price for an ingredient.

    This creates or finds a dist_ingredient linked to the specified distributor,
    then adds a price_history record with source='manual'.
    """
    from datetime import datetime, date
    from decimal import Decimal

    # Check ingredient exists
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    # Check distributor exists
    distributor = db.query(Distributor).filter(Distributor.id == data.distributor_id).first()
    if not distributor:
        raise HTTPException(status_code=404, detail="Distributor not found")

    # Find or create dist_ingredient for this ingredient + distributor
    dist_ingredient = (
        db.query(DistIngredient)
        .filter(
            DistIngredient.ingredient_id == ingredient_id,
            DistIngredient.distributor_id == data.distributor_id,
            DistIngredient.is_active == True,
        )
        .first()
    )

    if not dist_ingredient:
        # Create a new dist_ingredient for manual pricing
        dist_ingredient = DistIngredient(
            distributor_id=data.distributor_id,
            ingredient_id=ingredient_id,
            description=f"{ingredient.name} (Manual)",
            pack_unit=data.pack_description,
            grams_per_unit=data.total_base_units,
            notes=data.notes,
        )
        db.add(dist_ingredient)
        db.flush()
    else:
        # Update existing dist_ingredient with new pack info if provided
        if data.pack_description:
            dist_ingredient.pack_unit = data.pack_description
        if data.total_base_units:
            dist_ingredient.grams_per_unit = data.total_base_units

    # Create price history record
    effective_date = data.effective_date.date() if data.effective_date else date.today()
    price_history = PriceHistory(
        dist_ingredient_id=dist_ingredient.id,
        price_cents=data.price_cents,
        effective_date=effective_date,
        source="manual",
        source_reference=data.notes or "Manual entry",
    )
    db.add(price_history)
    db.commit()
    db.refresh(price_history)

    # Calculate price per base unit
    price_per_base = Decimal(str(data.price_cents)) / data.total_base_units

    return ManualPriceResponse(
        dist_ingredient_id=dist_ingredient.id,
        price_history_id=price_history.id,
        price_per_base_unit_cents=price_per_base,
    )


@router.post("/{ingredient_id}/prices/from-invoice", response_model=FromInvoicePriceResponse, status_code=201)
def add_price_from_invoice(
    ingredient_id: UUID,
    data: FromInvoicePriceRequest,
    db: Session = Depends(get_db),
):
    """Add a price from an existing invoice line.

    This links the invoice line to the ingredient (via dist_ingredient) and
    creates a price_history record with source='invoice'.

    If the line is already mapped to a different ingredient, requires
    remap_to_ingredient=True to proceed.
    """
    from datetime import date
    from decimal import Decimal
    from app.models.invoice import InvoiceLine, Invoice

    # Check ingredient exists
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    # Get the invoice line
    invoice_line = (
        db.query(InvoiceLine)
        .filter(InvoiceLine.id == data.invoice_line_id)
        .first()
    )
    if not invoice_line:
        raise HTTPException(status_code=404, detail="Invoice line not found")

    # Get the invoice for distributor_id and date
    invoice = db.query(Invoice).filter(Invoice.id == invoice_line.invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    remapped = False
    previous_ingredient_name = None

    # Check if line already has a dist_ingredient
    if invoice_line.dist_ingredient_id:
        existing_di = db.query(DistIngredient).filter(
            DistIngredient.id == invoice_line.dist_ingredient_id
        ).first()

        if existing_di and existing_di.ingredient_id:
            if str(existing_di.ingredient_id) == str(ingredient_id):
                # Already mapped to this ingredient - just update price
                dist_ingredient = existing_di
            else:
                # Mapped to different ingredient
                if not data.remap_to_ingredient:
                    # Get the other ingredient's name for error message
                    other_ing = db.query(Ingredient).filter(
                        Ingredient.id == existing_di.ingredient_id
                    ).first()
                    other_name = other_ing.name if other_ing else "Unknown"
                    raise HTTPException(
                        status_code=400,
                        detail=f"Line is already mapped to '{other_name}'. Set remap_to_ingredient=True to remap."
                    )

                # Remap: update the dist_ingredient's ingredient_id
                other_ing = db.query(Ingredient).filter(
                    Ingredient.id == existing_di.ingredient_id
                ).first()
                previous_ingredient_name = other_ing.name if other_ing else None

                existing_di.ingredient_id = ingredient_id
                dist_ingredient = existing_di
                remapped = True
        else:
            # Has dist_ingredient but not mapped to any ingredient
            existing_di.ingredient_id = ingredient_id
            dist_ingredient = existing_di
    else:
        # No dist_ingredient - create one
        dist_ingredient = DistIngredient(
            distributor_id=invoice.distributor_id,
            ingredient_id=ingredient_id,
            sku=invoice_line.raw_sku,
            description=invoice_line.raw_description,
            grams_per_unit=data.grams_per_unit,
        )
        db.add(dist_ingredient)
        db.flush()

        # Link invoice line to dist_ingredient
        invoice_line.dist_ingredient_id = dist_ingredient.id

    # Update grams_per_unit on dist_ingredient
    dist_ingredient.grams_per_unit = data.grams_per_unit

    # Create price history record
    effective_date = invoice.invoice_date if invoice.invoice_date else date.today()
    price_cents = invoice_line.unit_price_cents or invoice_line.extended_price_cents or 0

    price_history = PriceHistory(
        dist_ingredient_id=dist_ingredient.id,
        price_cents=price_cents,
        effective_date=effective_date,
        source="invoice",
        source_reference=f"Invoice #{invoice.invoice_number}",
    )
    db.add(price_history)
    db.commit()
    db.refresh(price_history)

    # Calculate price per base unit
    price_per_base = Decimal(str(price_cents)) / data.grams_per_unit

    return FromInvoicePriceResponse(
        dist_ingredient_id=dist_ingredient.id,
        price_history_id=price_history.id,
        price_per_base_unit_cents=price_per_base,
        remapped=remapped,
        previous_ingredient_name=previous_ingredient_name,
    )


@router.post("/prices/parse", response_model=ParsePriceContentResponse)
def parse_price_content(
    data: ParsePriceContentRequest,
    db: Session = Depends(get_db),
):
    """Parse pricing content (image, PDF, text, email) using Claude Haiku.

    Accepts various content types:
    - image/png, image/jpeg: Screenshot or photo (base64 encoded)
    - application/pdf: PDF document (base64 encoded)
    - text/plain: Plain text
    - text/email: Email with headers (from Gmail "Copy to clipboard")

    Returns extracted line items with pricing information.
    """
    from app.services.price_parser import parse_price_content as do_parse

    # Build ingredient context for fuzzy matching
    ingredient_context = None
    if data.ingredient_name:
        ingredient_context = {
            "name": data.ingredient_name,
            "category": data.ingredient_category,
            "base_unit": data.ingredient_base_unit or "g",
        }

    # Determine if content is binary (needs base64 decode) or text
    content = data.content
    if data.content_type.startswith("image/") or data.content_type == "application/pdf":
        # Binary content - pass as-is (already base64)
        pass
    else:
        # Text content - pass as string
        pass

    # Get custom prompt - use provided, or fall back to distributor's, or use default
    custom_prompt = data.custom_prompt
    if custom_prompt is None and data.distributor_id:
        distributor = db.query(Distributor).filter(Distributor.id == data.distributor_id).first()
        if distributor:
            # Use screenshot prompt for images, pdf prompt for PDFs
            if data.content_type.startswith("image/"):
                custom_prompt = distributor.parsing_prompt_screenshot
            elif data.content_type == "application/pdf":
                custom_prompt = distributor.parsing_prompt_pdf
            else:
                custom_prompt = distributor.parsing_prompt_email

    try:
        result = do_parse(
            content=content,
            content_type=data.content_type,
            ingredient_context=ingredient_context,
            custom_prompt=custom_prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse content: {str(e)}")

    # Convert to response format
    items = [
        ParsedPriceItemResponse(
            description=item.description,
            sku=item.sku,
            pack_size=str(item.pack_size) if item.pack_size is not None else None,
            pack_unit=item.pack_unit,
            unit_contents=item.unit_contents,
            unit_contents_unit=item.unit_contents_unit,
            price_cents=item.price_cents,
            price_type=item.price_type,
            total_base_units=item.total_base_units,
            base_unit=item.base_unit,
            price_per_base_unit_cents=item.price_per_base_unit_cents,
            raw_text=item.raw_text,
            confidence=item.confidence,
        )
        for item in result.items
    ]

    return ParsePriceContentResponse(
        items=items,
        detected_distributor=result.detected_distributor,
        document_date=result.document_date,
        prompt_used=result.prompt_used,
    )


@router.post("/{ingredient_id}/prices/from-parsed", response_model=ManualPriceResponse, status_code=201)
def save_parsed_price(
    ingredient_id: UUID,
    data: SaveParsedPriceRequest,
    db: Session = Depends(get_db),
):
    """Save a price from parsed content.

    This creates a dist_ingredient and price_history record for a price
    that was extracted from parsed content (image, PDF, text, email).

    If distributor_id is not provided, uses the system "One-off/Manual" distributor.
    """
    from datetime import date
    from decimal import Decimal
    from uuid import UUID as PyUUID

    ONEOFF_DISTRIBUTOR_ID = PyUUID("00000000-0000-0000-0000-000000000001")

    # Check ingredient exists
    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    # Use provided distributor or default to one-off
    distributor_id = data.distributor_id or ONEOFF_DISTRIBUTOR_ID

    # Check distributor exists
    distributor = db.query(Distributor).filter(Distributor.id == distributor_id).first()
    if not distributor:
        raise HTTPException(status_code=404, detail="Distributor not found")

    # Create dist_ingredient
    dist_ingredient = DistIngredient(
        distributor_id=distributor_id,
        ingredient_id=ingredient_id,
        sku=data.sku,
        description=data.description,
        pack_unit=data.pack_description,
        grams_per_unit=data.total_base_units,
    )
    db.add(dist_ingredient)
    db.flush()

    # Create price history record
    effective_date = data.effective_date.date() if data.effective_date else date.today()
    price_history = PriceHistory(
        dist_ingredient_id=dist_ingredient.id,
        price_cents=data.price_cents,
        effective_date=effective_date,
        source="parsed",
        source_reference="Parsed from uploaded content",
    )
    db.add(price_history)
    db.commit()
    db.refresh(price_history)

    # Calculate price per base unit
    price_per_base = Decimal(str(data.price_cents)) / data.total_base_units

    return ManualPriceResponse(
        dist_ingredient_id=dist_ingredient.id,
        price_history_id=price_history.id,
        price_per_base_unit_cents=price_per_base,
    )


@router.get("/{ingredient_id}/price-history", response_model=IngredientPriceHistory)
def get_ingredient_price_history(
    ingredient_id: UUID,
    days: int = Query(90, description="Number of days of history to return"),
    db: Session = Depends(get_db),
):
    """Get price history for an ingredient across all distributors.

    Useful for trend analysis and price change detection.
    """
    from datetime import datetime, timedelta
    from decimal import Decimal

    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    cutoff_date = datetime.utcnow().date() - timedelta(days=days)

    # Get all dist_ingredients for this ingredient
    dist_ingredients = (
        db.query(DistIngredient, Distributor.name.label("distributor_name"))
        .join(Distributor, DistIngredient.distributor_id == Distributor.id)
        .filter(DistIngredient.ingredient_id == ingredient_id)
        .filter(DistIngredient.is_active == True)
        .all()
    )

    dist_histories = []
    for di, dist_name in dist_ingredients:
        # Get price history for this variant
        prices = (
            db.query(PriceHistory)
            .filter(PriceHistory.dist_ingredient_id == di.id)
            .filter(PriceHistory.effective_date >= cutoff_date)
            .order_by(PriceHistory.effective_date)
            .all()
        )

        history_entries = []
        for p in prices:
            price_per_base = None
            if di.grams_per_unit:
                price_per_base = Decimal(str(p.price_cents)) / Decimal(str(di.grams_per_unit))

            history_entries.append(PriceHistoryEntry(
                date=p.effective_date,
                price_cents=p.price_cents,
                price_per_base_unit_cents=price_per_base,
                source=p.source,
                source_reference=p.source_reference,
            ))

        dist_histories.append(DistributorPriceHistory(
            distributor_id=di.distributor_id,
            distributor_name=dist_name,
            dist_ingredient_id=di.id,
            description=di.description,
            history=history_entries,
        ))

    return IngredientPriceHistory(
        ingredient_id=ingredient.id,
        ingredient_name=ingredient.name,
        base_unit=ingredient.base_unit,
        distributors=dist_histories,
    )
