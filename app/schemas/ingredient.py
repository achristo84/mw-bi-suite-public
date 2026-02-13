"""Pydantic schemas for Ingredient and related models."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.services.units import INGREDIENT_CATEGORIES, BaseUnit


INGREDIENT_TYPES = ["raw", "component", "packaging"]


class IngredientBase(BaseModel):
    """Base ingredient fields."""

    name: str = Field(..., min_length=1, max_length=100)
    category: Optional[str] = Field(None, description=f"One of: {', '.join(INGREDIENT_CATEGORIES)}")
    base_unit: str = Field(..., description="Base unit: 'g', 'ml', or 'each'")
    ingredient_type: str = Field(default="raw", description=f"One of: {', '.join(INGREDIENT_TYPES)}")
    source_recipe_id: Optional[UUID] = Field(None, description="For component ingredients, the recipe that produces this ingredient")
    storage_type: Optional[str] = Field(None, description="Storage: 'refrigerated', 'frozen', 'dry', 'ambient'")
    shelf_life_days: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class IngredientCreate(IngredientBase):
    """Schema for creating an ingredient."""

    pass


class IngredientUpdate(BaseModel):
    """Schema for updating an ingredient. All fields optional."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = None
    base_unit: Optional[str] = None
    ingredient_type: Optional[str] = None
    source_recipe_id: Optional[UUID] = None
    storage_type: Optional[str] = None
    shelf_life_days: Optional[int] = Field(None, ge=0)
    par_level_base_units: Optional[Decimal] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class IngredientResponse(IngredientBase):
    """Schema for ingredient response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_recipe_name: Optional[str] = None  # Populated from relationship
    par_level_base_units: Optional[Decimal] = None
    yield_factor: Decimal = Decimal("1.0")
    created_at: datetime
    updated_at: datetime


class IngredientList(BaseModel):
    """Schema for list of ingredients."""

    ingredients: list[IngredientResponse]
    count: int


class IngredientWithVariants(IngredientResponse):
    """Ingredient with its distributor variants."""

    variants: list["DistIngredientSummary"] = []


class IngredientWithPrice(IngredientResponse):
    """Ingredient with current best price information."""

    current_price_per_base_unit_cents: Optional[Decimal] = None
    best_distributor_name: Optional[str] = None
    has_price: bool = False
    variant_count: int = 0


class IngredientWithPriceList(BaseModel):
    """Schema for list of ingredients with prices."""

    ingredients: list[IngredientWithPrice]
    count: int


# Dist Ingredient schemas
class DistIngredientBase(BaseModel):
    """Base dist_ingredient fields."""

    distributor_id: UUID
    ingredient_id: Optional[UUID] = None
    sku: Optional[str] = None
    description: str
    pack_size: Optional[Decimal] = None
    pack_unit: Optional[str] = None
    units_per_pack: Optional[int] = 1
    grams_per_unit: Optional[Decimal] = None
    quality_tier: Optional[str] = None
    quality_notes: Optional[str] = None
    notes: Optional[str] = None


class DistIngredientCreate(DistIngredientBase):
    """Schema for creating a dist_ingredient."""

    pass


class DistIngredientUpdate(BaseModel):
    """Schema for updating a dist_ingredient."""

    ingredient_id: Optional[UUID] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    pack_size: Optional[Decimal] = None
    pack_unit: Optional[str] = None
    units_per_pack: Optional[int] = None
    grams_per_unit: Optional[Decimal] = None
    quality_tier: Optional[str] = None
    quality_notes: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class DistIngredientSummary(BaseModel):
    """Summary of a dist_ingredient for embedding in other responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    distributor_id: UUID
    distributor_name: Optional[str] = None
    sku: Optional[str] = None
    description: str
    pack_size: Optional[Decimal] = None
    pack_unit: Optional[str] = None
    is_active: bool


