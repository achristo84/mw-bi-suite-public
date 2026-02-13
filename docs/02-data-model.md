# Data Model

## Entity Relationship Diagram

```
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│   DISTRIBUTOR    │       │    INGREDIENT    │       │      RECIPE      │
├──────────────────┤       ├──────────────────┤       ├──────────────────┤
│ id               │       │ id               │       │ id               │
│ name             │       │ name             │       │ name             │
│ rep_name         │       │ category         │       │ yield_quantity   │
│ rep_email        │       │ base_unit (g/ml) │       │ yield_unit       │
│ rep_phone        │       │ storage_type     │       │ instructions     │
│ portal_url       │       │ shelf_life_days  │       │ prep_time_min    │
│ order_email      │       │ par_level        │       │ is_active        │
│ minimum_order    │       └────────┬─────────┘       └────────┬─────────┘
│ delivery_days    │                │                          │
│ order_deadline   │                │                          │
│ payment_terms    │                ▼                          ▼
│ notes            │       ┌──────────────────┐       ┌──────────────────┐
└────────┬─────────┘       │ DIST_INGREDIENT  │       │ RECIPE_INGREDIENT│
         │                 │ (variant/SKU)    │       ├──────────────────┤
         │                 ├──────────────────┤       │ recipe_id        │
         │                 │ id               │       │ ingredient_id    │
         │                 │ distributor_id   │───┐   │ quantity_grams   │
         │                 │ ingredient_id    │   │   │ prep_note        │
         └────────────────▶│ sku              │   │   └──────────────────┘
                           │ description      │   │
                           │ pack_size        │   │
                           │ pack_unit        │   │   ┌──────────────────┐
                           │ units_per_pack   │   │   │    MENU_ITEM     │
                           │ grams_per_unit   │   │   ├──────────────────┤
                           └────────┬─────────┘   │   │ id               │
                                    │             │   │ name             │
                                    ▼             │   │ recipe_id        │
                           ┌──────────────────┐   │   │ portion_size     │
                           │   PRICE_HISTORY  │   │   │ menu_price       │
                           ├──────────────────┤   │   │ category         │
                           │ dist_ingredient_id│   │   │ is_active        │
                           │ price            │   │   └──────────────────┘
                           │ effective_date   │   │
                           │ source (invoice/ │   │
                           │   catalog/manual)│   │
                           └──────────────────┘   │
                                                  │
         ┌────────────────────────────────────────┘
         │
         ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│      ORDER       │       │     INVOICE      │       │     DISPUTE      │
├──────────────────┤       ├──────────────────┤       ├──────────────────┤
│ id               │       │ id               │       │ id               │
│ distributor_id   │       │ order_id (null)  │       │ invoice_id       │
│ status (draft/   │       │ distributor_id   │       │ invoice_line_id  │
│   sent/received) │       │ invoice_number   │       │ type (wrong_item/│
│ submitted_at     │       │ invoice_date     │       │   bad_quality/   │
│ expected_date    │       │ due_date         │       │   missing/price) │
│ received_at      │       │ total_amount     │       │ description      │
│ notes            │       │ pdf_path         │       │ amount_disputed  │
└────────┬─────────┘       │ paid_at          │       │ status (open/    │
         │                 │ payment_ref      │       │   resolved/      │
         ▼                 └────────┬─────────┘       │   written_off)   │
┌──────────────────┐                │                 │ resolved_at      │
│   ORDER_LINE     │                ▼                 │ credit_received  │
├──────────────────┤       ┌──────────────────┐       └──────────────────┘
│ order_id         │       │  INVOICE_LINE    │
│ dist_ingredient_id       ├──────────────────┤
│ quantity         │       │ invoice_id       │
│ expected_price   │       │ dist_ingredient_id (nullable)
│ actual_price     │       │ raw_description  │
│ actual_quantity  │       │ quantity         │
└──────────────────┘       │ unit_price       │
                           │ extended_price   │
                           │ matched_order_line_id (nullable)
                           └──────────────────┘
```

## Table Definitions

### Core Entities

