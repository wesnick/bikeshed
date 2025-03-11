from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import os

POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}
metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)

# Get database URL from environment or use default
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql+asyncpg://postgres:postgres@localhost:5432/flibberflow"
)
DEBUG = False

engine = create_async_engine(
    DATABASE_URL,
    echo=DEBUG,
)

async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False
)

async def get_db():
    """Dependency for getting async database session"""
    async with async_session_factory() as session:
        yield session
