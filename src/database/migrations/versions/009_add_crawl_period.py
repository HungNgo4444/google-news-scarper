"""add crawl_period to categories

Revision ID: 009_add_crawl_period
Revises: 008_backfill_job_type
Create Date: 2025-10-02 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '009_add_crawl_period'
down_revision: Union[str, None] = '008_backfill_job_type'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add crawl_period column to categories table with format validation."""

    # Add crawl_period column
    op.add_column('categories',
        sa.Column('crawl_period', sa.String(10), nullable=True,
                  comment="Time period for scheduled crawls (e.g., '1h', '7d', '1m'). Format: number + unit (h=hours, d=days, m=months, w=weeks, y=years)")
    )

    # Add CHECK constraint for format validation
    # Pattern: one or more digits followed by h, d, m, w, or y
    op.create_check_constraint(
        'crawl_period_format_valid',
        'categories',
        "crawl_period IS NULL OR crawl_period ~ '^\\d+[hdmwy]$'"
    )


def downgrade() -> None:
    """Remove crawl_period column and its constraint."""

    # Drop check constraint
    op.drop_constraint('crawl_period_format_valid', 'categories', type_='check')

    # Drop column
    op.drop_column('categories', 'crawl_period')
