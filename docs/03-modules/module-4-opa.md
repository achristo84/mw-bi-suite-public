# Module 4: Order Planning & Automation (OPA)

**Priority**: MEDIUM — Build after Modules 1-3 stable  
**Dependencies**: Module 1 (DMS), Module 2 (IPI), Module 3 (RMC)  
**Estimated Timeline**: Weeks 7-8

## Overview

The Order Planning & Automation module transforms reactive ordering into proactive inventory management:
- Par level management with alerts
- Delivery calendar with order deadlines
- Order optimization considering minimums and delivery windows
- Automated order draft generation
- Order tracking from submission to receipt

## Components

### 4.1 Par Level Manager

**Purpose**: Define and monitor minimum inventory levels.

#### Par Level Strategy

For a small operation like Mill & Whistle, par levels should be based on:
1. **Usage rate** - How much you use per day/week
2. **Lead time** - How many days until next delivery
3. **Safety buffer** - Extra stock for variability

```
PAR LEVEL = (Daily Usage × Lead Time Days) + Safety Stock

Example: Butter
- Daily usage: ~500g
- Farm Direct delivers Friday (order by Wed 10am)
- Lead time: 2-4 days depending on when you order
- Safety stock: 1 day buffer

If ordering Wednesday for Friday:
PAR = (500g × 2 days) + 500g = 1,500g minimum before ordering
```

#### Par Level Interface

```
┌─────────────────────────────────────────────────────────────────────┐
│  PAR LEVELS                                            [+ Add New]  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Filter: [All Categories ▼]    Show: [● Active  ○ Below Par  ○ All] │
│                                                                      │
│  ═══════════════════════════════════════════════════════════════   │
│  INGREDIENT          PAR LEVEL    ON HAND    STATUS    ACTION       │
│  ═══════════════════════════════════════════════════════════════   │
│                                                                      │
│  DAIRY                                                               │
│  ─────────────────────────────────────────────────────────────────  │
│  butter              1,500g       800g       🔴 LOW    [Order]      │
│  heavy cream         2,000ml      3,500ml    ✓ OK                   │
│  eggs large          180 each     96 each    🔴 LOW    [Order]      │
│  mascarpone          1,000g       1,200g     ✓ OK                   │
│                                                                      │
│  PRODUCE                                                             │
│  ─────────────────────────────────────────────────────────────────  │
│  yellow onion        2,000g       2,400g     ✓ OK                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### On-Hand Tracking Options

**Option A: Manual Count (MVP)**
- Weekly inventory count entered manually
- Simple form to update quantities

**Option B: Theoretical Depletion**
- Start with delivery quantities
- Subtract theoretical usage based on sales
- Periodic physical count to reconcile

**Option C: Full Inventory System (Future)**
- Integrate with Toast inventory
- Real-time tracking

For Phase 1, recommend **Option A** with gradual move to **Option B**.

---

### 4.2 Demand Forecaster

**Purpose**: Predict ingredient needs based on sales patterns.

#### Forecasting Approach

```
DAILY INGREDIENT DEMAND = Σ (Menu Item Sales × Ingredient per Item)

Example: Butter demand for Monday
─────────────────────────────────
Breakfast Sandwiches: 45 sold × 10g butter = 450g
Breakfast Creemee: 12 sold × 15g butter = 180g
Baked Goods: 30 sold × 8g butter = 240g
──────────────────────────────────────────────
Total butter demand: 870g

With 15% safety buffer: 1,000g
```

#### Sales Pattern Analysis

```python
def forecast_demand(ingredient_id, days_ahead=7):
    """
    Forecast ingredient demand for next N days.
    Uses rolling average with day-of-week adjustment.
    """
    # Get historical sales by menu item
    sales_history = get_sales_history(days=28)  # 4 weeks
    
    # Calculate day-of-week multipliers
    dow_multipliers = calculate_dow_multipliers(sales_history)
    # e.g., {Monday: 0.85, Saturday: 1.35, Sunday: 1.20, ...}
    
    # Get base daily average
    base_daily = calculate_base_daily_sales(sales_history)
    
    forecasts = []
    for day_offset in range(days_ahead):
        forecast_date = today() + timedelta(days=day_offset)
        dow = forecast_date.weekday()
        
        # Forecast sales per menu item
        daily_demand = 0
        for item in get_menu_items_using(ingredient_id):
            item_forecast = base_daily[item.id] * dow_multipliers[dow]
            ingredient_per_item = get_ingredient_usage(item.id, ingredient_id)
            daily_demand += item_forecast * ingredient_per_item
        
        forecasts.append({
            'date': forecast_date,
            'demand_grams': daily_demand,
            'confidence': calculate_confidence(sales_history)
        })
    
    return forecasts
