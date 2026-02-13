# Module 3: Recipe & Menu Costing (RMC)

**Priority**: HIGH — Build after IPI foundation  
**Dependencies**: Module 2 (Ingredient & Pricing Intelligence)  
**Estimated Timeline**: Weeks 5-6

## Overview

The Recipe & Menu Costing module transforms your recipe sheets into a dynamic costing system that:
- Calculates true cost of each recipe based on current ingredient prices
- Rolls up recipe costs to menu item prices
- Analyzes food cost percentages and margins
- Simulates "what if" scenarios for price changes
- Accounts for waste/trim factors

## Components

### 3.1 Recipe Database

**Purpose**: Structured storage for recipes with full ingredient linkage.

#### Recipe Structure

```
RECIPE: Breakfast Sandwich Batch
├── Yield: 12 sandwiches
├── Prep Time: 45 min
├── Ingredients:
│   ├── eggs (1440g) — linked to canonical "eggs large"
│   ├── butter (120g) — linked to canonical "butter"
│   ├── cheddar cheese (360g) — linked to canonical "cheddar sharp"
│   ├── english muffins (12 each) — linked to canonical "english muffin"
│   └── salt (6g) — linked to canonical "kosher salt"
├── Instructions: [text]
└── Notes: [text]

MENU ITEM: Breakfast Sandwich
├── Based on: Breakfast Sandwich Batch
├── Portion: 1/12 of batch (0.0833)
├── Menu Price: $7.50
├── Calculated Cost: $2.14
└── Food Cost %: 28.5%
```

#### Recipe Types

| Type | Description | Example |
|------|-------------|---------|
| **Batch Recipe** | Makes multiple portions | "Breakfast Sandwich Batch (12)" |
| **Component Recipe** | Sub-recipe used in others | "Praline Topping" |
| **Prep Recipe** | Mise en place | "Diced Onions" |
| **Direct** | No recipe, just portioned ingredient | "Hard Boiled Egg" |

---

### 3.2 Recipe Importer

**Purpose**: Parse existing Google Sheets recipes into structured format.

#### Expected Input Format

Based on your existing sheets, define a standard format:

```
Recipe Name: Breakfast Creemee Base
Yield: 2000g
Yield Unit: grams

INGREDIENTS:
| Ingredient | Amount | Unit | Notes |
|------------|--------|------|-------|
| maple yogurt | 1200 | g | Cabot brand |
| mascarpone | 600 | g | |
| maple syrup | 150 | g | Grade A dark |
| vanilla extract | 15 | g | |
| salt | 3 | g | kosher |

INSTRUCTIONS:
1. Combine yogurt and mascarpone in mixer
2. ...
```

#### Import Process

```python
def import_recipe_from_sheet(sheet_data):
    """Parse recipe from Google Sheet format."""
    
    # Extract header info
    recipe = Recipe(
        name=sheet_data['recipe_name'],
        yield_quantity=sheet_data['yield'],
        yield_unit=sheet_data['yield_unit'],
        instructions=sheet_data.get('instructions', '')
    )
    
    # Process ingredients
    for row in sheet_data['ingredients']:
        # Try to match to canonical ingredient
        canonical = find_canonical_ingredient(row['ingredient'])
        
        if not canonical:
            # Queue for manual mapping
            queue_unmapped_ingredient(row['ingredient'], recipe.id)
            continue
        
        # Convert to base units (grams)
        quantity_grams = convert_to_grams(
            row['amount'], 
            row['unit'],
            canonical.base_unit
        )
        
        recipe_ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=canonical.id,
            quantity_grams=quantity_grams,
            prep_note=row.get('notes', '')
        )
        recipe.ingredients.append(recipe_ingredient)
    
    return recipe
```

#### Handling Unmapped Ingredients

When importing, some ingredients may not exist in the canonical database yet:

