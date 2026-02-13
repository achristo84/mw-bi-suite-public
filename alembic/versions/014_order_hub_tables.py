"""Add Order Hub tables and extend distributors for ordering.

Creates the Order Hub infrastructure:
- order_list_items: Shared "need to order" list
- order_list_item_assignments: Links items to specific SKUs/distributors
- distributor_sessions: Cached API sessions for distributors

Extends distributors table with:
- order_minimum_items: Minimum item count if applicable
- order_cutoff_hours: Hours before delivery day for cutoff
- order_cutoff_time: Specific cutoff time
- api_config: JSON endpoints, auth patterns, headers
- platform_id: Groups distributors on same platform (e.g., "valleyfoods")
- capture_status: API capture progress tracking
- ordering_enabled: Whether ready for Order Hub

Also extends orders table with:
- confirmation_number: From distributor API response
- confirmation_data: Full API response JSON
- actual_delivery_date: When actually delivered

Revision ID: 014
Revises: 013
Create Date: 2024-12-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    # Extend distributors table with Order Hub fields
    op.add_column(
        "distributors",
        sa.Column("order_minimum_items", sa.Integer(), nullable=True),
    )
    op.add_column(
        "distributors",
        sa.Column("order_cutoff_hours", sa.Integer(), nullable=True),
    )
    op.add_column(
        "distributors",
        sa.Column("order_cutoff_time", sa.Time(), nullable=True),
    )
    op.add_column(
        "distributors",
        sa.Column("api_config", JSONB(), nullable=True),
    )
    op.add_column(
        "distributors",
        sa.Column("platform_id", sa.String(50), nullable=True),
    )
    op.add_column(
        "distributors",
        sa.Column(
            "capture_status",
            sa.String(20),
            nullable=False,
            server_default="not_started",
        ),
    )
    op.add_column(
        "distributors",
        sa.Column("ordering_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )

    # Extend orders table with confirmation tracking
    op.add_column(
        "orders",
        sa.Column("confirmation_number", sa.String(100), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("confirmation_data", JSONB(), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("actual_delivery_date", sa.Date(), nullable=True),
    )

    # Create order_list_items table
    op.create_table(
        "order_list_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.String(100), nullable=True),  # Freeform: "2 cases", "about 20 lbs"
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("ingredient_id", UUID(as_uuid=True), sa.ForeignKey("ingredients.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("idx_order_list_items_status", "order_list_items", ["status"])

    # Create order_list_item_assignments table
    op.create_table(
        "order_list_item_assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "order_list_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("order_list_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dist_ingredient_id",
            UUID(as_uuid=True),
            sa.ForeignKey("dist_ingredients.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "order_id",
            UUID(as_uuid=True),
            sa.ForeignKey("orders.id"),
            nullable=True,  # Linked when order is placed
        ),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_order_list_item_assignments_item",
        "order_list_item_assignments",
        ["order_list_item_id"],
    )

    # Create distributor_sessions table
    op.create_table(
        "distributor_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "distributor_id",
            UUID(as_uuid=True),
            sa.ForeignKey("distributors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cookies", JSONB(), nullable=True),
        sa.Column("headers", JSONB(), nullable=True),
        sa.Column("auth_token", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("last_used_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_distributor_sessions_distributor",
        "distributor_sessions",
        ["distributor_id"],
    )


def downgrade():
    # Drop new tables
    op.drop_index("idx_distributor_sessions_distributor")
    op.drop_table("distributor_sessions")
    op.drop_index("idx_order_list_item_assignments_item")
    op.drop_table("order_list_item_assignments")
    op.drop_index("idx_order_list_items_status")
    op.drop_table("order_list_items")

    # Drop orders extensions
    op.drop_column("orders", "actual_delivery_date")
    op.drop_column("orders", "confirmation_data")
    op.drop_column("orders", "confirmation_number")

    # Drop distributors extensions
    op.drop_column("distributors", "ordering_enabled")
    op.drop_column("distributors", "capture_status")
    op.drop_column("distributors", "platform_id")
    op.drop_column("distributors", "api_config")
    op.drop_column("distributors", "order_cutoff_time")
    op.drop_column("distributors", "order_cutoff_hours")
    op.drop_column("distributors", "order_minimum_items")