```

#### Forecast Display

```
┌─────────────────────────────────────────────────────────────────────┐
│  DEMAND FORECAST: BUTTER                              Next 7 Days   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Current On-Hand: 800g                                              │
│  Par Level: 1,500g                                                  │
│                                                                      │
│     Mon    Tue    Wed    Thu    Fri    Sat    Sun                   │
│    850g   820g   780g   900g  1050g  1200g  1100g                   │
│     ▓▓     ▓▓     ▓▓     ▓▓     ▓▓▓    ▓▓▓    ▓▓▓                  │
│                                                                      │
│  Total 7-Day Demand: 6,700g                                         │
│                                                                      │
│  ⚠️ ALERT: On-hand (800g) below par (1,500g)                        │
│  📦 Recommended Order: 7,000g (accounts for par + forecast)         │
│                                                                      │
│  Next Deliveries:                                                    │
│  • Farm Direct: Friday (order by Wed 10am)                          │
│  • Valley Foods: Mon-Fri (order day before)                         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 4.3 Delivery Calendar

**Purpose**: Visualize delivery schedule and order deadlines.

#### Calendar View

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  DELIVERY CALENDAR                                          November 2024       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐       │
│  │   MON   │   TUE   │   WED   │   THU   │   FRI   │   SAT   │   SUN   │       │
│  │   25    │   26    │   27    │   28    │   29    │   30    │   1     │       │
│  ├─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┤       │
│  │ 🚚 VF   │ 🚚 VF   │ 🚚 VF   │ 🚚 VF   │ 🚚 VF   │         │         │       │
│  │ 📦 GM   │         │ 📦 GM   │         │ 🚚 FD   │         │         │       │
│  │         │         │         │ 🚚 MW   │         │         │         │       │
│  │         │         │ ⏰ FD   │         │         │         │         │       │
│  │         │         │   10am  │         │         │         │         │       │
│  └─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘       │
│                                                                                  │
│  Legend: 🚚 Delivery  📦 Delivery (alt)  ⏰ Order Deadline                       │
│                                                                                  │
│  ─────────────────────────────────────────────────────────────────────────────  │
│                                                                                  │
│  UPCOMING DEADLINES:                                                             │
│  • Wed Nov 27, 10:00 AM - Farm Direct order due for Fri delivery                │
│  • Thu Nov 28, 11:00 AM - Metro Wholesale order due for Mon delivery            │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### Deadline Notifications

System sends reminders before order deadlines:

- **24 hours before**: Email reminder with suggested order
- **2 hours before**: Final reminder if order not submitted
- **Deadline passed**: Alert that window was missed

---

### 4.4 Order Optimizer

**Purpose**: Generate optimal orders considering minimums, prices, and delivery windows.

#### Optimization Logic

```python
def optimize_order(target_date, distributor_id=None):
    """
    Generate optimized order recommendations.
    
    If distributor_id specified, optimize for that distributor.
    Otherwise, optimize across all distributors.
    """
    
    # Get items below par or forecasted to be below par
    needed_items = get_items_below_par() + get_forecasted_needs(target_date)
    
    if distributor_id:
        return optimize_single_distributor(distributor_id, needed_items, target_date)
    else:
        return optimize_multi_distributor(needed_items, target_date)


def optimize_single_distributor(distributor_id, needed_items, target_date):
    """Optimize order for a single distributor."""
    distributor = get_distributor(distributor_id)
    
    # Filter to items available from this distributor
    available_items = [
        item for item in needed_items 
        if has_variant(item.ingredient_id, distributor_id)
    ]
    
    order_lines = []
    order_total = 0
    
    for item in available_items:
        variant = get_best_variant(item.ingredient_id, distributor_id)
        quantity = calculate_order_quantity(item, variant)
        line_total = quantity * variant.current_price
        
        order_lines.append({
            'variant': variant,
            'quantity': quantity,
            'line_total': line_total
        })
        order_total += line_total
    
    # Check minimum
    minimum_gap = distributor.minimum_order - order_total
    
    if minimum_gap > 0:
        # Suggest additional items to meet minimum
        suggestions = suggest_fill_items(distributor_id, minimum_gap, available_items)
        return {
            'order_lines': order_lines,
            'order_total': order_total,
            'minimum': distributor.minimum_order,
            'gap': minimum_gap,
            'fill_suggestions': suggestions,
            'status': 'below_minimum'
        }
    
    return {
        'order_lines': order_lines,
        'order_total': order_total,
        'minimum': distributor.minimum_order,
        'gap': 0,
        'status': 'ready'
    }


def suggest_fill_items(distributor_id, gap_amount, exclude_items):
    """
    Suggest items to add to meet minimum order.
    Prioritize items that:
    1. You'll need soon anyway (approaching par)
    2. Are cheaper from this distributor
    3. Have long shelf life
    """
    candidates = get_fill_candidates(distributor_id, exclude_items)
    
    suggestions = []
    remaining_gap = gap_amount
    
    for candidate in candidates:
        if remaining_gap <= 0:
            break
        
        # Calculate sensible order quantity
        quantity = calculate_fill_quantity(candidate, remaining_gap)
        line_total = quantity * candidate.current_price
        
        suggestions.append({
            'variant': candidate,
            'quantity': quantity,
            'line_total': line_total,
            'reason': candidate.suggestion_reason
        })
        
        remaining_gap -= line_total
    
    return suggestions
```

