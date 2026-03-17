# Recipe & Cost Intelligence System — Design Spec

## Overview

This feature branch transforms the Mill & Whistle BI Suite from a data-collection tool into a **cost intelligence platform** centered on recipe management. The core value proposition: when browsing distributor prices and building orders, you see exactly how each decision affects your active menu margins in real time.

### Scope

**Core (must ship together):**
- Live cost impact simulation during distributor search/selection
- Three-tier pricing model (confirmed/observed/intent) with visual differentiation
- Passive price capture from search results with auto-mapping to known SKUs
- Menu Dashboard with expandable ingredient breakdowns and live cost stats
- AI recipe features (proofread, kitchen review, Spanish translation) with HITL prompt editing

**High value (should be in this branch if feasible):**
- Recipe editor UX overhaul (two-column editor + live preview)
- Print-optimized recipe view (English/Spanish side-by-side)
- Google Sheets export

**Fast-follow (next branch):**
- What-if simulator (P3.5)
- Cart review rollup summary
- Sheets import improvements
- Google Drive browsing for import

### Key Decisions

- **MenuItem is the "active menu" unit** — recipes without a MenuItem link are R&D, archived, or components. No new "on_menu" flag needed.
- **Backend-driven cost simulation (Approach B)** — single source of truth for cost math in Python. ~100-200ms API round-trip is acceptable. No client-side cost duplication.
- **Database is source of truth** — Google Sheets is I/O only (import existing recipes, export snapshots for sharing/printing). No two-way sync.
- **All development on `main` branch** (or feature branch off `main`). The `public-repo-prep` branch is not touched.

---

## 1. Data Model Changes

### 1.1 PriceHistory — add `price_type`

New column on existing `price_history` table:

```sql
ALTER TABLE price_history ADD COLUMN price_type VARCHAR(10) NOT NULL DEFAULT 'confirmed';
```

Values:
- **`confirmed`** — From an approved invoice or completed order. The "real" price. All existing records receive this value via migration.
- **`observed`** — Price change detected on a SKU we already buy. Captured passively during distributor search. Only created when: (a) the search result maps to an existing `DistIngredient` with confirmed price history, AND (b) the price differs from the most recent confirmed price.
- **`intent`** — Item assigned in Order Builder (in cart). Transitions to `confirmed` when the order is finalized.

The existing `source` column (`invoice`, `catalog`, `manual`, `quote`, `order_hub_search`) is orthogonal — it records *where* the price came from, while `price_type` records *how certain* it is.

### 1.2 Recipe — add `instructions_es`

```sql
ALTER TABLE recipes ADD COLUMN instructions_es TEXT;
```

Stores AI-generated Spanish translation of recipe instructions. Persisted so it doesn't need re-translation on every view. The frontend flags when English instructions have been modified since the last translation.

### 1.3 AI Prompts — new table

```sql
CREATE TABLE ai_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation VARCHAR(30) NOT NULL UNIQUE,  -- 'recipe_proofread', 'recipe_kitchen_review', 'recipe_translate'
    prompt TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT now()
);
```

Stores system-level prompts for AI recipe operations. Each starts with a sensible default. Users can iterate via the HITL PromptEditorModal flow and promote improved prompts. One prompt per operation (not per-recipe — the prompts are generic).

### 1.4 No other schema changes

- `MenuItem` already has `is_active`, `menu_price_cents`, `category`, `recipe_id`, `portion_of_recipe` — no changes needed.
- Cost impact simulation is stateless (no new tables).
- `DistIngredient` and `Ingredient` models unchanged.

---

## 2. Backend API

### 2.1 Cost Impact Simulation

**`POST /api/v1/cost-impact/simulate`**

The centerpiece endpoint. Accepts hypothetical price changes and returns full downstream impact on recipes and menu items.

Request:
```json
{
  "price_scenarios": [
    {
      "ingredient_id": "<uuid>",
      "price_per_base_unit_cents": 4.2,  // Decimal, not integer — sub-cent precision required (e.g., $0.042/gram)
      "price_type": "observed",
      "distributor_name": "Distributor A",
      "dist_ingredient_id": "<uuid>"
    }
  ],
  "scope": "active_menu"
}
```

