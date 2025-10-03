"""Update crawl_period constraint to use GNews valid values

Revision ID: 010_crawl_period_values
Revises: 009_add_crawl_period
Create Date: 2025-10-03 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010_crawl_period_values'
down_revision: Union[str, None] = '009_add_crawl_period'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update crawl_period CHECK constraint to use explicit GNews valid values."""
    # Drop old regex-based constraint
    op.drop_constraint('crawl_period_format_valid', 'categories', type_='check')

    # Add new constraint with GNews supported values
    op.create_check_constraint(
        'crawl_period_format_valid',
        'categories',
        "crawl_period IS NULL OR crawl_period IN ('1h', '2h', '6h', '12h', '1d', '2d', '7d', '1m', '3m', '6m', '1y')"
    )


def downgrade() -> None:
    """Revert to regex-based constraint."""
    # Drop new constraint
    op.drop_constraint('crawl_period_format_valid', 'categories', type_='check')

    # Restore old regex constraint
    op.create_check_constraint(
        'crawl_period_format_valid',
        'categories',
        "crawl_period IS NULL OR crawl_period ~ '^\\d+[hdmwy]$'"
    )