class DistIngredientResponse(DistIngredientBase):
    """Full dist_ingredient response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DistIngredientWithPrice(DistIngredientResponse):
    """Dist ingredient with current price info."""

    current_price_cents: Optional[int] = None
    price_per_base_unit_cents: Optional[Decimal] = None
    price_effective_date: Optional[datetime] = None


class DistIngredientList(BaseModel):
    """Schema for list of dist_ingredients."""

    dist_ingredients: list[DistIngredientResponse]
    count: int


class UnmappedDistIngredient(BaseModel):
    """Unmapped dist_ingredient with extra context for mapping UI."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    distributor_id: UUID
    distributor_name: str
    sku: Optional[str] = None
    description: str
    pack_size: Optional[Decimal] = None
    pack_unit: Optional[str] = None
    grams_per_unit: Optional[Decimal] = None
    # Parsed pack info
    parsed_pack_quantity: Optional[Decimal] = None
    parsed_unit_quantity: Optional[Decimal] = None
    parsed_unit: Optional[str] = None
    parsed_total_base_units: Optional[Decimal] = None
    parsed_base_unit: Optional[str] = None
    # Price context
    last_price_cents: Optional[int] = None
    last_price_date: Optional[datetime] = None
    created_at: datetime


class UnmappedDistIngredientList(BaseModel):
    """List of unmapped dist_ingredients for mapping UI."""

    items: list[UnmappedDistIngredient]
    count: int


class MapDistIngredientRequest(BaseModel):
    """Request to map a dist_ingredient to a canonical ingredient."""

    ingredient_id: UUID
    pack_size: Optional[Decimal] = None
    pack_unit: Optional[str] = None
    grams_per_unit: Optional[Decimal] = None


class CreateAndMapRequest(BaseModel):
    """Request to create a new canonical ingredient and map the dist_ingredient to it."""

    # New ingredient details
    ingredient_name: str
    ingredient_category: Optional[str] = None
    ingredient_base_unit: str  # g, ml, each
    # Mapping details
    pack_size: Optional[Decimal] = None
    pack_unit: Optional[str] = None
    grams_per_unit: Optional[Decimal] = None


# Mapping suggestion schema
class MappingSuggestion(BaseModel):
    """LLM-suggested mapping for a dist_ingredient."""

    dist_ingredient_id: UUID
    suggested_ingredient_id: Optional[UUID] = None
    suggested_ingredient_name: Optional[str] = None
    suggested_new_ingredient: bool = False
    suggested_pack_size: Optional[Decimal] = None
    suggested_pack_unit: Optional[str] = None
    suggested_grams_per_unit: Optional[Decimal] = None
    confidence: float = Field(..., ge=0, le=1)
    reasoning: Optional[str] = None


# ============================================================================
# Price Comparison Schemas
# ============================================================================


class DistributorPrice(BaseModel):
    """Price info for a single distributor variant."""

    distributor_id: Optional[UUID] = None  # None for component ingredients (price from recipe)
    distributor_name: str
    dist_ingredient_id: Optional[UUID] = None  # None for component ingredients
    sku: Optional[str] = None
    description: Optional[str] = None
    pack_size: Optional[Decimal] = None
    pack_unit: Optional[str] = None
    grams_per_unit: Optional[Decimal] = None
    price_cents: Optional[int] = None
    price_per_base_unit_cents: Optional[Decimal] = None
    effective_date: Optional[datetime] = None
    is_best_price: bool = False


class IngredientPriceComparison(BaseModel):
    """Price comparison for a single ingredient across all distributors."""

    model_config = ConfigDict(from_attributes=True)

    ingredient_id: UUID
    ingredient_name: str
    category: Optional[str] = None
    base_unit: str
    distributor_prices: list[DistributorPrice] = []
    best_price_per_base_unit: Optional[Decimal] = None
    best_distributor_id: Optional[UUID] = None
    price_spread_percent: Optional[Decimal] = None  # (max-min)/min * 100