`scope` options:
- `"active_menu"` — all active MenuItems (default)
- `"all"` — all recipes/menu items including inactive
- `["<recipe_id>", ...]` — specific recipe IDs (for R&D recipes not on the menu)

Response:
```json
{
  "affected_menu_items": [
    {
      "menu_item_id": "<uuid>",
      "name": "Lasagna",
      "category": "dinner",
      "menu_price_cents": 1800,
      "current_cost_cents": 485,
      "simulated_cost_cents": 522,
      "current_food_cost_pct": 26.9,
      "simulated_food_cost_pct": 29.0,
      "current_margin_status": "healthy",
      "simulated_margin_status": "warning",
      "cost_change_cents": 37,
      "cost_change_per_serving_cents": 37,
      "ingredients_affected": ["Ricotta", "Mozzarella"]
    }
  ],
  "summary": {
    "total_items_affected": 8,
    "avg_food_cost_current_pct": 27.1,
    "avg_food_cost_simulated_pct": 28.8,
    "items_changing_status": 2,
    "total_cost_impact_cents": 142
  }
}
```

Implementation: Uses existing `cost_calculator` logic but overrides specific ingredient prices with scenario values before computing. Pure read + compute — no database writes. The `get_ingredient_best_price()` and `calculate_recipe_cost()` functions gain an optional `price_overrides: dict[UUID, Decimal]` parameter (ingredient_id → price_per_base_unit) that, when provided, bypasses the database lookup for those ingredients.

### 2.2 Menu Items Dashboard

**`GET /api/v1/menu-items/dashboard`**

Extends the existing `GET /menu-items/analyze` endpoint (which returns `MenuAnalyzerResponse` via `calculate_all_menu_item_costs()`). The dashboard endpoint adds price-type confidence indicators and per-ingredient cost drivers to the existing cost/margin data. Implementation should extend the existing `MenuItemAnalysis` schema rather than creating a parallel response type.

Query params:
- `pricing_mode`: `"recent"` (default) or `"average"`
- `average_days`: `30` (default, 1-365)
- `category`: optional filter
- `include_observed`: `true` (default) — whether to factor in observed prices
- `include_intent`: `true` (default) — whether to factor in intent prices

Response includes per-item:
```json
{
  "menu_item_id": "<uuid>",
  "name": "Egg Sandwich",
  "category": "breakfast",
  "menu_price_cents": 1000,
  "food_cost_cents": 291,
  "packaging_cost_cents": 22,
  "total_cost_cents": 313,
  "food_cost_pct": 31.3,
  "gross_margin_cents": 687,
  "margin_status": "warning",
  "price_confidence": "mixed",
  "cost_drivers": [
    {
      "ingredient_id": "<uuid>",
      "ingredient_name": "Eggs, large",
      "price_type": "observed",
      "price_per_base_unit_cents": 0.11,
      "previous_confirmed_cents": 0.08,
      "change_pct": 37.5,
      "line_cost_cents": 33,
      "pct_of_total": 10.5,
      "distributor_name": "Distributor C"
    }
  ]
}
```

`price_confidence` values:
- `"all_confirmed"` — every ingredient priced from confirmed sources
- `"mixed"` — some ingredients use observed or intent prices
- `"mostly_observed"` — majority of cost driven by non-confirmed prices

### 2.3 Modified Distributor Search

**`GET /api/v1/distributor-search`** (existing endpoint, modified behavior)

After returning search results, the backend passively records observed price changes via a background task (fire-and-forget, does not block the search response):

1. Check if the search result's SKU + distributor matches an existing `DistIngredient`.
2. If yes, check if that `DistIngredient` has any confirmed price history.
3. If yes, and the search result price differs from the most recent confirmed price, upsert a `PriceHistory` entry with `price_type='observed'` and `source='order_hub_search'`. **Deduplication**: only one `observed` entry per `dist_ingredient_id` per day — if one already exists for today, update the price rather than creating a duplicate.
4. If no existing `DistIngredient` match, skip (no auto-creation of SKU mappings).

