set dotenv-load

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
migrate *args:
    pg-schema-diff apply --dsn "postgres://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB" --schema-dir config/database --allow-hazards ACQUIRES_ACCESS_EXCLUSIVE_LOCK,INDEX_BUILD,INDEX_DROPPED {{args}}

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

# Start the ARQ worker
arq-worker:
    .venv/bin/arq src.service.worker.WorkerSettings --watch src/

# Set up test database
setup-test-db:
    PGPASSWORD=$POSTGRES_PASSWORD createdb -U $POSTGRES_USER $POSTGRES_DB_test || echo "Test database already exists"
    PGPASSWORD=$POSTGRES_PASSWORD psql -U $POSTGRES_USER -d $POSTGRES_DB_test -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Fix formatting on html templates
html-lint:
    uvx djlint templates/ --reformat --extension=html.j2 --indent 2

# Python lint and fix
py-lint:
    uvx ruff check src/ --fix
    
# Lint the jinja extensions file
jinja-ext-lint:
    uvx ruff check src/jinja_extensions.py --fix

# Test the file icon filter
test-file-icon filename:
    python -c "from src.jinja_extensions import get_file_icon; print(f'Icon for {\"{{filename}}\"}: {get_file_icon(\"{{filename}}\")}');"

# List all blobs in the database
list-blobs:
    python -m src.cli list-blobs

# Upload a file as a blob
upload-blob file_path:
    python -m src.cli upload-blob {{file_path}}

# Chat with an LLM model
chat message model="ollama/llama3":
    python -m src.cli chat --model {{model}} "{{message}}"

# Install python-magic dependency
install-magic:
    uv pip install python-magic