class PriceComparisonMatrix(BaseModel):
    """Full price comparison matrix for dashboard."""

    ingredients: list[IngredientPriceComparison]
    distributors: list[dict]  # [{id, name}]
    count: int
    total_potential_savings_cents: Optional[int] = None


class PriceHistoryEntry(BaseModel):
    """Single price history entry."""

    date: datetime
    price_cents: int
    price_per_base_unit_cents: Optional[Decimal] = None
    source: Optional[str] = None
    source_reference: Optional[str] = None


class DistributorPriceHistory(BaseModel):
    """Price history for a single distributor variant."""

    distributor_id: UUID
    distributor_name: str
    dist_ingredient_id: UUID
    description: str
    history: list[PriceHistoryEntry] = []


class IngredientPriceHistory(BaseModel):
    """Full price history for an ingredient across distributors."""

    ingredient_id: UUID
    ingredient_name: str
    base_unit: str
    distributors: list[DistributorPriceHistory] = []


# ============================================================================
# Manual Pricing Schemas
# ============================================================================


class ManualPriceRequest(BaseModel):
    """Request to add a manual price for an ingredient."""

    distributor_id: UUID
    price_cents: int = Field(..., ge=0, description="Total price for the pack in cents")
    total_base_units: Decimal = Field(..., gt=0, description="Total base units (g/ml/each) in the pack")
    pack_description: Optional[str] = Field(None, description="Pack description e.g. '12 x 1LB'")
    effective_date: Optional[datetime] = Field(None, description="When this price became effective")
    notes: Optional[str] = None


class ManualPriceResponse(BaseModel):
    """Response after adding a manual price."""

    dist_ingredient_id: UUID
    price_history_id: UUID
    price_per_base_unit_cents: Decimal


class FromInvoicePriceRequest(BaseModel):
    """Request to add a price from an existing invoice line."""

    invoice_line_id: UUID = Field(..., description="The invoice line to use as price source")
    grams_per_unit: Decimal = Field(..., gt=0, description="Base units (g/ml/each) per invoice unit")
    remap_to_ingredient: bool = Field(
        default=False,
        description="If the line is already mapped to a different ingredient, remap it"
    )


class FromInvoicePriceResponse(BaseModel):
    """Response after adding a price from an invoice."""

    dist_ingredient_id: UUID
    price_history_id: UUID
    price_per_base_unit_cents: Decimal
    remapped: bool = Field(default=False, description="Whether the line was remapped to this ingredient")
    previous_ingredient_name: Optional[str] = Field(None, description="If remapped, the previous ingredient name")


class ParsedPriceItemResponse(BaseModel):
    """A single parsed price item."""

    description: str
    sku: Optional[str] = None
    pack_size: Optional[str] = None
    pack_unit: Optional[str] = None
    unit_contents: Optional[float] = None
    unit_contents_unit: Optional[str] = None
    price_cents: int
    price_type: str  # "case" or "unit"
    total_base_units: Optional[float] = None
    base_unit: Optional[str] = None
    price_per_base_unit_cents: Optional[float] = None
    raw_text: str
    confidence: float = Field(default=0.5, description="Match confidence 0.0-1.0")


class ParsePriceContentRequest(BaseModel):
    """Request to parse pricing content."""

    content: str = Field(..., description="Content to parse (base64 for binary, plain text otherwise)")
    content_type: str = Field(
        ...,
        description="Content type: image/png, image/jpeg, application/pdf, text/plain, text/email"
    )
    distributor_id: Optional[UUID] = Field(None, description="Distributor ID (null for one-off)")
    ingredient_name: Optional[str] = Field(None, description="Ingredient name for fuzzy matching")
    ingredient_category: Optional[str] = Field(None, description="Ingredient category for context")
    ingredient_base_unit: Optional[str] = Field(None, description="Base unit (g, ml, each)")
    custom_prompt: Optional[str] = Field(None, description="Custom prompt to use instead of default")