Note: This write happens asynchronously after the search response is returned, keeping the GET semantics clean (the response itself is pure read). The background task handles the price capture side effect.

Search response enhanced with:
```json
{
  "last_confirmed_price_cents": 1410,
  "last_confirmed_date": "2026-03-02",
  "last_confirmed_distributor": "Distributor C",
  "price_delta_cents": 654,
  "price_delta_pct": 46.4,
  "canonical_ingredient_id": "<uuid>",
  "canonical_ingredient_name": "Eggs, large"
}
```

These fields are null for unmapped SKUs (no purchase history available).

### 2.4 Modified Order Builder Assignment

**`POST /api/v1/order-builder/assign`** (existing endpoint, modified behavior)

When creating an assignment:
- If a `PriceHistory` entry with `price_type='observed'` exists for this `DistIngredient` at this price, update it to `price_type='intent'`.
- Otherwise, create a new `PriceHistory` entry with `price_type='intent'`.

**`POST /api/v1/orders/finalize`** (existing endpoint, modified behavior)

When finalizing orders:
- All `intent` prices for the finalized order's line items transition to `confirmed`.

### 2.5 AI Recipe Endpoints

**`POST /api/v1/recipes/{recipe_id}/ai/proofread`**

Request:
```json
{
  "custom_prompt": null
}
```

Response:
```json
{
  "original": "string (original instructions)",
  "revised": "string (improved instructions)",
  "changes_summary": "string (what was changed and why)",
  "prompt_used": "string (the prompt that generated this)"
}
```

Does NOT auto-save. Frontend shows diff-style comparison for user to accept or reject.

Default prompt focus: improve clarity, fix grammar, standardize formatting (numbered steps, consistent verb tense, standard cooking terminology), preserve author's voice.

Model: Claude Haiku.

**`POST /api/v1/recipes/{recipe_id}/ai/kitchen-review`**

Request:
```json
{
  "custom_prompt": null
}
```

Response:
```json
{
  "findings": [
    {
      "step": 3,
      "issue": "Step says 'fold in gently' but doesn't specify what tool to use or what 'gently' means for someone unfamiliar with the technique",
      "suggestion": "Add: 'Using a rubber spatula, fold in with slow, sweeping motions from bottom to top. Stop when just combined — overmixing will deflate the batter.'",
      "severity": "warning"
    }
  ],
  "prompt_used": "string"
}
```

Sends full recipe (ingredients + instructions) to Claude acting as an inexperienced kitchen employee. Flags: missing steps, assumed knowledge, unclear quantities, unexplained techniques, ambiguous timing.

Model: Claude Haiku (bump to Sonnet if quality is insufficient during testing).

**`POST /api/v1/recipes/{recipe_id}/ai/translate`**

Request:
```json
{
  "custom_prompt": null
}
```

Response:
```json
{
  "instructions_es": "string (Spanish translation)",
  "prompt_used": "string"
}
```

Translates instructions only (not ingredients — those reference canonical names in the system). Uses natural, contextual Latin American Spanish appropriate for a professional kitchen. Not literal/mechanical translation.

On user confirmation, saves to `recipe.instructions_es`.

Model: Claude Haiku.

### 2.6 AI Prompt Management (HITL)

**`GET /api/v1/ai-prompts/recipe`**

Returns current prompts for all three operations:
```json
{
  "proofread": "string (current or default prompt)",
  "kitchen_review": "string",
  "translate": "string",
  "has_custom_proofread": true,
  "has_custom_kitchen_review": false,
  "has_custom_translate": false
}
```

**`PATCH /api/v1/ai-prompts/recipe`**

Updates a specific operation's prompt:
```json
{
  "operation": "kitchen_review",
  "prompt": "string (new prompt text)"
}
```

Follows the same HITL pattern as invoice parsing prompts: user edits prompt → clicks "Try" → sees results → iterates → "Save & Accept" promotes the prompt for all future use.

