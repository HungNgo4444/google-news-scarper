"""add category scheduling support

Revision ID: 007_add_category_scheduling
Revises: 006_add_language_country
Create Date: 2025-10-02 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '007_add_category_scheduling'
down_revision: Union[str, None] = '006_add_language_country'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add scheduling columns to categories table and job_type to crawl_jobs table."""

    # Add scheduling columns to categories table
    op.add_column('categories',
        sa.Column('schedule_enabled', sa.Boolean(), nullable=False, server_default='false',
                  comment='Whether auto-crawl schedule is enabled')
    )

    op.add_column('categories',
        sa.Column('schedule_interval_minutes', sa.Integer(), nullable=True,
                  comment='Schedule interval in minutes (1, 30, 60, 1440)')
    )

    op.add_column('categories',
        sa.Column('last_scheduled_run_at', sa.DateTime(timezone=True), nullable=True,
                  comment='Timestamp of last scheduled crawl execution')
    )

    op.add_column('categories',
        sa.Column('next_scheduled_run_at', sa.DateTime(timezone=True), nullable=True,
                  comment='Timestamp of next scheduled crawl')
    )

    # Add indexes for schedule queries
    op.create_index('idx_categories_schedule_enabled', 'categories', ['schedule_enabled'])

    # Partial index for enabled schedules only (PostgreSQL-specific)
    op.execute("""
        CREATE INDEX idx_categories_next_run
        ON categories(next_scheduled_run_at)
        WHERE schedule_enabled = true
    """)

    # Add check constraints for schedule validation
    op.create_check_constraint(
        'schedule_interval_valid',
        'categories',
        'schedule_interval_minutes IS NULL OR schedule_interval_minutes IN (1, 30, 60, 1440)'
    )

    op.create_check_constraint(
        'schedule_enabled_requires_interval',
        'categories',
        '(schedule_enabled = false) OR (schedule_enabled = true AND schedule_interval_minutes IS NOT NULL)'
    )

    # Create job_type enum first
    op.execute("CREATE TYPE job_type_enum AS ENUM ('SCHEDULED', 'ON_DEMAND')")

    # Add job_type column to crawl_jobs table
    op.add_column('crawl_jobs',
        sa.Column('job_type',
                  sa.Enum('SCHEDULED', 'ON_DEMAND', name='job_type_enum', create_type=False),
                  nullable=False,
                  server_default='ON_DEMAND',
                  comment='Job trigger type: SCHEDULED or ON_DEMAND')
    )

    # Add index for job type filtering
    op.create_index('idx_crawl_jobs_job_type', 'crawl_jobs', ['job_type'])

    # Backfill existing jobs with ON_DEMAND type
    op.execute("""
        UPDATE crawl_jobs
        SET job_type = 'ON_DEMAND'
        WHERE job_type IS NULL
    """)


def downgrade() -> None:
    """Remove scheduling columns and job_type enum."""

    # Drop crawl_jobs job_type index and column
    op.drop_index('idx_crawl_jobs_job_type', table_name='crawl_jobs')
    op.drop_column('crawl_jobs', 'job_type')

    # Drop job_type enum type
    op.execute('DROP TYPE IF EXISTS job_type_enum')

    # Drop categories schedule constraints
    op.drop_constraint('schedule_enabled_requires_interval', 'categories', type_='check')
    op.drop_constraint('schedule_interval_valid', 'categories', type_='check')

    # Drop categories schedule indexes
    op.drop_index('idx_categories_next_run', table_name='categories')
    op.drop_index('idx_categories_schedule_enabled', table_name='categories')

    # Drop categories schedule columns
    op.drop_column('categories', 'next_scheduled_run_at')
    op.drop_column('categories', 'last_scheduled_run_at')
    op.drop_column('categories', 'schedule_interval_minutes')
    op.drop_column('categories', 'schedule_enabled')
