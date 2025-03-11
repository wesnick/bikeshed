from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.config import get_config
from src.models import Base

config = get_config()

# Create engine with the Base metadata from models
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
