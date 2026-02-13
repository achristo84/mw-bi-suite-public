# Module 2: Ingredient & Pricing Intelligence (IPI)

**Priority**: HIGH — Build in parallel with DMS  
**Dependencies**: Module 1.1 (Distributor Registry)  
**Estimated Timeline**: Weeks 3-4

## Overview

The Ingredient & Pricing Intelligence module creates a normalized view of all ingredients across distributors, enabling:
- Price comparison across distributors for the same ingredient
- Unit normalization (cases → lbs → grams)
- Price trend analysis and alerts
- Optimal sourcing recommendations

## The Core Problem

Distributors intentionally make comparison difficult:

| Distributor | Item Description | Pack | Price |
|-------------|------------------|------|-------|
| Valley Foods | Butter AA 36/1lb | 36 lb case | $142.56 |
| Mountain Produce | Plugra Euro Butter | 10 kg case | $89.00 |
| Green Market | Cabot Butter Prints 4/4ct | 16 ct (1lb ea) | $67.20 |

**All of these are butter.** But which is cheapest? That requires normalization.

## Components

### 2.1 Canonical Ingredient Database

**Purpose**: Master list of ingredients with standardized names and base units.

#### Design Principles

1. **One canonical ingredient per unique item** - "butter" not "Plugra butter" vs "Cabot butter"
2. **Base unit is always metric** - grams for solids, milliliters for liquids, 'each' for countables
3. **Categories for organization** - dairy, produce, protein, dry goods, etc.

#### Example Records

| id | name | category | base_unit | yield_factor | notes |
|----|------|----------|-----------|--------------|-------|
| uuid1 | butter | dairy | g | 1.0 | |
| uuid2 | heavy cream | dairy | ml | 1.0 | |
| uuid3 | yellow onion | produce | g | 0.85 | 15% trim loss |
| uuid4 | eggs large | protein | each | 1.0 | |
| uuid5 | all-purpose flour | dry_goods | g | 1.0 | |

#### Yield Factor

The `yield_factor` represents usable portion after trim/waste:
- 1.0 = 100% usable (butter, flour)
- 0.85 = 85% usable, 15% waste (onions after peeling/trimming)
- 0.45 = 45% usable (whole fish after filleting)

This affects true cost calculations.

---

### 2.2 Distributor Variant Mapping

**Purpose**: Link distributor SKUs to canonical ingredients with conversion factors.

#### The Mapping Challenge

When an invoice says "BUTTER AA 36/1LB CS", the system needs to know:
1. This is "butter" (canonical ingredient)
2. It's sold in a 36-pack of 1lb units = 36 lbs total
3. 36 lbs = 16,329 grams
4. Therefore price per gram = invoice_price / 16,329

#### Mapping Interface

```
┌─────────────────────────────────────────────────────────────────────┐
│  MAP DISTRIBUTOR ITEM                                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Distributor: [Valley Foods ▼]                                      │
│                                                                      │
│  SKU: [48291______]    Description: [BUTTER AA 36/1LB CS________]  │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  Canonical Ingredient: [butter ▼] (or [+ Create New])              │
│                                                                      │
│  Pack Configuration:                                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Pack contains: [36___] × [1_____] [lb ▼]                   │   │
│  │                                                              │   │
│  │  = 36 lbs total = 16,329 grams                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Current Price: $142.56 → $0.0087/gram                             │
│                                                                      │
│  [Cancel]                                    [Save Mapping]         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### Auto-Mapping Suggestions

Use LLM to suggest mappings for new invoice items:

```python
def suggest_mapping(raw_description, existing_ingredients):
    """Use Claude to suggest ingredient mapping."""
    prompt = f"""
    Given this distributor item description: "{raw_description}"
    
    And these existing canonical ingredients:
    {[i.name for i in existing_ingredients]}
    
    Suggest:
    1. Which canonical ingredient this maps to (or "NEW" if none match)
    2. Your best guess at pack configuration
    
    Respond in JSON:
    {{
      "canonical_ingredient": "string or NEW",
      "suggested_new_name": "string if NEW",
      "pack_quantity": number,
      "unit_quantity": number,
      "unit_type": "lb|oz|kg|g|gallon|quart|each|case",
      "confidence": 0.0-1.0
    }}
    """
    return call_claude(prompt)
