"""Add invoice review support.

Revision ID: 004
Revises: 003
Create Date: 2025-12-19

- Add filename_pattern to distributors for multi-distributor email matching
- Add source column to invoices (email, manual, upload)
- Add review_status to invoices for workflow tracking
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add filename_pattern column to distributors
    # Used to distinguish invoices from distributors sharing the same email
    op.add_column(
        'distributors',
        sa.Column('filename_pattern', sa.String(100), nullable=True,
                  comment='Regex pattern to match invoice filenames (e.g., pfs_bur_)')
    )

    # Add source column to invoices
    # Tracks how the invoice was ingested
    op.add_column(
        'invoices',
        sa.Column('source', sa.String(20), nullable=False, server_default='email',
                  comment='How invoice was created: email, manual, upload')
    )

    # Add review_status column to invoices
    # Tracks approval workflow: pending, approved, rejected
    op.add_column(
        'invoices',
        sa.Column('review_status', sa.String(20), nullable=False, server_default='pending',
                  comment='Review workflow status: pending, approved, rejected')
    )

    # Index for filtering by review status
    op.create_index(
        'idx_invoices_review_status',
        'invoices',
        ['review_status']
    )


def downgrade() -> None:
    op.drop_index('idx_invoices_review_status')
    op.drop_column('invoices', 'review_status')
    op.drop_column('invoices', 'source')
    op.drop_column('distributors', 'filename_pattern')
