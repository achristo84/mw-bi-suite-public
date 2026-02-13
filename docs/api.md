# REST API Documentation

Mill & Whistle BI Suite API endpoints. All routes are prefixed with `/api/v1` unless otherwise noted.

Base URL (production): `https://your-cloud-run-url.run.app`

## Core Endpoints

### Health Check

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check for Cloud Run |
| GET | `/` | Root endpoint (returns docs link) |

## Distributors

Base: `/api/v1/distributors`

| Method | Path | Description | Key Params |
|--------|------|-------------|------------|
| GET | `/` | List all distributors | `include_inactive` (bool) |
| GET | `/{distributor_id}` | Get single distributor | - |
| POST | `/` | Create distributor | Body: `DistributorCreate` |
| PATCH | `/{distributor_id}` | Update distributor | Body: `DistributorUpdate` |
| DELETE | `/{distributor_id}` | Soft delete (sets inactive) | - |
| GET | `/{distributor_id}/prompts` | Get parsing prompts (custom or defaults) | - |
| PATCH | `/{distributor_id}/prompts` | Update parsing prompts | Body: `DistributorPromptsUpdate` |

## Invoices

Base: `/api/v1/invoices`

### Invoice Management

| Method | Path | Description | Key Params |
|--------|------|-------------|------------|
| GET | `/` | List invoices (paginated) | `status`, `distributor_id`, `page`, `limit` |
| GET | `/with-stats` | List invoices with mapping stats | `distributor_id` |
| GET | `/{invoice_id}` | Get invoice with line items | - |
| POST | `/` | Create manual invoice | Body: `ManualInvoiceCreate` |
| POST | `/upload` | Upload PDF/image/text invoice | Form: `distributor_id`, `file`, `email_content` |
| DELETE | `/{invoice_id}` | Hard delete invoice | - |

### Invoice Review

| Method | Path | Description |
|--------|------|-------------|
| POST | `/{invoice_id}/approve` | Approve invoice (populates price_history) |
| POST | `/{invoice_id}/reject` | Reject invoice |
| POST | `/{invoice_id}/reparse` | Delete lines and re-parse PDF |
| POST | `/{invoice_id}/reparse-preview` | Preview re-parse with custom prompt |
| GET | `/{invoice_id}/pdf` | Download invoice PDF |

### Invoice Lines

| Method | Path | Description |
|--------|------|-------------|
| GET | `/{invoice_id}/lines-for-pricing/{ingredient_id}` | Get lines with mapping status |
| PATCH | `/{invoice_id}/lines/{line_id}` | Update line item |
| POST | `/{invoice_id}/lines/{line_id}/map-ingredient` | Map line to ingredient |
| POST | `/{invoice_id}/lines/{line_id}/confirm` | Mark line as confirmed |
| POST | `/{invoice_id}/lines/{line_id}/remove` | Mark line as removed |
| POST | `/{invoice_id}/lines/{line_id}/reset-status` | Reset line to pending |

## Ingredients

Base: `/api/v1/ingredients`

### Canonical Ingredients

| Method | Path | Description | Key Params |
|--------|------|-------------|------------|
| GET | `/` | List ingredients | `category`, `search`, `include_inactive` |
| GET | `/with-prices` | List ingredients with best prices | `category`, `search`, `unpriced_only` |
| GET | `/categories` | List available categories | - |
| GET | `/unified-pricing` | Get unified pricing view | `category`, `search`, `include_ingredients`, `include_components`, `include_recipes` |
| GET | `/{ingredient_id}` | Get ingredient with variants | - |
| GET | `/{ingredient_id}/mapping-view` | Get ingredient with SKUs grouped by distributor | `history_limit` |
| POST | `/` | Create ingredient | Body: `IngredientCreate` |
| PATCH | `/{ingredient_id}` | Update ingredient | Body: `IngredientUpdate` |
| DELETE | `/{ingredient_id}` | Delete ingredient | - |

### Distributor Ingredients (SKUs)

| Method | Path | Description | Key Params |
|--------|------|-------------|------------|
| GET | `/dist` | List distributor SKUs | `distributor_id`, `unmapped_only`, `search` |
| GET | `/dist/unmapped` | List unmapped SKUs with context | `distributor_id`, `search` |
| GET | `/dist/{dist_ingredient_id}` | Get single SKU | - |
| POST | `/dist` | Create SKU mapping | Body: `DistIngredientCreate` |
| PATCH | `/dist/{dist_ingredient_id}` | Update SKU | Body: `DistIngredientUpdate` |
| POST | `/dist/{dist_ingredient_id}/recalculate` | Recalculate base units | - |
| POST | `/dist/{dist_ingredient_id}/map` | Map SKU to ingredient | Query: `ingredient_id` |
| POST | `/dist/{dist_ingredient_id}/parse-pack` | Parse pack from description | - |
| POST | `/dist/{dist_ingredient_id}/map-with-details` | Map SKU with pack details | Body: `MapDistIngredientRequest` |
| POST | `/dist/{dist_ingredient_id}/create-and-map` | Create ingredient and map SKU | Body: `CreateAndMapRequest` |

