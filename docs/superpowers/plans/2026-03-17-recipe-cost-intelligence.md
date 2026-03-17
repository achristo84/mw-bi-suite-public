# Recipe & Cost Intelligence Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the BI Suite into a cost intelligence platform where distributor pricing decisions show real-time impact on active menu margins, with AI-powered recipe management.

**Architecture:** Backend-driven cost simulation via a `price_overrides` parameter threaded through the existing cost calculator. Three-tier pricing (confirmed/observed/intent) stored in `PriceHistory`. AI recipe features use Claude Haiku via the existing `anthropic` client. Frontend uses React Query for data fetching with debounced simulation calls.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy / Alembic / PostgreSQL / React 19 / TypeScript / Tailwind CSS / Claude Haiku API

**Spec:** `docs/superpowers/specs/2026-03-17-recipe-cost-intelligence-design.md`

---

## Chunk 1: Data Model & Core Backend

### Task 1: Database Migration

**Files:**
- Create: `alembic/versions/016_recipe_cost_intelligence.py`
- Modify: `app/models/ingredient.py`
- Modify: `app/models/recipe.py`

- [ ] **Step 1: Create migration file**

```python
# alembic/versions/016_recipe_cost_intelligence.py
"""Add price_type, instructions_es, ai_prompts table"""

from alembic import op
import sqlalchemy as sa

revision = '016'
down_revision = '015'

def upgrade():
    # 1. Add price_type to price_history
    op.add_column('price_history',
        sa.Column('price_type', sa.String(10), nullable=False, server_default='confirmed')
    )
    op.create_index('ix_price_history_price_type', 'price_history', ['price_type'])

    # 2. Add instructions_es to recipes
    op.add_column('recipes',
        sa.Column('instructions_es', sa.Text(), nullable=True)
    )

    # 3. Create ai_prompts table
    op.create_table('ai_prompts',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('operation', sa.String(30), nullable=False, unique=True),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'))
    )

    # 4. Seed default AI prompts
    op.execute("""
        INSERT INTO ai_prompts (operation, prompt) VALUES
        ('recipe_proofread', 'You are a professional recipe editor for a cafe kitchen. Improve the clarity and formatting of these recipe instructions. Use numbered steps, consistent imperative verb tense, and standard cooking terminology. Preserve the author''s voice and intent. Do not add steps or change quantities — only improve how existing steps are written. Return ONLY the improved instructions text, nothing else.'),
        ('recipe_kitchen_review', 'You are a new kitchen employee with basic home cooking skills but no professional experience. You have been handed this recipe to prepare. Read the ingredients list and instructions carefully. Flag anything that would confuse you or cause you to make a mistake. For each issue found, respond with JSON: {"findings": [{"step": <step_number_or_null>, "issue": "<what_is_unclear>", "suggestion": "<how_to_fix_it>", "severity": "warning|info"}]}. Focus on: missing steps, assumed techniques, unclear quantities, ambiguous timing, unexplained terminology.'),
        ('recipe_translate', 'You are a professional translator specializing in culinary content. Translate the following recipe instructions from English to Latin American Spanish appropriate for a professional kitchen. Use natural, idiomatic Spanish — not literal word-for-word translation. Use the imperative mood (tú form). Keep cooking terminology accurate (e.g., "fold" = "incorporar con movimientos envolventes", not "doblar"). Do NOT translate ingredient names — leave them as-is since they reference the system''s canonical ingredient database. Return ONLY the Spanish translation, nothing else.')
    """)

def downgrade():
    op.drop_table('ai_prompts')
    op.drop_column('recipes', 'instructions_es')
    op.drop_index('ix_price_history_price_type', 'price_history')
    op.drop_column('price_history', 'price_type')
```

- [ ] **Step 2: Update PriceHistory model**

In `app/models/ingredient.py`, add to the `PriceHistory` class after the `source_reference` column:

```python
    price_type = Column(String(10), nullable=False, server_default='confirmed')  # confirmed, observed, intent
```

- [ ] **Step 3: Update Recipe model**

In `app/models/recipe.py`, add to the `Recipe` class after the `instructions` column:

```python
    instructions_es = Column(Text)
```

- [ ] **Step 4: Create AiPrompt model**

Create `app/models/ai_prompt.py`:

```python
from sqlalchemy import Column, String, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class AiPrompt(Base):
    __tablename__ = 'ai_prompts'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    operation = Column(String(30), nullable=False, unique=True)
    prompt = Column(Text, nullable=False)
    updated_at = Column(TIMESTAMP, server_default=text('now()'))
```

- [ ] **Step 5: Register new model in `app/models/__init__.py`**

Add `AiPrompt` to the imports and `__all__` list.

- [ ] **Step 5b: Add instructions_es to recipe schemas**

In `app/schemas/recipe.py`, add `instructions_es: str | None = None` to both `RecipeBase` and `RecipeUpdate` classes. This must happen early (before AI translate endpoints are built) so the PATCH endpoint can save Spanish translations.

- [ ] **Step 6: Run migration locally and verify**

```bash
DB_PASSWORD=$(gcloud secrets versions access latest --secret=YOUR_DB_SECRET --project=YOUR_GCP_PROJECT) \
  DB_PORT=5434 python3 -m alembic upgrade head
```

- [ ] **Step 7: Commit**

```bash
git add alembic/versions/016_recipe_cost_intelligence.py app/models/ingredient.py app/models/recipe.py app/models/ai_prompt.py app/models/__init__.py
git commit -m "Add price_type, instructions_es, ai_prompts migration and models"
```

---

### Task 2: Cost Calculator — Price Overrides

**Files:**
- Modify: `app/services/cost_calculator.py`
- Modify: `tests/services/test_cost_calculator.py`

- [ ] **Step 1: Write failing test for price_overrides**

Add to `tests/services/test_cost_calculator.py`:

Note: The existing cost calculator functions are **synchronous** (`def`, not `async def`) and use a synchronous `Session`. Tests and endpoint code must call them synchronously. Async endpoints should call them directly (FastAPI handles sync functions in a threadpool automatically).

```python
import pytest
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from app.services.cost_calculator import get_ingredient_best_price, calculate_recipe_cost


class TestPriceOverrides:
    """Test that price_overrides bypass database lookup."""

    def test_get_ingredient_best_price_uses_override(self):
        """When ingredient_id is in price_overrides, return override price."""
        ingredient_id = uuid4()
        override_price = Decimal("5.50")
        overrides = {ingredient_id: override_price}

        db = MagicMock()
        price, source = get_ingredient_best_price(
            db, ingredient_id, price_overrides=overrides
        )

        assert price == override_price
        assert source == "simulated"
        # DB should NOT have been queried
        db.execute.assert_not_called()

    def test_get_ingredient_best_price_falls_through_without_override(self):
        """When ingredient_id is NOT in price_overrides, query DB as normal."""
        ingredient_id = uuid4()
        other_id = uuid4()
        overrides = {other_id: Decimal("5.50")}

        db = MagicMock()
        # Mock the DB query to return None (no price found)
        db.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
        )

        price, source = get_ingredient_best_price(
            db, ingredient_id, price_overrides=overrides
        )

        # Should have attempted DB lookup (price is None because mock returns None)
        assert price is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/services/test_cost_calculator.py::TestPriceOverrides -v
```