#### distributors
Central registry of all suppliers.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| name | VARCHAR(100) | NOT NULL, UNIQUE | Company name |
| rep_name | VARCHAR(100) | | Primary contact name |
| rep_email | VARCHAR(255) | | Primary contact email |
| rep_phone | VARCHAR(20) | | Primary contact phone |
| portal_url | VARCHAR(500) | | Online ordering portal URL |
| portal_username | VARCHAR(100) | | Portal login (encrypted) |
| portal_password_encrypted | TEXT | | Portal password (encrypted via Secret Manager) |
| scraper_module | VARCHAR(100) | | Python module for scraping, e.g., 'scrapers.valleyfoods' |
| scrape_frequency | VARCHAR(20) | DEFAULT 'weekly' | 'daily', 'weekly', 'manual' |
| last_successful_scrape | TIMESTAMP | | Last successful catalog scrape |
| order_email | VARCHAR(255) | | Email for placing orders |
| minimum_order_cents | INTEGER | DEFAULT 0 | Minimum order in cents |
| delivery_days | VARCHAR(50)[] | | Array of delivery days ['monday', 'friday'] |
| order_deadline | VARCHAR(100) | | Human-readable deadline ("Wednesday 10am for Friday delivery") |
| payment_terms_days | INTEGER | DEFAULT 15 | Net payment terms |
| vendor_category | VARCHAR(50) | | 'food_distributor', 'retail', 'service', etc. |
| is_active | BOOLEAN | DEFAULT TRUE | Whether actively ordering from |
| notes | TEXT | | Free-form notes |
| created_at | TIMESTAMP | DEFAULT NOW() | |
| updated_at | TIMESTAMP | DEFAULT NOW() | |

#### ingredients
Canonical ingredient list with normalized base units.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| name | VARCHAR(100) | NOT NULL, UNIQUE | Canonical name ("butter", "heavy cream") |
| category | VARCHAR(50) | | 'dairy', 'produce', 'protein', 'dry_goods', etc. |
| base_unit | VARCHAR(10) | NOT NULL | 'g', 'ml', 'each' |
| storage_type | VARCHAR(20) | | 'refrigerated', 'frozen', 'dry', 'ambient' |
| shelf_life_days | INTEGER | | Typical shelf life |
| par_level_base_units | DECIMAL(10,2) | | Minimum to keep on hand |
| yield_factor | DECIMAL(4,3) | DEFAULT 1.0 | Usable portion (0.85 = 15% trim waste) |
| notes | TEXT | | |
| created_at | TIMESTAMP | DEFAULT NOW() | |
| updated_at | TIMESTAMP | DEFAULT NOW() | |

#### dist_ingredients
Distributor-specific variants/SKUs mapped to canonical ingredients.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| distributor_id | UUID | FK → distributors | |
| ingredient_id | UUID | FK → ingredients | Canonical ingredient (nullable if unmapped) |
| sku | VARCHAR(50) | | Distributor's SKU/item number |
| description | VARCHAR(255) | NOT NULL | Distributor's item description |
| pack_size | DECIMAL(10,3) | | Size of pack (36 for "36 lb case") |
| pack_unit | VARCHAR(20) | | Unit of pack ('lb', 'oz', 'each', 'gallon') |
| units_per_pack | INTEGER | DEFAULT 1 | For cases of individual items |
| grams_per_unit | DECIMAL(12,4) | | Conversion factor to base unit |
| is_active | BOOLEAN | DEFAULT TRUE | Currently available from distributor |
| quality_tier | VARCHAR(20) | | 'premium', 'standard', 'commodity' for decision support |
| quality_notes | TEXT | | Notes on quality differences vs alternatives |
| notes | TEXT | | |
| created_at | TIMESTAMP | DEFAULT NOW() | |
| updated_at | TIMESTAMP | DEFAULT NOW() | |

**Unique constraint**: (distributor_id, sku)

#### price_history
Track price changes over time for analysis and alerts.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| dist_ingredient_id | UUID | FK → dist_ingredients | |
| price_cents | INTEGER | NOT NULL | Price in cents |
| effective_date | DATE | NOT NULL | When this price became effective |
| source | VARCHAR(20) | | 'invoice', 'catalog', 'manual', 'quote' |
| source_reference | VARCHAR(100) | | Invoice number, catalog date, etc. |
| created_at | TIMESTAMP | DEFAULT NOW() | |

**Index**: (dist_ingredient_id, effective_date DESC)

### Recipe & Menu

#### recipes
Batch recipes with yields.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| name | VARCHAR(100) | NOT NULL, UNIQUE | Recipe name |
| yield_quantity | DECIMAL(10,2) | NOT NULL | How much this makes |
| yield_unit | VARCHAR(20) | NOT NULL | 'servings', 'grams', 'each', 'quarts' |
| instructions | TEXT | | Preparation steps |
| prep_time_minutes | INTEGER | | |
| cook_time_minutes | INTEGER | | |
| is_active | BOOLEAN | DEFAULT TRUE | |
| notes | TEXT | | |
| created_at | TIMESTAMP | DEFAULT NOW() | |
| updated_at | TIMESTAMP | DEFAULT NOW() | |

