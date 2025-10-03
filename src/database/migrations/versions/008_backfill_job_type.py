"""backfill job_type for existing crawl_jobs

Revision ID: 008_backfill_job_type
Revises: 007_add_category_scheduling
Create Date: 2025-10-02 08:00:00.000000

This is a compensating migration for environments where migration 007
was already applied without the backfill statement. It ensures all
existing crawl_jobs have job_type='ON_DEMAND' instead of NULL.

Context:
- Migration 007 added job_type column with server_default='ON_DEMAND'
- Original migration 007 did NOT include backfill UPDATE statement
- QA review identified this caused existing jobs to display incorrectly
- Fix was added to 007 (lines 83-87) but some environments may have
  already run the original version
- This migration provides idempotent backfill for those environments
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '008_backfill_job_type'
down_revision: Union[str, None] = '007_add_category_scheduling'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Backfill job_type for existing crawl_jobs.

    This migration is idempotent - it only updates rows where job_type is NULL.
    If migration 007 already included the backfill, this will update 0 rows.
    """

    # Backfill existing jobs with ON_DEMAND type
    # This is safe to run multiple times (idempotent)
    op.execute("""
        UPDATE crawl_jobs
        SET job_type = 'ON_DEMAND'
        WHERE job_type IS NULL
    """)


def downgrade() -> None:
    """No downgrade needed - this is a data fix only.

    Downgrading would set job_type back to NULL which would break the system.
    The downgrade is intentionally a no-op.
    """
    pass
