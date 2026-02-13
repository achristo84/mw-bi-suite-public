import type {
  Invoice,
  InvoiceListParams,
  InvoiceListResponse,
  Distributor,
  DistributorPrompts,
  DistributorPromptsUpdate,
  ReparsePreviewResponse,
} from '@/types/invoice'
import type {
  Ingredient,
  IngredientWithVariants,
  IngredientListResponse,
  IngredientWithPriceListResponse,
  UnmappedDistIngredient,
  UnmappedDistIngredientListResponse,
  MapDistIngredientRequest,
  CreateAndMapRequest,
  PriceComparisonMatrix,
  IngredientPriceComparison,
  IngredientPriceHistory,
  ManualPriceRequest,
  ManualPriceResponse,
  IngredientMappingView,
  UnifiedPricingResponse,
} from '@/types/ingredient'

// Re-export types that components need
export type { UnmappedDistIngredient }
import type { RecipeWithDetails, RecipeListResponse, RecipeCostBreakdown } from '@/types/recipe'

const API_BASE = '/api/v1'

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `API error: ${response.status}`)
  }

  return response.json()
}

// Invoices
export async function getInvoices(params?: InvoiceListParams): Promise<InvoiceListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.status && params.status !== 'all') searchParams.set('status', params.status)
  if (params?.distributor_id) searchParams.set('distributor_id', params.distributor_id)
  if (params?.page) searchParams.set('page', params.page.toString())
  if (params?.limit) searchParams.set('limit', params.limit.toString())

  const query = searchParams.toString()
  return fetchAPI<InvoiceListResponse>(`/invoices${query ? `?${query}` : ''}`)
}

export async function getInvoice(id: string): Promise<Invoice> {
  return fetchAPI<Invoice>(`/invoices/${id}`)
}

export async function approveInvoice(id: string): Promise<Invoice> {
  return fetchAPI<Invoice>(`/invoices/${id}/approve`, { method: 'POST' })
}

