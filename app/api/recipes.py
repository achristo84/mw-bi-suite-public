"""Recipe and Menu Item CRUD endpoints."""
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.recipe import Recipe, RecipeIngredient, RecipeComponent, MenuItem, MenuItemPackaging
from app.models.ingredient import Ingredient
from app.schemas.recipe import (
    RecipeCreate,
    RecipeUpdate,
    RecipeResponse,
    RecipeWithDetails,
    RecipeList,
    RecipeSummary,
    RecipeIngredientCreate,
    RecipeIngredientResponse,
    RecipeComponentCreate,
    RecipeComponentResponse,
    MenuItemCreate,
    MenuItemUpdate,
    MenuItemResponse,
    MenuItemWithDetails,
    MenuItemList,
    MenuItemPackagingCreate,
    MenuItemPackagingResponse,
    MenuItemCostBreakdown,
    MenuAnalyzerResponse,
    PriceMoverResponse,
    RecipeImportRequest,
    RecipeImportFromDataRequest,
    RecipeImportResult,
    BatchImportRequest,
    BatchImportResult,
    RecipeCostBreakdown,
)
from app.services.cost_calculator import (
    calculate_recipe_cost,
    calculate_menu_item_cost,
    calculate_all_menu_item_costs,
    get_price_movements,
)

router = APIRouter(prefix="/recipes", tags=["recipes"])
menu_router = APIRouter(prefix="/menu-items", tags=["menu-items"])


# ============================================================================
# Recipe Endpoints
# ============================================================================


