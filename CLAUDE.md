# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mill & Whistle BI Suite - A modular business intelligence system for a small cafe/retail operation. The project automates distributor management, ingredient costing, recipe analytics, and operational reporting.

**Current Status**: Phase 4 (Order Hub) - Distributor API clients complete for 5 distributors.

### Phase 4 Summary (OPA - Order Hub)
- **P4.1**: Order Hub Infrastructure - COMPLETE
  - Database: order_list_items, assignments, distributor_sessions tables
  - Distributor extensions: api_config, ordering_enabled, capture_status
  - DistributorApiClient base class with session management
  - SearchAggregator for parallel distributor search
  - Order List API (CRUD, history), Order Builder API (assignments, finalize)
  - Frontend: OrderList page, OrderBuilder page, ComparisonSearchModal
- **P4.2**: Distributor API Clients - COMPLETE
  - 5 food distributors working: Valley Foods, Mountain Produce, Metro Wholesale, Farm Direct, Green Market
  - Browser automation via SeleniumBase UC + Playwright CDP
  - Automated OAuth2 login with token refresh
  - Credentials in GCP Secret Manager
- **Next**: Wire up SearchAggregator, test cart operations

### Phase 3 Summary (RMC - Recipe & Menu Costing)
- **P3.1-P3.3**: Complete - Recipe database, importer, cost calculator
- **Remaining**: Margin analyzer (P3.4), what-if simulator (P3.5)

## Technology Stack

- **Database**: PostgreSQL on GCP Cloud SQL
- **Backend**: Python 3.12 with FastAPI
- **Frontend**: React + Vite + TypeScript + Tailwind CSS
- **Invoice Parsing**: Claude Haiku API (PDF + text)
- **Hosting**: GCP Cloud Run
- **CI/CD**: GitHub Actions with Workload Identity Federation
- **Migrations**: Alembic
- **Key Libraries**:
  - `anthropic` - Claude API client
  - `google-cloud-storage` - PDF storage
  - `google-cloud-secret-manager` - Credentials
  - `google-api-python-client` - Gmail API, Sheets API
  - `react-query` - Frontend data fetching
  - `react-router-dom` - Frontend routing
  - `seleniumbase` - Anti-bot browser automation (undetected-chromedriver)
  - `playwright` - Browser automation and CDP connection

## Project Structure

```
mw-bi-suite/
├── .github/workflows/
│   └── deploy.yml              # CI/CD pipeline (GitHub Actions -> Cloud Run)
├── alembic/
│   └── versions/               # Database migrations (001-015)
├── app/
│   ├── api/
│   │   ├── distributors.py     # Distributor CRUD endpoints
│   │   ├── invoices.py         # Invoice review + upload + line mapping endpoints
│   │   ├── ingredients.py      # Ingredient + mapping + pricing endpoints
│   │   ├── recipes.py          # Recipe + menu item CRUD
│   │   ├── units.py            # Unit conversions + pack parsing API
│   │   ├── order_list.py       # Order Hub - shared order list
│   │   ├── order_builder.py    # Order Hub - cart building + orders
│   │   ├── distributor_search.py # Order Hub - parallel search
│   │   └── email_ingestion.py  # Email processing trigger
│   ├── models/                 # SQLAlchemy models
│   │   ├── distributor.py
│   │   ├── invoice.py          # Invoice + InvoiceLine
│   │   ├── ingredient.py       # Ingredient, DistIngredient, PriceHistory
│   │   ├── recipe.py           # Recipe, RecipeIngredient, MenuItem
│   │   ├── order.py            # Order, OrderLine
│   │   └── order_hub.py        # OrderListItem, Assignment, DistributorSession
│   ├── services/
│   │   ├── gmail_service.py    # Gmail API + Cloud Storage
│   │   ├── invoice_parser.py   # Claude Haiku parsing (PDF + images)
│   │   ├── invoice_processor.py # Parse + save orchestration
│   │   ├── email_ingestion.py  # Email -> Invoice pipeline
│   │   ├── price_pipeline.py   # Approved invoices -> price_history
│   │   ├── price_parser.py     # Claude Haiku price list parsing
│   │   ├── cost_calculator.py  # Recipe costing + batch pricing
│   │   ├── units.py            # Unit conversions + pack parsing
│   │   ├── recipe_importer.py  # Sheet -> recipe import
│   │   ├── sheets_service.py   # Google Sheets API
│   │   ├── distributor_client.py # Order Hub - API client base class
│   │   └── search_aggregator.py  # Order Hub - parallel search
│   ├── database.py
│   └── main.py
├── frontend/                   # React SPA
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/             # Reusable UI components
│   │   │   └── PriceIngredientModal.tsx
│   │   ├── hooks/
│   │   │   └── useUnits.ts     # Units conversion hook
│   │   ├── pages/
│   │   │   ├── Invoices.tsx, InvoiceReview.tsx
│   │   │   ├── IngredientsList.tsx, IngredientDetail.tsx
│   │   │   ├── MapSkus.tsx     # SKU mapping (ingredient-first navigation)
│   │   │   ├── Prices.tsx      # Price comparison matrix
│   │   │   ├── Recipes.tsx, RecipeDetail.tsx, RecipeEdit.tsx
│   │   │   ├── Settings.tsx    # Distributor management
│   │   │   ├── Upload.tsx      # Invoice upload (PDF/image/text)
│   │   │   ├── OrderList.tsx   # Order Hub - shared order list
│   │   │   └── OrderBuilder.tsx # Order Hub - cart builder
│   │   ├── lib/                # Utils + API client
│   │   └── types/              # TypeScript types
│   ├── package.json
│   └── vite.config.ts
├── scripts/
├── docs/
├── DEVELOPMENT.md              # Session log, decisions, progress
├── Dockerfile
└── requirements.txt
```

