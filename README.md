# Mill & Whistle BI Suite

A modular business intelligence platform built for a small cafe and retail operation. Automates the full supply chain from invoice ingestion through recipe costing and order management -- replacing spreadsheets and manual workflows with an integrated system.

Built as a solo project to solve real operational problems at a small business in Vermont.

## What It Does

**Invoice Intelligence** -- Emails arrive with PDF invoices. Claude Haiku parses them into structured line items with confidence scoring. A human review queue catches edge cases before prices flow into the system.

**Ingredient Pricing** -- Every distributor SKU maps to a canonical ingredient. Prices normalize to base units (grams, ml, each) so you can compare a 36-lb case from one distributor against a 50-lb case from another at a glance.

**Recipe Costing** -- Recipes pull live ingredient prices to calculate real-time food costs. Component ingredients (like house-made cold brew) derive their price from the recipe that produces them. Menu items show margin analysis against selling price.

**Order Hub** -- Search across five distributor APIs simultaneously, compare prices side-by-side, build carts with minimum-order tracking, and generate orders. Browser automation handles OAuth flows for distributors with anti-bot protection.

## Architecture

```
                          EXTERNAL SYSTEMS
    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
    │  Email   │  │ Dist.    │  │  Google  │  │ Dist.    │
    │ (Gmail)  │  │ Portals  │  │  Sheets  │  │  APIs    │
    └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
         │             │             │              │
         v             v             v              v
    ┌─────────────────────────────────────────────────────┐
    │               INGESTION LAYER                       │
    │  Email listener  |  PDF parser (Claude Haiku)       │
    │  Price scraper   |  Sheets importer                 │
    │  Browser capture |  Manual entry forms              │
    └────────────────────────┬────────────────────────────┘
                             │
                             v
    ┌─────────────────────────────────────────────────────┐
    │            CORE DATABASE (PostgreSQL)                │
    │                                                     │
    │  distributors ──> dist_ingredients ──> price_history │
    │  ingredients  <── recipe_ingredients ──> recipes     │
    │  invoices ──> invoice_lines    menu_items            │
    │  order_list_items ──> assignments ──> orders         │
    └────────────────────────┬────────────────────────────┘
                             │
                             v
    ┌─────────────────────────────────────────────────────┐
    │              PROCESSING LAYER                       │
    │  Price normalization (units -> grams/ml/each)       │
    │  Cost roll-up (ingredient -> recipe -> menu item)   │
    │  Search aggregation (parallel distributor queries)  │
    │  Confidence scoring (invoice parse quality)         │
    └────────────────────────┬────────────────────────────┘
                             │
                             v
    ┌─────────────────────────────────────────────────────┐
    │                OUTPUT LAYER                         │
    │  React SPA   |  REST API  |  Daily digest email    │
    │  PDF reports |  Order generation                   │
    └─────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend** | Python 3.12, FastAPI | Async-first, excellent for data pipelines, strong LLM library ecosystem |
| **Frontend** | React, TypeScript, Vite, Tailwind CSS | Component model fits complex UI (modals, tables, search), mobile-responsive |
| **Database** | PostgreSQL 15 (Cloud SQL) | Relational model fits the domain perfectly -- prices, recipes, invoices are all relational |
| **Invoice Parsing** | Claude Haiku API | Handles messy PDF layouts (columnar invoices, credits, multi-format) at low cost |
| **Browser Automation** | SeleniumBase UC + Playwright CDP | Anti-bot evasion for distributor portals with OAuth/reCAPTCHA |
| **Hosting** | GCP Cloud Run | Scales to zero, ~$25/mo total infrastructure cost |
| **CI/CD** | GitHub Actions + Workload Identity Federation | Keyless auth to GCP, auto-deploy on push to main |
| **Migrations** | Alembic | Schema versioning with up/down migrations |

## Project Structure

```
mw-bi-suite/
├── app/
│   ├── main.py                     # FastAPI entry point
│   ├── database.py                 # DB connection + session management
│   ├── api/
│   │   ├── distributors.py         # Distributor CRUD
│   │   ├── invoices.py             # Invoice upload, review, line mapping
│   │   ├── ingredients.py          # Ingredients, SKU mapping, pricing
│   │   ├── recipes.py              # Recipes, menu items, cost endpoints
│   │   ├── units.py                # Unit conversion + pack parsing API
│   │   ├── order_list.py           # Shared order list CRUD
│   │   ├── order_builder.py        # Cart assignments, order finalization
│   │   └── distributor_search.py   # Parallel distributor search
│   ├── models/                     # SQLAlchemy ORM models
│   ├── schemas/                    # Pydantic request/response schemas
│   └── services/
│       ├── invoice_parser.py       # Claude Haiku PDF/image parsing
│       ├── invoice_processor.py    # Parse + save orchestration
│       ├── price_parser.py         # Price list parsing (any format)
│       ├── cost_calculator.py      # Recipe costing + component pricing
│       ├── units.py                # Unit conversions + pack size parsing
│       ├── gmail_service.py        # Email ingestion + Cloud Storage
│       ├── distributor_client.py   # Base class for distributor API clients
│       ├── search_aggregator.py    # Parallel multi-distributor search
│       └── clients/                # Per-distributor API implementations
├── frontend/
│   ├── src/
│   │   ├── pages/                  # Route pages (14 pages)
│   │   ├── components/             # Shared components + UI primitives
│   │   ├── hooks/                  # Custom React hooks
│   │   ├── lib/                    # API client, utilities
│   │   └── types/                  # TypeScript interfaces
│   └── vite.config.ts
├── alembic/versions/               # Database migrations (001-015)
├── docs/                           # Architecture, data model, module specs
├── .github/workflows/deploy.yml    # CI/CD pipeline
├── Dockerfile
└── requirements.txt
```

## Key Design Decisions

**Prices in cents.** All monetary values stored as integers to avoid floating-point arithmetic issues. A `$35.49` case is stored as `3549`.

**Base unit normalization.** Every ingredient quantity converts to grams, milliliters, or each. This makes cross-distributor comparison possible: a 36-lb case and a 50-lb case both reduce to price-per-gram.

**Confidence-based review with adaptive prompts.** Invoice parsing produces a confidence score. High confidence (>0.9) can auto-approve. Low confidence (<0.7) gets full manual review. When parsing fails, operators refine the prompt through a side-by-side comparison UI and save the winning version -- a human-in-the-loop feedback cycle that improves extraction accuracy per distributor over time. See [Adaptive Parsing](#adaptive-parsing-human-in-the-loop-prompt-optimization) below.

**Component ingredients.** An ingredient like "Cold Brew Concentrate" can link to the recipe that produces it. Its cost is derived from the recipe's ingredient costs divided by yield -- no manual price entry needed.

**Browser automation for auth.** Some distributors use Azure B2C OAuth with PKCE, reCAPTCHA, or sophisticated anti-bot detection. SeleniumBase UC handles initial auth; refresh tokens keep sessions alive without repeated browser launches.

## Phase Roadmap

| Phase | Module | Status | Description |
|-------|--------|--------|-------------|
| 0 | Foundation | **Complete** | GCP setup, database schema, FastAPI skeleton, CI/CD pipeline |
| 1 | DMS - Distributor Management | **Complete** | Email ingestion, PDF parsing with Claude Haiku, review queue, price pipeline |
| 2 | IPI - Ingredient Pricing | **Complete** | Unit conversion engine, SKU mapping UI, cross-distributor price comparison |
| 3 | RMC - Recipe Costing | **Complete** | Recipe database, Google Sheets import, cost calculator, component pricing |
| 4 | OPA - Order Hub | **In Progress** | Multi-distributor search, cart builder, browser automation, 5 API clients |
| 5 | SOA - Sales Integration | Planned | Toast POS integration, margin dashboards, sales forecasting |

## Quick Start (Local Development)

### Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL 15 (local or Cloud SQL with proxy)
- Google Cloud SDK (if using Cloud SQL)

### Environment Variables

```bash
# Database
export DB_HOST=localhost
export DB_PORT=5432          # or 5434 if using Cloud SQL Proxy
export DB_NAME=mw_bi_suite
export DB_USER=mw_app
export DB_PASSWORD=your_db_password

