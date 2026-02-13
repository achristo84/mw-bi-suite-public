"""Add ingredient_type column and menu_item_packaging table

Revision ID: 007
Revises: 006
Create Date: 2025-12-20

- Add ingredient_type to ingredients (raw, component, packaging)
- Create menu_item_packaging for packaging items with usage_rate
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add ingredient_type to ingredients table
    # Types: 'raw' (purchased), 'component' (made from recipe), 'packaging'
    op.add_column(
        "ingredients",
        sa.Column(
            "ingredient_type",
            sa.String(20),
            server_default="raw",
            nullable=False,
        ),
    )
    op.create_index(
        "idx_ingredients_type",
        "ingredients",
        ["ingredient_type"],
    )

    # Create menu_item_packaging table
    # Links menu items to packaging ingredients with usage_rate
    op.create_table(
        "menu_item_packaging",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "menu_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("menu_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ingredient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingredients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "quantity",
            sa.Numeric(10, 3),
            nullable=False,
            server_default="1",
        ),  # How many of this packaging item per menu item
        sa.Column(
            "usage_rate",
            sa.Numeric(4, 3),
            nullable=False,
            server_default="1.0",
        ),  # 0.0-1.0, e.g., 0.5 means used 50% of the time
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        # Prevent duplicate packaging entries per menu item
        sa.UniqueConstraint(
            "menu_item_id", "ingredient_id", name="uq_menu_item_packaging"
        ),
    )
    op.create_index(
        "idx_menu_item_packaging_menu_item",
        "menu_item_packaging",
        ["menu_item_id"],
    )


def downgrade() -> None:
    op.drop_table("menu_item_packaging")
    op.drop_index("idx_ingredients_type", table_name="ingredients")
    op.drop_column("ingredients", "ingredient_type")