#### Order Recommendation View

```
┌─────────────────────────────────────────────────────────────────────┐
│  ORDER RECOMMENDATION: FARM DIRECT                                   │
│  Delivery: Friday, Nov 29                Order by: Wed Nov 27, 10am │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  NEEDED ITEMS (below par or forecasted need):                        │
│  ─────────────────────────────────────────────────────────────────  │
│  │ Item              │ SKU      │ Qty │ Unit    │ Price  │ Total  │ │
│  ├───────────────────┼──────────┼─────┼─────────┼────────┼────────┤ │
│  │ Eggs 15 dozen     │ FD-2341  │ 2   │ case    │ $32.00 │ $64.00 │ │
│  │ Heavy Cream       │ FD-1122  │ 4   │ quart   │ $2.95  │ $11.80 │ │
│  │ Local Yogurt      │ FD-3390  │ 6   │ 32oz    │ $5.50  │ $33.00 │ │
│  ─────────────────────────────────────────────────────────────────  │
│                                              Subtotal:    $108.80   │
│                                                                      │
│  ⚠️ MINIMUM NOT MET                                                  │
│  Order minimum: $300.00                                              │
│  Current total: $108.80                                              │
│  Gap: $191.20                                                        │
│                                                                      │
│  SUGGESTED ADDITIONS (to meet minimum):                              │
│  ─────────────────────────────────────────────────────────────────  │
│  │ ☑ Butter (approaching par)      │ 2 case │ $45.00  │ $90.00   │ │
│  │ ☑ Maple Syrup (good price)      │ 1 gal  │ $52.00  │ $52.00   │ │
│  │ ☐ Flour AP (long shelf life)    │ 1 bag  │ $28.00  │ $28.00   │ │
│  │ ☐ Coffee Retail (can sell)      │ 6 bag  │ $12.00  │ $72.00   │ │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  Selected additions: $142.00                                         │
│  NEW TOTAL: $250.80 (still $49.20 short)                            │
│                                                                      │
│  [Add More Items]           [Generate Order Draft]                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 4.5 Order Draft Generator

**Purpose**: Create formatted order emails ready to send to reps.

#### Email Format

```
To: rep@distributor.example.com
Subject: Mill & Whistle Order for Friday Nov 29

Hi [Rep Name],

Please deliver the following order on Friday, November 29:

┌─────────────────────────────────────────────────────────────────┐
│ SKU       │ Item Description           │ Qty │ Unit   │ Price  │
├───────────┼────────────────────────────┼─────┼────────┼────────┤
│ FD-2341   │ Eggs Large 15 Dozen        │ 2   │ case   │ $32.00 │
│ FD-1122   │ Heavy Cream                │ 4   │ quart  │ $2.95  │
│ FD-3390   │ Cabot Greek Yogurt 32oz    │ 6   │ each   │ $5.50  │
│ FD-0892   │ Plugra Butter              │ 2   │ case   │ $45.00 │
│ FD-4421   │ VT Maple Syrup Grade A     │ 1   │ gallon │ $52.00 │
└───────────┴────────────────────────────┴─────┴────────┴────────┘

Estimated Total: $250.80

Please confirm receipt and let me know if any items are unavailable.

Thanks!
[Your Name]
Mill & Whistle
(555) 123-4567
```

#### Draft Generation Options

1. **Copy to clipboard** - Paste into email client
2. **Open in Gmail** - Pre-populated draft
3. **Send directly** - If Gmail API configured with send permission

---

### 4.6 Order Tracker

**Purpose**: Track orders from submission through receipt and invoicing.

#### Order Lifecycle

```
┌─────────┐    ┌─────────┐    ┌───────────┐    ┌──────────┐    ┌─────────┐
│  DRAFT  │───▶│  SENT   │───▶│ CONFIRMED │───▶│ RECEIVED │───▶│ INVOICED│
└─────────┘    └─────────┘    └───────────┘    └──────────┘    └─────────┘
     │              │               │                │               │
     │              │               │                │               │
  Created       Emailed to      Rep confirms     Delivery        Invoice
  in system     distributor     (optional)       checked in      matched
