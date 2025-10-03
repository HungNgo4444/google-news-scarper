"""Add 5 and 15 minute intervals to schedule_interval_valid constraint

Revision ID: 012_schedule_intervals
Revises: 011_article_categories
Create Date: 2025-10-03 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '012_schedule_intervals'
down_revision: Union[str, None] = '011_article_categories'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update schedule_interval_valid constraint to include 5 and 15 minutes."""

    # Drop the old constraint
    op.drop_constraint('schedule_interval_valid', 'categories', type_='check')

    # Create the new constraint with 5 and 15 minutes added
    op.create_check_constraint(
        'schedule_interval_valid',
        'categories',
        'schedule_interval_minutes IS NULL OR schedule_interval_minutes IN (1, 5, 15, 30, 60, 1440)'
    )


def downgrade() -> None:
    """Revert to the old constraint without 5 and 15 minutes."""

    # Drop the new constraint
    op.drop_constraint('schedule_interval_valid', 'categories', type_='check')

    # Recreate the old constraint
    op.create_check_constraint(
        'schedule_interval_valid',
        'categories',
        'schedule_interval_minutes IS NULL OR schedule_interval_minutes IN (1, 30, 60, 1440)'
    )