```

---

### 2.3 Unit Conversion Engine

**Purpose**: Convert any unit to base units (grams/ml/each).

#### Conversion Tables

```python
# Weight conversions to grams
WEIGHT_TO_GRAMS = {
    'g': 1,
    'kg': 1000,
    'oz': 28.3495,
    'lb': 453.592,
    '#': 453.592,  # pound symbol
}

# Volume conversions to milliliters
VOLUME_TO_ML = {
    'ml': 1,
    'l': 1000,
    'liter': 1000,
    'fl_oz': 29.5735,
    'cup': 236.588,
    'pint': 473.176,
    'pt': 473.176,
    'quart': 946.353,
    'qt': 946.353,
    'gallon': 3785.41,
    'gal': 3785.41,
}

# Count-based (no conversion needed)
COUNT_UNITS = ['each', 'ea', 'ct', 'dozen', 'dz']

def to_base_unit(quantity, unit, base_unit_type):
    """Convert quantity to base units (g, ml, or each)."""
    unit_lower = unit.lower().strip()
    
    if base_unit_type == 'g':
        if unit_lower in WEIGHT_TO_GRAMS:
            return quantity * WEIGHT_TO_GRAMS[unit_lower]
    
    elif base_unit_type == 'ml':
        if unit_lower in VOLUME_TO_ML:
            return quantity * VOLUME_TO_ML[unit_lower]
    
    elif base_unit_type == 'each':
        if unit_lower in ['dozen', 'dz']:
            return quantity * 12
        return quantity
    
    raise ValueError(f"Cannot convert {unit} to {base_unit_type}")
```

#### Pack Size Parsing

Distributor descriptions often encode pack info:
- "36/1LB" = 36 units of 1 lb each
- "4/1GAL" = 4 gallons
- "15DZ" = 15 dozen
- "10KG" = 10 kg case

```python
import re

def parse_pack_description(description):
    """Extract pack configuration from description."""
    patterns = [
        r'(\d+)/(\d+\.?\d*)\s*(LB|OZ|KG|GAL|QT)',  # 36/1LB
        r'(\d+)\s*(DZ|DOZEN)',                       # 15DZ
        r'(\d+\.?\d*)\s*(LB|KG|GAL)\s*CS',          # 10KG CS
    ]
    
    for pattern in patterns:
        match = re.search(pattern, description.upper())
        if match:
            return parse_match(match, pattern)
    
    return None  # Manual entry required
```

---

### 2.4 Price Comparison Matrix

**Purpose**: Show price per base unit across all distributors for each ingredient.

#### Comparison View

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  INGREDIENT PRICE COMPARISON                                    [Export CSV]    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Filter: [All Categories ▼]    Search: [____________]                           │
│                                                                                  │
│  ═══════════════════════════════════════════════════════════════════════════   │
│  BUTTER ($/gram)                                             Best: Valley Foods │
│  ───────────────────────────────────────────────────────────────────────────   │
│  │ Valley Foods │ $0.0087/g │ ████████████░░░░░░░░ │ 36lb case @ $142.56      │
│  │ Mtn Produce  │ $0.0089/g │ █████████████░░░░░░░ │ 10kg case @ $89.00       │
│  │ Green Market │ $0.0093/g │ ██████████████░░░░░░ │ 16lb case @ $67.20       │
│                                                                                  │
│  ═══════════════════════════════════════════════════════════════════════════   │
│  HEAVY CREAM ($/ml)                                           Best: Farm Direct │
│  ───────────────────────────────────────────────────────────────────────────   │
│  │ Farm Direct  │ $0.0031/ml│ ████████████░░░░░░░░ │ 4qt case @ $11.80        │
│  │ Valley Foods │ $0.0035/ml│ ██████████████░░░░░░ │ 6qt case @ $19.90        │
│  │ Green Market │ $0.0042/ml│ █████████████████░░░ │ 1qt × 6 @ $23.95         │
│                                                                                  │
│  ═══════════════════════════════════════════════════════════════════════════   │
│  EGGS LARGE ($/each)                                          Best: Farm Direct │
│  ───────────────────────────────────────────────────────────────────────────   │
│  │ Farm Direct  │ $0.178/ea │ ████████████░░░░░░░░ │ 15dz @ $32.00            │
│  │ Valley Foods │ $0.194/ea │ ██████████████░░░░░░ │ 15dz @ $34.90            │
│  │ Mtn Produce  │ $0.201/ea │ ███████████████░░░░░ │ 15dz @ $36.20            │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### Comparison Logic

```python
def get_price_comparison(ingredient_id):
    """Get all distributor prices for an ingredient, normalized."""
    query = """
        SELECT 
            d.name as distributor_name,
            di.sku,
            di.description,
            di.pack_size,
            di.pack_unit,
            di.grams_per_unit,
            ph.price_cents,
            ph.price_cents / (di.pack_size * di.grams_per_unit) as price_per_gram
        FROM dist_ingredients di
        JOIN distributors d ON d.id = di.distributor_id
        JOIN v_current_prices ph ON ph.dist_ingredient_id = di.id
        WHERE di.ingredient_id = %s
          AND di.is_active = TRUE
          AND d.is_active = TRUE
        ORDER BY price_per_gram ASC
    """
    return db.execute(query, [ingredient_id])