### 2.7 Google Sheets Export

**`POST /api/v1/recipes/{recipe_id}/export/sheet`**

Creates a new Google Sheet with the recipe formatted for sharing:
- Recipe name, yield info
- Ingredients table (name, amount, unit, prep note)
- Instructions (numbered steps)
- Cost breakdown (optional, controlled by query param `include_costs=true`)

Requires upgrading the OAuth scope from `spreadsheets.readonly` to `spreadsheets` in `SheetsService`. Since the existing OAuth refresh token in Secret Manager was consented for the readonly scope, a one-time re-authorization is needed to grant the broader scope, and the stored refresh token must be updated.

Response:
```json
{
  "spreadsheet_id": "string",
  "spreadsheet_url": "string"
}
```

---

## 3. Frontend Design

### 3.1 Order Hub Search — Cost Impact Panel

Layout: **Inline expand (Option A)** within the existing ComparisonSearchModal.

Search results grouped by distributor, with multiple SKUs per distributor. Each result row shows:
- Distributor name, SKU description, pack size
- Pack price + normalized price per base unit (e.g., `$2.84/lb`)
- "BEST PRICE" badge on lowest normalized price per canonical ingredient
- **Price delta vs. last confirmed purchase**: `+$0.04/lb vs last purchase (Distributor C, Mar 2)` — compared against last confirmed price for the same canonical ingredient, regardless of distributor
- Unmapped SKUs show: `No purchase history — unmapped SKU`

Clicking a result expands an **impact panel** below it showing:
- All active menu items that use this canonical ingredient
- Per-item: current food cost % → simulated food cost %, per-serving cost delta
- Summary: total items affected, average menu cost impact

The impact panel calls `POST /cost-impact/simulate` with the selected price as a scenario. Debounced to avoid excessive API calls during rapid clicking.

### 3.2 Menu Dashboard — Expandable Rows

Replaces or enhances the existing Menu page. Full-width table with:

**Summary bar** (top):
- Active item count
- Average food cost %
- Price alerts count (observed changes) — clickable to filter
- Margin health breakdown (healthy/warning/danger counts)

**Category filter** pills below summary bar.

**Table columns**: Item, Category, Menu Price, Total Cost, Food Cost %, Margin, Status.

**Collapsed rows** show:
- `▶` chevron for expand
- Price-type icon if non-confirmed prices affect the item (👁 observed, 🛒 intent)
- Old → new cost with strikethrough when prices have changed

**Expanded rows** show full ingredient breakdown:
- Ingredient name, amount (dual units: base + practical), unit price, line cost, % of total, source distributor
- Changed ingredients highlighted with price-type indicator and old → new strikethrough
- Packaging section with quantity and usage rate
- Totals row
- Action buttons: "View Recipe", "Edit Menu Item"

**Three-tier visual language** (consistent across all screens):

| Tier | Color | Icon | Treatment |
|------|-------|------|-----------|
| Confirmed | Default (no decoration) | None | Clean numbers |
| Observed | Orange (`#fb923c`) | 👁 | Strikethrough old price, subtle row highlight |
| Intent | Blue (`#60a5fa`) | 🛒 | Strikethrough old price |

**Sorting**: Click any column header. Default sort: food cost % descending (worst margins first).

### 3.3 Recipe Editor — Two-Column with Live Preview

Replaces existing `RecipeEdit.tsx`.

**Left column (editor):**
- Sticky cost bar at top: recipe name, cost/serving, food cost %, margin status badge — stays visible while scrolling
- Recipe metadata: name, yield quantity, yield unit, yield weight (for component ingredients)
- Ingredient table: ingredient name, amount in base units + practical units (e.g., `500g (1.1 lb)`), prep note, per-ingredient cost — inline editing
- `+ Add ingredient` with search/picker
- Instructions textarea (numbered steps, one per line)
- Notes textarea
- AI tool buttons (see 3.4)

