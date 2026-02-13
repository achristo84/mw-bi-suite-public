"""Enable ordering for distributor API clients.

Enables ordering_enabled and sets platform_id + api_config for distributors
with working API clients. Configure base_url in api_config for each distributor.

Revision ID: 015
Revises: 014
Create Date: 2024-12-22
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    # Enable ordering for food distributors with working API clients.
    # base_url should be configured per-deployment in each distributor's api_config.
    # The platform_id maps to the correct client class in distributor_client.py.

    # Valley Foods (primary) - OAuth2 platform
    op.execute("""
        UPDATE distributors
        SET ordering_enabled = true,
            platform_id = 'valleyfoods',
            capture_status = 'search_captured',
            api_config = COALESCE(api_config, '{}'::jsonb)
        WHERE LOWER(name) LIKE '%valley%food%' AND LOWER(name) NOT LIKE '%mountain%'
    """)

    # Mountain Produce (shared platform with Valley Foods)
    op.execute("""
        UPDATE distributors
        SET ordering_enabled = true,
            platform_id = 'valleyfoods',
            capture_status = 'search_captured',
            api_config = COALESCE(api_config, '{}'::jsonb)
        WHERE LOWER(name) LIKE '%mountain%produce%'
    """)

    # Metro Wholesale
    op.execute("""
        UPDATE distributors
        SET ordering_enabled = true,
            platform_id = 'metrowholesale',
            capture_status = 'search_captured',
            api_config = COALESCE(api_config, '{}'::jsonb)
        WHERE LOWER(name) LIKE '%metro%wholesale%'
    """)

    # Farm Direct
    op.execute("""
        UPDATE distributors
        SET ordering_enabled = true,
            platform_id = 'farmdirect',
            capture_status = 'search_captured',
            api_config = COALESCE(api_config, '{}'::jsonb)
        WHERE LOWER(name) LIKE '%farm%direct%'
    """)

    # Green Market
    op.execute("""
        UPDATE distributors
        SET ordering_enabled = true,
            platform_id = 'greenmarket',
            capture_status = 'search_captured',
            api_config = COALESCE(api_config, '{}'::jsonb)
        WHERE LOWER(name) LIKE '%green%market%'
    """)


def downgrade():
    # Disable ordering for all distributors we enabled
    op.execute("""
        UPDATE distributors
        SET ordering_enabled = false,
            platform_id = NULL,
            capture_status = 'not_started',
            api_config = NULL
        WHERE platform_id IN ('valleyfoods', 'metrowholesale', 'farmdirect', 'greenmarket')
    """)
