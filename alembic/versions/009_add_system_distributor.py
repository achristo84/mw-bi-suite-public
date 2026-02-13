"""Add system distributor for one-off/manual purchases.

Revision ID: 009
Revises: 008
Create Date: 2024-12-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None

# Fixed UUID for the system distributor so we can reference it in code
ONEOFF_DISTRIBUTOR_ID = '00000000-0000-0000-0000-000000000001'


def upgrade():
    # Insert the system distributor for one-off/manual purchases
    op.execute(f"""
        INSERT INTO distributors (id, name, vendor_category, is_active, notes)
        VALUES (
            '{ONEOFF_DISTRIBUTOR_ID}',
            'One-off / Manual',
            'system',
            true,
            'System distributor for one-off purchases and manual price entries without a regular distributor.'
        )
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade():
    op.execute(f"""
        DELETE FROM distributors WHERE id = '{ONEOFF_DISTRIBUTOR_ID}'
    """)
