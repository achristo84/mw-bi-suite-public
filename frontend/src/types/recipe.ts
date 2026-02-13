// Recipe types for the frontend

export interface RecipeIngredient {
  id: string
  ingredient_id: string
  quantity_grams: number
  prep_note: string | null
  is_optional: boolean
  ingredient_name: string | null
  ingredient_base_unit: string | null
}

export interface RecipeComponent {
  id: string
  component_recipe_id: string
  quantity: number
  notes: string | null
  component_recipe_name: string | null
  component_recipe_yield_unit: string | null
  created_at: string
}

export interface Recipe {
  id: string
  name: string
  yield_quantity: number
  yield_unit: string
  yield_weight_grams: number | null  // Actual yield weight for component costing
  instructions: string | null
  prep_time_minutes: number | null
  cook_time_minutes: number | null
  is_active: boolean
  notes: string | null
  created_at: string
  updated_at: string
}

export interface RecipeWithDetails extends Recipe {
  ingredients: RecipeIngredient[]
  components: RecipeComponent[]
}

export interface RecipeListResponse {
  recipes: Recipe[]
  count: number
}

export interface RecipeSummary {
  id: string
  name: string
  yield_quantity: number
  yield_unit: string
  yield_weight_grams: number | null
  is_active: boolean
}

// Cost Breakdown Types
export interface IngredientCostBreakdown {
  ingredient_id: string
  ingredient_name: string
  ingredient_base_unit: string
  quantity_grams: number
  price_per_base_unit_cents: number | null
  cost_cents: number | null
  distributor_name: string | null
  has_price: boolean
}

export interface RecipeCostBreakdown {
  recipe_id: string
  recipe_name: string
  yield_quantity: number
  yield_unit: string
  yield_weight_grams: number | null
  ingredients: IngredientCostBreakdown[]
  components: RecipeCostBreakdown[]
  total_ingredient_cost_cents: number
  total_component_cost_cents: number
  total_cost_cents: number
  cost_per_unit_cents: number
  cost_per_gram_cents: number | null  // For component costing
  has_unpriced_ingredients: boolean
  unpriced_count: number
}

// Menu Item Cost Types
export interface PackagingCostItem {
  ingredient_id: string
  ingredient_name: string
  quantity: number
  usage_rate: number
  price_per_unit_cents: number | null
  cost_cents: number | null
  has_price: boolean
}

export interface MenuItemCostBreakdown {
  menu_item_id: string
  name: string
  menu_price_cents: number
  recipe_cost_cents: number | null
  packaging_cost_cents: number
  total_cost_cents: number
  gross_margin_cents: number
  food_cost_percent: number
  recipe_cost_breakdown: RecipeCostBreakdown | null
  packaging_breakdown: PackagingCostItem[]
  has_unpriced_ingredients: boolean
  margin_status: 'healthy' | 'warning' | 'danger'
}

// Menu Analyzer Types
export interface MenuItemAnalysis {
  id: string
  name: string
  category: string | null
  menu_price_cents: number
  total_cost_cents: number
  food_cost_percent: number
  gross_margin_cents: number
  margin_status: 'healthy' | 'warning' | 'danger'
  recipe_name: string | null
  portion_of_recipe: number
  has_unpriced_ingredients: boolean
}

export interface CategorySummary {
  total_items: number
  avg_food_cost_percent: number
  healthy_count: number
  warning_count: number
  danger_count: number
}

export interface MenuAnalyzerSummary {
  total_items: number
  avg_food_cost_percent: number
  healthy_count: number
  warning_count: number
  danger_count: number
  by_category: Record<string, CategorySummary>
}

export interface MenuAnalyzerResponse {
  items: MenuItemAnalysis[]
  summary: MenuAnalyzerSummary
}

export interface AffectedMenuItem {
  name: string
  cost_impact_cents: number
}

export interface IngredientMover {
  ingredient_id: string
  ingredient_name: string
  old_price_per_unit: number | null
  new_price_per_unit: number | null
  change_percent: number | null
  affected_items: AffectedMenuItem[]
}

export interface ItemMover {
  menu_item_id: string
  menu_item_name: string
  old_total_cost: number
  new_total_cost: number
  cost_change_cents: number
  new_food_cost_percent: number
}

export interface PriceMoverResponse {
  period_days: number
  ingredient_movers: IngredientMover[]
  item_movers: ItemMover[]
}
