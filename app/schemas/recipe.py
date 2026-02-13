"""Pydantic schemas for Recipe, MenuItem, and related models."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# Recipe Schemas
# ============================================================================


class RecipeIngredientBase(BaseModel):
    """Base recipe ingredient fields."""

    ingredient_id: UUID
    quantity_grams: Decimal = Field(..., description="Quantity in base units (g, ml, or each)")
    prep_note: Optional[str] = Field(None, max_length=100, description="e.g., 'diced', 'room temperature'")
    is_optional: bool = False


class RecipeIngredientCreate(RecipeIngredientBase):
    """Schema for creating a recipe ingredient."""

    pass


class RecipeIngredientResponse(RecipeIngredientBase):
    """Recipe ingredient response with ingredient details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ingredient_name: Optional[str] = None
    ingredient_base_unit: Optional[str] = None


class RecipeComponentBase(BaseModel):
    """Base recipe component fields (sub-recipes)."""

    component_recipe_id: UUID
    quantity: Decimal = Field(..., description="Amount of component recipe's yield needed")
    notes: Optional[str] = None


class RecipeComponentCreate(RecipeComponentBase):
    """Schema for creating a recipe component."""

    pass


class RecipeComponentResponse(RecipeComponentBase):
    """Recipe component response with recipe details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    component_recipe_name: Optional[str] = None
    component_recipe_yield_unit: Optional[str] = None
    created_at: datetime


class RecipeBase(BaseModel):
    """Base recipe fields."""

    name: str = Field(..., min_length=1, max_length=100)
    yield_quantity: Decimal = Field(..., gt=0, description="Number of portions/units this recipe makes")
    yield_unit: str = Field(..., max_length=20, description="e.g., 'servings', 'grams', 'quarts'")
    yield_weight_grams: Optional[Decimal] = Field(None, gt=0, description="Actual yield weight in grams (for costing when volume != weight)")
    instructions: Optional[str] = None
    prep_time_minutes: Optional[int] = Field(None, ge=0)
    cook_time_minutes: Optional[int] = Field(None, ge=0)
    is_active: bool = True
    notes: Optional[str] = None


class RecipeCreate(RecipeBase):
    """Schema for creating a recipe."""

    ingredients: list[RecipeIngredientCreate] = []
    components: list[RecipeComponentCreate] = []


class RecipeUpdate(BaseModel):
    """Schema for updating a recipe. All fields optional."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    yield_quantity: Optional[Decimal] = Field(None, gt=0)
    yield_unit: Optional[str] = None
    yield_weight_grams: Optional[Decimal] = Field(None, gt=0)
    instructions: Optional[str] = None
    prep_time_minutes: Optional[int] = Field(None, ge=0)
    cook_time_minutes: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class RecipeResponse(RecipeBase):
    """Full recipe response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class RecipeWithDetails(RecipeResponse):
    """Recipe with ingredients and components."""

    ingredients: list[RecipeIngredientResponse] = []
    components: list[RecipeComponentResponse] = []


class RecipeList(BaseModel):
    """Schema for list of recipes."""

    recipes: list[RecipeResponse]
    count: int


class RecipeSummary(BaseModel):
    """Brief recipe summary for dropdowns and references."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    yield_quantity: Decimal
    yield_unit: str
    yield_weight_grams: Optional[Decimal] = None
    is_active: bool


# ============================================================================
# Menu Item Schemas
# ============================================================================


class MenuItemPackagingBase(BaseModel):
    """Base menu item packaging fields."""

    ingredient_id: UUID
    quantity: Decimal = Field(default=1, ge=0, description="How many of this packaging item per menu item")
    usage_rate: Decimal = Field(default=1.0, ge=0, le=1, description="0.0-1.0, e.g., 0.5 = used 50% of the time")
    notes: Optional[str] = None


class MenuItemPackagingCreate(MenuItemPackagingBase):
    """Schema for creating menu item packaging."""

    pass


