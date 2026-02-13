"""Add yield_weight_grams to recipes for accurate component costing.

Revision ID: 012
Revises: 011
Create Date: 2025-12-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    # Add yield_weight_grams for recipes where volume yield doesn't match weight
    # (e.g., syrups where water cooks off)
    op.add_column(
        "recipes",
        sa.Column("yield_weight_grams", sa.Numeric(12, 3), nullable=True),
    )


def downgrade():
    op.drop_column("recipes", "yield_weight_grams")
