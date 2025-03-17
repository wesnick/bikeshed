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

# Create database fixtures for development
create-fixtures:
    python -m src.cli create-fixtures

# Create database fixtures with custom parameters
create-fixtures-custom:
    python -m src.cli create-fixtures --templates=3 --flows=5 --sessions=10 --messages-per-session=8 --artifacts=15 --scratchpads=3 --complete-flows=2

# Run all tests
test:
    pytest tests/ -v

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
    
# Load schemas from modules
load-schemas:
    python -m src.cli load-schemas

# Load all schemas (including non-decorated ones)
load-all-schemas:
    python -m src.cli load-schemas --scan-all
    
# Load templates from directories
load-templates *dirs:
    python -m src.cli load-templates {{dirs}}
    
# Load session templates from YAML files
load-session-templates *files:
    python -m src.cli load-session-templates {{files}}
    
# Create a new session from a template
create-session template_name *args:
    python -m src.cli create-session {{template_name}} {{args}}