Expected: FAIL — `get_ingredient_best_price()` doesn't accept `price_overrides` parameter.

- [ ] **Step 3: Add price_overrides parameter to get_ingredient_best_price()**

In `app/services/cost_calculator.py`, modify the function signature (around line 94):

```python
def get_ingredient_best_price(
    db,
    ingredient_id,
    pricing_mode="recent",
    average_days=30,
    _calculating_recipes=None,
    price_overrides: dict = None,  # NEW: {ingredient_id: Decimal price_per_base_unit}
):
```

Add at the top of the function body, before any DB queries:

```python
    # Check overrides first
    if price_overrides and ingredient_id in price_overrides:
        return (price_overrides[ingredient_id], "simulated")
```

- [ ] **Step 4: Thread price_overrides through calculate_recipe_cost()**

Modify `calculate_recipe_cost()` signature (around line 313):

```python
def calculate_recipe_cost(
    db,
    recipe_id,
    pricing_mode="recent",
    average_days=30,
    _calculating_recipes=None,
    price_overrides: dict = None,  # NEW
):
```

Pass `price_overrides` to every call to `get_ingredient_best_price()` and recursive `calculate_recipe_cost()` within this function.

- [ ] **Step 5: Thread price_overrides through calculate_menu_item_cost()**

Same pattern — add `price_overrides: dict = None` parameter, pass through to `calculate_recipe_cost()`.

- [ ] **Step 6: Thread price_overrides through calculate_all_menu_item_costs()**

Same pattern — add `price_overrides: dict = None` parameter, pass through to `calculate_menu_item_cost()`.

- [ ] **Step 7: Run tests**

```bash
pytest tests/services/test_cost_calculator.py -v
```

Expected: All tests PASS including new `TestPriceOverrides`.

- [ ] **Step 8: Commit**

```bash
git add app/services/cost_calculator.py tests/services/test_cost_calculator.py
git commit -m "Add price_overrides parameter to cost calculator functions"
```

---

### Task 3: Cost Calculator — Price Type Awareness

**Files:**
- Modify: `app/services/cost_calculator.py`
- Test: `tests/services/test_cost_calculator.py`

- [ ] **Step 1: Write failing test for price_type priority**

```python
class TestPriceTypePriority:
    """Test that cost calculator respects intent > observed > confirmed priority."""

    @pytest.mark.asyncio
    async def test_intent_price_overrides_confirmed(self):
        """Intent price should be used over confirmed when include_intent=True."""
        # This test will need a real or well-mocked DB with multiple PriceHistory entries
        # for the same dist_ingredient_id with different price_types
        pass  # Flesh out with actual DB fixture

    @pytest.mark.asyncio
    async def test_observed_price_overrides_confirmed(self):
        """Observed price should be used over confirmed when include_observed=True."""
        pass

    @pytest.mark.asyncio
    async def test_confirmed_only_mode(self):
        """When include_observed=False and include_intent=False, only use confirmed."""
        pass
```

- [ ] **Step 2: Modify get_ingredient_best_price() to accept price_type filters**

Add parameters:

```python
    include_observed: bool = True,
    include_intent: bool = True,
```

Modify the price query to filter by `price_type` based on these flags. When multiple types exist, use priority: intent > observed > confirmed (select the most recent price of the highest-priority type).

- [ ] **Step 3: Add price_type and source tracking to return value**

Change return type to include `price_type` info for the dashboard's `cost_drivers` array. Return a named tuple or dataclass:

```python
@dataclass
class PriceResult:
    price_per_base_unit: Decimal | None
    source_name: str | None
    price_type: str  # 'confirmed', 'observed', 'intent'
    previous_confirmed_price: Decimal | None  # for delta display
```

- [ ] **Step 4: Update all callers to handle new return type**

Update `calculate_recipe_cost()`, `calculate_menu_item_cost()`, and `calculate_all_menu_item_costs()` to unpack the new return type and propagate `price_type` info into response schemas.

- [ ] **Step 5: Run all cost calculator tests**

```bash
pytest tests/services/test_cost_calculator.py -v
```

- [ ] **Step 6: Commit**

```bash
git add app/services/cost_calculator.py tests/services/test_cost_calculator.py
git commit -m "Add price_type awareness and priority to cost calculator"
```

---

### Task 4: Cost Impact Simulation Endpoint

**Files:**
- Create: `app/api/cost_impact.py`
- Modify: `app/schemas/recipe.py`
- Modify: `app/main.py`
- Create: `tests/api/test_cost_impact.py`

- [ ] **Step 1: Add schemas to `app/schemas/recipe.py`**

```python
class PriceScenario(BaseModel):
    ingredient_id: UUID
    price_per_base_unit_cents: Decimal  # Sub-cent precision (e.g., 4.2 = $0.042/gram)
    price_type: str = "observed"
    distributor_name: str | None = None
    dist_ingredient_id: UUID | None = None

class AffectedMenuItem(BaseModel):
    menu_item_id: UUID
    name: str
    category: str | None
    menu_price_cents: int
    current_cost_cents: int
    simulated_cost_cents: int
    current_food_cost_pct: Decimal
    simulated_food_cost_pct: Decimal
    current_margin_status: str
    simulated_margin_status: str
    cost_change_cents: int
    cost_change_per_serving_cents: int
    ingredients_affected: list[str]

class ImpactSummary(BaseModel):
    total_items_affected: int
    avg_food_cost_current_pct: Decimal
    avg_food_cost_simulated_pct: Decimal
    items_changing_status: int
    total_cost_impact_cents: int

class CostImpactRequest(BaseModel):
    price_scenarios: list[PriceScenario]
    scope: str | list[UUID] = "active_menu"

class CostImpactResponse(BaseModel):
    affected_menu_items: list[AffectedMenuItem]
    summary: ImpactSummary
```

