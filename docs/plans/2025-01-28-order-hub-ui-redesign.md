# Order Hub UI Redesign Plan

**Date:** 2025-01-28
**Status:** Ready for Implementation
**Context:** All 5 distributor APIs now working (Valley Foods, Mountain Produce, Metro Wholesale, Farm Direct, Green Market)

## Overview

Redesign Order Hub to be search-first with lightweight list management. The primary workflow is: **Search → Compare prices → Select SKU per vendor → Build carts → Execute orders manually**.

## Current State

- Backend: All 5 distributors authenticated and searching
- Frontend: Basic OrderList, OrderBuilder, ComparisonSearchModal exist
- API: `/api/v1/distributor-search` returns results with prices from all vendors

## User Requirements (from conversation)

1. **Quick item entry** - Type and press Enter to add items, click to edit details later
2. **Search-first design** - Search and price comparison is the main functionality
3. **SKU mapping** - Once SKU is picked at a vendor, it's saved but can be changed (sales, new brands)
4. **Color-coded statuses** for list items:
   - a) Added, no history/not assigned (new)
   - b) On list with history (past prices/providers)
   - c) Assigned to product(s) at vendors
   - d) Ordered
   - e) Arrived (removed from list)
5. **History pages** - Order history by vendor, price history by item
6. **Cart/Order Building** - Drag list items to vendor columns, show prices, hover for comparison
7. **Enhanced price display** - Case size, unit price, AND normalized pricing (per oz, lb, etc.)
8. **Right-click override** - Allow user to pick display unit for normalized prices

## Implementation Phases

### Phase 1: Search-First Main Screen

**Goal:** Make search the primary entry point with lightweight list management in header/sidebar.

**File:** `frontend/src/pages/OrderHub.tsx` (new - replaces OrderList as main page)

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ [Search input with Enter to search]          [+ Quick Add Item] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─ List Sidebar (collapsible) ─┐  ┌─ Search Results ─────────┐│
│  │ Items to Order (12)          │  │                          ││
│  │ ● Ricotta (assigned)         │  │ Distributor 1            ││
│  │ ○ Eggs (history)             │  │ ├─ SKU: XXX @ $25.00     ││
│  │ ◌ Lemons (new)               │  │ │   2x5lb case | $2.50/lb││
│  │ ...                          │  │ ├─ SKU: YYY @ $30.00     ││
│  │                              │  │     1x10lb | $3.00/lb    ││
│  │ [View Cart Builder →]        │  │                          ││
│  └──────────────────────────────┘  │ Distributor 2            ││
│                                    │ ├─ ...                   ││
│                                    └──────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Components:**
- `QuickAddInput` - Type item name, Enter to add to list
- `ListSidebar` - Collapsible list with color-coded items
- `SearchResults` - Main area showing results grouped by distributor
- `PriceDisplay` - Shows case price + normalized price with right-click menu

**Quick Add behavior:**
- Enter adds item with status "new" (no assignment)
- Item appears in sidebar immediately
- User can click item to search for it

### Phase 2: Enhanced Price Display

**Goal:** Show comprehensive pricing info with normalization.

**Component:** `frontend/src/components/PriceDisplay.tsx`

**Display format:**
```
$45.14                    ← Case/unit price
1x15 DZ Case              ← Pack size description
$0.25/oz | $4.00/lb       ← Normalized prices (auto-detected)
[Best Price] badge        ← When lowest per-unit across vendors
```

**Normalization logic:**
- Weight items (lb, kg, oz, g): Show per-lb and per-oz
- Volume items (gal, L, fl oz): Show per-gal and per-fl-oz
- Count items (each, dozen, case): Show per-each
- Auto-detect from `pack_unit` field

**Right-click context menu:**
- "Show price per oz"
- "Show price per lb"
- "Show price per each"
- "Show price per case"
- Saves preference per item or globally

**Backend support:**
- `price_per_base_unit_cents` already calculated (per gram)
- Add frontend conversion: grams → oz, lb, etc.

