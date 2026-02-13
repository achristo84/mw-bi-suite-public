# Module 5: Sales & Operations Analytics (SOA)

**Priority**: MEDIUM — Build when Toast data flowing  
**Dependencies**: Module 3 (Recipe & Menu Costing)  
**Estimated Timeline**: Weeks 9-10

## Overview

The Sales & Operations Analytics module connects actual sales data to ingredient costs:
- Import sales data from Toast
- Analyze product mix and trends
- Calculate theoretical vs actual ingredient usage
- Provide operational dashboards
- Support labor cost analysis

## Components

### 5.1 Sales Importer

**Purpose**: Ingest sales data from Toast into the system.

#### Phase 1: Manual CSV Export

Toast allows export of various reports. Key reports needed:

| Report | Data | Frequency |
|--------|------|-----------|
| Product Mix | Items sold, quantity, revenue | Daily |
| Sales Summary | Total sales by period | Daily |
| Time of Day | Hourly sales breakdown | Weekly |

#### CSV Import Process

```python
def import_toast_product_mix(csv_file):
    """
    Import Toast Product Mix report.
    
    Expected columns:
    - Menu Item
    - Quantity Sold
    - Net Sales
    - Date (or report date)
    """
    reader = csv.DictReader(csv_file)
    
    for row in reader:
        # Match to our menu items
        menu_item = match_toast_item(row['Menu Item'])
        
        if not menu_item:
            log_unmatched_item(row['Menu Item'])
            continue
        
        daily_sale = DailySale(
            sale_date=parse_date(row['Date']),
            menu_item_id=menu_item.id,
            quantity_sold=int(row['Quantity Sold']),
            net_sales_cents=parse_currency(row['Net Sales'])
        )
        
        upsert_daily_sale(daily_sale)
```

#### Toast Item Mapping

Toast menu items need to be mapped to our menu items:

```
┌─────────────────────────────────────────────────────────────────────┐
│  TOAST MENU ITEM MAPPING                                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Unmatched Toast Items:                                              │
│  ─────────────────────────────────────────────────────────────────  │
│  │ Toast Name                │ Our Menu Item       │ Status        │ │
│  ├───────────────────────────┼─────────────────────┼───────────────┤ │
│  │ Bfast Sandwich            │ [Breakfast Sand. ▼] │ [Save]        │ │
│  │ Bfast Sand + Sausage      │ [Select... ▼]       │               │ │
│  │ Yogurt Parfait            │ [Yogurt Bowl ▼]     │ [Save]        │ │
│  │ HB Eggs                   │ [Hard Boiled Egg ▼] │ [Save]        │ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### Phase 2: Toast API Integration (Future)

```python
# Future: Direct API integration
class ToastClient:
    def __init__(self, api_key, restaurant_guid):
        self.api_key = api_key
        self.restaurant_guid = restaurant_guid
        self.base_url = "https://api.toasttab.com"
    
    def get_orders(self, start_date, end_date):
        """Fetch orders for date range."""
        endpoint = f"/orders/v2/orders"
        params = {
            'startDate': start_date.isoformat(),
            'endDate': end_date.isoformat()
        }
        return self._get(endpoint, params)
    
    def get_menu_items(self):
        """Fetch current menu configuration."""
        endpoint = f"/menus/v2/menus"
        return self._get(endpoint)