#### recipe_ingredients
Ingredients used in each recipe.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| recipe_id | UUID | FK → recipes | |
| ingredient_id | UUID | FK → ingredients | |
| quantity_grams | DECIMAL(10,3) | NOT NULL | Amount in base units (grams/ml) |
| prep_note | VARCHAR(100) | | "diced", "room temperature", etc. |
| is_optional | BOOLEAN | DEFAULT FALSE | |

**Unique constraint**: (recipe_id, ingredient_id)

#### menu_items
Items sold to customers with pricing.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| name | VARCHAR(100) | NOT NULL | Menu display name |
| recipe_id | UUID | FK → recipes | Base recipe (nullable for retail) |
| portion_of_recipe | DECIMAL(5,4) | DEFAULT 1.0 | What fraction of recipe yield (0.0833 = 1/12) |
| menu_price_cents | INTEGER | NOT NULL | Selling price |
| category | VARCHAR(50) | | 'breakfast', 'drinks', 'retail', 'add-on' |
| toast_id | VARCHAR(50) | | Toast menu item ID for sync |
| is_active | BOOLEAN | DEFAULT TRUE | |
| created_at | TIMESTAMP | DEFAULT NOW() | |
| updated_at | TIMESTAMP | DEFAULT NOW() | |

### Orders & Invoices

#### orders
Orders placed with distributors.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| distributor_id | UUID | FK → distributors | |
| status | VARCHAR(20) | NOT NULL | 'draft', 'sent', 'confirmed', 'received', 'invoiced' |
| submitted_at | TIMESTAMP | | When order was sent |
| expected_delivery | DATE | | |
| received_at | TIMESTAMP | | Actual delivery time |
| submitted_by | VARCHAR(50) | | Who placed the order |
| notes | TEXT | | |
| created_at | TIMESTAMP | DEFAULT NOW() | |
| updated_at | TIMESTAMP | DEFAULT NOW() | |

#### order_lines
Line items on orders.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| order_id | UUID | FK → orders | |
| dist_ingredient_id | UUID | FK → dist_ingredients | |
| quantity | DECIMAL(10,3) | NOT NULL | Number of units ordered |
| expected_price_cents | INTEGER | | Price at time of order |
| actual_quantity | DECIMAL(10,3) | | What was actually received |
| actual_price_cents | INTEGER | | Actual invoiced price |
| notes | TEXT | | |

#### invoices
Invoices received from distributors.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| distributor_id | UUID | FK → distributors | |
| order_id | UUID | FK → orders | Nullable - may not have matching order |
| invoice_number | VARCHAR(50) | NOT NULL | Distributor's invoice number |
| invoice_date | DATE | NOT NULL | |
| delivery_date | DATE | | Actual delivery date (may differ from invoice_date) |
| due_date | DATE | | |
| account_number | VARCHAR(50) | | Customer account # with this distributor |
| sales_rep_name | VARCHAR(100) | | Sales rep on invoice (for relationship tracking) |
| sales_order_number | VARCHAR(50) | | Distributor's SO# (for order reconciliation) |
| subtotal_cents | INTEGER | | |
| tax_cents | INTEGER | | |
| total_cents | INTEGER | NOT NULL | |
| pdf_path | VARCHAR(500) | | Cloud Storage path to PDF |
| raw_text | TEXT | | Extracted text for search |
| parsed_at | TIMESTAMP | | When LLM parsing completed |
| parse_confidence | DECIMAL(3,2) | | 0.0-1.0 confidence score |
| reviewed_by | VARCHAR(50) | | Human reviewer |
| reviewed_at | TIMESTAMP | | |
| paid_at | TIMESTAMP | | |
| payment_reference | VARCHAR(100) | | Check number, transfer ID |
| created_at | TIMESTAMP | DEFAULT NOW() | |
| updated_at | TIMESTAMP | DEFAULT NOW() | |

**Unique constraint**: (distributor_id, invoice_number)

