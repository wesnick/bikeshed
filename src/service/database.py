from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.config import get_config

config = get_config()

POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}
metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)

engine = create_async_engine(
    str(config.database_url),
    echo=config.log_level == "DEBUG",
)

async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False
)

async def get_db():
    """Dependency for getting async database session"""
    async with async_session_factory() as session:
        yield session