### Pricing

| Method | Path | Description | Key Params |
|--------|------|-------------|------------|
| GET | `/prices/comparison` | Price comparison matrix | `category`, `distributor_id`, `search`, `mapped_only` |
| GET | `/{ingredient_id}/prices` | Price comparison for one ingredient | - |
| GET | `/{ingredient_id}/price-history` | Price history across distributors | `days` (default: 90) |
| POST | `/{ingredient_id}/prices/manual` | Add manual price | Body: `ManualPriceRequest` |
| POST | `/{ingredient_id}/prices/from-invoice` | Add price from invoice line | Body: `FromInvoicePriceRequest` |
| POST | `/prices/parse` | Parse pricing content (image/PDF/text) | Body: `ParsePriceContentRequest` |
| POST | `/{ingredient_id}/prices/from-parsed` | Save parsed price | Body: `SaveParsedPriceRequest` |

## Recipes

Base: `/api/v1/recipes`

| Method | Path | Description | Key Params |
|--------|------|-------------|------------|
| GET | `/` | List recipes | `include_inactive` |
| GET | `/summary` | List recipe summaries (for dropdowns) | `include_inactive` |
| GET | `/{recipe_id}` | Get recipe with ingredients/components | - |
| GET | `/{recipe_id}/cost` | Get recipe cost breakdown | `pricing_mode` (recent/average), `average_days` |
| POST | `/` | Create recipe | Body: `RecipeCreate` |
| PATCH | `/{recipe_id}` | Update recipe | Body: `RecipeUpdate` |
| DELETE | `/{recipe_id}` | Delete recipe | - |

## Menu Items

Base: `/api/v1/menu-items`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List menu items |
| GET | `/{menu_item_id}` | Get menu item with details |
| POST | `/` | Create menu item |
| PATCH | `/{menu_item_id}` | Update menu item |
| DELETE | `/{menu_item_id}` | Delete menu item |

## Units

Base: `/api/v1/units`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Get all unit conversion factors |
| POST | `/parse-pack` | Parse pack description (e.g., "36/1LB") |

## Order Hub

### Order List (Shared Cart)

Base: `/api/v1/order-list`

| Method | Path | Description | Key Params |
|--------|------|-------------|------------|
| GET | `/` | List order list items | `status` (pending/ordered/received) |
| GET | `/{item_id}` | Get single item | - |
| GET | `/{item_id}/history` | Get order history for item | - |
| POST | `/` | Add item to order list | Body: `OrderListItemCreate` |
| PATCH | `/{item_id}` | Update item | Body: `OrderListItemUpdate` |
| DELETE | `/{item_id}` | Remove item from list | - |
| POST | `/{item_id}/link-ingredient` | Link item to canonical ingredient | Query: `ingredient_id` |

### Order Builder (Cart Assignment)

Base: `/api/v1/order-builder`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/summary` | Get all carts with totals and minimum order status |
| POST | `/assign` | Assign item to distributor SKU (add to cart) |
| PATCH | `/assign/{assignment_id}` | Update assignment (change quantity/SKU) |
| DELETE | `/assign/{assignment_id}` | Remove assignment from cart |

### Orders

Base: `/api/v1/orders`

| Method | Path | Description | Key Params |
|--------|------|-------------|------------|
| GET | `/` | List orders | `status`, `limit` (default: 50) |
| GET | `/{order_id}` | Get order with details | - |
| GET | `/{order_id}/copy-list` | Get order formatted for copy-paste | - |
| POST | `/finalize` | Finalize assignments into orders | Body: `FinalizeRequest` |
| PATCH | `/{order_id}` | Update order status/notes | Query: `status`, `confirmation_number`, `notes` |

### Distributor Search

Base: `/api/v1/distributor-search`

| Method | Path | Description | Key Params |
|--------|------|-------------|------------|
| GET | `/` | Search all distributors in parallel | `q` (query), `limit` (per distributor) |
| GET | `/enabled` | Get distributors enabled for Order Hub | - |
| GET | `/{distributor_id}` | Search single distributor | `q`, `limit` |

## Authentication

Currently single-user system with no authentication required. Future versions may add OAuth.

## Rate Limits

No rate limits currently enforced. Claude API calls for invoice/price parsing count toward Anthropic usage limits.

## Error Responses

Standard HTTP status codes:
- `200` - Success
- `201` - Created
- `204` - No Content (successful delete)
- `400` - Bad Request (validation error)
- `404` - Not Found
- `409` - Conflict (duplicate)
- `500` - Internal Server Error

Error response format:
```json
{
  "detail": "Error message here"
}
```

## Response Formats

All responses are JSON. Dates are ISO 8601 format. Prices are in cents (integer). UUIDs are used for all IDs.

## OpenAPI Documentation

Interactive API docs available at:
- Swagger UI: `/docs`
- ReDoc: `/redoc`
