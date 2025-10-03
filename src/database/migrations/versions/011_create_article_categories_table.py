"""Create article_categories junction table

Revision ID: 011_article_categories
Revises: 010_crawl_period_values
Create Date: 2025-10-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '011_article_categories'
down_revision: Union[str, None] = '010_crawl_period_values'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create article_categories junction table with proper indexes and constraints."""

    # Create the table
    op.create_table(
        'article_categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('article_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('relevance_score', sa.DECIMAL(precision=3, scale=2), nullable=True, server_default='1.0'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('relevance_score >= 0.0 AND relevance_score <= 1.0', name='valid_relevance_score')
    )

    # Create indexes
    op.create_index('idx_article_categories_article_id', 'article_categories', ['article_id'])
    op.create_index('idx_article_categories_category_id', 'article_categories', ['category_id'])
    op.create_index('idx_article_categories_composite', 'article_categories', ['article_id', 'category_id'], unique=True)
    op.create_index('idx_article_categories_relevance', 'article_categories', ['relevance_score'])

    # Migrate existing data from articles → article_categories (via crawl_jobs)
    # This creates the many-to-many relationship for existing articles
    op.execute("""
        INSERT INTO article_categories (article_id, category_id, relevance_score, created_at, updated_at)
        SELECT
            a.id as article_id,
            cj.category_id,
            COALESCE(a.relevance_score, 1.0) as relevance_score,
            a.created_at,
            a.updated_at
        FROM articles a
        JOIN crawl_jobs cj ON a.crawl_job_id = cj.id
        WHERE cj.category_id IS NOT NULL
        ON CONFLICT (article_id, category_id) DO NOTHING
    """)


def downgrade() -> None:
    """Drop article_categories table and all associated indexes."""
    op.drop_index('idx_article_categories_relevance', table_name='article_categories')
    op.drop_index('idx_article_categories_composite', table_name='article_categories')
    op.drop_index('idx_article_categories_category_id', table_name='article_categories')
    op.drop_index('idx_article_categories_article_id', table_name='article_categories')
    op.drop_table('article_categories')
