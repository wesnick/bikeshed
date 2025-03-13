from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.config import get_config

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