- [ ] **Step 2: Create `app/api/cost_impact.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
from uuid import UUID

from app.database import get_db
from app.schemas.recipe import CostImpactRequest, CostImpactResponse
from app.services.cost_calculator import (
    calculate_all_menu_item_costs,
    calculate_menu_item_cost,
)

router = APIRouter(prefix="/cost-impact", tags=["cost-impact"])

@router.post("/simulate", response_model=CostImpactResponse)
async def simulate_cost_impact(
    request: CostImpactRequest,
    db: AsyncSession = Depends(get_db),
):
    """Simulate the impact of hypothetical price changes on menu items."""

    # Build price_overrides dict from scenarios
    price_overrides = {
        s.ingredient_id: s.price_per_base_unit_cents
        for s in request.price_scenarios
    }

    # Build set of scenario ingredient IDs for quick lookup
    scenario_ingredient_ids = {s.ingredient_id for s in request.price_scenarios}
    scenario_ingredient_names = {
        s.ingredient_id: s.distributor_name or "simulated"
        for s in request.price_scenarios
    }

    # Get current costs (no overrides) for comparison
    current = calculate_all_menu_item_costs(db)

    # Get simulated costs (with overrides)
    simulated = calculate_all_menu_item_costs(db, price_overrides=price_overrides)

    # Build response by comparing current vs simulated
    affected = []
    for curr_item in current.items:
        sim_item = next((s for s in simulated.items if s.id == curr_item.id), None)
        if not sim_item:
            continue

        cost_change = sim_item.total_cost_cents - curr_item.total_cost_cents
        if cost_change == 0:
            continue

        # Determine which scenario ingredients are used in this menu item's recipe
        # by checking the recipe's ingredient list against scenario IDs
        item_ingredient_ids = set()
        if curr_item.recipe_cost_breakdown:
            item_ingredient_ids = {
                ing.ingredient_id for ing in curr_item.recipe_cost_breakdown.ingredients
            }
        affected_names = [
            scenario_ingredient_names.get(iid, "unknown")
            for iid in scenario_ingredient_ids & item_ingredient_ids
        ]

        affected.append(AffectedMenuItem(
            menu_item_id=curr_item.id,
            name=curr_item.name,
            category=curr_item.category,
            menu_price_cents=curr_item.menu_price_cents,
            current_cost_cents=curr_item.total_cost_cents,
            simulated_cost_cents=sim_item.total_cost_cents,
            current_food_cost_pct=curr_item.food_cost_percent,
            simulated_food_cost_pct=sim_item.food_cost_percent,
            current_margin_status=curr_item.margin_status,
            simulated_margin_status=sim_item.margin_status,
            cost_change_cents=cost_change,
            cost_change_per_serving_cents=cost_change,
            ingredients_affected=affected_names,
        ))

    # Build summary
    avg_current = (
        Decimal(sum(a.current_food_cost_pct for a in affected)) / len(affected)
        if affected else Decimal(0)
    )
    avg_simulated = (
        Decimal(sum(a.simulated_food_cost_pct for a in affected)) / len(affected)
        if affected else Decimal(0)
    )

    summary = ImpactSummary(
        total_items_affected=len(affected),
        avg_food_cost_current_pct=avg_current,
        avg_food_cost_simulated_pct=avg_simulated,
        items_changing_status=sum(1 for a in affected if a.current_margin_status != a.simulated_margin_status),
        total_cost_impact_cents=sum(a.cost_change_cents for a in affected),
    )

    return CostImpactResponse(affected_menu_items=affected, summary=summary)
```

Note: The above is a skeleton — the implementer should flesh out the `affected_ingredients` lookup and summary calculations based on the actual `calculate_all_menu_item_costs()` return structure.

- [ ] **Step 3: Register router in `app/main.py`**

```python
from app.api import cost_impact
app.include_router(cost_impact.router, prefix="/api/v1")
```

- [ ] **Step 4: Write integration test**

Create `tests/api/test_cost_impact.py`:

```python
import pytest
from httpx import AsyncClient

class TestCostImpactSimulation:
    @pytest.mark.asyncio
    async def test_simulate_returns_affected_items(self, client: AsyncClient):
        """POST /cost-impact/simulate returns affected menu items."""
        response = await client.post("/api/v1/cost-impact/simulate", json={
            "price_scenarios": [],
            "scope": "active_menu"
        })
        assert response.status_code == 200
        data = response.json()
        assert "affected_menu_items" in data
        assert "summary" in data

    @pytest.mark.asyncio
    async def test_simulate_with_no_scenarios_returns_empty(self, client: AsyncClient):
        """Empty scenarios = no affected items."""
        response = await client.post("/api/v1/cost-impact/simulate", json={
            "price_scenarios": [],
            "scope": "active_menu"
        })
        assert response.json()["summary"]["total_items_affected"] == 0
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/api/test_cost_impact.py -v
```

- [ ] **Step 6: Commit**

```bash
git add app/api/cost_impact.py app/schemas/recipe.py app/main.py tests/api/test_cost_impact.py
git commit -m "Add cost impact simulation endpoint"
```

---

### Task 5: Passive Price Capture in Search

**Files:**
- Modify: `app/services/search_aggregator.py`
- Modify: `app/schemas/order_hub.py`

- [ ] **Step 1: Extend SearchResult schema**

In `app/schemas/order_hub.py`, add fields to the `SearchResult` model:

```python
    last_confirmed_price_cents: int | None = None
    last_confirmed_date: str | None = None
    last_confirmed_distributor: str | None = None
    price_delta_cents: int | None = None
    price_delta_pct: float | None = None
    canonical_ingredient_id: str | None = None
    canonical_ingredient_name: str | None = None
```

- [ ] **Step 2: Add price enrichment to search_aggregator.py**

In `_normalize_result()`, after the existing normalization logic, add a lookup:

```python
async def _enrich_with_price_history(self, db, result: dict, dist_ingredient) -> dict:
    """Add last confirmed price and delta to search result."""
    if not dist_ingredient or not dist_ingredient.ingredient_id:
        return result

    # Get most recent confirmed price for the canonical ingredient
    latest_confirmed = await db.execute(
        select(PriceHistory)
        .join(DistIngredient)
        .where(
            DistIngredient.ingredient_id == dist_ingredient.ingredient_id,
            PriceHistory.price_type == 'confirmed'
        )
        .order_by(PriceHistory.effective_date.desc())
        .limit(1)
    )
    confirmed = latest_confirmed.scalars().first()

    if confirmed:
        result["last_confirmed_price_cents"] = confirmed.price_cents
        result["last_confirmed_date"] = str(confirmed.effective_date)
        # ... calculate delta

    return result
```

- [ ] **Step 3: Add background task for observed price capture**

After `search_all()` returns results, fire a background task:

Note: This runs as a FastAPI `BackgroundTasks` function — it gets its own DB session since the request session will be closed by the time this runs.

