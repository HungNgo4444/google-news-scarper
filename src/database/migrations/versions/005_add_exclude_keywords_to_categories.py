"""add exclude_keywords to categories

Revision ID: 005_add_exclude_keywords
Revises: 004_add_crawl_jobs_table
Create Date: 2025-09-13 14:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '005_add_exclude_keywords'
down_revision: Union[str, None] = '004_add_crawl_jobs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add exclude_keywords column to categories table
    op.add_column('categories', sa.Column('exclude_keywords', JSONB, nullable=False, server_default=sa.text('jsonb_build_array()')))

    # Create GIN index for exclude_keywords
    op.create_index('idx_categories_exclude_keywords_gin', 'categories', ['exclude_keywords'], postgresql_using='gin')


def downgrade() -> None:
    # Remove the index and column
    op.drop_index('idx_categories_exclude_keywords_gin', table_name='categories')
    op.drop_column('categories', 'exclude_keywords')