#### invoice_lines
Line items parsed from invoices.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| invoice_id | UUID | FK → invoices | |
| dist_ingredient_id | UUID | FK → dist_ingredients | Nullable until matched |
| raw_description | VARCHAR(255) | NOT NULL | Original text from invoice |
| raw_sku | VARCHAR(50) | | SKU as it appeared |
| quantity_ordered | DECIMAL(10,3) | | Quantity originally ordered (if shown on invoice) |
| quantity | DECIMAL(10,3) | | Quantity shipped/invoiced |
| unit_price_cents | INTEGER | | Price per unit (list price) |
| extended_price_cents | INTEGER | | Line total (can be negative for credits) |
| is_taxable | BOOLEAN | DEFAULT FALSE | Whether this line is taxable |
| line_type | VARCHAR(20) | DEFAULT 'product' | 'product', 'credit', 'fee' |
| parent_line_id | UUID | FK → invoice_lines | For credits: links to the product line |
| matched_order_line_id | UUID | FK → order_lines | If reconciled to an order |
| match_status | VARCHAR(20) | | 'matched', 'price_mismatch', 'quantity_mismatch', 'unmatched' |
| notes | TEXT | | |

**Note on credits**: When a distributor applies a credit/allowance to a product (e.g., "CUST TRACS ALLOWANCE"), it appears as a separate line with `line_type='credit'`, negative `extended_price_cents`, and `parent_line_id` pointing to the product line. The effective price = product price + credit.

### Disputes & Issues

#### disputes
Track issues with deliveries and invoices.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| invoice_id | UUID | FK → invoices | |
| invoice_line_id | UUID | FK → invoice_lines | Nullable for invoice-level issues |
| dispute_type | VARCHAR(30) | NOT NULL | 'wrong_item', 'bad_quality', 'missing', 'price_discrepancy', 'short_quantity' |
| description | TEXT | NOT NULL | What went wrong |
| amount_disputed_cents | INTEGER | | Dollar amount of dispute |
| photo_paths | VARCHAR(500)[] | | Cloud Storage paths to photos |
| status | VARCHAR(20) | NOT NULL DEFAULT 'open' | 'open', 'contacted', 'resolved', 'written_off' |
| resolution_notes | TEXT | | How it was resolved |
| credit_received_cents | INTEGER | | Actual credit received |
| resolved_at | TIMESTAMP | | |
| created_at | TIMESTAMP | DEFAULT NOW() | |
| updated_at | TIMESTAMP | DEFAULT NOW() | |

### Sales (Future - Phase 5)

#### daily_sales
Aggregated sales data from Toast.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| sale_date | DATE | NOT NULL | |
| menu_item_id | UUID | FK → menu_items | |
| quantity_sold | INTEGER | NOT NULL | |
| gross_sales_cents | INTEGER | | |
| net_sales_cents | INTEGER | | After discounts |
| imported_at | TIMESTAMP | DEFAULT NOW() | |

**Unique constraint**: (sale_date, menu_item_id)

### Catalog Scraping (Phase 2)

#### catalog_scrapes
Track scraping runs from distributor portals.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| distributor_id | UUID | FK → distributors | |
| started_at | TIMESTAMP | NOT NULL | When scrape began |
| completed_at | TIMESTAMP | | When scrape finished |
| status | VARCHAR(20) | NOT NULL | 'running', 'success', 'failed', 'partial' |
| items_found | INTEGER | | Total items scraped |
| items_matched | INTEGER | | Items matched to existing dist_ingredients |
| items_new | INTEGER | | New items discovered |
| error_message | TEXT | | Error details if failed |
| created_at | TIMESTAMP | DEFAULT NOW() | |

#### scraped_items
Staging table for items scraped from distributor catalogs before mapping.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| scrape_id | UUID | FK → catalog_scrapes | |
| distributor_id | UUID | FK → distributors | |
| raw_sku | VARCHAR(100) | | SKU as scraped |
| raw_name | VARCHAR(500) | | Product name as scraped |
| raw_description | TEXT | | Description as scraped |
| raw_price_text | VARCHAR(100) | | Price string as scraped |
| raw_unit_text | VARCHAR(100) | | Unit/pack info as scraped |
| parsed_price_cents | INTEGER | | Parsed price in cents |
| parsed_pack_size | DECIMAL(10,3) | | Parsed pack size |
| parsed_pack_unit | VARCHAR(20) | | Parsed unit type |
| dist_ingredient_id | UUID | FK → dist_ingredients | NULL if unmapped |
| mapping_confidence | DECIMAL(3,2) | | 0.0-1.0 confidence score |
| mapping_status | VARCHAR(20) | | 'auto_matched', 'llm_suggested', 'human_verified', 'unmapped' |
| created_at | TIMESTAMP | DEFAULT NOW() | |

**Index**: (distributor_id, raw_sku) for matching

