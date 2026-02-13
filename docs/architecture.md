# System Architecture

## Overview

The Mill & Whistle BI Suite is a layered system that automates the supply chain for a small food service operation. Data flows from external systems (email, distributor portals, spreadsheets) through ingestion and processing layers, ultimately surfacing as actionable information in a React frontend and daily digest emails.

## System Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SYSTEMS                             │
├────────────┬────────────┬────────────┬────────────┬────────────────┤
│   Gmail    │ Distributor│   Google   │ Distributor│   Manual       │
│  (invoices)│  Portals   │   Sheets   │    APIs    │   Entry        │
└─────┬──────┴─────┬──────┴─────┬──────┴─────┬──────┴───────┬───────┘
      │            │            │            │              │
      v            v            v            v              v
┌─────────────────────────────────────────────────────────────────────┐
│                       INGESTION LAYER                               │
│                                                                     │
│  gmail_service.py      Handles email polling, PDF extraction,       │
│                        Cloud Storage upload                         │
│                                                                     │
│  invoice_parser.py     Claude Haiku parses PDFs/images into         │
│                        structured line items with confidence scores  │
│                                                                     │
│  price_parser.py       Claude Haiku parses ad-hoc price info        │
│                        (screenshots, text, email) into prices       │
│                                                                     │
│  recipe_importer.py    Reads Google Sheets, matches ingredients,    │
│                        creates recipe records                       │
│                                                                     │
│  distributor_client.py Base class for distributor API integrations   │
│  clients/*.py          Per-distributor implementations (5 total)    │
│                                                                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               v
┌─────────────────────────────────────────────────────────────────────┐
│                       CORE DATABASE                                 │
│                    PostgreSQL (Cloud SQL)                            │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  distributors ──> dist_ingredients ──> price_history         │   │
│  │       │                   │                                  │   │
│  │       │           ingredients (canonical)                    │   │
│  │       │                   │                                  │   │
│  │       v           recipe_ingredients ──> recipes             │   │
│  │  invoices ──>            │                   │               │   │
│  │  invoice_lines     menu_items ──> menu_item_packaging       │   │
│  │                                                              │   │
│  │  order_list_items ──> assignments                            │   │
│  │  distributor_sessions                                        │   │
│  │  orders ──> order_lines                                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  All prices in cents (integer). UUIDs for primary keys.             │
│  15 Alembic migrations track schema evolution.                      │
│                                                                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               v
┌─────────────────────────────────────────────────────────────────────┐
│                     PROCESSING LAYER                                │
│                                                                     │
│  units.py              Convert between measurement systems.         │
│                        Parse pack descriptions ("9/1/2GAL").        │
│                        Normalize to base units (g, ml, each).       │
│                                                                     │
│  price_pipeline.py     On invoice approval: calculate effective     │
│                        prices (list price + credits), match to      │
│                        dist_ingredients, write to price_history.    │
│                                                                     │
│  cost_calculator.py    Roll up ingredient prices through recipes    │
│                        to menu items. Handle component ingredients  │
│                        (recursive cost from sub-recipes). Support   │
│                        "recent" and "average" pricing modes.        │
│                                                                     │
│  search_aggregator.py  Fan out search queries to all enabled        │
│                        distributor APIs in parallel. Merge and      │
│                        rank results by price.                       │
│                                                                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               v
┌─────────────────────────────────────────────────────────────────────┐
│                       OUTPUT LAYER                                  │
│                                                                     │
│  FastAPI REST API       ~40 endpoints across 9 resource groups      │
│  React SPA              14 pages: invoices, ingredients, recipes,   │
│                         prices, orders, settings                    │
│  Daily digest email     Alerts, action items, metrics (planned)     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow: Invoice to Recipe Cost

This is the core pipeline that connects raw invoices to actionable cost data.

```
1. Invoice PDF arrives (email or upload)
        |
2. Claude Haiku extracts line items
   - raw_description, quantity, unit_price, extended_price
   - confidence score per field (0.0 - 1.0)
        |
3. Human review queue
   - High confidence (>0.9): can auto-approve
   - Medium (0.7-0.9): quick review
   - Low (<0.7): full manual review
        |
4. On approval, price pipeline runs:
   - Match invoice lines to dist_ingredients via SKU
   - Calculate effective price = list price + credits
   - Insert into price_history with source='invoice'
        |
5. Price normalization:
   - total_grams = pack_size * units_per_pack * grams_per_unit
   - price_per_gram = price_cents / total_grams
        |
6. Recipe costing:
   - For each recipe_ingredient:
     ingredient_cost = quantity_grams * best_price_per_gram
   - Sum all ingredients = recipe_cost
   - Divide by yield = cost_per_portion
        |
7. Menu margin:
   - food_cost_pct = cost_per_portion / menu_price
   - margin = menu_price - cost_per_portion
```

## Data Flow: Order Hub

The Order Hub enables price comparison and ordering across multiple distributors.

```
1. User adds items to shared order list
        |
2. For each item, search across distributors:
   - SearchAggregator fans out to all enabled distributor clients
   - Each client authenticates (OAuth/cookie) and queries API
   - Results merged, sorted by price
        |
3. User assigns items to distributor carts:
   - Compare prices across distributors
   - Track order minimums per distributor
   - Running totals per cart
        |
4. Finalize orders:
   - Group assignments by distributor
   - Create order records
   - Generate formatted order lists for submission
```

## Claude API Integration

The system uses Claude Haiku for two parsing tasks:

### Invoice Parsing (`invoice_parser.py`)

Inputs: PDF pages (as images), raw text, or pasted email content

The parser handles complex invoice formats:
- **Columnar layouts**: Distinguishes quantity-ordered vs quantity-shipped columns
- **Credits/allowances**: Negative lines linked to parent product lines via `parent_line_id`
- **Multi-page documents**: Each page parsed independently, results merged
- **Mixed content**: Headers, subtotals, and non-product lines filtered out

Output: Structured JSON with per-field confidence scores

### Price List Parsing (`price_parser.py`)

Inputs: Screenshots (images), PDF price lists, pasted text, email content

Used for ad-hoc pricing from sources that are not regular invoices. Same structured output format but optimized for price list layouts rather than invoice formats.

### Model Selection Rationale

| Task | Model | Cost per Call | Why |
|------|-------|--------------|-----|
| Invoice parsing | Haiku | ~$0.01 | High volume (dozens/month), structured output, accuracy sufficient |
| Price parsing | Haiku | ~$0.01 | Same reasoning as invoice parsing |
| Distributor analysis | Sonnet | ~$0.10 | One-time per distributor, needs reasoning about page structure |

## Browser Automation Architecture

Some distributor portals use aggressive anti-bot measures that prevent standard HTTP-based API access.

```
┌─────────────────────────────────────┐
│         Initial Authentication       │
│                                     │
│  SeleniumBase UC (undetected-chrome) │
│         |                           │
│  Playwright connects via CDP         │
│         |                           │
│  Fill credentials, complete OAuth   │
│         |                           │
│  Extract tokens from sessionStorage │
│         |                           │
│  Store refresh_token in Secret Mgr  │
└──────────────┬──────────────────────┘
               │
               v
┌─────────────────────────────────────┐
│         Ongoing API Access           │
│                                     │
│  Use access_token for API calls     │
│         |                           │
│  Token expired?                      │
│    -> Use refresh_token (no browser) │
│         |                           │
│  Refresh failed?                     │
│    -> Re-run browser authentication  │
└─────────────────────────────────────┘
```

**Why two tools?**
- **SeleniumBase UC**: Provides undetected-chromedriver, bypasses bot detection
- **Playwright CDP**: Connects to the already-running Chrome via DevTools Protocol for precise DOM manipulation and network interception

## Technology Decisions

### Why FastAPI?

- Async-first design fits well with parallel distributor API calls
- Automatic OpenAPI/Swagger documentation
- Pydantic schemas provide request/response validation
- Python ecosystem has the best LLM library support (anthropic SDK)

### Why React (not HTMX)?

The UI requires:
- Complex modals (multi-tab pricing modal, comparison search)
- Inline editing (invoice lines, recipe ingredients)
- Real-time search with debouncing
- Multi-column drag layouts (cart builder)

HTMX was considered for simplicity but the interaction complexity justified a full SPA.

### Why PostgreSQL?

The domain is deeply relational:
- Distributors have SKUs. SKUs have price histories.
- Ingredients appear in recipes. Recipes produce menu items.
- Invoices contain lines that map to SKUs.

Document databases would require duplicating data or complex joins. PostgreSQL handles this naturally with foreign keys and the query planner optimizes the joins.

### Why Cloud Run?

- Scales to zero: no cost when idle (this is a small business tool, not a high-traffic service)
- Automatic scaling: handles burst traffic during invoice processing
- Simple deployment: push Docker image, done
- Integrates with Cloud SQL via Unix socket (no public IP needed)

### Why Alembic?

- Schema versioning with up/down migrations
- Supports both auto-generated and hand-written migrations
- The 15 migrations document the evolution of the data model from initial tables through Order Hub

## Security Model

| Layer | Approach |
|-------|----------|
| **Secrets** | GCP Secret Manager (never in code or environment files) |
| **Database** | Private networking via Cloud SQL connector (no public IP in production) |
| **CI/CD** | Workload Identity Federation (no service account keys) |
| **Distributor credentials** | Stored in Secret Manager, referenced by distributor ID |
| **API authentication** | Currently simple (intended for single-user internal tool) |
| **Invoice PDFs** | Cloud Storage with restricted bucket access |
