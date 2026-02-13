"""Add recipe_components table for sub-recipe hierarchy

Revision ID: 006
Revises: 005
Create Date: 2025-12-19

Enables recipes to use other recipes as components:
- Chocolate syrup (sub-recipe) used in Mocha (final recipe)
- Allows proper cost roll-up through component hierarchy
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Recipe components - links a recipe to sub-recipes it uses
    op.create_table(
        "recipe_components",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "recipe_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "component_recipe_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "quantity",
            sa.Numeric(10, 3),
            nullable=False,
        ),  # Amount of component's yield_unit needed
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        # Prevent duplicate component entries
        sa.UniqueConstraint(
            "recipe_id", "component_recipe_id", name="uq_recipe_components"
        ),
        # Prevent self-reference
        sa.CheckConstraint(
            "recipe_id != component_recipe_id", name="ck_no_self_reference"
        ),
    )
    op.create_index(
        "idx_recipe_components_recipe", "recipe_components", ["recipe_id"]
    )
    op.create_index(
        "idx_recipe_components_component", "recipe_components", ["component_recipe_id"]
    )


def downgrade() -> None:
    op.drop_table("recipe_components")