```

---

### 2.5 Price Alert System

**Purpose**: Proactively notify when prices change significantly.

#### Alert Triggers

| Trigger | Threshold | Alert Level |
|---------|-----------|-------------|
| Price increase | >10% | 🔴 HIGH |
| Price increase | 5-10% | 🟡 MEDIUM |
| Price crosses competitor | Any | 🟡 MEDIUM |
| Price decrease | Any | 🟢 INFO |
| New lower-cost option | Any | 🟢 INFO |

#### Alert Generation

```python
def generate_price_alerts(new_invoice):
    """Generate alerts based on prices in new invoice."""
    alerts = []
    
    for line in new_invoice.lines:
        if not line.dist_ingredient_id:
            continue
            
        # Get previous price
        previous = get_previous_price(line.dist_ingredient_id)
        if not previous:
            continue
        
        change_pct = (line.unit_price - previous.price) / previous.price * 100
        
        if change_pct > 10:
            alerts.append({
                'level': 'HIGH',
                'type': 'price_increase',
                'ingredient': line.dist_ingredient.ingredient.name,
                'distributor': new_invoice.distributor.name,
                'old_price': previous.price,
                'new_price': line.unit_price,
                'change_pct': change_pct,
                'alternatives': get_cheaper_alternatives(line.dist_ingredient.ingredient_id)
            })
        elif change_pct > 5:
            alerts.append({
                'level': 'MEDIUM',
                'type': 'price_increase',
                # ... similar fields
            })
        elif change_pct < 0:
            alerts.append({
                'level': 'INFO',
                'type': 'price_decrease',
                # ... similar fields
            })
    
    return alerts
```

#### Alert Email Section

```
📈 PRICE CHANGES DETECTED
─────────────────────────

🔴 HIGH PRIORITY
   Heavy Cream (Valley Foods): $3.45 → $3.89/qt (+12.8%)
   ↳ Alternative: Farm Direct at $2.95/qt (24% cheaper)
   ↳ Note: Farm Direct delivers Friday only

🟡 MEDIUM PRIORITY
   Butter (Mountain Produce): $3.85 → $4.20/lb (+9.1%)
   ↳ Valley Foods still cheaper at $3.96/lb

🟢 GOOD NEWS
   Eggs 15dz (Farm Direct): $34.00 → $32.00 (-5.9%)
   ↳ Now the cheapest option
```

---

### 2.6 Catalog Scraping (Proactive Price Capture)

**Purpose**: Capture prices from distributor websites BEFORE ordering, not just after invoices arrive.

#### The Problem with Invoice-Only Pricing

Invoices tell you what you paid, but by then you've already ordered. For informed purchasing decisions, you need current prices across distributors before placing orders.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SCRAPER ONBOARDING (One-time per distributor)        │
├─────────────────────────────────────────────────────────────────────────┤
│  1. Claude + Puppeteer MCP analyzes website structure                   │
│  2. Claude generates static Python scraper (Playwright + BeautifulSoup) │
│  3. Scraper tested and committed to repo                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    RUNTIME PRICE CAPTURE (Scheduled/On-demand)          │
├─────────────────────────────────────────────────────────────────────────┤
│  Static Python scrapers run weekly (Cloud Run Jobs)                     │
│  • Login with credentials from Secret Manager                           │
│  • Export/scrape price list                                             │
│  • Parse into staged scraped_items                                      │
│  • Cost: ~$0 (just compute)                                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    ITEM MAPPING & NORMALIZATION                         │
├─────────────────────────────────────────────────────────────────────────┤
│  • Match scraped items to existing dist_ingredients by SKU              │
│  • New items: LLM-assisted mapping to canonical ingredients             │
│  • Normalize to price-per-gram/ml for comparison                        │
│  • Update price_history with source='catalog'                           │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Target Distributors

| Distributor | Portal | Scraping Approach |
|-------------|--------|-------------------|
| Valley Foods/Mountain Produce | portal.valleyfoods.example.com | Playwright login → export or scrape catalog |
| Farm Direct | shop.farmdirect.example.com | Playwright login → scrape or find export |
| Green Market | shop.greenmarket.example.com | Playwright login → scrape product pages |

#### Anti-Detection Strategy (80/20 Principle)

Distributors block aggressive scraping. Design scrapers to mimic human behavior:
- **Rate limiting**: Random delays between requests (2-5 seconds)
- **Session reuse**: Login once, reuse session for full catalog
- **Human-like patterns**: Scrape during business hours, not at 3am
- **Gentle frequency**: Weekly scrapes default, not daily hammering

#### Scraper Base Class

```python
from abc import ABC, abstractmethod
from playwright.async_api import async_playwright