```

---

### 5.2 Product Mix Analysis

**Purpose**: Understand what's selling and identify trends.

#### Product Mix Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  PRODUCT MIX ANALYSIS                                    Period: Last 7 Days    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  SALES BY CATEGORY                          TOP SELLERS                         │
│  ──────────────────                         ────────────                         │
│  Breakfast    ████████████████  68%         1. Breakfast Sandwich   312 (45%)   │
│  Drinks       ████████          28%         2. Drip Coffee          245 (35%)   │
│  Retail       ██                 4%         3. Yogurt Bowl           89 (13%)   │
│                                             4. Breakfast Creemee     52 ( 7%)   │
│                                             5. Overnight Oats        45 ( 6%)   │
│                                                                                  │
│  ═══════════════════════════════════════════════════════════════════════════   │
│                                                                                  │
│  DAILY TREND                                                                     │
│  ───────────────────────────────────────────────────────────────────────────   │
│  │                                                            ╭─╮             │ │
│  │                                              ╭─╮          │  │             │ │
│  │            ╭─╮    ╭─╮          ╭─╮          │  │    ╭─╮   │  │             │ │
│  │      ╭─╮  │  │   │  │   ╭─╮  │  │   ╭─╮   │  │   │  │  │  │             │ │
│  │  ───│  │──│  │───│  │───│  │──│  │───│  │───│  │───│  │──│  │───         │ │
│  │     Mon   Tue    Wed    Thu    Fri    Sat    Sun    Mon   Tue   Wed       │ │
│  │                                                                            │ │
│  │  Units: 78    82     79     85    112    134    128     81    85          │ │
│  │                                                                            │ │
│  ─────────────────────────────────────────────────────────────────────────────  │
│                                                                                  │
│  📈 TRENDS:                                                                     │
│  • Saturday/Sunday sales 45% higher than weekdays                               │
│  • Breakfast Sandwich up 12% week-over-week                                     │
│  • Breakfast Creemee down 8% (weather related?)                                 │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### Comparative Analysis

```python
def analyze_product_trends(menu_item_id, days=30):
    """Analyze sales trends for a menu item."""
    
    sales = get_daily_sales(menu_item_id, days)
    
    # Calculate week-over-week change
    current_week = sum(s.quantity for s in sales[:7])
    prior_week = sum(s.quantity for s in sales[7:14])
    wow_change = (current_week - prior_week) / prior_week * 100
    
    # Day of week patterns
    dow_averages = calculate_dow_averages(sales)
    
    # Moving average
    ma_7 = calculate_moving_average(sales, window=7)
    
    return {
        'total_units': sum(s.quantity for s in sales),
        'daily_average': sum(s.quantity for s in sales) / days,
        'wow_change_pct': wow_change,
        'dow_pattern': dow_averages,
        'trend': 'up' if ma_7[-1] > ma_7[-7] else 'down',
        'peak_day': max(dow_averages, key=dow_averages.get)
    }
```

---

### 5.3 Theoretical vs Actual Usage

**Purpose**: Compare what ingredients *should* have been used (based on sales) vs what was actually ordered/received.

#### The Gap Analysis Problem

```
THEORETICAL:
Sold 300 breakfast sandwiches this week
Each uses 10g butter
Theoretical butter usage: 3,000g

ACTUAL:
Received 5,000g butter this week
Started week with 1,000g
Ended week with 800g
Actual usage: 5,000 + 1,000 - 800 = 5,200g

VARIANCE: 5,200 - 3,000 = 2,200g (73% over)

