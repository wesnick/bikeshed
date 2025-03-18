# List all available commands
default:
    @just --list

# Create a local .env file from .env.dist if it doesn't exist
setup-env:
    [ -f .env ] || cp .env.dist .env
    uv pip install transitions[asyncio]

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

# Create and run a workflow from a template
run-workflow template_name:
    python -m src.cli run-workflow {{template_name}}

# Create an ad-hoc session
create-ad-hoc description:
    python -m src.cli create-ad-hoc "{{description}}"

# Run all tests
test:
    pytest tests/ -v

# Run workflow tests
test-workflow:
    pytest tests/test_workflow.py -v

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

# Start both frontend and backend development servers
dev:
    just frontend-dev & just fastapi-dev