@router.get("", response_model=RecipeList)
def list_recipes(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    """List all recipes."""
    query = db.query(Recipe)
    if not include_inactive:
        query = query.filter(Recipe.is_active == True)
    recipes = query.order_by(Recipe.name).all()
    return RecipeList(recipes=recipes, count=len(recipes))


@router.get("/summary", response_model=list[RecipeSummary])
def list_recipe_summaries(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    """List recipe summaries for dropdowns."""
    query = db.query(Recipe)
    if not include_inactive:
        query = query.filter(Recipe.is_active == True)
    return query.order_by(Recipe.name).all()


@router.get("/{recipe_id}", response_model=RecipeWithDetails)
def get_recipe(
    recipe_id: UUID,
    db: Session = Depends(get_db),
):
    """Get a single recipe with all ingredients and components."""
    recipe = (
        db.query(Recipe)
        .options(
            joinedload(Recipe.ingredients).joinedload(RecipeIngredient.ingredient),
            joinedload(Recipe.components).joinedload(RecipeComponent.component_recipe),
        )
        .filter(Recipe.id == recipe_id)
        .first()
    )
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Build response with ingredient/component details
    ingredients_response = []
    for ri in recipe.ingredients:
        ingredients_response.append(
            RecipeIngredientResponse(
                id=ri.id,
                ingredient_id=ri.ingredient_id,
                quantity_grams=ri.quantity_grams,
                prep_note=ri.prep_note,
                is_optional=ri.is_optional,
                ingredient_name=ri.ingredient.name if ri.ingredient else None,
                ingredient_base_unit=ri.ingredient.base_unit if ri.ingredient else None,
            )
        )

    components_response = []
    for rc in recipe.components:
        components_response.append(
            RecipeComponentResponse(
                id=rc.id,
                component_recipe_id=rc.component_recipe_id,
                quantity=rc.quantity,
                notes=rc.notes,
                component_recipe_name=rc.component_recipe.name if rc.component_recipe else None,
                component_recipe_yield_unit=rc.component_recipe.yield_unit if rc.component_recipe else None,
                created_at=rc.created_at,
            )
        )

    return RecipeWithDetails(
        id=recipe.id,
        name=recipe.name,
        yield_quantity=recipe.yield_quantity,
        yield_unit=recipe.yield_unit,
        instructions=recipe.instructions,
        prep_time_minutes=recipe.prep_time_minutes,
        cook_time_minutes=recipe.cook_time_minutes,
        is_active=recipe.is_active,
        notes=recipe.notes,
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
        ingredients=ingredients_response,
        components=components_response,
    )


@router.get("/{recipe_id}/cost", response_model=RecipeCostBreakdown)
def get_recipe_cost(
    recipe_id: UUID,
    pricing_mode: str = Query("recent", regex="^(recent|average)$"),
    average_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """
    Get cost breakdown for a recipe.

    - pricing_mode: 'recent' uses most recent price, 'average' uses average over last N days
    - average_days: number of days to average over (only used if pricing_mode='average')
    """
    try:
        return calculate_recipe_cost(
            db,
            recipe_id,
            pricing_mode=pricing_mode,  # type: ignore
            average_days=average_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("", response_model=RecipeWithDetails, status_code=201)
def create_recipe(
    data: RecipeCreate,
    db: Session = Depends(get_db),
):
    """Create a new recipe with ingredients and components."""
    # Check for duplicate name
    existing = db.query(Recipe).filter(Recipe.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Recipe with this name already exists")

    # Create recipe
    recipe = Recipe(
        id=uuid.uuid4(),
        name=data.name,
        yield_quantity=data.yield_quantity,
        yield_unit=data.yield_unit,
        instructions=data.instructions,
        prep_time_minutes=data.prep_time_minutes,
        cook_time_minutes=data.cook_time_minutes,
        is_active=data.is_active,
        notes=data.notes,
    )
    db.add(recipe)

    # Add ingredients
    for ing_data in data.ingredients:
        # Validate ingredient exists
        ingredient = db.query(Ingredient).filter(Ingredient.id == ing_data.ingredient_id).first()
        if not ingredient:
            raise HTTPException(
                status_code=400,
                detail=f"Ingredient with ID {ing_data.ingredient_id} not found"
            )
        recipe_ingredient = RecipeIngredient(
            id=uuid.uuid4(),
            recipe_id=recipe.id,
            ingredient_id=ing_data.ingredient_id,
            quantity_grams=ing_data.quantity_grams,
            prep_note=ing_data.prep_note,
            is_optional=ing_data.is_optional,
        )
        db.add(recipe_ingredient)

    # Add components (sub-recipes)
    for comp_data in data.components:
        # Validate component recipe exists
        component_recipe = db.query(Recipe).filter(Recipe.id == comp_data.component_recipe_id).first()
        if not component_recipe:
            raise HTTPException(
                status_code=400,
                detail=f"Component recipe with ID {comp_data.component_recipe_id} not found"
            )
        # Prevent self-reference
        if comp_data.component_recipe_id == recipe.id:
            raise HTTPException(status_code=400, detail="Recipe cannot reference itself as a component")

        recipe_component = RecipeComponent(
            id=uuid.uuid4(),
            recipe_id=recipe.id,
            component_recipe_id=comp_data.component_recipe_id,
            quantity=comp_data.quantity,
            notes=comp_data.notes,
        )
        db.add(recipe_component)

    db.commit()

    # Return full recipe with details
    return get_recipe(recipe.id, db)


@router.patch("/{recipe_id}", response_model=RecipeResponse)
def update_recipe(
    recipe_id: UUID,
    data: RecipeUpdate,
    db: Session = Depends(get_db),
):
    """Update a recipe's basic info (not ingredients/components)."""
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    update_data = data.model_dump(exclude_unset=True)

    # Check for duplicate name if name is being changed
    if "name" in update_data and update_data["name"] != recipe.name:
        existing = db.query(Recipe).filter(Recipe.name == update_data["name"]).first()
        if existing:
            raise HTTPException(status_code=400, detail="Recipe with this name already exists")

    for field, value in update_data.items():
        setattr(recipe, field, value)

    db.commit()
    db.refresh(recipe)
    return recipe


@router.delete("/{recipe_id}", status_code=204)
def delete_recipe(
    recipe_id: UUID,
    db: Session = Depends(get_db),
):
    """Soft delete a recipe (sets is_active=False)."""
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    recipe.is_active = False
    db.commit()
    return None


# ============================================================================
# Recipe Ingredient Endpoints
# ============================================================================


@router.post("/{recipe_id}/ingredients", response_model=RecipeIngredientResponse, status_code=201)
def add_recipe_ingredient(
    recipe_id: UUID,
    data: RecipeIngredientCreate,
    db: Session = Depends(get_db),
):
    """Add an ingredient to a recipe."""
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    ingredient = db.query(Ingredient).filter(Ingredient.id == data.ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=400, detail="Ingredient not found")

    # Check for duplicate
    existing = (
        db.query(RecipeIngredient)
        .filter(RecipeIngredient.recipe_id == recipe_id, RecipeIngredient.ingredient_id == data.ingredient_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Ingredient already in recipe")

    recipe_ingredient = RecipeIngredient(
        id=uuid.uuid4(),
        recipe_id=recipe_id,
        ingredient_id=data.ingredient_id,
        quantity_grams=data.quantity_grams,
        prep_note=data.prep_note,
        is_optional=data.is_optional,
    )
    db.add(recipe_ingredient)
    db.commit()
    db.refresh(recipe_ingredient)

    return RecipeIngredientResponse(
        id=recipe_ingredient.id,
        ingredient_id=recipe_ingredient.ingredient_id,
        quantity_grams=recipe_ingredient.quantity_grams,
        prep_note=recipe_ingredient.prep_note,
        is_optional=recipe_ingredient.is_optional,
        ingredient_name=ingredient.name,
        ingredient_base_unit=ingredient.base_unit,
    )


@router.patch("/{recipe_id}/ingredients/{ingredient_id}", response_model=RecipeIngredientResponse)
def update_recipe_ingredient(
    recipe_id: UUID,
    ingredient_id: UUID,
    quantity_grams: float = None,
    prep_note: str = None,
    is_optional: bool = None,
    db: Session = Depends(get_db),
):
    """Update an ingredient's quantity or notes in a recipe."""
    recipe_ingredient = (
        db.query(RecipeIngredient)
        .filter(RecipeIngredient.recipe_id == recipe_id, RecipeIngredient.ingredient_id == ingredient_id)
        .first()
    )
    if not recipe_ingredient:
        raise HTTPException(status_code=404, detail="Recipe ingredient not found")

    ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()

    if quantity_grams is not None:
        recipe_ingredient.quantity_grams = quantity_grams
    if prep_note is not None:
        recipe_ingredient.prep_note = prep_note if prep_note else None
    if is_optional is not None:
        recipe_ingredient.is_optional = is_optional

    db.commit()
    db.refresh(recipe_ingredient)

    return RecipeIngredientResponse(
        id=recipe_ingredient.id,
        ingredient_id=recipe_ingredient.ingredient_id,
        quantity_grams=recipe_ingredient.quantity_grams,
        prep_note=recipe_ingredient.prep_note,
        is_optional=recipe_ingredient.is_optional,
        ingredient_name=ingredient.name if ingredient else None,
        ingredient_base_unit=ingredient.base_unit if ingredient else None,
    )


@router.delete("/{recipe_id}/ingredients/{ingredient_id}", status_code=204)
def remove_recipe_ingredient(
    recipe_id: UUID,
    ingredient_id: UUID,
    db: Session = Depends(get_db),
):
    """Remove an ingredient from a recipe."""
    recipe_ingredient = (
        db.query(RecipeIngredient)
        .filter(RecipeIngredient.recipe_id == recipe_id, RecipeIngredient.ingredient_id == ingredient_id)
        .first()
    )
    if not recipe_ingredient:
        raise HTTPException(status_code=404, detail="Recipe ingredient not found")

    db.delete(recipe_ingredient)
    db.commit()
    return None


# ============================================================================
# Recipe Component Endpoints
# ============================================================================


@router.post("/{recipe_id}/components", response_model=RecipeComponentResponse, status_code=201)
def add_recipe_component(
    recipe_id: UUID,
    data: RecipeComponentCreate,
    db: Session = Depends(get_db),
):
    """Add a sub-recipe component to a recipe."""
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    component_recipe = db.query(Recipe).filter(Recipe.id == data.component_recipe_id).first()
    if not component_recipe:
        raise HTTPException(status_code=400, detail="Component recipe not found")

    # Prevent self-reference
    if data.component_recipe_id == recipe_id:
        raise HTTPException(status_code=400, detail="Recipe cannot reference itself as a component")

    # Check for duplicate
    existing = (
        db.query(RecipeComponent)
        .filter(RecipeComponent.recipe_id == recipe_id, RecipeComponent.component_recipe_id == data.component_recipe_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Component already in recipe")

    recipe_component = RecipeComponent(
        id=uuid.uuid4(),
        recipe_id=recipe_id,
        component_recipe_id=data.component_recipe_id,
        quantity=data.quantity,
        notes=data.notes,
    )
    db.add(recipe_component)
    db.commit()
    db.refresh(recipe_component)

    return RecipeComponentResponse(
        id=recipe_component.id,
        component_recipe_id=recipe_component.component_recipe_id,
        quantity=recipe_component.quantity,
        notes=recipe_component.notes,
        component_recipe_name=component_recipe.name,
        component_recipe_yield_unit=component_recipe.yield_unit,
        created_at=recipe_component.created_at,
    )


@router.delete("/{recipe_id}/components/{component_recipe_id}", status_code=204)
def remove_recipe_component(
    recipe_id: UUID,
    component_recipe_id: UUID,
    db: Session = Depends(get_db),
):
    """Remove a sub-recipe component from a recipe."""
    recipe_component = (
        db.query(RecipeComponent)
        .filter(RecipeComponent.recipe_id == recipe_id, RecipeComponent.component_recipe_id == component_recipe_id)
        .first()
    )
    if not recipe_component:
        raise HTTPException(status_code=404, detail="Recipe component not found")

    db.delete(recipe_component)
    db.commit()
    return None


# ============================================================================
# Recipe Import Endpoints
# ============================================================================


@router.post("/import/from-sheet", response_model=RecipeImportResult)
def import_recipe_from_sheet(
    data: RecipeImportRequest,
    db: Session = Depends(get_db),
):
    """
    Import a recipe from a Google Sheet.

    Parses the sheet, matches ingredients to canonical database,
    and creates the recipe if all ingredients are mapped.
    """
    from app.services.sheets_service import get_sheets_service
    from app.services.recipe_importer import import_recipe_from_sheet_data

    try:
        # Get sheet data
        sheets_service = get_sheets_service()
        sheet_data = sheets_service.get_sheet_data(
            spreadsheet_id=data.spreadsheet_id,
            sheet_name=data.sheet_name
        )

        if not sheet_data:
            raise HTTPException(status_code=400, detail="Sheet is empty or could not be read")

        # Import the recipe
        result = import_recipe_from_sheet_data(
            db=db,
            sheet_data=sheet_data,
            auto_create_ingredients=data.auto_create_ingredients
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post("/import/from-data", response_model=RecipeImportResult)
def import_recipe_from_data(
    data: RecipeImportFromDataRequest,
    db: Session = Depends(get_db),
):
    """
    Import a recipe from raw sheet data (for testing or manual import).

    Expects a 2D array of cell values in the standard recipe format.
    """
    from app.services.recipe_importer import import_recipe_from_sheet_data

    try:
        result = import_recipe_from_sheet_data(
            db=db,
            sheet_data=data.sheet_data,
            auto_create_ingredients=data.auto_create_ingredients
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post("/import/batch", response_model=BatchImportResult)
def import_recipes_batch(
    data: BatchImportRequest,
    db: Session = Depends(get_db),
):
    """
    Import multiple recipes from a Google Spreadsheet.

    If sheet_names is empty, attempts to import all sheets.
    Each sheet should contain one recipe in the standard format.
    """
    from app.services.sheets_service import get_sheets_service
    from app.services.recipe_importer import import_recipe_from_sheet_data

    sheets_service = get_sheets_service()

    # Get spreadsheet metadata
    try:
        metadata = sheets_service.get_spreadsheet_metadata(data.spreadsheet_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not access spreadsheet: {str(e)}")

    # Determine which sheets to import
    available_sheets = [s['title'] for s in metadata['sheets']]
    if data.sheet_names:
        sheets_to_import = [s for s in data.sheet_names if s in available_sheets]
    else:
        sheets_to_import = available_sheets

    results = []
    errors = []

    for sheet_name in sheets_to_import:
        try:
            sheet_data = sheets_service.get_sheet_data(
                spreadsheet_id=data.spreadsheet_id,
                sheet_name=sheet_name
            )

            if not sheet_data or len(sheet_data) < 3:
                errors.append({
                    'sheet_name': sheet_name,
                    'error': 'Sheet is empty or too short to contain a recipe'
                })
                continue

            result = import_recipe_from_sheet_data(
                db=db,
                sheet_data=sheet_data,
                auto_create_ingredients=data.auto_create_ingredients
            )
            results.append(result)

        except Exception as e:
            errors.append({
                'sheet_name': sheet_name,
                'error': str(e)
            })

    return {
        'total_sheets': len(sheets_to_import),
        'successful': len([r for r in results if r.get('created', False)]),
        'failed': len(errors) + len([r for r in results if not r.get('created', False)]),
        'results': results,
        'errors': errors,
    }


@router.get("/import/preview/{spreadsheet_id}")
def preview_spreadsheet(
    spreadsheet_id: str,
    db: Session = Depends(get_db),
):
    """
    Preview a spreadsheet to see available sheets before importing.
    """
    from app.services.sheets_service import get_sheets_service

    try:
        sheets_service = get_sheets_service()
        metadata = sheets_service.get_spreadsheet_metadata(spreadsheet_id)

        return {
            'spreadsheet_title': metadata['title'],
            'sheets': [
                {'name': s['title'], 'index': s['index']}
                for s in metadata['sheets']
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not access spreadsheet: {str(e)}")


# ============================================================================
# Menu Item Endpoints
# ============================================================================


@menu_router.get("/analyze", response_model=MenuAnalyzerResponse)
def analyze_menu_items(
    pricing_mode: str = Query("recent", regex="^(recent|average)$"),
    average_days: int = Query(30, ge=1, le=365),
    category: str = Query(None, description="Filter by category"),
    db: Session = Depends(get_db),
):
    """
    Analyze all menu items with costs, margins, and margin health status.

    Returns per-item analysis and summary statistics.
    Margin thresholds: <30% = healthy, 30-35% = warning, >35% = danger.
    """
    return calculate_all_menu_item_costs(
        db,
        pricing_mode=pricing_mode,  # type: ignore
        average_days=average_days,
        category=category,
    )


@menu_router.get("/analyze/movers", response_model=PriceMoverResponse)
def get_menu_movers(
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
    pricing_mode: str = Query("recent", regex="^(recent|average)$"),
    average_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """
    Get ingredients and menu items with the biggest price changes.

    Returns ingredient-level price movements and their impact on menu item costs.
    """
    return get_price_movements(
        db,
        days_back=days,
        pricing_mode=pricing_mode,  # type: ignore
        average_days=average_days,
    )


@menu_router.get("/{menu_item_id}/cost", response_model=MenuItemCostBreakdown)
def get_menu_item_cost(
    menu_item_id: UUID,
    pricing_mode: str = Query("recent", regex="^(recent|average)$"),
    average_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """
    Get full cost breakdown for a single menu item.

    Includes recipe cost (scaled by portion), packaging cost, margin, and food cost %.
    """
    try:
        return calculate_menu_item_cost(
            db,
            menu_item_id,
            pricing_mode=pricing_mode,  # type: ignore
            average_days=average_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@menu_router.get("", response_model=MenuItemList)
def list_menu_items(
    include_inactive: bool = False,
    category: str = Query(None, description="Filter by category"),
    db: Session = Depends(get_db),
):
    """List all menu items."""
    query = db.query(MenuItem)
    if not include_inactive:
        query = query.filter(MenuItem.is_active == True)
    if category:
        query = query.filter(MenuItem.category == category)
    menu_items = query.order_by(MenuItem.category, MenuItem.name).all()
    return MenuItemList(menu_items=menu_items, count=len(menu_items))


@menu_router.get("/{menu_item_id}", response_model=MenuItemWithDetails)
def get_menu_item(
    menu_item_id: UUID,
    db: Session = Depends(get_db),
):
    """Get a single menu item with recipe and packaging details."""
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
        raise HTTPException(status_code=404, detail="Menu item not found")

    # Build packaging response
    packaging_response = []
    for pkg in menu_item.packaging:
        packaging_response.append(
            MenuItemPackagingResponse(
                id=pkg.id,
                ingredient_id=pkg.ingredient_id,
                quantity=pkg.quantity,
                usage_rate=pkg.usage_rate,
                notes=pkg.notes,
                ingredient_name=pkg.ingredient.name if pkg.ingredient else None,
                created_at=pkg.created_at,
            )
        )

    return MenuItemWithDetails(
        id=menu_item.id,
        name=menu_item.name,
        recipe_id=menu_item.recipe_id,
        portion_of_recipe=menu_item.portion_of_recipe,
        menu_price_cents=menu_item.menu_price_cents,
        category=menu_item.category,
        toast_id=menu_item.toast_id,
        is_active=menu_item.is_active,
        created_at=menu_item.created_at,
        updated_at=menu_item.updated_at,
        recipe_name=menu_item.recipe.name if menu_item.recipe else None,
        packaging=packaging_response,
    )


@menu_router.post("", response_model=MenuItemWithDetails, status_code=201)
def create_menu_item(
    data: MenuItemCreate,
    db: Session = Depends(get_db),
):
    """Create a new menu item with optional packaging."""
    # Validate recipe if provided
    if data.recipe_id:
        recipe = db.query(Recipe).filter(Recipe.id == data.recipe_id).first()
        if not recipe:
            raise HTTPException(status_code=400, detail="Recipe not found")

    # Create menu item
    menu_item = MenuItem(
        id=uuid.uuid4(),
        name=data.name,
        recipe_id=data.recipe_id,
        portion_of_recipe=data.portion_of_recipe,
        menu_price_cents=data.menu_price_cents,
        category=data.category,
        toast_id=data.toast_id,
        is_active=data.is_active,
    )
    db.add(menu_item)

    # Add packaging
    for pkg_data in data.packaging:
        # Validate packaging ingredient exists and is type 'packaging'
        ingredient = db.query(Ingredient).filter(Ingredient.id == pkg_data.ingredient_id).first()
        if not ingredient:
            raise HTTPException(
                status_code=400,
                detail=f"Packaging ingredient with ID {pkg_data.ingredient_id} not found"
            )

        packaging = MenuItemPackaging(
            id=uuid.uuid4(),
            menu_item_id=menu_item.id,
            ingredient_id=pkg_data.ingredient_id,
            quantity=pkg_data.quantity,
            usage_rate=pkg_data.usage_rate,
            notes=pkg_data.notes,
        )
        db.add(packaging)

    db.commit()

    # Return full menu item with details
    return get_menu_item(menu_item.id, db)


@menu_router.patch("/{menu_item_id}", response_model=MenuItemResponse)
def update_menu_item(
    menu_item_id: UUID,
    data: MenuItemUpdate,
    db: Session = Depends(get_db),
):
    """Update a menu item's basic info (not packaging)."""
    menu_item = db.query(MenuItem).filter(MenuItem.id == menu_item_id).first()
    if not menu_item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    update_data = data.model_dump(exclude_unset=True)

    # Validate recipe if being changed
    if "recipe_id" in update_data and update_data["recipe_id"]:
        recipe = db.query(Recipe).filter(Recipe.id == update_data["recipe_id"]).first()
        if not recipe:
            raise HTTPException(status_code=400, detail="Recipe not found")

    for field, value in update_data.items():
        setattr(menu_item, field, value)

    db.commit()
    db.refresh(menu_item)
    return menu_item


@menu_router.delete("/{menu_item_id}", status_code=204)
def delete_menu_item(
    menu_item_id: UUID,
    db: Session = Depends(get_db),
):
    """Soft delete a menu item (sets is_active=False)."""
    menu_item = db.query(MenuItem).filter(MenuItem.id == menu_item_id).first()
    if not menu_item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    menu_item.is_active = False
    db.commit()
    return None


# ============================================================================
# Menu Item Packaging Endpoints
# ============================================================================


@menu_router.post("/{menu_item_id}/packaging", response_model=MenuItemPackagingResponse, status_code=201)
def add_menu_item_packaging(
    menu_item_id: UUID,
    data: MenuItemPackagingCreate,
    db: Session = Depends(get_db),
):
    """Add a packaging item to a menu item."""
    menu_item = db.query(MenuItem).filter(MenuItem.id == menu_item_id).first()
    if not menu_item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    ingredient = db.query(Ingredient).filter(Ingredient.id == data.ingredient_id).first()
    if not ingredient:
        raise HTTPException(status_code=400, detail="Ingredient not found")

    # Check for duplicate
    existing = (
        db.query(MenuItemPackaging)
        .filter(MenuItemPackaging.menu_item_id == menu_item_id, MenuItemPackaging.ingredient_id == data.ingredient_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Packaging item already on menu item")

    packaging = MenuItemPackaging(
        id=uuid.uuid4(),
        menu_item_id=menu_item_id,
        ingredient_id=data.ingredient_id,
        quantity=data.quantity,
        usage_rate=data.usage_rate,
        notes=data.notes,
    )
    db.add(packaging)
    db.commit()
    db.refresh(packaging)

    return MenuItemPackagingResponse(
        id=packaging.id,
        ingredient_id=packaging.ingredient_id,
        quantity=packaging.quantity,
        usage_rate=packaging.usage_rate,
        notes=packaging.notes,
        ingredient_name=ingredient.name,
        created_at=packaging.created_at,
    )


@menu_router.delete("/{menu_item_id}/packaging/{ingredient_id}", status_code=204)
def remove_menu_item_packaging(
    menu_item_id: UUID,
    ingredient_id: UUID,
    db: Session = Depends(get_db),
):
    """Remove a packaging item from a menu item."""
    packaging = (
        db.query(MenuItemPackaging)
        .filter(MenuItemPackaging.menu_item_id == menu_item_id, MenuItemPackaging.ingredient_id == ingredient_id)
        .first()
    )
    if not packaging:
        raise HTTPException(status_code=404, detail="Packaging item not found")

    db.delete(packaging)
    db.commit()
    return None