class ParsePriceContentResponse(BaseModel):
    """Response from parsing price content."""

    items: list[ParsedPriceItemResponse]
    detected_distributor: Optional[str] = None
    document_date: Optional[str] = None
    prompt_used: str = ""


class SaveParsedPriceRequest(BaseModel):
    """Request to save a parsed price item."""

    description: str
    sku: Optional[str] = None
    pack_description: Optional[str] = None
    total_base_units: Decimal = Field(..., gt=0)
    price_cents: int = Field(..., ge=0)
    distributor_id: Optional[UUID] = Field(None, description="Distributor ID (null uses one-off distributor)")
    effective_date: Optional[datetime] = None


# ============================================================================
# Ingredient Mapping View Schemas (ingredient-centric)
# ============================================================================


class SKUPriceEntry(BaseModel):
    """A single price entry for a SKU with invoice reference."""

    price_cents: int
    price_per_base_unit_cents: Optional[Decimal] = None
    effective_date: datetime
    source: Optional[str] = None  # 'invoice', 'manual', 'parsed'
    invoice_number: Optional[str] = None
    invoice_id: Optional[UUID] = None


class MappedSKU(BaseModel):
    """A mapped SKU with its price history."""

    id: UUID
    sku: Optional[str] = None
    description: str
    pack_size: Optional[Decimal] = None
    pack_unit: Optional[str] = None
    grams_per_unit: Optional[Decimal] = None
    is_active: bool = True
    price_history: list[SKUPriceEntry] = []
    latest_price_cents: Optional[int] = None
    latest_price_date: Optional[datetime] = None


class DistributorSKUGroup(BaseModel):
    """SKUs grouped by distributor."""

    distributor_id: UUID
    distributor_name: str
    skus: list[MappedSKU] = []
    sku_count: int = 0


class IngredientMappingView(BaseModel):
    """Full ingredient view for mapping workflow."""

    id: UUID
    name: str
    category: Optional[str] = None
    base_unit: str
    distributor_groups: list[DistributorSKUGroup] = []
    total_mapped_skus: int = 0
    has_price: bool = False
    best_price_per_base_unit_cents: Optional[Decimal] = None
    best_distributor_name: Optional[str] = None


# ============================================================================
# Unified Pricing View Schemas (ingredients + recipes)
# ============================================================================


class MultiUnitPricing(BaseModel):
    """Pricing in multiple units for easy comparison."""

    per_g_cents: Optional[Decimal] = None  # Price per gram
    per_oz_cents: Optional[Decimal] = None  # Price per ounce (weight)
    per_lb_cents: Optional[Decimal] = None  # Price per pound
    per_ml_cents: Optional[Decimal] = None  # Price per milliliter
    per_fl_oz_cents: Optional[Decimal] = None  # Price per fluid ounce
    per_l_cents: Optional[Decimal] = None  # Price per liter
    per_each_cents: Optional[Decimal] = None  # Price per each


class UnifiedPricingItem(BaseModel):
    """A single item (ingredient or recipe) with unified pricing."""

    id: UUID
    name: str
    item_type: str  # 'ingredient', 'recipe', 'component'
    category: Optional[str] = None
    base_unit: str  # g, ml, each
    source: Optional[str] = None  # Distributor name, "Recipe", etc.
    has_price: bool = False

    # Multi-unit pricing (cents)
    pricing: MultiUnitPricing = MultiUnitPricing()

    # Recipe-specific fields
    yield_quantity: Optional[Decimal] = None
    yield_unit: Optional[str] = None
    yield_weight_grams: Optional[Decimal] = None
    cost_per_yield_cents: Optional[Decimal] = None

    # For component ingredients
    source_recipe_id: Optional[UUID] = None
    source_recipe_name: Optional[str] = None


class UnifiedPricingResponse(BaseModel):
    """Response for unified pricing view."""

    items: list[UnifiedPricingItem]
    count: int
    ingredient_count: int
    recipe_count: int
    component_count: int


# Update forward references
IngredientWithVariants.model_rebuild()
