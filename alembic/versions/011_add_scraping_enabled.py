"""Add scraping_enabled to distributors.

Revision ID: 011
Revises: 010
Create Date: 2024-12-21
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "distributors",
        sa.Column("scraping_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade():
    op.drop_column("distributors", "scraping_enabled")