```
┌─────────────────────────────────────────────────────────────────────┐
│  UNMAPPED INGREDIENTS FROM RECIPE IMPORT                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Recipe: Breakfast Creemee Base                                      │
│                                                                      │
│  ⚠️ "maple yogurt" - no canonical ingredient found                  │
│     [Create New: maple yogurt] [Map to Existing ▼]                  │
│                                                                      │
│  ⚠️ "mascarpone" - no canonical ingredient found                    │
│     [Create New: mascarpone] [Map to Existing ▼]                    │
│                                                                      │
│  ✓ "maple syrup" - mapped to "maple syrup"                          │
│  ✓ "vanilla extract" - mapped to "vanilla extract"                  │
│  ✓ "salt" - mapped to "kosher salt"                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 3.3 Cost Calculator

**Purpose**: Roll up ingredient costs to recipe and menu item costs.

#### Cost Calculation Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     COST CALCULATION FLOW                            │
└─────────────────────────────────────────────────────────────────────┘

INGREDIENT LEVEL
────────────────
butter (canonical)
├── Valley Foods: $0.0087/g (cheapest) ← used for costing
├── Mountain Produce: $0.0089/g
└── Green Market: $0.0093/g

                    │
                    ▼

RECIPE LEVEL
────────────
Breakfast Sandwich Batch (12 servings)
├── eggs: 1440g × $0.0148/g = $21.31
├── butter: 120g × $0.0087/g = $1.04
├── cheddar: 360g × $0.0132/g = $4.75
├── english muffins: 12ea × $0.35/ea = $4.20
└── salt: 6g × $0.0003/g = $0.00
────────────────────────────────────
Total Recipe Cost: $31.30
Cost Per Serving: $2.61

                    │
                    ▼

MENU ITEM LEVEL
───────────────
Breakfast Sandwich
├── Recipe cost per serving: $2.61
├── Yield factor applied: ÷ 1.0 (no waste)
├── Final portion cost: $2.61
├── Menu price: $7.50
├── Gross margin: $4.89 (65.2%)
└── Food cost %: 34.8%
```

#### Cost Calculator Implementation

```python
def calculate_recipe_cost(recipe_id, pricing_strategy='cheapest'):
    """
    Calculate total cost of a recipe.
    
    pricing_strategy options:
    - 'cheapest': Use lowest price across all distributors
    - 'preferred': Use preferred distributor for each ingredient
    - 'specific': Use specific distributor (passed as param)
    """
    recipe = get_recipe(recipe_id)
    total_cost_cents = 0
    ingredient_costs = []
    
    for ri in recipe.ingredients:
        ingredient = ri.ingredient
        
        # Get price per base unit based on strategy
        if pricing_strategy == 'cheapest':
            price_per_unit = get_cheapest_price(ingredient.id)
        elif pricing_strategy == 'preferred':
            price_per_unit = get_preferred_price(ingredient.id)
        
        # Apply yield factor (e.g., 15% trim waste on onions)
        adjusted_quantity = ri.quantity_grams / ingredient.yield_factor
        
        # Calculate cost
        cost_cents = adjusted_quantity * price_per_unit
        total_cost_cents += cost_cents
        
        ingredient_costs.append({
            'ingredient': ingredient.name,
            'quantity_grams': ri.quantity_grams,
            'adjusted_quantity': adjusted_quantity,
            'price_per_gram': price_per_unit,
            'cost_cents': cost_cents
        })
    
    return {
        'recipe_id': recipe_id,
        'recipe_name': recipe.name,
        'yield_quantity': recipe.yield_quantity,
        'yield_unit': recipe.yield_unit,
        'total_cost_cents': total_cost_cents,
        'cost_per_unit_cents': total_cost_cents / recipe.yield_quantity,
        'ingredient_breakdown': ingredient_costs
    }


def calculate_menu_item_cost(menu_item_id):
    """Calculate cost and margin for a menu item."""
    item = get_menu_item(menu_item_id)
    
    if item.recipe_id:
        recipe_cost = calculate_recipe_cost(item.recipe_id)
        portion_cost = recipe_cost['cost_per_unit_cents'] * item.portion_of_recipe
    else:
        # Direct ingredient (no recipe)
        portion_cost = get_direct_cost(item)
    
    return {
        'menu_item_id': menu_item_id,
        'name': item.name,
        'portion_cost_cents': portion_cost,
        'menu_price_cents': item.menu_price_cents,
        'gross_margin_cents': item.menu_price_cents - portion_cost,
        'gross_margin_pct': (item.menu_price_cents - portion_cost) / item.menu_price_cents * 100,
        'food_cost_pct': portion_cost / item.menu_price_cents * 100
    }
```

---

### 3.4 Margin Analyzer

**Purpose**: Analyze profitability across menu items.

