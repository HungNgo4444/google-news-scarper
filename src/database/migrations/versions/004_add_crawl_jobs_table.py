"""add crawl jobs table

Revision ID: 004_add_crawl_jobs
Revises: 
Create Date: 2025-09-12 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004_add_crawl_jobs'
down_revision: Union[str, None] = '003_add_articles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add categories and crawl_jobs tables with related indexes."""
    # First create categories table if it doesn't exist
    op.create_table('categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('keywords', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        if_not_exists=True
    )
    
    # Create indexes for categories table
    op.create_index('idx_categories_name', 'categories', ['name'], if_not_exists=True)
    op.create_index('idx_categories_is_active', 'categories', ['is_active'], if_not_exists=True)
    op.create_index('idx_categories_keywords_gin', 'categories', ['keywords'], postgresql_using='gin', if_not_exists=True)
    
    # Create crawl job status enum
    crawl_job_status_enum = sa.Enum(
        'pending',
        'running',
        'completed',
        'failed',
        name='crawljobstatus',
        create_type=True
    )
    
    # Create crawl_jobs table
    op.create_table('crawl_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', crawl_job_status_enum, nullable=False, server_default='pending'),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('articles_found', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('articles_saved', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('job_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('correlation_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint('articles_found >= 0', name='articles_found_non_negative'),
        sa.CheckConstraint('articles_saved >= 0', name='articles_saved_non_negative'),
        sa.CheckConstraint('articles_saved <= articles_found', name='articles_saved_not_exceed_found'),
        sa.CheckConstraint('retry_count >= 0', name='retry_count_non_negative'),
        sa.CheckConstraint('retry_count <= 10', name='retry_count_max_limit'),
        sa.CheckConstraint(
            "(started_at IS NULL AND status = 'pending') OR (started_at IS NOT NULL AND status != 'pending')",
            name='started_at_status_consistency'
        ),
        sa.CheckConstraint(
            "(completed_at IS NULL AND status IN ('pending', 'running')) OR (completed_at IS NOT NULL AND status IN ('completed', 'failed'))",
            name='completed_at_status_consistency'
        ),
        sa.CheckConstraint(
            "(started_at IS NULL OR completed_at IS NULL OR completed_at >= started_at)",
            name='completion_after_start'
        ),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for performance
    op.create_index('idx_crawl_jobs_category_id', 'crawl_jobs', ['category_id'])
    op.create_index('idx_crawl_jobs_status', 'crawl_jobs', ['status'])
    op.create_index('idx_crawl_jobs_celery_task_id', 'crawl_jobs', ['celery_task_id'])
    op.create_index('idx_crawl_jobs_started_at', 'crawl_jobs', ['started_at'])
    op.create_index('idx_crawl_jobs_completed_at', 'crawl_jobs', ['completed_at'])
    op.create_index('idx_crawl_jobs_priority', 'crawl_jobs', ['priority'])
    op.create_index('idx_crawl_jobs_correlation_id', 'crawl_jobs', ['correlation_id'])
    
    # Create composite indexes for common queries
    op.create_index('idx_crawl_jobs_category_status', 'crawl_jobs', ['category_id', 'status'])
    op.create_index('idx_crawl_jobs_status_priority', 'crawl_jobs', ['status', 'priority'])
    op.create_index('idx_crawl_jobs_status_created_at', 'crawl_jobs', ['status', 'created_at'])
    op.create_index('idx_crawl_jobs_completed_at_status', 'crawl_jobs', ['completed_at', 'status'])
    
    # Create GIN index for job_metadata JSONB column
    op.create_index('idx_crawl_jobs_job_metadata_gin', 'crawl_jobs', ['job_metadata'], postgresql_using='gin')
    
    # Create unique constraint on celery_task_id (allow NULL values)
    op.create_unique_constraint('uq_crawl_jobs_celery_task_id', 'crawl_jobs', ['celery_task_id'])


def downgrade() -> None:
    """Remove crawl_jobs and categories tables with related objects."""
    # Drop crawl_jobs indexes first
    op.drop_index('idx_crawl_jobs_job_metadata_gin', table_name='crawl_jobs')
    op.drop_index('idx_crawl_jobs_completed_at_status', table_name='crawl_jobs')
    op.drop_index('idx_crawl_jobs_status_created_at', table_name='crawl_jobs')
    op.drop_index('idx_crawl_jobs_status_priority', table_name='crawl_jobs')
    op.drop_index('idx_crawl_jobs_category_status', table_name='crawl_jobs')
    op.drop_index('idx_crawl_jobs_correlation_id', table_name='crawl_jobs')
    op.drop_index('idx_crawl_jobs_priority', table_name='crawl_jobs')
    op.drop_index('idx_crawl_jobs_completed_at', table_name='crawl_jobs')
    op.drop_index('idx_crawl_jobs_started_at', table_name='crawl_jobs')
    op.drop_index('idx_crawl_jobs_celery_task_id', table_name='crawl_jobs')
    op.drop_index('idx_crawl_jobs_status', table_name='crawl_jobs')
    op.drop_index('idx_crawl_jobs_category_id', table_name='crawl_jobs')
    
    # Drop crawl_jobs unique constraint
    op.drop_constraint('uq_crawl_jobs_celery_task_id', 'crawl_jobs', type_='unique')
    
    # Drop crawl_jobs table
    op.drop_table('crawl_jobs')
    
    # Drop crawl job status enum type
    op.execute("DROP TYPE IF EXISTS crawljobstatus")
    
    # Drop categories indexes
    op.drop_index('idx_categories_keywords_gin', table_name='categories')
    op.drop_index('idx_categories_is_active', table_name='categories')
    op.drop_index('idx_categories_name', table_name='categories')
    
    # Drop categories table
    op.drop_table('categories')