Possible explanations:
- Recipe not accurate (actually uses more)
- Waste during prep
- Theft
- Spoilage
- R&D/testing
- Employee meals
- Inventory count error
```

#### Variance Report

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  THEORETICAL VS ACTUAL USAGE                                     Week of Nov 25 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ⚠️ HIGH VARIANCE ITEMS (>20% difference)                                       │
│  ═══════════════════════════════════════════════════════════════════════════   │
│  │ Ingredient    │ Theoretical │ Actual  │ Variance │ Var %  │ Investigate? │  │
│  ├───────────────┼─────────────┼─────────┼──────────┼────────┼──────────────┤  │
│  │ butter        │ 3,000g      │ 5,200g  │ +2,200g  │ +73%   │ 🔴 YES       │  │
│  │ heavy cream   │ 4,500ml     │ 5,800ml │ +1,300ml │ +29%   │ 🟡 Maybe     │  │
│  │ eggs          │ 180 each    │ 210 ea  │ +30      │ +17%   │ ✓ Normal     │  │
│                                                                                  │
│  ✓ NORMAL VARIANCE ITEMS (<20%)                                                 │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  │ english muffins │ 300 each   │ 315 ea  │ +15      │ +5%    │ ✓           │  │
│  │ maple syrup     │ 800ml      │ 850ml   │ +50ml    │ +6%    │ ✓           │  │
│                                                                                  │
│  📊 SUMMARY:                                                                     │
│  Total theoretical cost: $487.50                                                 │
│  Total actual cost: $612.30                                                      │
│  Unexplained variance: $124.80 (25.6%)                                          │
│                                                                                  │
│  💡 RECOMMENDATIONS:                                                            │
│  1. Review butter usage in breakfast sandwich recipe                            │
│  2. Check for cream waste during coffee service                                 │
│  3. Schedule physical inventory count                                           │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### Calculating Actual Usage

```python
def calculate_actual_usage(ingredient_id, start_date, end_date):
    """
    Calculate actual ingredient usage from inventory movement.
    
    Actual Usage = Received - (Ending Inventory - Starting Inventory)
    """
    # Get inventory counts
    start_inventory = get_inventory_count(ingredient_id, start_date)
    end_inventory = get_inventory_count(ingredient_id, end_date)
    
    # Get received quantities
    received = sum(
        line.quantity_grams 
        for line in get_received_lines(ingredient_id, start_date, end_date)
    )
    
    # Calculate usage
    actual_usage = received - (end_inventory - start_inventory)
    
    return {
        'start_inventory': start_inventory,
        'received': received,
        'end_inventory': end_inventory,
        'actual_usage': actual_usage
    }


def calculate_theoretical_usage(ingredient_id, start_date, end_date):
    """
    Calculate theoretical ingredient usage from sales.
    
    Theoretical = Σ (Menu Items Sold × Ingredient per Item)
    """
    total_usage = 0
    
    # Get all menu items that use this ingredient
    menu_items = get_menu_items_using(ingredient_id)
    
    for item in menu_items:
        # Get sales in period
        sales = get_sales(item.id, start_date, end_date)
        
        # Get ingredient usage per menu item
        usage_per_item = get_ingredient_per_menu_item(item.id, ingredient_id)
        
        total_usage += sales.quantity * usage_per_item
    
    return total_usage
```

---

### 5.4 Labor Cost Integration

**Purpose**: Overlay labor costs on sales data for profitability analysis.

#### Labor Data Sources

**Option A: Manual Entry** (MVP)
- Enter total labor cost per day
- Simple form

**Option B: Toast Payroll Export** (if using Toast for payroll)
- Export labor reports
- Import alongside sales

#### Prime Cost Analysis

```
PRIME COST = Food Cost + Labor Cost

Target: <60% of revenue

Example Day:
─────────────
Gross Sales: $1,200
Food Cost: $340 (28.3%)
Labor Cost: $320 (26.7%)
Prime Cost: $660 (55.0%) ✓