## Indexes

```sql
-- Performance indexes
CREATE INDEX idx_price_history_lookup ON price_history(dist_ingredient_id, effective_date DESC);
CREATE INDEX idx_invoices_unpaid ON invoices(distributor_id) WHERE paid_at IS NULL;
CREATE INDEX idx_disputes_open ON disputes(status) WHERE status = 'open';
CREATE INDEX idx_orders_status ON orders(distributor_id, status);
CREATE INDEX idx_daily_sales_date ON daily_sales(sale_date DESC);

-- Foreign key indexes (PostgreSQL doesn't auto-create these)
CREATE INDEX idx_dist_ingredients_distributor ON dist_ingredients(distributor_id);
CREATE INDEX idx_dist_ingredients_ingredient ON dist_ingredients(ingredient_id);
CREATE INDEX idx_recipe_ingredients_recipe ON recipe_ingredients(recipe_id);
CREATE INDEX idx_invoice_lines_invoice ON invoice_lines(invoice_id);
CREATE INDEX idx_invoice_lines_parent ON invoice_lines(parent_line_id) WHERE parent_line_id IS NOT NULL;
CREATE INDEX idx_order_lines_order ON order_lines(order_id);

-- Price history source filtering
CREATE INDEX idx_price_history_source ON price_history(dist_ingredient_id, source, effective_date DESC);

-- Catalog scraping indexes
CREATE INDEX idx_catalog_scrapes_distributor ON catalog_scrapes(distributor_id, started_at DESC);
CREATE INDEX idx_scraped_items_scrape ON scraped_items(scrape_id);
CREATE INDEX idx_scraped_items_unmapped ON scraped_items(distributor_id) WHERE mapping_status = 'unmapped';
CREATE INDEX idx_scraped_items_sku ON scraped_items(distributor_id, raw_sku);
```

## Views

### v_invoice_line_effective_price
Calculate effective price after credits/allowances.

```sql
CREATE VIEW v_invoice_line_effective_price AS
SELECT
    product.id,
    product.invoice_id,
    product.dist_ingredient_id,
    product.quantity,
    product.extended_price_cents AS list_price_cents,
    COALESCE(SUM(credits.extended_price_cents), 0) AS credit_cents,
    product.extended_price_cents + COALESCE(SUM(credits.extended_price_cents), 0) AS effective_price_cents,
    CASE
        WHEN product.quantity > 0
        THEN (product.extended_price_cents + COALESCE(SUM(credits.extended_price_cents), 0)) / product.quantity
        ELSE NULL
    END AS effective_unit_price_cents
FROM invoice_lines product
LEFT JOIN invoice_lines credits
    ON credits.parent_line_id = product.id
    AND credits.line_type = 'credit'
WHERE product.line_type = 'product'
GROUP BY product.id, product.invoice_id, product.dist_ingredient_id,
         product.quantity, product.extended_price_cents;
```

### v_current_prices
Current price for each distributor ingredient, by source.

```sql
CREATE VIEW v_current_prices AS
SELECT DISTINCT ON (dist_ingredient_id, source)
    ph.dist_ingredient_id,
    ph.price_cents,
    ph.effective_date,
    ph.source
FROM price_history ph
ORDER BY dist_ingredient_id, source, effective_date DESC;
```

### v_current_invoice_prices
Most recent price we actually paid (from invoices, after credits).

```sql
CREATE VIEW v_current_invoice_prices AS
SELECT DISTINCT ON (dist_ingredient_id)
    ph.dist_ingredient_id,
    ph.price_cents,
    ph.effective_date,
    ph.source_reference
FROM price_history ph
WHERE ph.source = 'invoice'
ORDER BY dist_ingredient_id, effective_date DESC;
```

### v_current_catalog_prices
Most recent advertised price (from catalog scrapes).

```sql
CREATE VIEW v_current_catalog_prices AS
SELECT DISTINCT ON (dist_ingredient_id)
    ph.dist_ingredient_id,
    ph.price_cents,
    ph.effective_date,
    ph.source_reference
FROM price_history ph
WHERE ph.source = 'catalog'
ORDER BY dist_ingredient_id, effective_date DESC;
```

### v_ingredient_price_comparison
Compare prices across distributors for each canonical ingredient.
Uses invoice prices (what we actually paid) for recipe costing.

