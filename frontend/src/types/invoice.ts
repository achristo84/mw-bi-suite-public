export interface Distributor {
  id: string
  name: string
  rep_name: string | null
  rep_email: string | null
  rep_phone: string | null
  portal_url: string | null
  invoice_email: string | null
  filename_pattern: string | null
  scraping_enabled: boolean
  ordering_enabled: boolean
  scrape_frequency: string | null
  last_successful_scrape: string | null
  is_active: boolean
  notes: string | null
  created_at: string
  updated_at: string
}

export type LineStatus = 'pending' | 'confirmed' | 'removed'

export interface InvoiceLine {
  id: string
  invoice_id: string
  raw_description: string
  raw_sku: string | null
  quantity_ordered: number | null
  quantity: number | null
  unit: string | null
  unit_price_cents: number | null
  extended_price_cents: number | null
  is_taxable: boolean
  line_type: 'product' | 'credit' | 'fee'
  parent_line_id: string | null
  line_status: LineStatus
}

export interface Invoice {
  id: string
  distributor_id: string
  distributor?: Distributor
  invoice_number: string
  invoice_date: string
  delivery_date: string | null
  due_date: string | null
  account_number: string | null
  sales_rep_name: string | null
  sales_order_number: string | null
  subtotal_cents: number | null
  tax_cents: number | null
  total_cents: number
  pdf_path: string | null
  parse_confidence: number | null
  parsed_at: string | null
  reviewed_by: string | null
  reviewed_at: string | null
  paid_at: string | null
  source: 'email' | 'manual' | 'upload'
  review_status: ReviewStatus
  lines?: InvoiceLine[]
  created_at: string
}

export type ReviewStatus = 'pending' | 'approved' | 'rejected'

export interface InvoiceListParams {
  status?: ReviewStatus | 'all'
  distributor_id?: string
  page?: number
  limit?: number
}

export interface InvoiceListResponse {
  invoices: Invoice[]
  total: number
  page: number
  limit: number
}

// ============================================================================
// Distributor Prompts (for custom parsing)
// ============================================================================

export interface DistributorPrompts {
  pdf: string
  email: string
  screenshot: string
  has_custom_pdf: boolean
  has_custom_email: boolean
  has_custom_screenshot: boolean
}

export interface DistributorPromptsUpdate {
  prompt: string
  update_pdf?: boolean
  update_email?: boolean
  update_screenshot?: boolean
}

export type PromptContentType = 'pdf' | 'email' | 'screenshot'

// Response from reparse-preview endpoint
export interface ReparsePreviewResponse {
  lines: InvoiceLine[]
  prompt_used: string
}