# Claude API (for invoice parsing)
export ANTHROPIC_API_KEY=your_api_key

# Optional: Gmail API (for email ingestion)
export GMAIL_CLIENT_ID=your_client_id
export GMAIL_CLIENT_SECRET=your_client_secret
export GMAIL_REFRESH_TOKEN=your_refresh_token

# Optional: Cloud SQL (for GCP deployment)
export INSTANCE_CONNECTION_NAME=YOUR_GCP_PROJECT:us-east4:YOUR_DB_INSTANCE
```

### Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Run database migrations
python3 -m alembic upgrade head

# Start the API server
uvicorn app.main:app --reload

# API available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev

# Available at http://localhost:5173
# Proxies /api requests to backend at localhost:8000
```

### With Cloud SQL Proxy (GCP)

```bash
# Start proxy in a separate terminal
cloud-sql-proxy YOUR_GCP_PROJECT:us-east4:YOUR_DB_INSTANCE --port=5434

# Fetch DB password from Secret Manager
export DB_PASSWORD=$(gcloud secrets versions access latest \
  --secret=db-password --project=YOUR_GCP_PROJECT)

# Start server
DB_PORT=5434 uvicorn app.main:app --reload
```

## Deployment

Deployments are automatic on push to `main`:

```
Push to main --> GitHub Actions --> Build Docker image
    --> Push to Artifact Registry --> Deploy to Cloud Run
```