class MenuItemPackagingResponse(MenuItemPackagingBase):
    """Menu item packaging response with ingredient details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ingredient_name: Optional[str] = None
    created_at: datetime


class MenuItemBase(BaseModel):
    """Base menu item fields."""

    name: str = Field(..., min_length=1, max_length=100)
    recipe_id: Optional[UUID] = Field(None, description="Nullable for retail items without recipe")
    portion_of_recipe: Decimal = Field(default=1.0, gt=0, description="Fraction of recipe yield per menu item")
    menu_price_cents: int = Field(..., ge=0, description="Menu price in cents")
    category: Optional[str] = Field(None, max_length=50, description="e.g., 'breakfast', 'drinks', 'retail'")
    toast_id: Optional[str] = Field(None, max_length=50, description="Toast POS item ID for sync")
    is_active: bool = True


class MenuItemCreate(MenuItemBase):
    """Schema for creating a menu item."""

    packaging: list[MenuItemPackagingCreate] = []


class MenuItemUpdate(BaseModel):
    """Schema for updating a menu item. All fields optional."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    recipe_id: Optional[UUID] = None
    portion_of_recipe: Optional[Decimal] = Field(None, gt=0)
    menu_price_cents: Optional[int] = Field(None, ge=0)
    category: Optional[str] = None
    toast_id: Optional[str] = None
    is_active: Optional[bool] = None


class MenuItemResponse(MenuItemBase):
    """Full menu item response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class MenuItemWithDetails(MenuItemResponse):
    """Menu item with recipe and packaging details."""

    recipe_name: Optional[str] = None
    packaging: list[MenuItemPackagingResponse] = []


class MenuItemList(BaseModel):
    """Schema for list of menu items."""

    menu_items: list[MenuItemResponse]
    count: int


class MenuItemSummary(BaseModel):
    """Brief menu item summary."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    menu_price_cents: int
    category: Optional[str] = None
    is_active: bool


# ============================================================================
# Cost Calculation Schemas (for future use)
# ============================================================================


class IngredientCostBreakdown(BaseModel):
    """Cost breakdown for a single ingredient in a recipe."""

    ingredient_id: UUID
    ingredient_name: str
    ingredient_base_unit: str
    quantity_grams: Decimal
    price_per_base_unit_cents: Optional[Decimal] = None
    cost_cents: Optional[int] = None
    distributor_name: Optional[str] = None
    has_price: bool = False


class RecipeCostBreakdown(BaseModel):
    """Full cost breakdown for a recipe."""

    recipe_id: UUID
    recipe_name: str
    yield_quantity: Decimal
    yield_unit: str
    yield_weight_grams: Optional[Decimal] = None
    ingredients: list[IngredientCostBreakdown] = []
    components: list["RecipeCostBreakdown"] = []  # For sub-recipes
    total_ingredient_cost_cents: int = 0
    total_component_cost_cents: int = 0
    total_cost_cents: int = 0
    cost_per_unit_cents: Decimal = Decimal("0")
    cost_per_gram_cents: Optional[Decimal] = None  # For component costing
    has_unpriced_ingredients: bool = False
    unpriced_count: int = 0


class MenuItemCostBreakdown(BaseModel):
    """Full cost breakdown for a menu item."""

    menu_item_id: UUID
    name: str
    menu_price_cents: int
    recipe_cost_cents: Optional[int] = None
    packaging_cost_cents: int = 0
    total_cost_cents: int = 0
    gross_margin_cents: int = 0
    food_cost_percent: Decimal = Decimal("0")
    recipe_cost_breakdown: Optional[RecipeCostBreakdown] = None
    packaging_breakdown: list["PackagingCostItem"] = []
    has_unpriced_ingredients: bool = False
    margin_status: str = "healthy"  # healthy, warning, danger


class PackagingCostItem(BaseModel):
    """Cost for a single packaging item."""

    ingredient_id: UUID
    ingredient_name: str
    quantity: Decimal
    usage_rate: Decimal
    price_per_unit_cents: Optional[Decimal] = None
    cost_cents: Optional[int] = None
    has_price: bool = False


