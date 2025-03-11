import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Import application config to use the same database URL
from src.config import get_config
app_config = get_config()

# add your model's MetaData object here
# for 'autogenerate' support
from src.models import Base
from src.service.database import metadata
target_metadata = Base.metadata

def do_run_migrations(connection):
    context.configure(
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        # literal_binds=True,
        version_table_schema=target_metadata.schema,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_async_engine(
        str(app_config.database_url), future=True
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)


asyncio.run(run_migrations_online())