export async function rejectInvoice(id: string, reason?: string): Promise<Invoice> {
  return fetchAPI<Invoice>(`/invoices/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}

export async function deleteInvoice(id: string): Promise<{ status: string; invoice_id: string }> {
  return fetchAPI<{ status: string; invoice_id: string }>(`/invoices/${id}`, {
    method: 'DELETE',
  })
}

export async function reparseInvoice(id: string): Promise<Invoice> {
  return fetchAPI<Invoice>(`/invoices/${id}/reparse`, { method: 'POST' })
}

export async function confirmInvoiceLine(invoiceId: string, lineId: string): Promise<{ success: boolean; line_id: string; status: string }> {
  return fetchAPI(`/invoices/${invoiceId}/lines/${lineId}/confirm`, { method: 'POST' })
}

export async function removeInvoiceLine(invoiceId: string, lineId: string): Promise<{ success: boolean; line_id: string; status: string }> {
  return fetchAPI(`/invoices/${invoiceId}/lines/${lineId}/remove`, { method: 'POST' })
}

export async function resetInvoiceLineStatus(invoiceId: string, lineId: string): Promise<{ success: boolean; line_id: string; status: string }> {
  return fetchAPI(`/invoices/${invoiceId}/lines/${lineId}/reset-status`, { method: 'POST' })
}

export async function updateInvoiceLine(
  invoiceId: string,
  lineId: string,
  data: Partial<{
    raw_description: string
    raw_sku: string
    quantity: number
    unit: string
    unit_price_cents: number
    extended_price_cents: number
  }>
): Promise<Invoice> {
  return fetchAPI<Invoice>(`/invoices/${invoiceId}/lines/${lineId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export interface MapLineResponse {
  success: boolean
  dist_ingredient_id: string
  ingredient_id: string
  ingredient_name: string
}

export async function mapInvoiceLine(
  invoiceId: string,
  lineId: string,
  ingredientId: string,
  gramsPerUnit?: number
): Promise<MapLineResponse> {
  return fetchAPI<MapLineResponse>(
    `/invoices/${invoiceId}/lines/${lineId}/map-ingredient`,
    {
      method: 'POST',
      body: JSON.stringify({
        ingredient_id: ingredientId,
        grams_per_unit: gramsPerUnit,
      }),
    }
  )
}

// Get PDF URL for viewing
export function getInvoicePdfUrl(invoice: Invoice): string | null {
  if (!invoice.pdf_path) return null
  // Convert GCS path to a viewable URL via our API
  return `${API_BASE}/invoices/${invoice.id}/pdf`
}

// Distributors
export async function getDistributors(): Promise<Distributor[]> {
  const response = await fetchAPI<{ distributors: Distributor[]; count: number }>('/distributors')
  return response.distributors
}

// Manual invoice creation
export async function createManualInvoice(data: {
  distributor_id: string
  invoice_number: string
  invoice_date: string
  total_cents: number
  lines: Array<{
    raw_description: string
    raw_sku?: string
    quantity: number
    unit_price_cents: number
    extended_price_cents: number
  }>
}): Promise<Invoice> {
  return fetchAPI<Invoice>('/invoices', {
    method: 'POST',
    body: JSON.stringify({ ...data, source: 'manual' }),
  })
}

// Upload invoice (PDF or email content)
export async function uploadInvoice(
  distributorId: string,
  file?: File,
  emailContent?: string
): Promise<Invoice> {
  const formData = new FormData()
  formData.append('distributor_id', distributorId)
  if (file) {
    formData.append('file', file)
  }
  if (emailContent) {
    formData.append('email_content', emailContent)
  }

  const response = await fetch(`${API_BASE}/invoices/upload`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
    throw new Error(error.detail || `Upload error: ${response.status}`)
  }

  return response.json()
}

// ============================================================================
// Ingredients
// ============================================================================

export async function getIngredients(params?: {
  category?: string
  search?: string
}): Promise<IngredientListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.category) searchParams.set('category', params.category)
  if (params?.search) searchParams.set('search', params.search)

  const query = searchParams.toString()
  return fetchAPI<IngredientListResponse>(`/ingredients${query ? `?${query}` : ''}`)
}

export async function getIngredientsWithPrices(params?: {
  category?: string
  search?: string
  unpriced_only?: boolean
}): Promise<IngredientWithPriceListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.category) searchParams.set('category', params.category)
  if (params?.search) searchParams.set('search', params.search)
  if (params?.unpriced_only) searchParams.set('unpriced_only', 'true')

  const query = searchParams.toString()
  return fetchAPI<IngredientWithPriceListResponse>(`/ingredients/with-prices${query ? `?${query}` : ''}`)
}

export async function getUnifiedPricing(params?: {
  category?: string
  search?: string
  include_ingredients?: boolean
  include_components?: boolean
  include_recipes?: boolean
}): Promise<UnifiedPricingResponse> {
  const searchParams = new URLSearchParams()
  if (params?.category) searchParams.set('category', params.category)
  if (params?.search) searchParams.set('search', params.search)
  if (params?.include_ingredients !== undefined) searchParams.set('include_ingredients', String(params.include_ingredients))
  if (params?.include_components !== undefined) searchParams.set('include_components', String(params.include_components))
  if (params?.include_recipes !== undefined) searchParams.set('include_recipes', String(params.include_recipes))

  const query = searchParams.toString()
  return fetchAPI<UnifiedPricingResponse>(`/ingredients/unified-pricing${query ? `?${query}` : ''}`)
}

export async function getIngredient(id: string): Promise<IngredientWithVariants> {
  return fetchAPI<IngredientWithVariants>(`/ingredients/${id}`)
}

export async function getIngredientMappingView(
  id: string,
  historyLimit?: number
): Promise<IngredientMappingView> {
  const params = historyLimit ? `?history_limit=${historyLimit}` : ''
  return fetchAPI<IngredientMappingView>(`/ingredients/${id}/mapping-view${params}`)
}

