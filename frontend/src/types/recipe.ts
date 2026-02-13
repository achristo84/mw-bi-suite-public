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