```python
from fastapi import BackgroundTasks
from app.database import SessionLocal

def capture_observed_prices(results: list[dict]):
    """Background task: record observed prices for known SKUs with changed prices.
    Dedup: one observed entry per dist_ingredient per day. Updates existing if present."""
    from datetime import date
    db = SessionLocal()
    try:
        for dist_result in results:
            for item in dist_result.get("results", []):
                dist_ingredient_id = item.get("dist_ingredient_id")
                search_price_cents = item.get("price_cents")
                if not dist_ingredient_id or not search_price_cents:
                    continue

                # 1. Get most recent confirmed price for this SKU
                latest_confirmed = db.execute(
                    select(PriceHistory)
                    .where(
                        PriceHistory.dist_ingredient_id == dist_ingredient_id,
                        PriceHistory.price_type == 'confirmed',
                    )
                    .order_by(PriceHistory.effective_date.desc())
                    .limit(1)
                ).scalars().first()

                # Skip if no confirmed history (we only observe changes on things we buy)
                if not latest_confirmed:
                    continue

                # Skip if price hasn't changed
                if latest_confirmed.price_cents == search_price_cents:
                    continue

                # 2. Check for existing observed entry today (dedup)
                existing_today = db.execute(
                    select(PriceHistory)
                    .where(
                        PriceHistory.dist_ingredient_id == dist_ingredient_id,
                        PriceHistory.price_type == 'observed',
                        PriceHistory.effective_date == date.today(),
                    )
                ).scalars().first()

                if existing_today:
                    # Update existing observed price for today
                    existing_today.price_cents = search_price_cents
                else:
                    # Create new observed entry
                    db.add(PriceHistory(
                        dist_ingredient_id=dist_ingredient_id,
                        price_cents=search_price_cents,
                        source='order_hub_search',
                        price_type='observed',
                        effective_date=date.today(),
                    ))

        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
```

- [ ] **Step 4: Wire background task into search endpoint**

In `app/api/distributor_search.py`, pass `BackgroundTasks` and call the capture function after returning results.

- [ ] **Step 5: Commit**

```bash
git add app/services/search_aggregator.py app/schemas/order_hub.py app/api/distributor_search.py
git commit -m "Add passive price capture and price delta to distributor search"
```

---

### Task 6: Order Builder — Price Type Transitions

**Files:**
- Modify: `app/api/order_builder.py`

- [ ] **Step 1: Modify create_assignment() for intent pricing**

In the assignment creation logic, after creating the `PriceHistory` entry:

```python
# Check if an observed entry exists for this dist_ingredient at this price
existing_observed = await db.execute(
    select(PriceHistory)
    .where(
        PriceHistory.dist_ingredient_id == dist_ingredient_id,
        PriceHistory.price_type == 'observed',
        PriceHistory.price_cents == price_cents,
    )
    .order_by(PriceHistory.effective_date.desc())
    .limit(1)
)
observed = existing_observed.scalars().first()

if observed:
    observed.price_type = 'intent'
else:
    # Create new intent entry
    new_price = PriceHistory(
        dist_ingredient_id=dist_ingredient_id,
        price_cents=price_cents,
        source='order_hub_search',
        price_type='intent',
        effective_date=date.today(),
    )
    db.add(new_price)
```

- [ ] **Step 2: Modify finalize endpoint for confirmed transition**

In the finalize logic, after creating orders:

```python
# Transition all intent prices for finalized items to confirmed
for line in order_lines:
    await db.execute(
        update(PriceHistory)
        .where(
            PriceHistory.dist_ingredient_id == line.dist_ingredient_id,
            PriceHistory.price_type == 'intent',
        )
        .values(price_type='confirmed')
    )
```

- [ ] **Step 3: Commit**

```bash
git add app/api/order_builder.py
git commit -m "Add price_type transitions in order builder (intent on assign, confirmed on finalize)"
```

---

### Task 7: Menu Dashboard Endpoint

**Files:**
- Modify: `app/schemas/recipe.py`
- Modify: `app/api/recipes.py`
- Modify: `app/services/cost_calculator.py`

- [ ] **Step 1: Add CostDriver and dashboard schemas**

In `app/schemas/recipe.py`:

```python
class CostDriver(BaseModel):
    ingredient_id: UUID
    ingredient_name: str
    price_type: str  # 'confirmed', 'observed', 'intent'
    price_per_base_unit_cents: Decimal
    previous_confirmed_cents: Decimal | None = None
    change_pct: float | None = None
    line_cost_cents: int
    pct_of_total: float
    distributor_name: str | None = None

class MenuDashboardItem(MenuItemAnalysis):
    """Extends existing MenuItemAnalysis with price confidence info."""
    price_confidence: str  # 'all_confirmed', 'mixed', 'mostly_observed'
    cost_drivers: list[CostDriver] = []
    food_cost_cents: int = 0
    packaging_cost_cents: int = 0

class MenuDashboardResponse(BaseModel):
    items: list[MenuDashboardItem]
    summary: MenuAnalyzerSummary
    observed_change_count: int = 0
```

- [ ] **Step 2: Add dashboard endpoint to recipes.py**

```python
@menu_router.get("/dashboard", response_model=MenuDashboardResponse)
async def get_menu_dashboard(
    pricing_mode: str = Query("recent", regex="^(recent|average)$"),
    average_days: int = Query(30, ge=1, le=365),
    category: str = Query(None),
    include_observed: bool = Query(True),
    include_intent: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """Menu dashboard with cost drivers and price confidence."""
    # Use extended cost calculator that returns price_type info
    ...
```

- [ ] **Step 3: Extend calculate_all_menu_item_costs() to return cost drivers**

Add logic to collect per-ingredient price_type and previous_confirmed_price during calculation, returning the enriched data structure.

- [ ] **Step 4: Commit**

```bash
git add app/schemas/recipe.py app/api/recipes.py app/services/cost_calculator.py
git commit -m "Add menu dashboard endpoint with cost drivers and price confidence"
```

---

## Chunk 2: AI Recipe Features

### Task 8: AI Recipe Service

**Files:**
- Create: `app/services/ai_recipe_service.py`
- Create: `tests/services/test_ai_recipe_service.py`

- [ ] **Step 1: Create AI recipe service**