### Phase 3: Color-Coded Status System

**Statuses with colors:**

| Status | Color | Icon | Description |
|--------|-------|------|-------------|
| New | Gray | ◌ | Just added, no history, no assignment |
| Has History | Blue | ○ | Previously ordered, has price history |
| Assigned | Green | ● | Linked to SKU(s) at vendor(s) |
| Ordered | Orange | ◉ | In current order batch |
| Arrived | ✓ | Checkmark | Received, auto-removed from active list |

**Implementation:**
- Add `status` derivation logic based on:
  - `assignments_count > 0` → Assigned
  - `last_ordered_at != null` → Has History
  - `status == 'ordered'` → Ordered
  - `status == 'received'` → Arrived
  - else → New

**Component:** `frontend/src/components/ListItemBadge.tsx`

### Phase 4: Cart/Order Building Screen

**Goal:** Drag-and-drop interface to build orders by vendor.

**File:** `frontend/src/pages/CartBuilder.tsx` (enhance existing OrderBuilder)

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Cart Builder                                    [Finalize All]  │
├──────────────┬──────────────┬──────────────┬───────────────────┤
│ Items to     │ Valley Foods │ Mountain     │ Metro Wholesale    │
│ Assign       │ $245.00      │ $180.50      │ $312.00           │
│              │ Min: $300 ❌ │ Min: $300 ✓  │ Min: $250 ✓       │
├──────────────┼──────────────┼──────────────┼───────────────────┤
│ ◌ Lemons     │ ● Eggs       │ ● Ricotta    │ ● Butter          │
│ ○ Eggs       │   $45.00     │   $26.25     │   $85.00          │
│ ● Ricotta    │              │ ● Cream      │                   │
│              │              │   $32.00     │                   │
│              │              │              │                   │
│ [drag items →│ [hover shows │ [hover shows │ [hover shows      │
│  to assign]  │  alt prices] │  alt prices] │  alt prices]      │
└──────────────┴──────────────┴──────────────┴───────────────────┘
```

**Features:**
- Left column: Unassigned items from list
- Vendor columns: Items assigned to each vendor
- Drag-and-drop between columns (use @dnd-kit/core)
- Hover on assigned item → tooltip shows prices at other vendors
- Real-time subtotals per vendor
- Minimum order progress bars
- "Finalize" creates orders and outputs copy lists

**Hover tooltip:**
```
┌─────────────────────────┐
│ Ricotta @ Metro: $40    │
│ ─────────────────────── │
│ Valley Foods: $50.34   │
│ Farm Direct: $25.88    │ ← Best price highlighted
│ Mountain Produce: $36.54│
│ [Move to Farm Direct]  │
└─────────────────────────┘
```

### Phase 5: History Pages

**Goal:** View order and price history.

#### 5a: Order History by Vendor

**File:** `frontend/src/pages/OrderHistory.tsx`

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Order History                     [Filter by vendor ▼] [Date ▼]│
├─────────────────────────────────────────────────────────────────┤
│ Valley Foods - Order #12345 - Jan 15, 2025 - $456.78           │
│ ├─ Ricotta 2x @ $50.34 = $100.68                               │
│ ├─ Eggs 5x @ $45.00 = $225.00                                  │
│ └─ Butter 3x @ $43.70 = $131.10                                │
├─────────────────────────────────────────────────────────────────┤
│ Metro Wholesale - Order #54321 - Jan 12, 2025 - $312.00        │
│ └─ ...                                                          │
└─────────────────────────────────────────────────────────────────┘
```

#### 5b: Price History by Item

