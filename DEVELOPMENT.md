# Development Log

This document tracks development progress, session logs, and key decisions for the Mill & Whistle BI Suite.

## Quick Status

| Phase | Status | Last Updated |
|-------|--------|--------------|
| P0: Foundation | **Complete** | Dec 2024 |
| P1: Invoice Intelligence | **Complete** | Dec 2024 |
| P2: Ingredient & Pricing | **Complete** | Dec 2024 |
| P3: Recipe & Menu Costing | **In Progress** | Dec 2024 |
| P4: Order Hub | **In Progress** | Jan 2025 |
| P5: Sales Integration | Not Started | - |

## Current Work

**Phase 4: Order Hub** - Infrastructure and Distributor API Clients Complete

### Completed Work Units

- [x] **P3.1: Recipe Database** - Tables, models, CRUD endpoints
- [x] **P3.2: Recipe Importer** - Google Sheets integration, ingredient matching
- [x] **P3.3a-k: Cost Calculator & UX** - Cost calculator, component pricing, SKU mapping redesign, distributor management
- [x] **P4.1a-i: Order Hub Infrastructure** - Database, models, APIs, frontend pages, search modal
- [x] **P4.2a-c: Distributor Clients** - 5 clients with browser automation, live search working

### Remaining Work

- [ ] **P3.4: Margin Analyzer** - Menu profitability report
- [ ] **P3.5: What-If Simulator** - Price change impact modeling
- [ ] **P4.3a: UI Redesign** - Search-first design with lightweight list management
- [ ] **P4.3b: Cart Operations** - Test add_to_cart, get_cart, clear_cart on all distributors
- [ ] **P4.3c: Order Submission** - Capture and implement order placement

---

## Session Log

### Session: Jan 28, 2025 (Order Hub - All Distributors Working + UI Plan)

**Focus**: Fix remaining distributor search issues, create UI redesign plan

**Completed**:

1. **Fixed All 5 Distributors**
   - Added debug endpoints for troubleshooting
   - Fixed `api_config` to include `secret_name` for credential loading
   - Fixed Valley Foods `base_url` (was website URL, needed API URL)
   - Cleared corrupted session data
   - All distributors now authenticate and search successfully

2. **Search Test Results** (query: "ricotta"):
   - 14 results across 5 distributors in ~8.5 seconds
   - Prices range from $16.82 to $50.34

3. **UI Redesign Plan Created**
   - Search-first design with lightweight list management
   - Color-coded statuses (new/history/assigned/ordered/arrived)
   - Enhanced price display with normalization

### Session: Jan 28, 2025 (Order Hub - Phase 2 Distributor Clients)

**Focus**: Complete distributor API clients and fix search issues

**Completed**:

1. **All 5 Distributor Clients Working**
   - Fixed per-distributor operation company numbers
   - Fixed token refresh (Azure B2C returns `id_token` not `access_token` on refresh)
   - Parallel search completes in ~9 seconds

2. **Cart Operations Tested**

   | Distributor | Add to Cart | Get Cart | Notes |
   |-------------|-------------|----------|-------|
   | Farm Direct | Works | Full details | |
   | Green Market | Works | No retrieve API | |
   | Metro Wholesale | Works | Full details | |
   | Valley Foods | Works | Totals only | |
   | Mountain Produce | Works | Totals only | |

### Session: Jan 27, 2025 (Order Hub - Phase 1 Infrastructure)

**Focus**: Implement Order Hub centralized ordering system

**Completed**: Full infrastructure build including database migration, models, DistributorApiClient base class, Order List API, Search Aggregator, Order Builder API, and frontend pages (OrderList, OrderBuilder, ComparisonSearchModal).

---

## Decision Log

### Prices in Cents (Integer Storage)

**Decision**: Store all monetary values as integers (cents) rather than floats or decimals.

**Rationale**: Avoids floating-point arithmetic issues. `$35.49` is stored as `3549`. All calculations use integer math. Display formatting happens only at the UI layer.

### Base Unit Normalization

**Decision**: Convert all ingredient quantities to grams (weight), milliliters (volume), or each (count).

**Rationale**: Makes cross-distributor comparison possible. A 36-lb case and a 50-lb case both reduce to price-per-gram. The formula: `total_grams = pack_size * units_per_pack * grams_per_unit`, then `price_per_gram = price_cents / total_grams`.

### Confidence-Based Invoice Review

**Decision**: Invoice parsing produces a confidence score. >=0.9 auto-approve, 0.7-0.9 quick review, <0.7 full review.

**Rationale**: Most invoices from known distributors parse cleanly. The review queue focuses human attention on edge cases rather than rubber-stamping every invoice.

### Ingredient-First SKU Mapping

**Decision**: Redesign MapSkus page with ingredient-first navigation instead of SKU-first.

**Rationale**: Users think in terms of ingredients they need to price, not raw SKU lists. Select an ingredient first, then see all its mapped SKUs grouped by distributor. More intuitive mental model: "I need to price Salt" -> find Salt -> see/add its supplier SKUs.

### Component Ingredients

**Decision**: Ingredients with `source_recipe_id` derive price from recipe cost / yield.

**Rationale**: An ingredient like "Cold Brew Concentrate" links to the recipe that produces it. Cost automatically updates when recipe ingredients change. Circular reference protection via `_calculating_recipes` set.

### React Frontend

**Decision**: React + Vite + TypeScript + Tailwind CSS over HTMX.

**Rationale**: Better mobile responsiveness, rich component ecosystem (shadcn/ui), type safety with TypeScript, fast development iteration with Vite. The UI complexity (modals, inline editing, search-as-you-type) justified a full SPA framework.

### Unit Conversion Architecture

**Decision**: Display in practical units (lb, oz, L, gal), store in base units (g, ml, each).

**Rationale**: Users think in real-world units. Backend `units.py` service provides conversions. `useUnits()` hook gives consistent access across all frontend components. Single source of truth via `/api/v1/units` endpoint.

### Browser Automation for Distributor Auth

**Decision**: SeleniumBase UC + Playwright CDP for distributors with anti-bot protection.

**Rationale**: Many distributor sites block standard HTTP clients (Azure B2C OAuth with ROPC disabled, reCAPTCHA, fingerprinting). SeleniumBase UC provides anti-detection. Playwright CDP enables programmatic control after browser launch. Token refresh keeps sessions alive without repeated browser launches.

### Fraction Pack Pattern Support

**Decision**: Support pack descriptions with embedded fractions like `9/1/2GAL` (9 x 1/2 gallon).

**Rationale**: Real distributor invoices use this format. Pattern: `(count)/(numerator)/(denominator)(UNIT)`. Example: `9/1/2GAL` = 9 packs x 0.5 gallon each = 17,034 ml total.

### Pricing Mode Toggle

**Decision**: Recipe costs support "recent" (most recent price) and "average" (N-day average) modes.

**Rationale**: Recent shows current reality; average smooths volatility for long-term planning.