class BaseScraper(ABC):
    def __init__(self, distributor_id: str, credentials: dict):
        self.distributor_id = distributor_id
        self.credentials = credentials

    @abstractmethod
    async def login(self, page) -> bool:
        """Login to distributor portal. Return True on success."""
        pass

    @abstractmethod
    async def get_catalog(self, page) -> list[dict]:
        """Scrape or download catalog. Return list of raw items."""
        pass

    @abstractmethod
    def parse_item(self, raw: dict) -> ScrapedItem:
        """Parse raw scraped data into structured ScrapedItem."""
        pass

    async def run(self) -> CatalogScrape:
        """Execute full scrape workflow."""
        scrape = CatalogScrape(distributor_id=self.distributor_id, status='running')

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            try:
                await self.login(page)
                raw_items = await self.get_catalog(page)

                for raw in raw_items:
                    item = self.parse_item(raw)
                    item.scrape_id = scrape.id
                    # Match to existing dist_ingredient or flag for mapping
                    item.match_to_existing()
                    save(item)

                scrape.status = 'success'
                scrape.items_found = len(raw_items)
            except Exception as e:
                scrape.status = 'failed'
                scrape.error_message = str(e)

            await browser.close()

        return scrape
```

#### Manual CSV Import Fallback

If automated scraping fails or is blocked, support manual catalog upload:

```
┌─────────────────────────────────────────────────────────────────────┐
│  IMPORT CATALOG                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Distributor: [Farm Direct ▼]                                       │
│                                                                      │
│  Upload File: [Choose CSV/Excel...]                                 │
│                                                                      │
│  Column Mapping:                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  SKU Column:         [Item #     ▼]                         │   │
│  │  Description Column: [Description▼]                         │   │
│  │  Price Column:       [Price      ▼]                         │   │
│  │  Unit Column:        [Pack Size  ▼]                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Preview: (first 5 rows)                                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ SKU    │ Description          │ Price  │ Pack Size         │   │
│  │ 12345  │ Butter AA 36/1lb     │ $142.56│ 36 lb case        │   │
│  │ ...    │ ...                  │ ...    │ ...               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  [Cancel]                                    [Import Catalog]        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### Quality Tier Annotations

Enable management to make informed quality vs. price tradeoffs:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  BUTTER PRICE COMPARISON                                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ ⭐ PREMIUM                                                               │   │
│  │ Plugra Euro Butter (Mtn Produce)   $0.0089/g   $89.00/10kg              │   │
│  │ └─ Note: Higher fat content (82%), better for pastry                    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ STANDARD                                                                 │   │
│  │ Butter AA 36/1lb (Valley Foods)     $0.0087/g   $142.56/36lb   ← BEST $  │   │
│  │ └─ Note: Standard AA grade, good all-purpose                            │   │
│  │                                                                          │   │
│  │ Cabot Butter Prints (Green Market)  $0.0093/g   $67.20/16lb              │   │
│  │ └─ Note: Local Vermont brand, smaller pack size                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  💡 Decision: Valley Foods is cheapest, but Plugra worth +2% for pastry apps   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### Pre-Order Price Check Workflow

Before placing an order, compare current catalog prices:

1. Generate order draft based on par levels
2. For each item, show current prices across distributors
3. Highlight if a different distributor is now cheaper
4. Allow switching items between distributors to optimize

---

## Data Flow

```
┌─────────────────┐     ┌─────────────────┐
│  New Invoice    │     │  Catalog Scrape │
│  Received       │     │  (Weekly)       │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
┌─────────────────┐
│  Parse Line     │
│  Items          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Parse Line     │     │  Existing       │
│  Items          │────▶│  Mappings?      │
└─────────────────┘     └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
           ┌─────────────────┐     ┌─────────────────┐
           │  Yes: Auto-map  │     │  No: Queue for  │
           │  to canonical   │     │  manual mapping │
           └────────┬────────┘     └────────┬────────┘
                    │                        │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌─────────────────┐
                    │  Calculate      │
                    │  normalized     │
                    │  price/gram     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Update price   │
                    │  history        │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Check for      │
                    │  price alerts   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Add to daily   │
                    │  digest         │
                    └─────────────────┘
```

---

## API Endpoints

### Ingredients
- `GET /api/ingredients` - List canonical ingredients
- `GET /api/ingredients/{id}` - Get ingredient with all variants
- `POST /api/ingredients` - Create canonical ingredient
- `PUT /api/ingredients/{id}` - Update ingredient

### Distributor Ingredients (Variants)
- `GET /api/dist-ingredients` - List with filters
- `GET /api/dist-ingredients/unmapped` - Items needing mapping
- `POST /api/dist-ingredients` - Create mapping
- `PUT /api/dist-ingredients/{id}` - Update mapping
- `POST /api/dist-ingredients/suggest` - LLM mapping suggestion

### Pricing
- `GET /api/pricing/compare/{ingredient_id}` - Price comparison
- `GET /api/pricing/history/{dist_ingredient_id}` - Price history
- `GET /api/pricing/alerts` - Current price alerts

---

## Implementation Checklist

### Phase 2a (Foundation) ✅ COMPLETE
- [x] Create `ingredients` table
- [x] Create `dist_ingredients` table
- [x] Create `price_history` table
- [x] Build canonical ingredient CRUD interface
- [x] Build unit conversion engine (g/ml/each, pack size parser)
- [x] Enhanced pack parsing with fraction patterns (9/1/2GAL = 9 × ½ gallon)
- [x] Units API endpoint (`GET /units`, `POST /units/parse-pack`)

### Phase 2b (Mapping) ✅ COMPLETE
- [x] Build variant mapping interface (frontend at /ingredients)
- [x] Create unmapped items queue
- [x] Auto-populate from invoice parsing
- [ ] Implement LLM mapping suggestions (deferred - can add later)

### Phase 2c (Analysis) ✅ COMPLETE
- [x] Build price comparison view (frontend at /prices)
- [x] Price per base unit calculation with best-price highlighting
- [ ] Implement price change detection (deferred to future optimization phase)
- [ ] Create price alerts (deferred to future optimization phase)
- [ ] Add pricing section to daily digest (deferred to future optimization phase)

### Phase 2d (Catalog Scraping) - DEFERRED
Catalog scraping deferred to focus on recipe costing. Invoice-based pricing is sufficient for initial launch.

- [ ] Create `catalog_scrapes` and `scraped_items` tables
- [ ] Build base scraper class with anti-detection measures
- [ ] Implement manual CSV import fallback
- [ ] Analyze and build Valley Foods/Mountain Produce scraper (first target)
- [ ] Implement LLM-assisted item mapping for scraped items
- [ ] Build Farm Direct scraper
- [ ] Build Green Market scraper
- [ ] Add scraper health monitoring and alerts
- [ ] Build quality tier annotation interface
- [ ] Create pre-order price check workflow

---

## Completed Work Summary

**P2.1 - Unit Conversion Engine** (commit b353b77)
- Weight conversions (oz, lb, kg, g) → grams
- Volume conversions (fl oz, cup, pt, qt, gal, ml, l) → milliliters
- Count conversions (each, dozen) → each
- Pack size parser for descriptions like "36/1LB", "4/1GAL"
- Ingredient CRUD API endpoints

**P2.2 - Variant Mapping UI** (commit 4144647)
- Frontend page at /ingredients for mapping workflow
- Two-panel UI: unmapped items list + mapping form
- Map to existing canonical ingredient or create new
- Auto-populates pack info from parsed description

**P2.3 - Price Comparison View** (commit 42b3fcd)
- Frontend page at /prices with comparison matrix
- Price per base unit across all distributors
- Best-price highlighting (green), spread indicators
- Expandable rows showing all variants
- Filter by category, distributor, search
