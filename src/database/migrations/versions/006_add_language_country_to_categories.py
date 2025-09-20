"""add language and country to categories

Revision ID: 006_add_language_country
Revises: 005_add_exclude_keywords
Create Date: 2025-09-15 14:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '006_add_language_country'
down_revision: Union[str, None] = '005_add_exclude_keywords'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add language and country fields to categories table."""
    # Add language column with default 'vi' for Vietnamese
    op.add_column('categories', sa.Column('language', sa.String(length=5), nullable=False, server_default='vi', comment="Language code for Google News search (e.g., 'vi', 'en')"))

    # Add country column with default 'VN' for Vietnam
    op.add_column('categories', sa.Column('country', sa.String(length=5), nullable=False, server_default='VN', comment="Country code for Google News search (e.g., 'VN', 'US')"))

    # Add indexes for performance
    op.create_index('idx_categories_language', 'categories', ['language'], if_not_exists=True)
    op.create_index('idx_categories_country', 'categories', ['country'], if_not_exists=True)
    op.create_index('idx_categories_language_country', 'categories', ['language', 'country'], if_not_exists=True)


def downgrade() -> None:
    """Remove language and country fields from categories table."""
    # Drop indexes
    op.drop_index('idx_categories_language_country', table_name='categories', if_exists=True)
    op.drop_index('idx_categories_country', table_name='categories', if_exists=True)
    op.drop_index('idx_categories_language', table_name='categories', if_exists=True)

    # Drop columns
    op.drop_column('categories', 'country')
    op.drop_column('categories', 'language')