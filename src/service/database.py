from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator
from src.config import get_config
from src.models.models import Base

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

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session as an async generator.
    
    Usage:
        async for session in get_db():
            # Use session
            
        # Or with anext
        db_generator = get_db()
        session = await anext(db_generator)
        try:
            # Use session
        finally:
            await db_generator.aclose()
    """
    session = async_session_factory()
    try:
        yield session
    finally:
        await session.close()