```python
# app/services/ai_recipe_service.py
import json
from anthropic import Anthropic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ai_prompt import AiPrompt
from app.models.recipe import Recipe, RecipeIngredient
from app.models.ingredient import Ingredient


# Default prompts (used if no custom prompt in DB)
DEFAULT_PROMPTS = {
    "recipe_proofread": "...",  # From migration seed
    "recipe_kitchen_review": "...",
    "recipe_translate": "...",
}


async def get_prompt(db: AsyncSession, operation: str) -> str:
    """Get the current prompt for an operation, falling back to default."""
    result = await db.execute(
        select(AiPrompt).where(AiPrompt.operation == operation)
    )
    prompt = result.scalars().first()
    if prompt:
        return prompt.prompt
    return DEFAULT_PROMPTS.get(operation, "")


async def update_prompt(db: AsyncSession, operation: str, new_prompt: str) -> None:
    """Update or insert a prompt for an operation."""
    result = await db.execute(
        select(AiPrompt).where(AiPrompt.operation == operation)
    )
    existing = result.scalars().first()
    if existing:
        existing.prompt = new_prompt
        existing.updated_at = func.now()
    else:
        db.add(AiPrompt(operation=operation, prompt=new_prompt))
    await db.commit()


async def proofread_recipe(
    db: AsyncSession, recipe_id, custom_prompt: str | None = None
) -> dict:
    """Proofread and polish recipe instructions."""
    recipe = await _get_recipe(db, recipe_id)
    prompt = custom_prompt or await get_prompt(db, "recipe_proofread")

    client = Anthropic()
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"{prompt}\n\n---\n\nRecipe: {recipe.name}\n\nInstructions:\n{recipe.instructions}"
        }]
    )

    revised = message.content[0].text
    return {
        "original": recipe.instructions,
        "revised": revised,
        "changes_summary": "",  # Could add a second call to summarize changes
        "prompt_used": prompt,
    }


async def kitchen_review_recipe(
    db: AsyncSession, recipe_id, custom_prompt: str | None = None
) -> dict:
    """AI acts as inexperienced cook and flags unclear instructions."""
    recipe = await _get_recipe(db, recipe_id)
    ingredients = await _get_recipe_ingredients(db, recipe_id)
    prompt = custom_prompt or await get_prompt(db, "recipe_kitchen_review")

    ingredients_text = "\n".join(
        f"- {ing.ingredient_name}: {ing.quantity_grams}g ({ing.prep_note or 'no prep note'})"
        for ing in ingredients
    )

    client = Anthropic()
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"{prompt}\n\n---\n\nRecipe: {recipe.name}\nYield: {recipe.yield_quantity} {recipe.yield_unit}\n\nIngredients:\n{ingredients_text}\n\nInstructions:\n{recipe.instructions}"
        }]
    )

    # Parse JSON response
    try:
        result = json.loads(message.content[0].text)
        findings = result.get("findings", [])
    except json.JSONDecodeError:
        findings = [{"step": None, "issue": message.content[0].text, "suggestion": "", "severity": "info"}]

    return {
        "findings": findings,
        "prompt_used": prompt,
    }


async def translate_recipe(
    db: AsyncSession, recipe_id, custom_prompt: str | None = None
) -> dict:
    """Translate recipe instructions to Spanish."""
    recipe = await _get_recipe(db, recipe_id)
    prompt = custom_prompt or await get_prompt(db, "recipe_translate")

    client = Anthropic()
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"{prompt}\n\n---\n\nInstructions:\n{recipe.instructions}"
        }]
    )

    return {
        "instructions_es": message.content[0].text,
        "prompt_used": prompt,
    }


async def _get_recipe(db: AsyncSession, recipe_id):
    """Fetch recipe or raise 404."""
    from fastapi import HTTPException
    result = await db.execute(select(Recipe).where(Recipe.id == recipe_id))
    recipe = result.scalars().first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


async def _get_recipe_ingredients(db: AsyncSession, recipe_id):
    """Fetch recipe ingredients with names."""
    result = await db.execute(
        select(RecipeIngredient, Ingredient.name.label("ingredient_name"))
        .join(Ingredient, RecipeIngredient.ingredient_id == Ingredient.id)
        .where(RecipeIngredient.recipe_id == recipe_id)
    )
    return result.all()
```

- [ ] **Step 2: Write tests**

Create `tests/services/test_ai_recipe_service.py`:

```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.ai_recipe_service import proofread_recipe, kitchen_review_recipe, translate_recipe


class TestAiRecipeService:
    @pytest.mark.asyncio
    @patch("app.services.ai_recipe_service.Anthropic")
    async def test_proofread_returns_original_and_revised(self, mock_anthropic):
        """Proofread should return original + revised instructions."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Improved instructions here.")]
        )

        db = AsyncMock()
        # Mock recipe fetch
        mock_recipe = MagicMock(
            instructions="Original instructions.",
            name="Test Recipe"
        )
        db.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_recipe)))
        ))

        result = await proofread_recipe(db, "fake-uuid", custom_prompt="Test prompt")

        assert result["original"] == "Original instructions."
        assert result["revised"] == "Improved instructions here."
        assert result["prompt_used"] == "Test prompt"

    @pytest.mark.asyncio
    @patch("app.services.ai_recipe_service.Anthropic")
    async def test_translate_returns_spanish(self, mock_anthropic):
        """Translate should return Spanish instructions."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Instrucciones en español.")]
        )

        db = AsyncMock()
        mock_recipe = MagicMock(instructions="English instructions.", name="Test")
        db.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_recipe)))
        ))

        result = await translate_recipe(db, "fake-uuid", custom_prompt="Translate prompt")

        assert result["instructions_es"] == "Instrucciones en español."
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/services/test_ai_recipe_service.py -v
```

- [ ] **Step 4: Commit**

```bash
git add app/services/ai_recipe_service.py tests/services/test_ai_recipe_service.py
git commit -m "Add AI recipe service (proofread, kitchen review, translate)"
```

---

### Task 9: AI Recipe API Endpoints

**Files:**
- Modify: `app/api/recipes.py`
- Modify: `app/schemas/recipe.py`
- Modify: `app/main.py`

- [ ] **Step 1: Add AI response schemas**

In `app/schemas/recipe.py`:

```python
class AiCustomPromptRequest(BaseModel):
    custom_prompt: str | None = None

class ProofreadResponse(BaseModel):
    original: str
    revised: str
    changes_summary: str
    prompt_used: str

class KitchenReviewFinding(BaseModel):
    step: int | None = None
    issue: str
    suggestion: str
    severity: str  # 'warning' | 'info'

class KitchenReviewResponse(BaseModel):
    findings: list[KitchenReviewFinding]
    prompt_used: str

class TranslateResponse(BaseModel):
    instructions_es: str
    prompt_used: str

class AiPromptsResponse(BaseModel):
    proofread: str
    kitchen_review: str
    translate: str
    has_custom_proofread: bool
    has_custom_kitchen_review: bool
    has_custom_translate: bool

class AiPromptUpdate(BaseModel):
    operation: str  # 'recipe_proofread', 'recipe_kitchen_review', 'recipe_translate'
    prompt: str

class SheetExportResponse(BaseModel):
    spreadsheet_id: str
    spreadsheet_url: str
```

- [ ] **Step 2: Add AI endpoints to recipes.py**