Uses Workload Identity Federation for keyless GCP authentication (no service account keys stored in CI).

## API Overview

The API serves ~40 endpoints across these resource groups. Full OpenAPI docs available at `/docs` when running locally.

| Resource | Key Endpoints |
|----------|--------------|
| **Distributors** | CRUD, scraping toggle |
| **Invoices** | Upload (PDF/image/text), review queue, approve, line editing, ingredient mapping |
| **Ingredients** | CRUD, SKU mapping, manual/invoice/parsed pricing, price comparison |
| **Recipes** | CRUD, Google Sheets import, cost breakdown, component pricing |
| **Menu Items** | CRUD, margin calculation |
| **Units** | Conversion factors, pack description parsing |
| **Order List** | Shared "need to order" list with history |
| **Order Builder** | Cart assignments, distributor cart management, order finalization |
| **Distributor Search** | Parallel search across enabled distributors |

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System design, data flow, technology rationale |
| [Data Model](docs/02-data-model.md) | Database schema, ERD, pricing architecture |
| [Infrastructure](docs/infrastructure.md) | GCP setup guide, deployment, environment variables |
| [Module Specs](docs/03-modules/) | Detailed requirements per module |
| [Implementation Plan](docs/04-implementation.md) | Phased rollout plan |

## Claude API Integration

This project uses Anthropic's Claude API in two ways:

1. **Invoice Parsing** (Haiku) -- Extracts line items from PDF invoices. Handles columnar layouts, credits/allowances, and multi-page documents. Returns structured JSON with confidence scores per field.

2. **Price List Parsing** (Haiku) -- Parses ad-hoc price information from screenshots, emails, or text snippets into structured price data.

Both use Haiku for cost efficiency (~$0.01 per invoice parse). The structured output format ensures consistent data regardless of input quality.

### Adaptive Parsing: Human-in-the-Loop Prompt Optimization

The system implements a feedback loop where human operators improve Claude's parsing accuracy over time -- essentially RLHF applied to prompt engineering rather than model weights.

**How it works:**

```
  New invoice arrives
        │
        v
  Parse with distributor's prompt
  (or base prompt if first time)
        │
        v
  ┌─ Confidence ≥ 0.9 ──> Auto-approve, prices flow into system
  │
  ├─ Confidence 0.7-0.9 ──> Quick review, operator confirms/corrects
  │
  └─ Confidence < 0.7 ──> Full review ──> Operator opens Prompt Editor
                                                    │
                                                    v
                                          ┌──────────────────┐
                                          │  Side-by-side UI  │
                                          │                   │
                                          │  LEFT:  Original  │
                                          │  prompt + results  │
                                          │                   │
                                          │  RIGHT: Modified  │
                                          │  prompt + results  │
                                          └────────┬─────────┘
                                                   │
                                          Iterate: edit prompt,
                                          click "Try", compare
                                                   │
                                                   v
                                          Save winning prompt
                                          to distributor record
                                                   │
                                                   v
                                          All future invoices from
                                          this distributor use the
                                          optimized prompt
```

**What makes this HITL rather than simple configuration:**

- **Feedback is grounded in output quality.** The operator sees exactly how a prompt change affects parsed results before committing. This is A/B testing at the prompt level.
- **Knowledge accumulates per distributor.** Each distributor develops its own optimized prompt that encodes domain knowledge -- "PFG invoices have quantity in column 2, not column 3" or "Sysco credits appear as negative line items."
- **Three prompt channels.** Each distributor stores separate prompts for PDF invoices, email text, and screenshots/price lists, since the same distributor's data looks different across formats.
- **Non-technical operators can participate.** The UI abstracts away prompt engineering -- operators just tweak instructions in plain English and see if the output improves. No ML expertise required.

**Technical implementation:**
- Per-distributor prompt storage: `distributors.parsing_prompt_pdf`, `parsing_prompt_email`, `parsing_prompt_screenshot` (text columns)
- Preview endpoint: `POST /invoices/{id}/reparse-preview` -- parses without saving, returns results + prompt used
- Prompt management: `GET/PATCH /distributors/{id}/prompts` -- fetch current prompts, save optimized versions
- Frontend: `PromptEditorModal` component with side-by-side comparison, multi-format save

## Cost

Total infrastructure runs ~$25-50/month on GCP:

| Service | Monthly |
|---------|---------|
| Cloud SQL (db-f1-micro) | ~$10-15 |
| Cloud Run (scales to zero) | ~$5-10 |
| Claude Haiku API | ~$1-5 |
| Storage + Registry | <$2 |
