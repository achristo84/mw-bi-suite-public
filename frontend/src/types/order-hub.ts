// Order Hub Types

export interface OrderListItem {
  id: string
  name: string
  quantity: string | null
  notes: string | null
  ingredient_id: string | null
  status: 'pending' | 'ordered' | 'received'
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface OrderListItemWithDetails extends OrderListItem {
  ingredient_name: string | null
  assignments_count: number
  last_ordered_at: string | null
  last_ordered_distributor: string | null
  last_ordered_price_cents: number | null
}

export interface OrderListItemList {
  items: OrderListItemWithDetails[]
  count: number
}

export interface OrderListItemCreate {
  name: string
  quantity?: string
  notes?: string
  ingredient_id?: string
  created_by?: string
}

export interface OrderListItemUpdate {
  name?: string
  quantity?: string
  notes?: string
  ingredient_id?: string
  status?: 'pending' | 'ordered' | 'received'
}

// Distributor Search Types

export interface SearchResult {
  dist_ingredient_id: string | null
  distributor_id: string
  distributor_name: string
  sku: string
  description: string
  pack_size: string | null
  pack_unit: string | null
  price_cents: number | null
  price_per_base_unit_cents: number | null
  in_stock: boolean | null
  delivery_days: string[] | null
  last_ordered_date: string | null
  image_url: string | null
}

export interface DistributorSearchResults {
  distributor_id: string
  distributor_name: string
  results: SearchResult[]
  error: string | null
}

export interface AggregatedSearchResults {
  query: string
  distributors: DistributorSearchResults[]
  total_results: number
  search_duration_ms: number
}

// Assignment Types

export interface Assignment {
  id: string
  order_list_item_id: string
  dist_ingredient_id: string
  quantity: number
  order_id: string | null
  created_at: string
}

export interface AssignmentWithDetails extends Assignment {
  distributor_id: string
  distributor_name: string
  sku: string | null
  description: string
  pack_size: string | null
  pack_unit: string | null
  unit_price_cents: number | null
  extended_price_cents: number | null
}

export interface AssignmentCreate {
  order_list_item_id: string
  quantity: number
  // Option 1: Reference existing dist_ingredient
  dist_ingredient_id?: string
  // Option 2: Create from search result (when dist_ingredient doesn't exist)
  distributor_id?: string
  sku?: string
  description?: string
  pack_size?: string
  pack_unit?: string
  price_cents?: number
}

export interface AssignmentUpdate {
  quantity?: number
  dist_ingredient_id?: string
}

// Cart Builder Types

export interface CartItem {
  assignment_id: string
  order_list_item_id: string
  order_list_item_name: string
  dist_ingredient_id: string
  sku: string | null
  description: string
  quantity: number
  unit_price_cents: number | null
  extended_price_cents: number | null
}

export interface DistributorCart {
  distributor_id: string
  distributor_name: string
  delivery_days: string[] | null
  order_cutoff_time: string | null
  next_delivery_date: string | null
  minimum_order_cents: number
  order_minimum_items: number | null
  items: CartItem[]
  subtotal_cents: number
  meets_minimum: boolean
  ordering_enabled: boolean
}

export interface OrderBuilderSummary {
  carts: DistributorCart[]
  total_items: number
  total_cents: number
  ready_to_order: number
}

// Order Types

export interface Order {
  id: string
  distributor_id: string
  status: 'draft' | 'submitted' | 'confirmed' | 'delivered' | 'invoiced'
  submitted_at: string | null
  expected_delivery: string | null
  confirmation_number: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface OrderWithDetails extends Order {
  distributor_name: string
  lines: CartItem[]
  subtotal_cents: number
}

export interface FinalizeRequest {
  distributor_ids?: string[]
}

export interface FinalizeResponse {
  orders: OrderWithDetails[]
  items_ordered: number
  total_cents: number
}

// Order History

export interface OrderHistoryEntry {
  order_id: string
  order_date: string
  distributor_name: string
  sku: string | null
  description: string
  quantity: number
  price_cents: number
  status: string
}

export interface OrderHistoryResponse {
  item_name: string
  entries: OrderHistoryEntry[]
  count: number
}

// Copy List

export interface CopyListItem {
  sku: string
  description: string
  quantity: number
  notes: string | null
}

export interface CopyListResponse {
  distributor_name: string
  items: CopyListItem[]
  formatted_text: string
}

// Enabled Distributor

export interface EnabledDistributor {
  id: string
  name: string
  delivery_days: string[] | null
  order_cutoff_hours: number | null
  order_cutoff_time: string | null
  minimum_order_cents: number
  order_minimum_items: number | null
  capture_status: string
}
