"""add articles table

Revision ID: 003_add_articles
Revises:
Create Date: 2025-09-15 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_add_articles'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add articles table with indexes."""
    op.create_table('articles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('publish_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_url', sa.String(length=2000), nullable=False),
        sa.Column('image_url', sa.String(length=2000), nullable=True),
        sa.Column('url_hash', sa.String(length=64), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('crawl_job_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('keywords_matched', postgresql.ARRAY(sa.String), nullable=True, server_default='{}'),
        sa.Column('relevance_score', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("length(title) >= 1", name='title_not_empty'),
        sa.CheckConstraint("length(source_url) >= 1", name='source_url_not_empty'),
        sa.CheckConstraint("publish_date IS NULL OR publish_date <= last_seen", name='publish_date_before_last_seen'),
        sa.CheckConstraint("relevance_score >= 0.0 AND relevance_score <= 1.0", name='relevance_score_range'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url_hash'),
        if_not_exists=True
    )

    # Create indexes for performance
    op.create_index('idx_articles_title', 'articles', ['title'], if_not_exists=True)
    op.create_index('idx_articles_author', 'articles', ['author'], if_not_exists=True)
    op.create_index('idx_articles_publish_date', 'articles', ['publish_date'], if_not_exists=True)
    op.create_index('idx_articles_source_url', 'articles', ['source_url'], if_not_exists=True)
    op.create_index('idx_articles_url_hash', 'articles', ['url_hash'], if_not_exists=True)
    op.create_index('idx_articles_content_hash', 'articles', ['content_hash'], if_not_exists=True)
    op.create_index('idx_articles_last_seen', 'articles', ['last_seen'], if_not_exists=True)
    op.create_index('idx_articles_crawl_job_id', 'articles', ['crawl_job_id'], if_not_exists=True)
    op.create_index('idx_articles_keywords_matched', 'articles', ['keywords_matched'], postgresql_using='gin', if_not_exists=True)
    op.create_index('idx_articles_relevance_score', 'articles', ['relevance_score'], if_not_exists=True)
    op.create_index('idx_articles_created_at', 'articles', ['created_at'], if_not_exists=True)

    # Create composite indexes for common queries
    op.create_index('idx_articles_publish_date_created_at', 'articles', ['publish_date', 'created_at'], if_not_exists=True)
    op.create_index('idx_articles_author_publish_date', 'articles', ['author', 'publish_date'], if_not_exists=True)

    # Create full text search index on title and content (without CONCURRENTLY in transaction)
    op.execute("CREATE INDEX IF NOT EXISTS idx_articles_title_content_fts ON articles USING gin(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')))")


def downgrade() -> None:
    """Remove articles table with related objects."""
    # Drop indexes first
    op.drop_index('idx_articles_title_content_fts', table_name='articles', if_exists=True)
    op.drop_index('idx_articles_author_publish_date', table_name='articles', if_exists=True)
    op.drop_index('idx_articles_publish_date_created_at', table_name='articles', if_exists=True)
    op.drop_index('idx_articles_created_at', table_name='articles', if_exists=True)
    op.drop_index('idx_articles_last_seen', table_name='articles', if_exists=True)
    op.drop_index('idx_articles_content_hash', table_name='articles', if_exists=True)
    op.drop_index('idx_articles_url_hash', table_name='articles', if_exists=True)
    op.drop_index('idx_articles_source_url', table_name='articles', if_exists=True)
    op.drop_index('idx_articles_publish_date', table_name='articles', if_exists=True)
    op.drop_index('idx_articles_author', table_name='articles', if_exists=True)
    op.drop_index('idx_articles_title', table_name='articles', if_exists=True)

    # Drop table
    op.drop_table('articles')