class MenuItemAnalysis(BaseModel):
    """Single menu item with margin analysis."""

    id: UUID
    name: str
    category: Optional[str] = None
    menu_price_cents: int
    total_cost_cents: int
    food_cost_percent: Decimal
    gross_margin_cents: int
    margin_status: str  # healthy, warning, danger
    recipe_name: Optional[str] = None
    portion_of_recipe: Decimal
    has_unpriced_ingredients: bool = False


class CategorySummary(BaseModel):
    """Per-category margin aggregation."""

    total_items: int = 0
    avg_food_cost_percent: Decimal = Decimal("0")
    healthy_count: int = 0
    warning_count: int = 0
    danger_count: int = 0


class MenuAnalyzerSummary(BaseModel):
    """Summary stats for the menu analyzer."""

    total_items: int = 0
    avg_food_cost_percent: Decimal = Decimal("0")
    healthy_count: int = 0
    warning_count: int = 0
    danger_count: int = 0
    by_category: dict[str, CategorySummary] = {}


class MenuAnalyzerResponse(BaseModel):
    """Full menu analyzer response."""

    items: list[MenuItemAnalysis] = []
    summary: MenuAnalyzerSummary = MenuAnalyzerSummary()


class AffectedMenuItem(BaseModel):
    """A menu item affected by a price change."""

    name: str
    cost_impact_cents: int


class IngredientMover(BaseModel):
    """An ingredient with a significant price change."""

    ingredient_id: UUID
    ingredient_name: str
    old_price_per_unit: Optional[Decimal] = None
    new_price_per_unit: Optional[Decimal] = None
    change_percent: Optional[Decimal] = None
    affected_items: list[AffectedMenuItem] = []


class ItemMover(BaseModel):
    """A menu item with significant cost change."""

    menu_item_id: UUID
    menu_item_name: str
    old_total_cost: int
    new_total_cost: int
    cost_change_cents: int
    new_food_cost_percent: Decimal


class PriceMoverResponse(BaseModel):
    """Price movers response."""

    period_days: int = 7
    ingredient_movers: list[IngredientMover] = []
    item_movers: list[ItemMover] = []


# ============================================================================
# Recipe Import Schemas
# ============================================================================


class UnmappedIngredientInfo(BaseModel):
    """Info about an unmapped ingredient during import."""

    name: str
    quantity: Decimal
    unit: str


class RecipeImportRequest(BaseModel):
    """Request to import a recipe from Google Sheets."""

    spreadsheet_id: str = Field(..., description="Google Sheets spreadsheet ID")
    sheet_name: str = Field(..., description="Name of the sheet/tab containing the recipe")
    auto_create_ingredients: bool = Field(
        default=False,
        description="If true, automatically create missing canonical ingredients"
    )


class RecipeImportFromDataRequest(BaseModel):
    """Request to import a recipe from raw sheet data (for testing/manual import)."""

    sheet_data: list[list] = Field(..., description="2D array of cell values from the sheet")
    auto_create_ingredients: bool = Field(default=False)


class RecipeImportResult(BaseModel):
    """Result of a recipe import attempt."""

    recipe_name: str
    yield_quantity: Decimal
    yield_unit: str
    total_ingredients: int
    matched_ingredients: int
    unmapped_ingredients: list[UnmappedIngredientInfo] = []
    auto_created_ingredients: list[str] = []
    warnings: list[str] = []
    recipe_id: Optional[UUID] = None
    created: bool = False


class BatchImportRequest(BaseModel):
    """Request to import multiple recipes from a spreadsheet."""

    spreadsheet_id: str = Field(..., description="Google Sheets spreadsheet ID")
    sheet_names: list[str] = Field(default=[], description="Specific sheets to import (empty = all)")
    auto_create_ingredients: bool = Field(default=False)


class BatchImportResult(BaseModel):
    """Result of batch recipe import."""

    total_sheets: int
    successful: int
    failed: int
    results: list[RecipeImportResult] = []
    errors: list[dict] = []


# Update forward references
RecipeCostBreakdown.model_rebuild()
MenuItemCostBreakdown.model_rebuild()