#### Menu Profitability Report

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  MENU PROFITABILITY ANALYSIS                               Updated: Nov 25      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Target Food Cost: 30%                                                          │
│  Actual Weighted Average: 28.2% ✓                                               │
│                                                                                  │
│  ═══════════════════════════════════════════════════════════════════════════   │
│  ITEM                    COST    PRICE   MARGIN   FOOD%   STATUS               │
│  ═══════════════════════════════════════════════════════════════════════════   │
│                                                                                  │
│  BREAKFAST                                                                       │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  Breakfast Sandwich      $2.61   $7.50   $4.89    34.8%   ⚠️ Above target      │
│  + Add Sausage           $0.89   $2.00   $1.11    44.5%   ⚠️ Above target      │
│  Yogurt Bowl             $1.45   $6.00   $4.55    24.2%   ✓ Good              │
│  Overnight Oats          $1.12   $5.50   $4.38    20.4%   ✓ Good              │
│  Hard Boiled Eggs (2)    $0.59   $3.00   $2.41    19.7%   ✓ Excellent         │
│  Breakfast Creemee       $2.34   $8.00   $5.66    29.3%   ✓ Good              │
│                                                                                  │
│  BAKED GOODS                                                                     │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  Rotating Pastry (avg)   $0.95   $4.00   $3.05    23.8%   ✓ Good              │
│                                                                                  │
│  ═══════════════════════════════════════════════════════════════════════════   │
│                                                                                  │
│  💡 RECOMMENDATIONS:                                                            │
│  • Breakfast Sandwich at 34.8% food cost - consider $7.75 or $8.00 price       │
│  • Add Sausage at 44.5% - current sausage cost $0.89, price should be $2.50+   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### Margin Thresholds

| Food Cost % | Status | Recommendation |
|-------------|--------|----------------|
| <25% | 🟢 Excellent | Maintain |
| 25-30% | 🟢 Good | Target range |
| 30-35% | 🟡 Above target | Review pricing or recipe |
| >35% | 🔴 Attention needed | Action required |

---

### 3.5 What-If Simulator

**Purpose**: Model impact of price changes before they happen.

#### Simulation Scenarios

**Scenario 1: Ingredient Price Change**
```
What if butter increases 15%?

Current butter price: $0.0087/g
Simulated price: $0.0100/g

IMPACT ON MENU ITEMS:
─────────────────────
Breakfast Sandwich:
  Current cost: $2.61 → New cost: $2.73 (+$0.12)
  Food cost: 34.8% → 36.4%

Breakfast Creemee:
  Current cost: $2.34 → New cost: $2.42 (+$0.08)
  Food cost: 29.3% → 30.3%

TOTAL DAILY IMPACT (based on average sales):
  ~40 breakfast sandwiches/day × $0.12 = $4.80/day
  ~15 creemees/day × $0.08 = $1.20/day
  Total: ~$6.00/day or ~$180/month
```

**Scenario 2: Menu Price Change**
```
What if we raise Breakfast Sandwich to $8.00?

Current: $7.50, 34.8% food cost
New: $8.00, 32.6% food cost

Margin improvement: $0.50/sandwich
At 40/day: $20/day or $600/month additional margin
```

**Scenario 3: Recipe Modification**
```
What if we reduce cheese by 20%?

Current cheese per sandwich: 30g @ $0.0132/g = $0.40
New cheese per sandwich: 24g @ $0.0132/g = $0.32

Savings: $0.08/sandwich
At 40/day: $3.20/day or $96/month

⚠️ Note: May affect customer perception/satisfaction
```

#### Simulator Interface

```
┌─────────────────────────────────────────────────────────────────────┐
│  COST SIMULATOR                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  SCENARIO TYPE: [● Ingredient Price  ○ Menu Price  ○ Recipe Change] │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  Ingredient: [butter ▼]                                             │
│                                                                      │
│  Current Price: $0.0087/g                                           │
│                                                                      │
│  Change Type: [● Percentage  ○ Absolute]                            │
│  Change: [+15____] %                                                │
│                                                                      │
│  Simulated Price: $0.0100/g                                         │
│                                                                      │
│  [Run Simulation]                                                   │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  RESULTS:                                                           │
│  (shows after simulation runs)                                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 3.6 Waste/Trim Factors

**Purpose**: Account for the true cost of ingredients after prep waste.

#### Yield Factor Examples

| Ingredient | Yield Factor | Explanation |
|------------|--------------|-------------|
| Butter | 1.00 | No waste |
| Heavy cream | 1.00 | No waste |
| Yellow onion | 0.85 | 15% loss from skin/ends |
| Garlic | 0.80 | 20% loss from skin |
| Whole chicken | 0.65 | 35% loss from bones |
| Salmon fillet | 0.90 | 10% loss from trim |
| Strawberries | 0.92 | 8% loss from hulls |

#### True Cost Calculation

```python
def calculate_true_cost(ingredient_id, quantity_needed_grams):
    """
    Calculate true cost accounting for yield loss.
    
    If a recipe needs 100g of diced onion, and onions have
    a 0.85 yield factor, we actually need to buy:
    100g / 0.85 = 117.6g of whole onions
    """
    ingredient = get_ingredient(ingredient_id)
    
    # Amount we need to purchase
    purchase_quantity = quantity_needed_grams / ingredient.yield_factor
    
    # Cost based on purchase quantity
    price_per_gram = get_cheapest_price(ingredient_id)
    true_cost = purchase_quantity * price_per_gram
    
    return {
        'needed_quantity': quantity_needed_grams,
        'purchase_quantity': purchase_quantity,
        'waste_quantity': purchase_quantity - quantity_needed_grams,
        'yield_factor': ingredient.yield_factor,
        'true_cost_cents': true_cost
    }
