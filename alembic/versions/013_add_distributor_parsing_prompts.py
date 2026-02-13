"""Add parsing prompt columns to distributors table.

Revision ID: 013
Revises: 012
Create Date: 2024-12-22
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    # Add custom parsing prompt columns for each content type
    op.add_column(
        "distributors",
        sa.Column("parsing_prompt_pdf", sa.Text(), nullable=True),
    )
    op.add_column(
        "distributors",
        sa.Column("parsing_prompt_email", sa.Text(), nullable=True),
    )
    op.add_column(
        "distributors",
        sa.Column("parsing_prompt_screenshot", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("distributors", "parsing_prompt_screenshot")
    op.drop_column("distributors", "parsing_prompt_email")
    op.drop_column("distributors", "parsing_prompt_pdf")
