"""Initial schema - all core tables

Revision ID: 001
Revises:
Create Date: 2024-12-11

Creates all tables for Phase 0-1:
- distributors
- ingredients
- dist_ingredients
- price_history
- invoices
- invoice_lines
- orders
- order_lines
- disputes
- recipes
- recipe_ingredients
- menu_items
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === DISTRIBUTORS ===
    op.create_table(
        "distributors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("rep_name", sa.String(100)),
        sa.Column("rep_email", sa.String(255)),
        sa.Column("rep_phone", sa.String(20)),
        sa.Column("portal_url", sa.String(500)),
        sa.Column("portal_username", sa.String(100)),
        sa.Column("portal_password_encrypted", sa.Text),
        sa.Column("scraper_module", sa.String(100)),
        sa.Column("scrape_frequency", sa.String(20), server_default="weekly"),
        sa.Column("last_successful_scrape", sa.TIMESTAMP),
        sa.Column("order_email", sa.String(255)),
        sa.Column("minimum_order_cents", sa.Integer, server_default="0"),
        sa.Column("delivery_days", postgresql.ARRAY(sa.String(50))),
        sa.Column("order_deadline", sa.String(100)),
        sa.Column("payment_terms_days", sa.Integer, server_default="15"),
        sa.Column("vendor_category", sa.String(50)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
    )

    # === INGREDIENTS ===
    op.create_table(
        "ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("category", sa.String(50)),
        sa.Column("base_unit", sa.String(10), nullable=False),
        sa.Column("storage_type", sa.String(20)),
        sa.Column("shelf_life_days", sa.Integer),
        sa.Column("par_level_base_units", sa.Numeric(10, 2)),
        sa.Column("yield_factor", sa.Numeric(4, 3), server_default="1.0"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
    )

    # === DIST_INGREDIENTS ===
    op.create_table(
        "dist_ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("distributor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("distributors.id"), nullable=False),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingredients.id")),
        sa.Column("sku", sa.String(50)),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("pack_size", sa.Numeric(10, 3)),
        sa.Column("pack_unit", sa.String(20)),
        sa.Column("units_per_pack", sa.Integer, server_default="1"),
        sa.Column("grams_per_unit", sa.Numeric(12, 4)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("quality_tier", sa.String(20)),
        sa.Column("quality_notes", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.UniqueConstraint("distributor_id", "sku", name="uq_dist_ingredients_dist_sku"),
    )
    op.create_index("idx_dist_ingredients_distributor", "dist_ingredients", ["distributor_id"])
    op.create_index("idx_dist_ingredients_ingredient", "dist_ingredients", ["ingredient_id"])

    # === PRICE_HISTORY ===
    op.create_table(
        "price_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dist_ingredient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dist_ingredients.id"), nullable=False),
        sa.Column("price_cents", sa.Integer, nullable=False),
        sa.Column("effective_date", sa.DATE, nullable=False),
        sa.Column("source", sa.String(20)),
        sa.Column("source_reference", sa.String(100)),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
    )
    op.create_index("idx_price_history_lookup", "price_history", ["dist_ingredient_id", "effective_date"])
    op.create_index("idx_price_history_source", "price_history", ["dist_ingredient_id", "source", "effective_date"])

    # === ORDERS ===
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("distributor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("distributors.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("submitted_at", sa.TIMESTAMP),
        sa.Column("expected_delivery", sa.DATE),
        sa.Column("received_at", sa.TIMESTAMP),
        sa.Column("submitted_by", sa.String(50)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
    )
    op.create_index("idx_orders_status", "orders", ["distributor_id", "status"])

    # === ORDER_LINES ===
    op.create_table(
        "order_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("dist_ingredient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dist_ingredients.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False),
        sa.Column("expected_price_cents", sa.Integer),
        sa.Column("actual_quantity", sa.Numeric(10, 3)),
        sa.Column("actual_price_cents", sa.Integer),
        sa.Column("notes", sa.Text),
    )
    op.create_index("idx_order_lines_order", "order_lines", ["order_id"])

    # === INVOICES ===
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("distributor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("distributors.id"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id")),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("invoice_date", sa.DATE, nullable=False),
        sa.Column("delivery_date", sa.DATE),
        sa.Column("due_date", sa.DATE),
        sa.Column("account_number", sa.String(50)),
        sa.Column("sales_rep_name", sa.String(100)),
        sa.Column("sales_order_number", sa.String(50)),
        sa.Column("subtotal_cents", sa.Integer),
        sa.Column("tax_cents", sa.Integer),
        sa.Column("total_cents", sa.Integer, nullable=False),
        sa.Column("pdf_path", sa.String(500)),
        sa.Column("raw_text", sa.Text),
        sa.Column("parsed_at", sa.TIMESTAMP),
        sa.Column("parse_confidence", sa.Numeric(3, 2)),
        sa.Column("reviewed_by", sa.String(50)),
        sa.Column("reviewed_at", sa.TIMESTAMP),
        sa.Column("paid_at", sa.TIMESTAMP),
        sa.Column("payment_reference", sa.String(100)),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.UniqueConstraint("distributor_id", "invoice_number", name="uq_invoices_dist_number"),
    )
    op.create_index(
        "idx_invoices_unpaid",
        "invoices",
        ["distributor_id"],
        postgresql_where=sa.text("paid_at IS NULL"),
    )

    # === INVOICE_LINES ===
    op.create_table(
        "invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("dist_ingredient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dist_ingredients.id")),
        sa.Column("raw_description", sa.String(255), nullable=False),
        sa.Column("raw_sku", sa.String(50)),
        sa.Column("quantity_ordered", sa.Numeric(10, 3)),
        sa.Column("quantity", sa.Numeric(10, 3)),
        sa.Column("unit_price_cents", sa.Integer),
        sa.Column("extended_price_cents", sa.Integer),
        sa.Column("is_taxable", sa.Boolean, server_default="false"),
        sa.Column("line_type", sa.String(20), server_default="product"),
        sa.Column("parent_line_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoice_lines.id")),
        sa.Column("matched_order_line_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("order_lines.id")),
        sa.Column("match_status", sa.String(20)),
        sa.Column("notes", sa.Text),
    )
    op.create_index("idx_invoice_lines_invoice", "invoice_lines", ["invoice_id"])
    op.create_index(
        "idx_invoice_lines_parent",
        "invoice_lines",
        ["parent_line_id"],
        postgresql_where=sa.text("parent_line_id IS NOT NULL"),
    )

    # === DISPUTES ===
    op.create_table(
        "disputes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("invoice_line_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoice_lines.id")),
        sa.Column("dispute_type", sa.String(30), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("amount_disputed_cents", sa.Integer),
        sa.Column("photo_paths", postgresql.ARRAY(sa.String(500))),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("resolution_notes", sa.Text),
        sa.Column("credit_received_cents", sa.Integer),
        sa.Column("resolved_at", sa.TIMESTAMP),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_disputes_open",
        "disputes",
        ["status"],
        postgresql_where=sa.text("status = 'open'"),
    )

    # === RECIPES ===
    op.create_table(
        "recipes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("yield_quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("yield_unit", sa.String(20), nullable=False),
        sa.Column("instructions", sa.Text),
        sa.Column("prep_time_minutes", sa.Integer),
        sa.Column("cook_time_minutes", sa.Integer),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
    )

    # === RECIPE_INGREDIENTS ===
    op.create_table(
        "recipe_ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("recipe_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recipes.id"), nullable=False),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingredients.id"), nullable=False),
        sa.Column("quantity_grams", sa.Numeric(10, 3), nullable=False),
        sa.Column("prep_note", sa.String(100)),
        sa.Column("is_optional", sa.Boolean, server_default="false"),
        sa.UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_ingredients"),
    )
    op.create_index("idx_recipe_ingredients_recipe", "recipe_ingredients", ["recipe_id"])

    # === MENU_ITEMS ===
    op.create_table(
        "menu_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("recipe_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recipes.id")),
        sa.Column("portion_of_recipe", sa.Numeric(5, 4), server_default="1.0"),
        sa.Column("menu_price_cents", sa.Integer, nullable=False),
        sa.Column("category", sa.String(50)),
        sa.Column("toast_id", sa.String(50)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("menu_items")
    op.drop_table("recipe_ingredients")
    op.drop_table("recipes")
    op.drop_table("disputes")
    op.drop_table("invoice_lines")
    op.drop_table("invoices")
    op.drop_table("order_lines")
    op.drop_table("orders")
    op.drop_table("price_history")
    op.drop_table("dist_ingredients")
    op.drop_table("ingredients")
    op.drop_table("distributors")