```

---

## Daily Digest - Costing Section

```
📊 MENU COSTING UPDATE
──────────────────────

Overall Food Cost: 28.2% (target: 30%) ✓

⚠️ ITEMS ABOVE TARGET (>30%):
   Breakfast Sandwich: 34.8% ($2.61 cost, $7.50 price)
   Add Sausage: 44.5% ($0.89 cost, $2.00 price)

📈 COST CHANGES THIS WEEK:
   Breakfast Sandwich: $2.45 → $2.61 (+6.5%)
   ↳ Due to: butter +9.1%, eggs +3.2%

💡 OPTIMIZATION OPPORTUNITIES:
   Switch eggs from Valley Foods to Farm Direct
   ↳ Saves $0.09/sandwich = ~$108/month
```

---

## API Endpoints

### Recipes
- `GET /api/recipes` - List all recipes
- `GET /api/recipes/{id}` - Get recipe with ingredients
- `POST /api/recipes` - Create recipe
- `PUT /api/recipes/{id}` - Update recipe
- `POST /api/recipes/import` - Import from sheet format
- `GET /api/recipes/{id}/cost` - Calculate recipe cost

### Menu Items
- `GET /api/menu-items` - List menu items
- `GET /api/menu-items/{id}` - Get menu item with cost
- `POST /api/menu-items` - Create menu item
- `PUT /api/menu-items/{id}` - Update menu item
- `GET /api/menu-items/profitability` - Full margin report

### Simulation
- `POST /api/simulate/ingredient-price` - Simulate ingredient price change
- `POST /api/simulate/menu-price` - Simulate menu price change
- `POST /api/simulate/recipe-change` - Simulate recipe modification

---

## Implementation Checklist

### Phase 3a (Database) - COMPLETE
- [x] Create `recipes` table
- [x] Create `recipe_ingredients` table
- [x] Create `recipe_components` table (sub-recipes)
- [x] Create `menu_items` table
- [x] Create `menu_item_packaging` table
- [x] Add `ingredient_type` to ingredients (raw, component, packaging)
- [x] Add `source_recipe_id` to ingredients (for component pricing)
- [x] Build recipe CRUD interface

### Phase 3b (Import & Costing) - COMPLETE
- [x] Define standard recipe input format
- [x] Build recipe importer from Google Sheets
- [x] Implement cost calculator service
- [x] Support recent vs average pricing modes
- [x] Handle component ingredients (price from source recipe)
- [x] Cycle detection for circular recipe references
- [x] Build cost roll-up endpoint `/recipes/{id}/cost`

### Phase 3c (Frontend) - COMPLETE
- [x] Recipe list page
- [x] Recipe detail page with cost breakdown
- [x] Recipe edit page with unit conversion
- [x] Create ingredients inline from recipe editor
- [x] Master ingredients page with pricing (batch-optimized query)
- [x] Ingredient detail with type management
- [x] PriceIngredientModal (Manual tab)
- [x] PriceIngredientModal (From Invoice tab)
- [x] PriceIngredientModal (Upload/parse tab)
- [x] Invoice review - inline line editing (qty, unit, price)
- [x] Invoice review - inline ingredient mapping
- [x] Units API (`GET /units`, `POST /units/parse-pack`)
- [x] useUnits hook for frontend
- [x] Enhanced pack parsing (fraction patterns like 9/1/2GAL)

### Phase 3d (Analysis) - NOT STARTED
- [ ] Build margin analyzer report
- [ ] Create what-if simulator
- [ ] Implement yield/waste factors
- [ ] Add costing section to daily digest