```python
from app.services.ai_recipe_service import (
    proofread_recipe, kitchen_review_recipe, translate_recipe,
    get_prompt, update_prompt,
)

@router.post("/{recipe_id}/ai/proofread", response_model=ProofreadResponse)
async def ai_proofread(
    recipe_id: UUID,
    request: AiCustomPromptRequest = AiCustomPromptRequest(),
    db: AsyncSession = Depends(get_db),
):
    return await proofread_recipe(db, recipe_id, request.custom_prompt)

@router.post("/{recipe_id}/ai/kitchen-review", response_model=KitchenReviewResponse)
async def ai_kitchen_review(
    recipe_id: UUID,
    request: AiCustomPromptRequest = AiCustomPromptRequest(),
    db: AsyncSession = Depends(get_db),
):
    return await kitchen_review_recipe(db, recipe_id, request.custom_prompt)

@router.post("/{recipe_id}/ai/translate", response_model=TranslateResponse)
async def ai_translate(
    recipe_id: UUID,
    request: AiCustomPromptRequest = AiCustomPromptRequest(),
    db: AsyncSession = Depends(get_db),
):
    return await translate_recipe(db, recipe_id, request.custom_prompt)
```

- [ ] **Step 3: Add AI prompt management endpoints**

Add a new router section in recipes.py or create a separate small file:

```python
@router.get("/ai-prompts", response_model=AiPromptsResponse)
async def get_ai_prompts(db: AsyncSession = Depends(get_db)):
    ...

@router.patch("/ai-prompts", response_model=AiPromptsResponse)
async def update_ai_prompt_endpoint(
    request: AiPromptUpdate, db: AsyncSession = Depends(get_db)
):
    await update_prompt(db, request.operation, request.prompt)
    ...
```

- [ ] **Step 4: Commit**

```bash
git add app/api/recipes.py app/schemas/recipe.py
git commit -m "Add AI recipe endpoints (proofread, kitchen review, translate, prompt management)"
```

---

### Task 10: Google Sheets Export

**Files:**
- Modify: `app/services/sheets_service.py`
- Modify: `app/api/recipes.py`

- [ ] **Step 1: Upgrade Sheets OAuth scope**

In `app/services/sheets_service.py`, change line 13:

```python
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']  # Was: spreadsheets.readonly
```

Note: After deployment, the the OAuth refresh token in Secret Manager needs re-authorization with the new scope. This is a one-time manual step.

- [ ] **Step 2: Add write method to SheetsService**

```python
async def create_spreadsheet(self, title: str) -> dict:
    """Create a new Google Spreadsheet. Returns {spreadsheet_id, url}."""
    service = build('sheets', 'v4', credentials=self._get_credentials())
    spreadsheet = service.spreadsheets().create(body={
        'properties': {'title': title}
    }).execute()
    return {
        'spreadsheet_id': spreadsheet['spreadsheetId'],
        'url': spreadsheet['spreadsheetUrl'],
    }

async def write_sheet_data(self, spreadsheet_id: str, sheet_name: str, data: list[list]) -> None:
    """Write 2D array to a sheet."""
    service = build('sheets', 'v4', credentials=self._get_credentials())
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f'{sheet_name}!A1',
        valueInputOption='USER_ENTERED',
        body={'values': data}
    ).execute()
```

- [ ] **Step 3: Add export endpoint**

In `app/api/recipes.py`:

```python
@router.post("/{recipe_id}/export/sheet", response_model=SheetExportResponse)
async def export_recipe_to_sheet(
    recipe_id: UUID,
    include_costs: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """Export a recipe to a new Google Sheet."""
    recipe = await _get_recipe_with_details(db, recipe_id)

    # Build sheet data
    rows = [
        [recipe.name],
        [f"Yield: {recipe.yield_quantity} {recipe.yield_unit}"],
        [],
        ["Ingredient", "Amount", "Unit", "Prep Note"],
    ]
    for ing in recipe.ingredients:
        rows.append([ing.ingredient_name, str(ing.quantity_grams), ing.ingredient_base_unit or "g", ing.prep_note or ""])

    rows.append([])
    rows.append(["Instructions"])
    if recipe.instructions:
        for i, step in enumerate(recipe.instructions.split("\n"), 1):
            rows.append([f"{i}. {step.strip()}"])

    sheets_service = SheetsService()
    result = await sheets_service.create_spreadsheet(f"Recipe: {recipe.name}")
    await sheets_service.write_sheet_data(result['spreadsheet_id'], 'Sheet1', rows)

    return SheetExportResponse(
        spreadsheet_id=result['spreadsheet_id'],
        spreadsheet_url=result['url'],
    )
```

- [ ] **Step 4: Commit**

```bash
git add app/services/sheets_service.py app/api/recipes.py
git commit -m "Add Google Sheets export for recipes"
```

---

## Chunk 3: Frontend — Menu Dashboard & Cost Impact

### Task 11: Frontend Types & API Client

**Files:**
- Modify: `frontend/src/types/recipe.ts`
- Modify: `frontend/src/types/order-hub.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add cost impact types to recipe.ts**

```typescript
// Price type tier
export type PriceType = 'confirmed' | 'observed' | 'intent';
export type PriceConfidence = 'all_confirmed' | 'mixed' | 'mostly_observed';
export type MarginStatus = 'healthy' | 'warning' | 'danger';

export interface CostDriver {
  ingredient_id: string;
  ingredient_name: string;
  price_type: PriceType;
  price_per_base_unit_cents: number;
  previous_confirmed_cents: number | null;
  change_pct: number | null;
  line_cost_cents: number;
  pct_of_total: number;
  distributor_name: string | null;
}

export interface PriceScenario {
  ingredient_id: string;
  price_per_base_unit_cents: number;
  price_type: PriceType;
  distributor_name?: string;
  dist_ingredient_id?: string;
}

export interface AffectedMenuItem {
  menu_item_id: string;
  name: string;
  category: string | null;
  menu_price_cents: number;
  current_cost_cents: number;
  simulated_cost_cents: number;
  current_food_cost_pct: number;
  simulated_food_cost_pct: number;
  current_margin_status: MarginStatus;
  simulated_margin_status: MarginStatus;
  cost_change_cents: number;
  cost_change_per_serving_cents: number;
  ingredients_affected: string[];
}

export interface ImpactSummary {
  total_items_affected: number;
  avg_food_cost_current_pct: number;
  avg_food_cost_simulated_pct: number;
  items_changing_status: number;
  total_cost_impact_cents: number;
}

export interface CostImpactResponse {
  affected_menu_items: AffectedMenuItem[];
  summary: ImpactSummary;
}

export interface MenuDashboardItem extends MenuItemAnalysis {
  price_confidence: PriceConfidence;
  cost_drivers: CostDriver[];
  food_cost_cents: number;
  packaging_cost_cents: number;
}

export interface MenuDashboardResponse {
  items: MenuDashboardItem[];
  summary: MenuAnalyzerSummary;
  observed_change_count: number;
}

// AI types
export interface ProofreadResponse {
  original: string;
  revised: string;
  changes_summary: string;
  prompt_used: string;
}

export interface KitchenReviewFinding {
  step: number | null;
  issue: string;
  suggestion: string;
  severity: 'warning' | 'info';
}

export interface KitchenReviewResponse {
  findings: KitchenReviewFinding[];
  prompt_used: string;
}