**Right column (live preview):**
- Print-ready layout that updates as the editor changes
- Recipe name, yield
- Ingredients list with amounts
- Cost breakdown table
- Instructions — English and Spanish side-by-side (when `instructions_es` exists)
- Matches what will be printed via `Cmd+P` or "Print" button

Both columns scroll independently. The left column's sticky cost bar remains visible at all times.

### 3.4 AI Recipe Tools

Three buttons in the editor, below the notes section:

**Proofread & Polish** — calls `/ai/proofread`. Shows diff-style comparison (original vs. revised) with "Accept" / "Reject" / "Edit Prompt" buttons. Accept replaces instructions in the editor (not yet saved to DB until user saves the recipe).

**Kitchen Review** — calls `/ai/kitchen-review`. Shows annotated findings list with step references, severity indicators, and suggestions. User works through findings manually — this is advisory, not auto-applied.

**Translate to Spanish** — calls `/ai/translate`. Shows the Spanish translation in a preview. "Accept" saves to `recipe.instructions_es` and updates the live preview to show side-by-side layout.

All three buttons include an **"Edit Prompt"** option that opens the existing `PromptEditorModal` pattern: original prompt (left) + editable prompt (right), "Try" to test, iterate, "Save & Accept" to promote.

### 3.5 Print Layout

CSS print stylesheet applied to the recipe preview column. Triggered by `Cmd+P` or a "Print" button.

Layout:
- Recipe name (large heading)
- Yield info
- Ingredients table (practical units, prep notes)
- Instructions — English and Spanish in two columns side-by-side
- No cost data on printed version (costs are internal)

### 3.6 Google Sheets Export

"Export to Sheet" button on recipe detail page. Calls `POST /recipes/{recipe_id}/export/sheet`. Opens the resulting Sheet URL in a new tab.

The exported sheet is a read-only snapshot. Edits in the sheet do not sync back to the database.

---

## 4. Cost Calculation Priority

When multiple price types exist for the same ingredient, the cost calculator uses this priority:

**For simulation/dashboard views** (showing what's coming):
1. **Intent** (highest priority — we plan to buy at this price)
2. **Observed** (we saw this price change)
3. **Confirmed** (baseline — last actual purchase)

**For "confirmed only" baseline:**
- Only `confirmed` prices used
- Shown as strikethrough when a higher-priority price exists

This means the dashboard shows the most up-to-date picture by default, with visual indicators showing which prices are not yet confirmed.

---

## 5. Data Boundaries

| Data | Storage | Rationale |
|------|---------|-----------|
| Canonical recipes | PostgreSQL | Source of truth, linked to ingredients/costs/menu items |
| Recipe instructions (EN + ES) | PostgreSQL | Part of the recipe entity |
| AI prompts | PostgreSQL (`ai_prompts` table) | System config, versioned through HITL |
| Ingredient prices | PostgreSQL (`price_history`) | Time-series, supports three-tier model |
| Exported recipe sheets | Google Drive | Sharing/distribution snapshots, not authoritative |
| Imported source sheets | Google Drive (untouched) | Staff's original work, referenced but not modified |
| Printed recipes | PDF / paper | Kitchen use, generated on demand from preview |

Rule: **Nothing in Google Drive is authoritative.** It's either an input waiting to be ingested, or an output snapshot.

---

## 6. Migration Plan

Single Alembic migration covering:
1. Add `price_type` column to `price_history` with default `'confirmed'`
2. Add `instructions_es` column to `recipes`
3. Create `ai_prompts` table with default prompts for three operations
4. Add index on `price_history(price_type)` for efficient filtering

All existing `price_history` records receive `price_type='confirmed'` via the default value — no data backfill needed beyond the column default.

---

## 7. Model Usage

| Task | Model | Rationale |
|------|-------|-----------|
| Recipe proofreading | Haiku | Well-scoped, structured output, cost-effective |
| Kitchen review | Haiku (Sonnet fallback) | Needs some reasoning but Haiku should suffice; bump if quality is thin |
| Spanish translation | Haiku | Translation is a strength; professional kitchen vocabulary is bounded |
| Cost impact simulation | N/A (Python) | Pure math, no LLM needed |