**File:** `frontend/src/pages/ItemPriceHistory.tsx`

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Price History: Ricotta                                          │
├─────────────────────────────────────────────────────────────────┤
│ [Line chart showing price over time by vendor]                  │
├─────────────────────────────────────────────────────────────────┤
│ Date       │ Vendor          │ SKU    │ Price  │ Per lb        │
│ Jan 28     │ Farm Direct     │ 1624   │ $25.88 │ $4.31         │
│ Jan 28     │ Metro Wholesale │ D128   │ $16.82 │ $5.61         │
│ Jan 15     │ Valley Foods    │ NH004  │ $50.34 │ $5.04         │
│ Jan 10     │ Farm Direct     │ 1624   │ $24.50 │ $4.08         │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 6: Navigation Updates

**Update:** `frontend/src/components/Layout.tsx`

**New navigation structure:**
```
Order Hub
├─ Search & Order (main screen) - /orders
├─ Cart Builder - /orders/build
├─ Order History - /orders/history
└─ Price History - /orders/prices
```

## API Endpoints Needed

### Existing (working)
- `GET /api/v1/distributor-search?q=...` - Search all vendors
- `GET /api/v1/order-list` - List items
- `POST /api/v1/order-list` - Add item
- `POST /api/v1/order-builder/assign` - Assign item to SKU
- `GET /api/v1/order-builder/summary` - Get carts
- `POST /api/v1/orders/finalize` - Create orders

### New endpoints needed
- `GET /api/v1/orders/history?vendor_id=...` - Order history by vendor
- `GET /api/v1/items/{id}/price-history` - Price history for item
- `PATCH /api/v1/order-list/{id}/quick-update` - Quick status update

## File Changes Summary

### New Files
- `frontend/src/pages/OrderHub.tsx` - Main search-first screen
- `frontend/src/pages/OrderHistory.tsx` - Order history by vendor
- `frontend/src/pages/ItemPriceHistory.tsx` - Price history by item
- `frontend/src/components/PriceDisplay.tsx` - Enhanced price display
- `frontend/src/components/ListItemBadge.tsx` - Color-coded status badge
- `frontend/src/components/QuickAddInput.tsx` - Enter-to-add input
- `frontend/src/components/ListSidebar.tsx` - Collapsible item list
- `frontend/src/components/VendorPriceTooltip.tsx` - Hover comparison

### Modified Files
- `frontend/src/pages/OrderBuilder.tsx` → `CartBuilder.tsx` - Add drag-drop
- `frontend/src/components/Layout.tsx` - Update navigation
- `frontend/src/components/ComparisonSearchModal.tsx` - Use PriceDisplay
- `frontend/src/lib/api.ts` - Add new endpoints
- `frontend/src/types/order-hub.ts` - Add new types

### Backend Files
- `app/api/order_list.py` - Add price history endpoint
- `app/api/order_builder.py` - Add order history endpoint

## Implementation Order

1. **Phase 2: PriceDisplay** - Foundation component needed everywhere
2. **Phase 3: Status badges** - Visual feedback for list items
3. **Phase 1: OrderHub main screen** - New search-first layout
4. **Phase 4: CartBuilder** - Drag-drop with tooltips
5. **Phase 5: History pages** - Order and price history
6. **Phase 6: Navigation** - Wire everything together

## Testing Checklist

- [ ] Quick add: Type "eggs", press Enter → item appears in list
- [ ] Search: Type in search box → results from all 5 vendors
- [ ] Price display: Shows case price + per-lb price
- [ ] Right-click: Can change unit display
- [ ] Status colors: New=gray, History=blue, Assigned=green
- [ ] Drag-drop: Move item from list to vendor column
- [ ] Hover: Shows prices at other vendors
- [ ] Cart totals: Update in real-time
- [ ] Minimum indicators: Show progress toward minimums
- [ ] Finalize: Creates orders, outputs copy lists
- [ ] Order history: Filter by vendor, see past orders
- [ ] Price history: See price trends for an item

## Notes

- All 5 distributors confirmed working: Valley Foods, Mountain Produce, Metro Wholesale, Farm Direct, Green Market
- Search returns ~14 results for "ricotta" in ~8.5 seconds
- Cart totals calculated client-side from search result prices
- No auto-submit to vendors yet - output is copy list for manual entry
