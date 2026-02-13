"""Add unit column to invoice_lines.

Revision ID: 005
Revises: 004
Create Date: 2025-12-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add unit column to store the unit of measure (EA, OZ, LB, CS, etc.)
    op.add_column('invoice_lines', sa.Column('unit', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column('invoice_lines', 'unit')