export interface TranslateResponse {
  instructions_es: string;
  prompt_used: string;
}
```

Also extend the existing `Recipe` interface:

```typescript
// Add to Recipe interface:
instructions_es: string | null;
```

- [ ] **Step 2: Extend SearchResult in order-hub.ts**

```typescript
// Add to SearchResult interface:
last_confirmed_price_cents: number | null;
last_confirmed_date: string | null;
last_confirmed_distributor: string | null;
price_delta_cents: number | null;
price_delta_pct: number | null;
canonical_ingredient_id: string | null;
canonical_ingredient_name: string | null;
```

- [ ] **Step 3: Add API client functions**

In `frontend/src/lib/api.ts`:

```typescript
// Cost impact
async simulateCostImpact(scenarios: PriceScenario[], scope: string | string[] = 'active_menu'): Promise<CostImpactResponse> {
  return fetchAPI('/cost-impact/simulate', { method: 'POST', body: JSON.stringify({ price_scenarios: scenarios, scope }) });
}

async getMenuDashboard(params?: { pricing_mode?: string; category?: string; include_observed?: boolean; include_intent?: boolean }): Promise<MenuDashboardResponse> {
  const query = new URLSearchParams(params as any).toString();
  return fetchAPI(`/menu-items/dashboard?${query}`);
}

// AI recipe operations
async proofreadRecipe(recipeId: string, customPrompt?: string): Promise<ProofreadResponse> {
  return fetchAPI(`/recipes/${recipeId}/ai/proofread`, { method: 'POST', body: JSON.stringify({ custom_prompt: customPrompt || null }) });
}

async kitchenReviewRecipe(recipeId: string, customPrompt?: string): Promise<KitchenReviewResponse> {
  return fetchAPI(`/recipes/${recipeId}/ai/kitchen-review`, { method: 'POST', body: JSON.stringify({ custom_prompt: customPrompt || null }) });
}

async translateRecipe(recipeId: string, customPrompt?: string): Promise<TranslateResponse> {
  return fetchAPI(`/recipes/${recipeId}/ai/translate`, { method: 'POST', body: JSON.stringify({ custom_prompt: customPrompt || null }) });
}

async exportRecipeToSheet(recipeId: string, includeCosts = false): Promise<{ spreadsheet_id: string; spreadsheet_url: string }> {
  return fetchAPI(`/recipes/${recipeId}/export/sheet?include_costs=${includeCosts}`, { method: 'POST' });
}

// AI prompt management
async getRecipeAiPrompts(): Promise<AiPromptsResponse> {
  return fetchAPI('/recipes/ai-prompts');
}

