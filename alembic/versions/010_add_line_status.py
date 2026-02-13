"""Add status column to invoice_lines for line-by-line confirmation.

Revision ID: 010
Revises: 009
Create Date: 2024-12-21
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    # Add status column to invoice_lines
    # Values: 'pending' (default), 'confirmed', 'removed'
    op.add_column(
        'invoice_lines',
        sa.Column('line_status', sa.String(20), server_default='pending', nullable=False)
    )

    # Add index for filtering by status
    op.create_index('idx_invoice_lines_status', 'invoice_lines', ['line_status'])


def downgrade():
    op.drop_index('idx_invoice_lines_status')
    op.drop_column('invoice_lines', 'line_status')