Breakdown by Hour:
─────────────────
6-7am:  Sales $45,  Labor $40  → Prime 89% 🔴 (prep time)
7-8am:  Sales $180, Labor $60  → Prime 33% ✓
8-9am:  Sales $220, Labor $60  → Prime 27% ✓
9-10am: Sales $185, Labor $60  → Prime 32% ✓
10-11am: Sales $120, Labor $40 → Prime 33% ✓
11-12pm: Sales $95,  Labor $40 → Prime 42% ✓
```

---

### 5.5 Dashboard

**Purpose**: At-a-glance operational metrics for wall display and executive view.

#### Wall Display Mode

Designed for a mounted monitor in the kitchen/office:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                  │
│           MILL & WHISTLE                            Saturday, Nov 30            │
│                                                           8:47 AM               │
│                                                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│     TODAY'S SALES              │           WEEK TO DATE                         │
│     ────────────               │           ────────────                         │
│                                │                                                │
│         $847                   │              $4,892                            │
│                                │                                                │
│     vs Yesterday: +12%         │           vs Last Week: +8%                    │
│     vs Goal: +6%               │           Goal Progress: ████████░░ 82%       │
│                                │                                                │
├────────────────────────────────┼────────────────────────────────────────────────┤
│                                │                                                │
│     TOP SELLERS TODAY          │           ALERTS                               │
│     ─────────────────          │           ──────                               │
│                                │                                                │
│     1. Bfast Sandwich  52      │           ⚠️ Eggs below par (order today)     │
│     2. Coffee          78      │                                                │
│     3. Yogurt Bowl     23      │           📦 Farm Direct due by 10am          │
│     4. Creemee         18      │                                                │
│                                │           💰 2 invoices due this week         │
│                                │                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### Executive Dashboard (Web)

More detailed view with drill-down capability:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  EXECUTIVE DASHBOARD                                      [Today ▼] [Refresh]   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │
│  │  TODAY'S SALES  │  │  FOOD COST %    │  │  PRIME COST %   │                 │
│  │                 │  │                 │  │                 │                 │
│  │     $847        │  │     28.3%       │  │     54.2%       │                 │
│  │    ↑ 12%        │  │   Target: 30%   │  │   Target: 60%   │                 │
│  │                 │  │      ✓          │  │      ✓          │                 │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                 │
│                                                                                  │
│  HOURLY SALES                                                                    │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  │                    ╭──╮                                                    │  │
│  │               ╭────│  │────╮                                               │  │
│  │          ╭────│    │  │    │────╮                                          │  │
│  │     ╭────│    │    │  │    │    │────╮                                     │  │
│  │  ───│    │    │    │  │    │    │    │───                                  │  │
│  │     6am  7am  8am  9am 10am 11am 12pm                                      │  │
│  │     $45  $180 $220 $185 $120 $95  (now)                                    │  │
│                                                                                  │
│  ACTION ITEMS                              QUICK LINKS                          │
│  ────────────                              ───────────                          │
│  ☐ Review butter variance (+73%)           [Product Mix Report]                │
│  ☐ Submit Farm Direct order               [Invoice Queue]                      │
│  ☐ Pay Valley Foods invoice ($892)        [Order Recommendations]             │
│  ☐ Review pricing on sausage add-on       [Recipe Costing]                    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Daily Digest - Sales Section

```
📈 SALES SUMMARY
────────────────

Yesterday: $1,156.45 (+8% vs prior week)
Week to Date: $4,892.30 (82% of goal)
Month to Date: $18,456.20

🏆 TOP PERFORMERS:
   1. Breakfast Sandwich: 52 sold ($390.00)
   2. Drip Coffee: 78 sold ($234.00)
   3. Yogurt Bowl: 23 sold ($138.00)

📊 NOTABLE TRENDS:
   • Breakfast Creemee up 15% since adding praline
   • Saturday sales averaging 35% above weekdays
   • 9am hour consistently strongest

⚠️ WATCH LIST:
   • Overnight Oats down 20% - consider repositioning
   • Add Sausage attachment rate only 18% - train staff?
```

---

## API Endpoints

### Sales Import
- `POST /api/sales/import/csv` - Import Toast CSV
- `GET /api/sales/import/status` - Check import status
- `GET /api/sales/unmatched-items` - Toast items needing mapping

### Sales Data
- `GET /api/sales/daily` - Daily sales summary
- `GET /api/sales/by-item` - Sales by menu item
- `GET /api/sales/by-period` - Sales by time period
- `GET /api/sales/trends` - Trend analysis

### Usage Analysis
- `GET /api/usage/theoretical` - Theoretical usage
- `GET /api/usage/actual` - Actual usage
- `GET /api/usage/variance` - Variance report

### Dashboard
- `GET /api/dashboard/wall` - Wall display data
- `GET /api/dashboard/executive` - Executive dashboard
- `GET /api/dashboard/kpis` - Key metrics

---

## Implementation Checklist

### Phase 5a (Sales Import)
- [ ] Create `daily_sales` table
- [ ] Build Toast item mapping interface
- [ ] Implement CSV import parser
- [ ] Create import scheduling

### Phase 5b (Analysis)
- [ ] Build product mix dashboard
- [ ] Implement trend analysis
- [ ] Create theoretical usage calculator
- [ ] Build variance report

### Phase 5c (Dashboard)
- [ ] Design wall display UI
- [ ] Build executive dashboard
- [ ] Add sales section to daily digest
- [ ] Create KPI endpoints
