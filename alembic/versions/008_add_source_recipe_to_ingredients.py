"""Add source_recipe_id to ingredients for component costing.

Revision ID: 008
Revises: 007
Create Date: 2024-12-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    # Add source_recipe_id to ingredients table
    # This links component ingredients to their source recipe for cost calculation
    op.add_column(
        'ingredients',
        sa.Column(
            'source_recipe_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('recipes.id', ondelete='SET NULL'),
            nullable=True
        )
    )

    # Add index for looking up ingredients by source recipe
    op.create_index(
        'idx_ingredients_source_recipe',
        'ingredients',
        ['source_recipe_id']
    )


def downgrade():
    op.drop_index('idx_ingredients_source_recipe', table_name='ingredients')
    op.drop_column('ingredients', 'source_recipe_id')