export async function createIngredient(data: {
  name: string
  category?: string
  base_unit: 'g' | 'ml' | 'each'
  storage_type?: string
  notes?: string
}): Promise<Ingredient> {
  return fetchAPI<Ingredient>('/ingredients', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateIngredient(
  id: string,
  data: {
    name?: string
    category?: string
    base_unit?: 'g' | 'ml' | 'each'
    ingredient_type?: 'raw' | 'component' | 'packaging'
    source_recipe_id?: string | null
    storage_type?: string
    notes?: string
  }
): Promise<Ingredient> {
  return fetchAPI<Ingredient>(`/ingredients/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function getIngredientCategories(): Promise<string[]> {
  return fetchAPI<string[]>('/ingredients/categories')
}

// Unmapped distributor ingredients
export async function getUnmappedDistIngredients(params?: {
  distributor_id?: string
  search?: string
}): Promise<UnmappedDistIngredientListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.distributor_id) searchParams.set('distributor_id', params.distributor_id)
  if (params?.search) searchParams.set('search', params.search)

  const query = searchParams.toString()
  return fetchAPI<UnmappedDistIngredientListResponse>(`/ingredients/dist/unmapped${query ? `?${query}` : ''}`)
}

// Map a dist_ingredient to an existing ingredient
export async function mapDistIngredient(
  distIngredientId: string,
  data: MapDistIngredientRequest
): Promise<void> {
  await fetchAPI(`/ingredients/dist/${distIngredientId}/map-with-details`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// Create a new ingredient and map the dist_ingredient to it
export async function createAndMapIngredient(
  distIngredientId: string,
  data: CreateAndMapRequest
): Promise<void> {
  await fetchAPI(`/ingredients/dist/${distIngredientId}/create-and-map`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// Recalculate base units for a dist_ingredient
export async function recalculateDistIngredient(
  distIngredientId: string
): Promise<void> {
  await fetchAPI(`/ingredients/dist/${distIngredientId}/recalculate`, {
    method: 'POST',
  })
}

// ============================================================================
// Price Comparison
// ============================================================================

export async function getPriceComparisonMatrix(params?: {
  category?: string
  distributor_id?: string
  search?: string
  mapped_only?: boolean
}): Promise<PriceComparisonMatrix> {
  const searchParams = new URLSearchParams()
  if (params?.category) searchParams.set('category', params.category)
  if (params?.distributor_id) searchParams.set('distributor_id', params.distributor_id)
  if (params?.search) searchParams.set('search', params.search)
  if (params?.mapped_only !== undefined) searchParams.set('mapped_only', params.mapped_only.toString())

  const query = searchParams.toString()
  return fetchAPI<PriceComparisonMatrix>(`/ingredients/prices/comparison${query ? `?${query}` : ''}`)
}

export async function getIngredientPrices(ingredientId: string): Promise<IngredientPriceComparison> {
  return fetchAPI<IngredientPriceComparison>(`/ingredients/${ingredientId}/prices`)
}

export async function getIngredientPriceHistory(
  ingredientId: string,
  days?: number
): Promise<IngredientPriceHistory> {
  const searchParams = new URLSearchParams()
  if (days) searchParams.set('days', days.toString())

  const query = searchParams.toString()
  return fetchAPI<IngredientPriceHistory>(`/ingredients/${ingredientId}/price-history${query ? `?${query}` : ''}`)
}

// Add manual price for an ingredient
export async function addManualPrice(
  ingredientId: string,
  data: ManualPriceRequest
): Promise<ManualPriceResponse> {
  return fetchAPI<ManualPriceResponse>(`/ingredients/${ingredientId}/prices/manual`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ============================================================================
// Recipes
// ============================================================================

export async function getRecipes(params?: {
  include_inactive?: boolean
}): Promise<RecipeListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.include_inactive) searchParams.set('include_inactive', 'true')

  const query = searchParams.toString()
  return fetchAPI<RecipeListResponse>(`/recipes${query ? `?${query}` : ''}`)
}

export async function getRecipe(id: string): Promise<RecipeWithDetails> {
  return fetchAPI<RecipeWithDetails>(`/recipes/${id}`)
}

export async function getRecipeCost(
  id: string,
  params?: {
    pricing_mode?: 'recent' | 'average'
    average_days?: number
  }
): Promise<RecipeCostBreakdown> {
  const searchParams = new URLSearchParams()
  if (params?.pricing_mode) searchParams.set('pricing_mode', params.pricing_mode)
  if (params?.average_days) searchParams.set('average_days', params.average_days.toString())

  const query = searchParams.toString()
  return fetchAPI<RecipeCostBreakdown>(`/recipes/${id}/cost${query ? `?${query}` : ''}`)
}

export async function createRecipe(data: {
  name: string
  yield_quantity: number
  yield_unit: string
  yield_weight_grams?: number
  instructions?: string
  prep_time_minutes?: number
  cook_time_minutes?: number
  notes?: string
  ingredients?: Array<{
    ingredient_id: string
    quantity_grams: number
    prep_note?: string
    is_optional?: boolean
  }>
}): Promise<RecipeWithDetails> {
  return fetchAPI<RecipeWithDetails>('/recipes', {
    method: 'POST',
    body: JSON.stringify({
      ...data,
      is_active: true,
      components: [],
    }),
  })
}

export async function updateRecipe(
  id: string,
  data: {
    name?: string
    yield_quantity?: number
    yield_unit?: string
    yield_weight_grams?: number
    instructions?: string
    prep_time_minutes?: number | null
    cook_time_minutes?: number | null
    notes?: string | null
    is_active?: boolean
  }
): Promise<RecipeWithDetails> {
  return fetchAPI<RecipeWithDetails>(`/recipes/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteRecipe(id: string): Promise<void> {
  await fetchAPI(`/recipes/${id}`, { method: 'DELETE' })
}

export async function addRecipeIngredient(
  recipeId: string,
  data: {
    ingredient_id: string
    quantity_grams: number
    prep_note?: string
    is_optional?: boolean
  }
): Promise<void> {
  await fetchAPI(`/recipes/${recipeId}/ingredients`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateRecipeIngredient(
  recipeId: string,
  ingredientId: string,
  data: {
    quantity_grams?: number
    prep_note?: string
    is_optional?: boolean
  }
): Promise<void> {
  const params = new URLSearchParams()
  if (data.quantity_grams !== undefined) params.set('quantity_grams', data.quantity_grams.toString())
  if (data.prep_note !== undefined) params.set('prep_note', data.prep_note)
  if (data.is_optional !== undefined) params.set('is_optional', data.is_optional.toString())

  await fetchAPI(`/recipes/${recipeId}/ingredients/${ingredientId}?${params.toString()}`, {
    method: 'PATCH',
  })
}

export async function removeRecipeIngredient(recipeId: string, ingredientId: string): Promise<void> {
  await fetchAPI(`/recipes/${recipeId}/ingredients/${ingredientId}`, {
    method: 'DELETE',
  })
}

// ============================================================================
// Invoice Pricing APIs
// ============================================================================

export interface InvoiceLineStats {
  total_lines: number
  mapped_lines: number
  unmapped_lines: number
  priced_lines: number
}

export interface InvoiceWithStats {
  id: string
  distributor_id: string
  distributor_name: string
  invoice_number: string
  invoice_date: string
  total_cents: number
  review_status: string
  source: string
  stats: InvoiceLineStats
}

export interface InvoicesWithStatsResponse {
  invoices: InvoiceWithStats[]
  total: number
}

export async function getInvoicesWithStats(
  distributorId?: string
): Promise<InvoicesWithStatsResponse> {
  const params = new URLSearchParams()
  if (distributorId) params.set('distributor_id', distributorId)
  const query = params.toString()
  return fetchAPI<InvoicesWithStatsResponse>(`/invoices/with-stats${query ? `?${query}` : ''}`)
}

export interface InvoiceLineForPricing {
  id: string
  invoice_id: string
  raw_description: string
  raw_sku: string | null
  quantity: number | null
  unit: string | null
  unit_price_cents: number | null
  extended_price_cents: number | null
  dist_ingredient_id: string | null
  mapped_ingredient_id: string | null
  mapped_ingredient_name: string | null
  status: 'green' | 'yellow' | 'grey' | 'orange'
  has_price: boolean
}

export interface InvoiceLinesForPricingResponse {
  invoice_id: string
  invoice_number: string
  distributor_name: string
  invoice_date: string
  lines: InvoiceLineForPricing[]
}

export async function getInvoiceLinesForPricing(
  invoiceId: string,
  ingredientId: string
): Promise<InvoiceLinesForPricingResponse> {
  return fetchAPI<InvoiceLinesForPricingResponse>(
    `/invoices/${invoiceId}/lines-for-pricing/${ingredientId}`
  )
}

export interface FromInvoicePriceRequest {
  invoice_line_id: string
  grams_per_unit: number
  remap_to_ingredient?: boolean
}

export interface FromInvoicePriceResponse {
  dist_ingredient_id: string
  price_history_id: string
  price_per_base_unit_cents: number
  remapped: boolean
  previous_ingredient_name: string | null
}

export async function addPriceFromInvoice(
  ingredientId: string,
  data: FromInvoicePriceRequest
): Promise<FromInvoicePriceResponse> {
  return fetchAPI<FromInvoicePriceResponse>(
    `/ingredients/${ingredientId}/prices/from-invoice`,
    {
      method: 'POST',
      body: JSON.stringify(data),
    }
  )
}

// ============================================================================
// Price Parsing APIs (Upload tab)
// ============================================================================

export interface ParsedPriceItem {
  description: string
  sku: string | null
  pack_size: string | null
  pack_unit: string | null
  unit_contents: number | null
  unit_contents_unit: string | null
  price_cents: number
  price_type: 'case' | 'unit'
  total_base_units: number | null
  base_unit: string | null
  price_per_base_unit_cents: number | null
  raw_text: string
  confidence: number
}

export interface ParsePriceContentRequest {
  content: string
  content_type: string
  distributor_id?: string
  ingredient_name?: string
  ingredient_category?: string
  ingredient_base_unit?: string
}

export interface ParsePriceContentResponse {
  items: ParsedPriceItem[]
  detected_distributor: string | null
  document_date: string | null
}

export async function parsePriceContent(
  data: ParsePriceContentRequest
): Promise<ParsePriceContentResponse> {
  return fetchAPI<ParsePriceContentResponse>('/ingredients/prices/parse', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export interface SaveParsedPriceRequest {
  description: string
  sku?: string
  pack_description?: string
  total_base_units: number
  price_cents: number
  distributor_id?: string
  effective_date?: string
}

export async function saveParsedPrice(
  ingredientId: string,
  data: SaveParsedPriceRequest
): Promise<ManualPriceResponse> {
  return fetchAPI<ManualPriceResponse>(
    `/ingredients/${ingredientId}/prices/from-parsed`,
    {
      method: 'POST',
      body: JSON.stringify(data),
    }
  )
}

// ============================================================================
// Distributor Management
// ============================================================================

export interface CreateDistributorRequest {
  name: string
  vendor_category?: string
  invoice_email?: string
  filename_pattern?: string
  scraping_enabled?: boolean
  ordering_enabled?: boolean
  notes?: string
}

export interface UpdateDistributorRequest {
  name?: string
  vendor_category?: string
  invoice_email?: string
  filename_pattern?: string
  scraping_enabled?: boolean
  ordering_enabled?: boolean
  is_active?: boolean
  notes?: string
}

export interface DistributorResponse {
  id: string
  name: string
  vendor_category: string | null
  is_active: boolean
}

export async function createDistributor(
  data: CreateDistributorRequest
): Promise<DistributorResponse> {
  return fetchAPI<DistributorResponse>('/distributors', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateDistributor(
  id: string,
  data: UpdateDistributorRequest
): Promise<DistributorResponse> {
  return fetchAPI<DistributorResponse>(`/distributors/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteDistributor(id: string): Promise<void> {
  await fetchAPI(`/distributors/${id}`, {
    method: 'DELETE',
  })
}

// ============================================================================
// Units API
// ============================================================================

export interface UnitConversions {
  weight: Record<string, number>
  volume: Record<string, number>
  count: Record<string, number>
  base_units: string[]
}

export interface ParsePackRequest {
  description: string
}

export interface ParsePackResponse {
  success: boolean
  pack_count: number | null
  unit_size: number | null
  unit: string | null
  total_base_units: number | null
  base_unit: string | null
  display: string | null
  error: string | null
}

export async function getUnits(): Promise<UnitConversions> {
  return fetchAPI<UnitConversions>('/units')
}

export async function parsePack(description: string): Promise<ParsePackResponse> {
  return fetchAPI<ParsePackResponse>('/units/parse-pack', {
    method: 'POST',
    body: JSON.stringify({ description }),
  })
}

// ============================================================================
// Distributor Prompts (Custom Parsing)
// ============================================================================

export async function getDistributorPrompts(
  distributorId: string
): Promise<DistributorPrompts> {
  return fetchAPI<DistributorPrompts>(`/distributors/${distributorId}/prompts`)
}

export async function updateDistributorPrompts(
  distributorId: string,
  data: DistributorPromptsUpdate
): Promise<DistributorPrompts> {
  return fetchAPI<DistributorPrompts>(`/distributors/${distributorId}/prompts`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

// Reparse invoice with custom prompt (preview only - doesn't save)
export async function reparseInvoiceWithPrompt(
  invoiceId: string,
  customPrompt?: string
): Promise<ReparsePreviewResponse> {
  return fetchAPI<ReparsePreviewResponse>(`/invoices/${invoiceId}/reparse-preview`, {
    method: 'POST',
    body: JSON.stringify({ custom_prompt: customPrompt }),
  })
}

// Parse price content with custom prompt
export interface ParsePriceContentWithPromptRequest extends ParsePriceContentRequest {
  custom_prompt?: string
}

export interface ParsePriceContentWithPromptResponse extends ParsePriceContentResponse {
  prompt_used: string
}

export async function parsePriceContentWithPrompt(
  data: ParsePriceContentWithPromptRequest
): Promise<ParsePriceContentWithPromptResponse> {
  return fetchAPI<ParsePriceContentWithPromptResponse>('/ingredients/prices/parse', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ============================================================================
// Order Hub APIs
// ============================================================================

import type {
  OrderListItemList,
  OrderListItemWithDetails,
  OrderListItemCreate,
  OrderListItemUpdate,
  AggregatedSearchResults,
  DistributorSearchResults,
  AssignmentWithDetails,
  AssignmentCreate,
  AssignmentUpdate,
  OrderBuilderSummary,
  FinalizeRequest,
  FinalizeResponse,
  OrderWithDetails,
  OrderHistoryResponse,
  CopyListResponse,
  EnabledDistributor,
} from '@/types/order-hub'

// Order List

export async function getOrderListItems(
  status?: string
): Promise<OrderListItemList> {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  const query = params.toString()
  return fetchAPI<OrderListItemList>(`/order-list${query ? `?${query}` : ''}`)
}

export async function getOrderListItem(id: string): Promise<OrderListItemWithDetails> {
  return fetchAPI<OrderListItemWithDetails>(`/order-list/${id}`)
}

export async function createOrderListItem(
  data: OrderListItemCreate
): Promise<OrderListItemWithDetails> {
  return fetchAPI<OrderListItemWithDetails>('/order-list', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateOrderListItem(
  id: string,
  data: OrderListItemUpdate
): Promise<OrderListItemWithDetails> {
  return fetchAPI<OrderListItemWithDetails>(`/order-list/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteOrderListItem(id: string): Promise<void> {
  await fetchAPI(`/order-list/${id}`, { method: 'DELETE' })
}

export async function getOrderListItemHistory(
  id: string
): Promise<OrderHistoryResponse> {
  return fetchAPI<OrderHistoryResponse>(`/order-list/${id}/history`)
}

export async function linkOrderListItemToIngredient(
  itemId: string,
  ingredientId: string
): Promise<OrderListItemWithDetails> {
  return fetchAPI<OrderListItemWithDetails>(
    `/order-list/${itemId}/link-ingredient?ingredient_id=${ingredientId}`,
    { method: 'POST' }
  )
}

// Distributor Search

export async function searchDistributors(
  query: string,
  limit?: number
): Promise<AggregatedSearchResults> {
  const params = new URLSearchParams()
  params.set('q', query)
  if (limit) params.set('limit', limit.toString())
  return fetchAPI<AggregatedSearchResults>(`/distributor-search?${params.toString()}`)
}

export async function searchSingleDistributor(
  distributorId: string,
  query: string,
  limit?: number
): Promise<DistributorSearchResults> {
  const params = new URLSearchParams()
  params.set('q', query)
  if (limit) params.set('limit', limit.toString())
  return fetchAPI<DistributorSearchResults>(
    `/distributor-search/${distributorId}?${params.toString()}`
  )
}

export async function getEnabledDistributors(): Promise<EnabledDistributor[]> {
  return fetchAPI<EnabledDistributor[]>('/distributor-search/enabled')
}

// Order Builder

export async function createAssignment(
  data: AssignmentCreate
): Promise<AssignmentWithDetails> {
  return fetchAPI<AssignmentWithDetails>('/order-builder/assign', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateAssignment(
  id: string,
  data: AssignmentUpdate
): Promise<AssignmentWithDetails> {
  return fetchAPI<AssignmentWithDetails>(`/order-builder/assign/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteAssignment(id: string): Promise<void> {
  await fetchAPI(`/order-builder/assign/${id}`, { method: 'DELETE' })
}

export async function getOrderBuilderSummary(): Promise<OrderBuilderSummary> {
  return fetchAPI<OrderBuilderSummary>('/order-builder/summary')
}

// Orders

export async function finalizeOrders(
  data?: FinalizeRequest
): Promise<FinalizeResponse> {
  return fetchAPI<FinalizeResponse>('/orders/finalize', {
    method: 'POST',
    body: JSON.stringify(data || {}),
  })
}

export async function getOrders(status?: string): Promise<OrderWithDetails[]> {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  const query = params.toString()
  return fetchAPI<OrderWithDetails[]>(`/orders${query ? `?${query}` : ''}`)
}

export async function getOrder(id: string): Promise<OrderWithDetails> {
  return fetchAPI<OrderWithDetails>(`/orders/${id}`)
}

export async function updateOrder(
  id: string,
  data: {
    status?: string
    confirmation_number?: string
    notes?: string
  }
): Promise<{ status: string }> {
  const params = new URLSearchParams()
  if (data.status) params.set('status', data.status)
  if (data.confirmation_number !== undefined)
    params.set('confirmation_number', data.confirmation_number)
  if (data.notes !== undefined) params.set('notes', data.notes)
  return fetchAPI<{ status: string }>(`/orders/${id}?${params.toString()}`, {
    method: 'PATCH',
  })
}

export async function getOrderCopyList(id: string): Promise<CopyListResponse> {
  return fetchAPI<CopyListResponse>(`/orders/${id}/copy-list`)
}