```sql
CREATE VIEW v_ingredient_price_comparison AS
SELECT
    i.id AS ingredient_id,
    i.name AS ingredient_name,
    d.id AS distributor_id,
    d.name AS distributor_name,
    di.sku,
    di.description,
    di.pack_size,
    di.pack_unit,
    di.units_per_pack,
    di.grams_per_unit,
    ip.price_cents AS invoice_price_cents,
    ip.effective_date AS last_invoice_date,
    cp.price_cents AS catalog_price_cents,
    cp.effective_date AS last_catalog_date,
    -- Calculate price per base unit (gram or ml) from invoice price
    CASE
        WHEN di.grams_per_unit > 0 AND di.pack_size > 0 AND di.units_per_pack > 0
        THEN ip.price_cents / (di.pack_size * di.units_per_pack * di.grams_per_unit)
        ELSE NULL
    END AS price_per_gram_cents
FROM ingredients i
JOIN dist_ingredients di ON di.ingredient_id = i.id
JOIN distributors d ON d.id = di.distributor_id
LEFT JOIN v_current_invoice_prices ip ON ip.dist_ingredient_id = di.id
LEFT JOIN v_current_catalog_prices cp ON cp.dist_ingredient_id = di.id
WHERE di.is_active = TRUE AND d.is_active = TRUE;
```

### v_recipe_costs
Current cost to produce each recipe.

```sql
CREATE VIEW v_recipe_costs AS
SELECT 
    r.id AS recipe_id,
    r.name AS recipe_name,
    r.yield_quantity,
    r.yield_unit,
    SUM(
        ri.quantity_grams * 
        (SELECT MIN(price_per_gram_cents) FROM v_ingredient_price_comparison WHERE ingredient_id = i.id)
    ) AS total_cost_cents,
    SUM(
        ri.quantity_grams * 
        (SELECT MIN(price_per_gram_cents) FROM v_ingredient_price_comparison WHERE ingredient_id = i.id)
    ) / r.yield_quantity AS cost_per_unit_cents
FROM recipes r
JOIN recipe_ingredients ri ON ri.recipe_id = r.id
JOIN ingredients i ON i.id = ri.ingredient_id
GROUP BY r.id, r.name, r.yield_quantity, r.yield_unit;
```

## Migration Strategy

1. **Phase 0**: Create core tables (distributors, ingredients, dist_ingredients)
2. **Phase 1**: Add invoices, invoice_lines, price_history
3. **Phase 2**: Add recipes, recipe_ingredients, menu_items; add catalog_scrapes, scraped_items for price intelligence
4. **Phase 3**: Add orders, order_lines, disputes
5. **Phase 4**: Add daily_sales, inventory tables

Use a migration tool like Alembic (Python) to manage schema versions.

---

## Pricing Architecture

### Two Price Sources

| Source | Description | Use Cases |
|--------|-------------|-----------|
| `invoice` | What we actually paid (net of credits/allowances) | Recipe costing, menu pricing, margin tracking |
| `catalog` | Current advertised prices from distributor portals | Purchasing suggestions, order planning, price trend analysis |

Both sources populate `price_history` with different `source` values.

### Price Flow: Invoice → price_history

```
1. Invoice PDF arrives
        ↓
2. Claude Haiku parses line items
        ↓
3. Human reviews/approves (if needed)
        ↓
4. For each product line:
   - Calculate effective price = list price + credits (via parent_line_id)
   - Match to dist_ingredient via SKU
   - Insert into price_history with source='invoice'
```

### Price Flow: Catalog → price_history

```
1. Scraper runs on schedule
        ↓
2. Pulls current prices from distributor portal
        ↓
3. Matches to dist_ingredients via SKU
        ↓
4. Insert into price_history with source='catalog'
```

### Price Normalization for Recipe Costing

To compare prices across distributors and calculate recipe costs:

```
total_grams = pack_size × units_per_pack × grams_per_unit
price_per_gram = price_cents / total_grams
ingredient_cost = recipe_quantity_grams × price_per_gram
```

Example: Oat milk case
- pack_size = 12 (cartons)
- units_per_pack = 1
- grams_per_unit = 907.2 (32oz × 28.35g/oz)
- price_cents = 3549 ($35.49)
- price_per_gram = 3549 / (12 × 1 × 907.2) = 0.326¢/g

### Price Discrepancy Detection

When an invoice arrives, flag potential issues:

1. **vs Order expectation**: Compare `invoice_line.effective_unit_price_cents` to `order_line.expected_price_cents`
2. **vs Current catalog**: Compare invoice price to most recent catalog price

Both comparisons are useful:
- First catches undisclosed price changes between order and delivery
- Second catches stale catalog data or seasonal pricing
