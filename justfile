# List all available commands
default:
    @just --list

# Start the FastAPI development server with auto-reload
fastapi-dev:
    uvicorn src.main:app --reload --timeout-graceful-shutdown 2

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

# Start Redis server locally
redis-start:
    redis-server --daemonize yes

# Stop Redis server
redis-stop:
    redis-cli shutdown

# Run database migrations to the latest version
migrate:
    alembic upgrade head

# Create a new migration with the specified message
migmake args:
    alembic revision -m "{{args}}"

# Show current migration version
alembic-current:
    alembic current

# Search MCP with an optional query
search-mcp query="":
    python -m src.cli search-mcp {{query}}