## Architecture Highlights

- **Layered System**: External systems -> Ingestion layer -> Core database -> Processing layer -> Output layer
- **Invoice Pipeline**: Email listener -> PDF extraction -> Claude Haiku parsing -> Human review queue -> On approval: price_history populated
- **Price Normalization**: All units converted to base units (grams/ml/each) for cross-distributor comparison
- **Cost Roll-up**: Ingredient prices -> Recipe costs -> Menu item margins
- **Component Ingredients**: Ingredients with `source_recipe_id` derive price from recipe cost / yield

## Data Model

Key entities and relationships:
- `distributors` -> `dist_ingredients` (SKUs) -> `price_history`
- `ingredients` (canonical) <- `recipe_ingredients` -> `recipes` -> `menu_items`
- `ingredients.source_recipe_id` -> `recipes` (for component ingredients)
- `menu_items` -> `menu_item_packaging` -> `ingredients` (packaging type)
- `invoices` -> `invoice_lines` <- reconciliation -> orders

All prices stored in cents. UUIDs for primary keys.

## Module Priority

1. **DMS** (Distributor Management) - Complete. Invoice parsing, reconciliation, disputes, payments
2. **IPI** (Ingredient Pricing) - Complete. Unit normalization, price comparison across distributors
3. **RMC** (Recipe Costing) - In Progress. Cost roll-ups, margin analysis
4. **OPA** (Order Planning) - In Progress. Parallel search, cart builder, order optimization
5. **SOA** (Sales Integration) - Planned. Toast POS integration, dashboards

## Key Design Decisions

- Store all prices in **cents** (integer) to avoid floating-point issues
- Use **base units** (grams, ml, each) for all ingredient quantities
- Invoice parsing confidence thresholds: >=0.9 auto-approve, 0.7-0.9 quick review, <0.7 full review
- **Frontend**: React chosen over HTMX for mobile responsiveness and component ecosystem
- **Invoice sources**: email (automatic), upload (PDF or email text), manual entry
- **Review workflow**: All invoices start as `pending`, must be explicitly approved
- **Unit conversion**: Display in practical units (lb, oz, L), store in base units (g, ml)
- **Component ingredients**: Price derived from source recipe cost / yield quantity

## Model Usage

| Task | Model | Rationale |
|------|-------|-----------|
| Invoice PDF parsing | Haiku | High volume, structured output, cost-effective |
| Item mapping suggestions | Haiku | Batch processing, simple classification |
| Price list parsing | Haiku | Handles any format (PDF, image, text, email) |
| Website structure analysis | Sonnet | One-time per distributor, needs reasoning |

## Development Practices

- **CI/CD**: GitHub Actions with auto-deploy on push to main
- **Secrets**: GCP Secret Manager for production, GitHub Secrets for CI/CD pipelines
- **Credentials**: Portal logins stored in Secret Manager, referenced by distributor ID
- **Auth**: Workload Identity Federation (no service account keys)

## Local Development

**Prerequisites**:
- Python 3.12+
- Node.js 18+
- PostgreSQL 15 (local or Cloud SQL with proxy)
- Google Cloud SDK (if using Cloud SQL)

**Backend** (from repo root):
```bash
# Set environment variables (see docs/infrastructure.md for full list)
export DB_PASSWORD=your_password
export DB_PORT=5432

# Run migrations
python3 -m alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

**Frontend** (from `frontend/`):
```bash
npm install
npm run dev  # Runs on http://localhost:5173
```

The frontend proxies `/api` requests to the backend at `localhost:8000`.

**Troubleshooting**: See `docs/infrastructure.md` for common auth/connection issues.

## Browser Automation & Credential Capture

For distributors with anti-bot protection or complex OAuth flows, we use **SeleniumBase UC + Playwright CDP**.

### Why This Approach

Many distributor sites block standard HTTP clients:
- **OAuth2 PKCE flows**: Azure B2C with ROPC disabled - requires browser
- **reCAPTCHA**: Blocks programmatic login
- **Anti-bot detection**: Sophisticated fingerprinting

### How It Works

1. **SeleniumBase UC** launches Chrome with anti-bot evasion (undetected-chromedriver)
2. **Playwright** connects via Chrome DevTools Protocol (CDP)
3. Credentials are filled automatically, OAuth flows complete
4. Tokens extracted from MSAL sessionStorage, cookies captured
5. `refresh_token` enables ongoing access without re-running browser

### Token Lifecycle

```
Browser auto-login -> access_token (1hr) + refresh_token
                          |
              Use access_token for API calls
                          |
              Expired? Use refresh_token (no browser needed)
                          |
              Refresh failed? Re-run browser auto-login
```

### Supported Auth Methods

| Auth Method | Browser Needed? |
|-------------|-----------------|
| OAuth2 PKCE | Yes (initial + refresh fail) |
| Cookie (JSON POST) | No |
| Cookie + CSRF (form POST) | No |
| Cookie + reCAPTCHA | Yes |

## Session Tracking

See `DEVELOPMENT.md` at repo root for:
- Current work unit and next actions
- Session-by-session progress log
- Decision log with rationale
- Work unit breakdown by phase
