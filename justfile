# List all available commands
default:
    @just --list

# Create a local .env file from .env.dist if it doesn't exist
setup-env:
    [ -f .env ] || cp .env.dist .env

# Start the FastAPI development server with auto-reload
fastapi-dev:
    uvicorn src.main:app --reload --timeout-graceful-shutdown 2 --env-file .env --no-access-log

# Start the frontend development server
frontend-dev:
    npm run dev

# Build the frontend assets for production
build:
    npm run build
    
# Run aider with project documentation and justfile
aider *args:
    aider --file docs/project.md --file justfile {{args}}

# Start Docker containers in detached mode
docup:
    docker compose up -d

# Stop and remove Docker containers
docdown:
    docker compose down

# Run database migrations to the latest version
migrate:
    alembic upgrade head

# Create a new migration with the specified message
migmake args:
    alembic revision --autogenerate -m "{{args}}"

# Show current migration version
alembic-current:
    alembic current

# Search MCP with an optional query
search-mcp query="":
    python -m src.cli search-mcp {{query}}

# Run all tests
test:
    pytest tests/ -v

# Run model tests specifically
test-models:
    pytest tests/test_models.py -v

# Generate test data
generate-test-data:
    python -c "import asyncio; from src.fixtures import create_complete_flow_session; from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker; async def run(): engine = create_async_engine('postgresql+asyncpg://app:pass@localhost:5432/app'); async_session = async_sessionmaker(engine, expire_on_commit=False); async with async_session() as session: result = await create_complete_flow_session(session); await session.commit(); print('Test data generated successfully!'); asyncio.run(run())"

# Set up test database
setup-test-db:
    PGPASSWORD=postgres createdb -U postgres app_test || echo "Test database already exists"
    PGPASSWORD=postgres psql -U postgres -d app_test -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run tests with coverage report
test-cov:
    pytest tests/ --cov=src --cov-report=term-missing -v

# Run tests and watch for changes
test-watch:
    pytest-watch -- tests/ -v
