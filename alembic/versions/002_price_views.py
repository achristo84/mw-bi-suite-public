"""Price intelligence views

Revision ID: 002
Revises: 001
Create Date: 2024-12-11

Creates views for price analysis:
- v_invoice_line_effective_price
- v_current_invoice_prices
- v_current_catalog_prices
- v_ingredient_price_comparison
- v_recipe_costs
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # View: Calculate effective price after credits/allowances
    op.execute("""
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
    """)

    # View: Most recent price we actually paid (from invoices)
    op.execute("""
        CREATE VIEW v_current_invoice_prices AS
        SELECT DISTINCT ON (dist_ingredient_id)
            ph.dist_ingredient_id,
            ph.price_cents,
            ph.effective_date,
            ph.source_reference
        FROM price_history ph
        WHERE ph.source = 'invoice'
        ORDER BY dist_ingredient_id, effective_date DESC;
    """)

    # View: Most recent advertised price (from catalog scrapes)
    op.execute("""
        CREATE VIEW v_current_catalog_prices AS
        SELECT DISTINCT ON (dist_ingredient_id)
            ph.dist_ingredient_id,
            ph.price_cents,
            ph.effective_date,
            ph.source_reference
        FROM price_history ph
        WHERE ph.source = 'catalog'
        ORDER BY dist_ingredient_id, effective_date DESC;
    """)

    # View: Compare prices across distributors for each canonical ingredient
    op.execute("""
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
    """)

    # View: Current cost to produce each recipe
    op.execute("""
        CREATE VIEW v_recipe_costs AS
        SELECT
            r.id AS recipe_id,
            r.name AS recipe_name,
            r.yield_quantity,
            r.yield_unit,
            SUM(
                ri.quantity_grams *
                (SELECT MIN(price_per_gram_cents)
                 FROM v_ingredient_price_comparison
                 WHERE ingredient_id = i.id)
            ) AS total_cost_cents,
            CASE
                WHEN r.yield_quantity > 0
                THEN SUM(
                    ri.quantity_grams *
                    (SELECT MIN(price_per_gram_cents)
                     FROM v_ingredient_price_comparison
                     WHERE ingredient_id = i.id)
                ) / r.yield_quantity
                ELSE NULL
            END AS cost_per_unit_cents
        FROM recipes r
        JOIN recipe_ingredients ri ON ri.recipe_id = r.id
        JOIN ingredients i ON i.id = ri.ingredient_id
        GROUP BY r.id, r.name, r.yield_quantity, r.yield_unit;
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_recipe_costs;")
    op.execute("DROP VIEW IF EXISTS v_ingredient_price_comparison;")
    op.execute("DROP VIEW IF EXISTS v_current_catalog_prices;")
    op.execute("DROP VIEW IF EXISTS v_current_invoice_prices;")
    op.execute("DROP VIEW IF EXISTS v_invoice_line_effective_price;")
