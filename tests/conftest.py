import pytest
import asyncio
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from src.database.models import Base
from src.shared.config import Settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with in-memory SQLite database."""
    return Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        DATABASE_ECHO=True,
        ENVIRONMENT="testing",
        LOG_LEVEL="DEBUG",
        DATABASE_POOL_SIZE=1,
        DATABASE_MAX_OVERFLOW=0,
        DATABASE_POOL_TIMEOUT=5
    )


@pytest.fixture
async def test_engine(test_settings: Settings):
    """Create test database engine."""
    engine = create_async_engine(
        test_settings.DATABASE_URL,
        echo=test_settings.DATABASE_ECHO,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def test_session_factory(test_engine):
    """Create test session factory."""
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )


@pytest.fixture
async def test_session(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async with test_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


@pytest.fixture
def sample_article_data():
    """Sample article data for testing."""
    return {
        "title": "Test Article Title",
        "content": "This is test article content with some text to validate content processing.",
        "author": "Test Author",
        "source_url": "https://example.com/test-article",
        "image_url": "https://example.com/test-image.jpg",
        "url_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "content_hash": "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"
    }


@pytest.fixture
def sample_category_data():
    """Sample category data for testing."""
    return {
        "name": "Technology",
        "keywords": ["python", "programming", "software"],
        "exclude_keywords": ["deprecated", "legacy"],
        "is_active": True
    }