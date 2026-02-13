export interface Ingredient {
  id: string
  name: string
  category: string | null
  base_unit: 'g' | 'ml' | 'each'
  ingredient_type: 'raw' | 'component' | 'packaging'
  source_recipe_id: string | null
  source_recipe_name: string | null
  storage_type: string | null
  shelf_life_days: number | null
  par_level_base_units: number | null
  yield_factor: number
  notes: string | null
  created_at: string
  updated_at: string
}

export interface DistIngredientVariant {
  id: string
  distributor_id: string
  distributor_name: string | null
  sku: string | null
  description: string
  pack_size: number | null
  pack_unit: string | null
  is_active: boolean
}

export interface IngredientWithVariants extends Ingredient {
  variants: DistIngredientVariant[]
}

export interface IngredientWithPrice extends Ingredient {
  current_price_per_base_unit_cents: number | null
  best_distributor_name: string | null  // For raw ingredients: distributor name. For components: "Recipe: X"
  has_price: boolean
  variant_count: number
}

export type IngredientType = 'raw' | 'component' | 'packaging'

export interface IngredientWithPriceListResponse {
  ingredients: IngredientWithPrice[]
  count: number
}

export interface IngredientListResponse {
  ingredients: Ingredient[]
  count: number
}

export interface UnmappedDistIngredient {
  id: string
  distributor_id: string
  distributor_name: string
  sku: string | null
  description: string
  pack_size: number | null
  pack_unit: string | null
  grams_per_unit: number | null
  // Parsed pack info
  parsed_pack_quantity: number | null
  parsed_unit_quantity: number | null
  parsed_unit: string | null
  parsed_total_base_units: number | null
  parsed_base_unit: string | null
  // Price context
  last_price_cents: number | null
  last_price_date: string | null
  created_at: string
}

export interface UnmappedDistIngredientListResponse {
  items: UnmappedDistIngredient[]
  count: number
}

export interface MapDistIngredientRequest {
  ingredient_id: string
  pack_size?: number
  pack_unit?: string
  grams_per_unit?: number
}

export interface CreateAndMapRequest {
  ingredient_name: string
  ingredient_category?: string
  ingredient_base_unit: 'g' | 'ml' | 'each'
  pack_size?: number
  pack_unit?: string
  grams_per_unit?: number
}

export const INGREDIENT_CATEGORIES = [
  'dairy',
  'produce',
  'protein',
  'dry_goods',
  'beverages',
  'coffee',
  'bakery',
  'frozen',
  'packaging',
  'cleaning',
  'other',
] as const

export type IngredientCategory = typeof INGREDIENT_CATEGORIES[number]

// Price Comparison Types
export interface DistributorPrice {
  distributor_id: string | null  // null for component ingredients (price from recipe)
  distributor_name: string
  dist_ingredient_id: string | null  // null for component ingredients
  sku: string | null
  description: string | null
  pack_size: number | null
  pack_unit: string | null
  grams_per_unit: number | null
  price_cents: number | null
  price_per_base_unit_cents: number | null
  effective_date: string | null
  is_best_price: boolean
}

export interface IngredientPriceComparison {
  ingredient_id: string
  ingredient_name: string
  category: string | null
  base_unit: string
  distributor_prices: DistributorPrice[]
  best_price_per_base_unit: number | null
  best_distributor_id: string | null
  price_spread_percent: number | null
}

export interface PriceComparisonMatrix {
  ingredients: IngredientPriceComparison[]
  distributors: { id: string; name: string }[]
  count: number
  total_potential_savings_cents: number | null
}

export interface PriceHistoryEntry {
  date: string
  price_cents: number
  price_per_base_unit_cents: number | null
  source: string | null
  source_reference: string | null
}

export interface DistributorPriceHistory {
  distributor_id: string
  distributor_name: string
  dist_ingredient_id: string
  description: string
  history: PriceHistoryEntry[]
}

export interface IngredientPriceHistory {
  ingredient_id: string
  ingredient_name: string
  base_unit: string
  distributors: DistributorPriceHistory[]
}

// Manual Pricing Types
export interface ManualPriceRequest {
  distributor_id: string
  price_cents: number
  total_base_units: number
  pack_description?: string
  effective_date?: string
  notes?: string
}

export interface ManualPriceResponse {
  dist_ingredient_id: string
  price_history_id: string
  price_per_base_unit_cents: number
}

// Ingredient Mapping View Types (ingredient-centric)
export interface SKUPriceEntry {
  price_cents: number
  price_per_base_unit_cents: number | null
  effective_date: string
  source: string | null
  invoice_number: string | null
  invoice_id: string | null
}

export interface MappedSKU {
  id: string
  sku: string | null
  description: string
  pack_size: number | null
  pack_unit: string | null
  grams_per_unit: number | null
  is_active: boolean
  price_history: SKUPriceEntry[]
  latest_price_cents: number | null
  latest_price_date: string | null
}

export interface DistributorSKUGroup {
  distributor_id: string
  distributor_name: string
  skus: MappedSKU[]
  sku_count: number
}

export interface IngredientMappingView {
  id: string
  name: string
  category: string | null
  base_unit: string
  distributor_groups: DistributorSKUGroup[]
  total_mapped_skus: number
  has_price: boolean
  best_price_per_base_unit_cents: number | null
  best_distributor_name: string | null
}

// Unified Pricing Types
export interface MultiUnitPricing {
  per_g_cents: number | null
  per_oz_cents: number | null
  per_lb_cents: number | null
  per_ml_cents: number | null
  per_fl_oz_cents: number | null
  per_l_cents: number | null
  per_each_cents: number | null
}

export interface UnifiedPricingItem {
  id: string
  name: string
  item_type: 'ingredient' | 'recipe' | 'component'
  category: string | null
  base_unit: string
  source: string | null
  has_price: boolean
  pricing: MultiUnitPricing
  // Recipe-specific fields
  yield_quantity: number | null
  yield_unit: string | null
  yield_weight_grams: number | null
  cost_per_yield_cents: number | null
  // Component fields
  source_recipe_id: string | null
  source_recipe_name: string | null
}

export interface UnifiedPricingResponse {
  items: UnifiedPricingItem[]
  count: number
  ingredient_count: number
  recipe_count: number
  component_count: number
}
