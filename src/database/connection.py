import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from contextlib import asynccontextmanager
from src.shared.config import Settings, get_settings

logger = logging.getLogger(__name__)


class DatabaseConnection:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
    
    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError("Database engine not initialized. Call setup() first.")
        return self._engine
    
    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            raise RuntimeError("Database session factory not initialized. Call setup() first.")
        return self._session_factory
    
    def setup(self) -> None:
        database_url = self.settings.DATABASE_URL
        
        # Convert postgresql:// to postgresql+asyncpg:// if needed
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        engine_kwargs = {
            "echo": self.settings.DATABASE_ECHO,
            "pool_size": self.settings.DATABASE_POOL_SIZE,
            "max_overflow": self.settings.DATABASE_MAX_OVERFLOW,
            "pool_timeout": self.settings.DATABASE_POOL_TIMEOUT,
            "pool_pre_ping": True,
        }
        
        # For testing with in-memory database
        if ":memory:" in database_url or "sqlite" in database_url:
            engine_kwargs.update({
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            })
            engine_kwargs.pop("pool_size", None)
            engine_kwargs.pop("max_overflow", None)
            engine_kwargs.pop("pool_timeout", None)
        
        self._engine = create_async_engine(database_url, **engine_kwargs)
        
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False,
        )
        
        logger.info(f"Database connection initialized for environment: {self.settings.ENVIRONMENT}")
    
    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            logger.info("Database connection closed")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def health_check(self) -> bool:
        try:
            async with self.get_session() as session:
                result = await session.execute("SELECT 1")
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database connection instance
_db_connection: DatabaseConnection | None = None


def get_database_connection(settings: Settings | None = None) -> DatabaseConnection:
    global _db_connection
    
    if _db_connection is None:
        if settings is None:
            settings = get_settings()
        _db_connection = DatabaseConnection(settings)
        _db_connection.setup()
    
    return _db_connection


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    db_connection = get_database_connection()
    async with db_connection.get_session() as session:
        yield session


async def close_database_connection() -> None:
    global _db_connection
    if _db_connection:
        await _db_connection.close()
        _db_connection = None