```

#### Order List View

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ORDERS                                                    [+ New Order Draft]  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Filter: [All Distributors ▼]  Status: [All ▼]  Date: [Last 30 days ▼]         │
│                                                                                  │
│  ═══════════════════════════════════════════════════════════════════════════   │
│  ORDER         DISTRIBUTOR      STATUS       TOTAL      EXPECTED    ACTION      │
│  ═══════════════════════════════════════════════════════════════════════════   │
│                                                                                  │
│  #ORD-0042    Farm Direct      🟡 SENT      $312.40    Fri 11/29   [Track]     │
│  #ORD-0041    Valley Foods     ✓ RECEIVED   $892.15    Wed 11/27   [View]      │
│  #ORD-0040    Mtn Produce      ✓ INVOICED   $234.56    Mon 11/25   [View]      │
│  #ORD-0039    Green Market     🟡 SENT      $445.20    Mon 11/25   ⚠️ Late     │
│  #ORD-0038    Valley Foods     ✓ INVOICED   $567.89    Fri 11/22   [View]      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### Receiving Workflow

When delivery arrives:

1. **Quick receive**: Mark entire order as received (no discrepancies)
2. **Detailed receive**: Check each line item
   - Quantity received (vs ordered)
   - Condition (good, damaged, wrong item)
   - Create dispute if issues

```
┌─────────────────────────────────────────────────────────────────────┐
│  RECEIVE ORDER #ORD-0042                                            │
│  Farm Direct - Expected Fri Nov 29                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  │ Item                  │ Ordered │ Received │ Status │            │
│  ├───────────────────────┼─────────┼──────────┼────────┤            │
│  │ Eggs 15 Dozen         │ 2 case  │ [2____]  │ [OK ▼] │            │
│  │ Heavy Cream           │ 4 quart │ [4____]  │ [OK ▼] │            │
│  │ Greek Yogurt 32oz     │ 6 each  │ [5____]  │ [Short▼]│  ⚠️       │
│  │ Plugra Butter         │ 2 case  │ [2____]  │ [OK ▼] │            │
│  │ Maple Syrup           │ 1 gal   │ [1____]  │ [OK ▼] │            │
│                                                                      │
│  Issues Found: 1                                                     │
│  ☑ Create dispute for short yogurt (1 unit)                        │
│                                                                      │
│  [Cancel]                                [Complete Receiving]        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Daily Digest - Ordering Section

```
📦 ORDERING STATUS
──────────────────

⏰ UPCOMING DEADLINES:
   • Wed Nov 27, 10:00 AM - Farm Direct (2 hours away!)
     Draft ready: $250.80 (minimum: $300)
     ⚠️ Add $49.20 to meet minimum

   • Fri Nov 29, 11:00 AM - Metro Wholesale
     No draft yet

🚚 EXPECTED DELIVERIES TODAY:
   • Valley Foods #ORD-0043 - $456.78

⚠️ OVERDUE DELIVERIES:
   • Green Market #ORD-0039 - Expected Mon 11/25 (4 days late)
     Last contact: None
     [Draft follow-up email]

📊 THIS WEEK'S ORDERS:
   Total ordered: $1,847.23
   Total received: $1,126.71
   Pending: $720.52
```

---

## API Endpoints

### Par Levels
- `GET /api/par-levels` - List par levels
- `PUT /api/par-levels/{ingredient_id}` - Set par level
- `GET /api/par-levels/alerts` - Items below par

### Inventory
- `GET /api/inventory` - Current on-hand quantities
- `PUT /api/inventory/{ingredient_id}` - Update quantity
- `POST /api/inventory/count` - Submit inventory count

### Forecasting
- `GET /api/forecast/{ingredient_id}` - Demand forecast
- `GET /api/forecast/all` - All ingredients forecast

### Orders
- `GET /api/orders` - List orders
- `GET /api/orders/{id}` - Order details
- `POST /api/orders` - Create order
- `PUT /api/orders/{id}/send` - Mark as sent
- `PUT /api/orders/{id}/receive` - Receive order
- `GET /api/orders/optimize/{distributor_id}` - Get order recommendation

### Calendar
- `GET /api/calendar/deliveries` - Delivery calendar
- `GET /api/calendar/deadlines` - Upcoming deadlines

---

## Implementation Checklist

### Phase 4a (Par Levels & Inventory)
- [ ] Add par_level field to ingredients
- [ ] Build par level management interface
- [ ] Create inventory count form
- [ ] Implement below-par alerts

### Phase 4b (Calendar & Deadlines)
- [ ] Build delivery calendar view
- [ ] Create deadline reminder system
- [ ] Add deadline notifications to digest

### Phase 4c (Order Optimization)
- [ ] Implement order optimizer logic
- [ ] Build minimum-fill suggestions
- [ ] Create order recommendation view

### Phase 4d (Order Workflow)
- [ ] Create order draft generator
- [ ] Build order tracking system
- [ ] Implement receiving workflow
- [ ] Connect receiving to disputes (Module 1)