async updateRecipeAiPrompt(operation: string, prompt: string): Promise<AiPromptsResponse> {
  return fetchAPI('/recipes/ai-prompts', { method: 'PATCH', body: JSON.stringify({ operation, prompt }) });
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/recipe.ts frontend/src/types/order-hub.ts frontend/src/lib/api.ts
git commit -m "Add frontend types and API client for cost impact, dashboard, and AI features"
```

---

### Task 12: Menu Dashboard Page

**Files:**
- Modify: `frontend/src/pages/Menu.tsx`

- [ ] **Step 1: Rewrite Menu.tsx as Menu Dashboard**

Full rewrite following the spec Section 3.2 mockup. Key components within the page:

1. **Summary bar**: Active items, avg food cost %, price alerts (observed count), margin health badges
2. **Category filter pills**: All | Breakfast | Lunch | Drinks | etc.
3. **Sortable table**: Item, Category, Menu Price, Total Cost, Food Cost %, Margin, Status
4. **Expandable rows**: Click `▶` to expand and show ingredient breakdown with cost drivers
5. **Three-tier visual indicators**: Confirmed (clean), Observed (orange/👁), Intent (blue/🛒)

Use `useQuery` to fetch from `getMenuDashboard()`. Each expanded row shows `cost_drivers` array from the dashboard response.

Implementation details:
- Collapsed row: show price-type icon, old→new strikethrough when non-confirmed prices
- Expanded row: ingredient table with Amount (dual units), Unit Price, Line Cost, % of Total, Source columns
- Packaging sub-section below ingredients
- Action buttons: "View Recipe", "Edit Menu Item"
- State: `expandedItemId` for which row is expanded, `categoryFilter`, `sortColumn`, `sortDirection`

- [ ] **Step 2: Test locally**

```bash
cd frontend && npm run dev
```

Navigate to `/menu` and verify dashboard renders with mock or real data.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Menu.tsx
git commit -m "Rewrite Menu page as expandable dashboard with cost drivers and price confidence"
```

---

### Task 13: Cost Impact Panel in Search Modal

**Files:**
- Modify: `frontend/src/components/ComparisonSearchModal.tsx`

- [ ] **Step 1: Add price delta display to search results**

Each result row gets:
- Normalized price per base unit
- Delta vs last confirmed purchase: `+$0.04/lb vs last purchase (Distributor C, Mar 2)`
- "BEST PRICE" badge on lowest per canonical ingredient
- "No purchase history — unmapped SKU" for unmapped results

- [ ] **Step 2: Add expandable cost impact panel**

When a search result is clicked, expand an inline panel below it:
- Call `simulateCostImpact()` with the selected price as a scenario (debounced 300ms)
- Show affected menu items grid: current % → simulated %, per-serving delta
- Summary line: "N menu items affected, avg impact +X%"

State additions: `expandedResultId`, `impactData` (from simulation API), `impactLoading`.

- [ ] **Step 3: Group results by distributor**

Refactor the results list to group by `distributor_name`, with distributor headers showing delivery info. Multiple SKUs per distributor displayed as sub-items.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ComparisonSearchModal.tsx
git commit -m "Add cost impact panel and price delta to comparison search modal"
```

---

## Chunk 4: Frontend — Recipe Editor & AI Tools

### Task 14: Recipe Editor — Two-Column Layout

**Files:**
- Modify: `frontend/src/pages/RecipeEdit.tsx`

- [ ] **Step 1: Restructure as two-column layout**

Left column (editor):
- Sticky cost bar: recipe name, cost/serving, food cost %, margin status
- Recipe metadata inputs: name, yield_quantity, yield_unit, yield_weight_grams
- Ingredient table: inline editable rows with dual units (base + practical), prep note, per-ingredient cost
- `+ Add ingredient` with existing ingredient picker
- Instructions textarea
- Notes textarea
- AI tool buttons section (Task 15)

Right column (live preview):
- Print-ready recipe layout
- Updates reactively as left column fields change
- Recipe name heading, yield, ingredients list, cost breakdown
- English/Spanish side-by-side when `instructions_es` exists

CSS: Use Tailwind `flex` with `lg:flex-row` for responsive two-column. Each column gets `overflow-y-auto` for independent scrolling. Cost bar uses `sticky top-0`.

- [ ] **Step 2: Add dual-unit display to ingredient table**

Use the existing `useUnits()` hook to convert base units to practical units:

```typescript
// Example: 500g → "500g (1.1 lb)"
const practicalDisplay = convertFromBase(quantity_grams, ingredient_base_unit);
```

Show both in the ingredient row. Show per-ingredient cost from the cost breakdown data.

- [ ] **Step 3: Add sticky cost bar**

Fetch recipe cost on load via existing `GET /recipes/{id}/cost` endpoint. Display in a sticky header:

```tsx
<div className="sticky top-0 z-10 bg-slate-900 border-b border-slate-700 px-4 py-3 flex justify-between items-center">
  <h2 className="font-semibold text-lg">{recipe.name}</h2>
  <div className="flex gap-6 text-sm">
    <div><span className="text-slate-400">Cost/serving:</span> <span className="font-semibold">${formatCents(cost.cost_per_unit_cents)}</span></div>
    <div><span className="text-slate-400">Food cost:</span> <span className={marginColor}>{foodCostPct}%</span></div>
    <MarginBadge status={marginStatus} />
  </div>
</div>
```

- [ ] **Step 4: Add live preview column**

Right column renders a print-ready view using recipe state from the editor form. When `instructions_es` exists, show side-by-side English/Spanish.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/RecipeEdit.tsx
git commit -m "Rewrite recipe editor as two-column layout with sticky cost bar and live preview"
```

---

### Task 15: AI Tool Buttons & Modals

**Files:**
- Create: `frontend/src/components/ai/ProofreadModal.tsx`
- Create: `frontend/src/components/ai/KitchenReviewPanel.tsx`
- Create: `frontend/src/components/ai/TranslateModal.tsx`
- Modify: `frontend/src/pages/RecipeEdit.tsx`

- [ ] **Step 1: Create ProofreadModal**

Diff-style modal showing original (left) vs revised (right) instructions. Buttons: "Accept" (replaces instructions in editor state), "Reject" (closes), "Edit Prompt" (opens PromptEditorModal).

```tsx
// Uses existing Dialog/Modal component from ui/
// Calls api.proofreadRecipe(recipeId) on open
// Shows loading state while API call runs
// On accept: updates parent's instructions state (not yet saved to DB)
```

- [ ] **Step 2: Create KitchenReviewPanel**

Renders as an inline panel (not modal) below the AI buttons. Shows a scrollable list of findings:

```tsx
{findings.map(f => (
  <div className={`border-l-2 ${f.severity === 'warning' ? 'border-orange-400' : 'border-blue-400'} pl-3 py-2`}>
    {f.step && <span className="text-xs text-slate-400">Step {f.step}</span>}
    <p className="text-sm">{f.issue}</p>
    <p className="text-xs text-slate-400 mt-1">Suggestion: {f.suggestion}</p>
  </div>
))}
```

- [ ] **Step 3: Create TranslateModal**

Shows the Spanish translation in a preview. "Accept" saves to `recipe.instructions_es` via PATCH and updates the live preview. "Edit Prompt" opens PromptEditorModal.

- [ ] **Step 4: Add AI buttons to RecipeEdit.tsx**

Below the notes textarea, add three buttons:

```tsx
<div className="flex gap-3 mt-4">
  <Button variant="outline" onClick={() => setShowProofread(true)} disabled={!recipe.instructions}>
    ✍️ Proofread & Polish
  </Button>
  <Button variant="outline" onClick={() => setShowKitchenReview(true)} disabled={!recipe.instructions}>
    👨‍🍳 Kitchen Review
  </Button>
  <Button variant="outline" onClick={() => setShowTranslate(true)} disabled={!recipe.instructions}>
    🇪🇸 Translate to Spanish
  </Button>
</div>
```

Each button also has an "Edit Prompt" sub-option that opens the existing `PromptEditorModal` with the appropriate operation name and test callback.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ai/ frontend/src/pages/RecipeEdit.tsx
git commit -m "Add AI recipe tools: proofread, kitchen review, and Spanish translation"
```

---

### Task 16: Print Layout & Recipe Detail Enhancements

**Files:**
- Modify: `frontend/src/pages/RecipeDetail.tsx`
- Create: `frontend/src/styles/print.css` (or add to existing Tailwind config)

- [ ] **Step 1: Add side-by-side English/Spanish to RecipeDetail**

When `recipe.instructions_es` exists, render instructions in two columns:

```tsx
<div className="grid grid-cols-2 gap-8 print:gap-4">
  <div>
    <h3 className="font-semibold mb-2">Instructions</h3>
    {renderInstructions(recipe.instructions)}
  </div>
  <div>
    <h3 className="font-semibold mb-2">Instrucciones</h3>
    {renderInstructions(recipe.instructions_es)}
  </div>
</div>
```

- [ ] **Step 2: Add print stylesheet**

```css
@media print {
  /* Hide navigation, buttons, cost data */
  nav, .no-print, [data-no-print] { display: none !important; }

  /* Clean formatting */
  body { background: white; color: black; font-size: 12pt; }

  /* Recipe title prominent */
  h1 { font-size: 24pt; border-bottom: 2px solid black; }

  /* Two-column instructions */
  .print-bilingual { columns: 2; column-gap: 2em; }
}
```

- [ ] **Step 3: Add "Export to Sheet" button to RecipeDetail**

```tsx
<Button variant="outline" onClick={handleExportToSheet}>
  Export to Sheet
</Button>
```

Opens the resulting spreadsheet URL in a new tab.

- [ ] **Step 4: Add "Print" button**

```tsx
<Button variant="outline" onClick={() => window.print()}>
  Print Recipe
</Button>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/RecipeDetail.tsx frontend/src/styles/print.css
git commit -m "Add bilingual recipe display, print layout, and sheet export button"
```

---

---

## Final Steps

### Task 18: Integration Testing & Cleanup

- [ ] **Step 1: Run full backend test suite**

```bash
pytest tests/ -v
```

Fix any failures.

- [ ] **Step 2: Run frontend build**

```bash
cd frontend && npm run build
```

Fix any TypeScript errors.

- [ ] **Step 3: Test end-to-end locally**

Start backend + frontend:
```bash
# Terminal 1: Backend
DB_PASSWORD=$(gcloud secrets versions access latest --secret=YOUR_DB_SECRET --project=YOUR_GCP_PROJECT) DB_PORT=5434 uvicorn app.main:app --reload

# Terminal 2: Frontend
cd frontend && npm run dev
```

Verify:
1. Menu Dashboard loads with expandable rows
2. Search results show price deltas and cost impact panels
3. Recipe editor two-column layout works
4. AI tools (proofread, kitchen review, translate) work
5. Print layout looks correct
6. Sheet export creates a new spreadsheet

- [ ] **Step 4: Final commit and push**

```bash
git push origin <feature-branch-name>
```
