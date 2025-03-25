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

# Start the ARQ worker
arq-dev:
    .venv/bin/arq src.service.worker.WorkerSettings --watch src/

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

# Run all tests
test:
    pytest tests/ -v

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
    
commit:
    #!/usr/bin/env bash
    git diff --staged > /tmp/git_diff_tmp
    cat templates/prompts/git_commit.md.j2 | sed -e '/{{{{ git_diff }}/{r /tmp/git_diff_tmp' -e 'd}' > /tmp/commit_prompt_tmp
    cat /tmp/commit_prompt_tmp | llm > /tmp/commit_msg_tmp

    # Display the generated commit message
    echo "Generated commit message:"
    echo "------------------------"
    cat /tmp/commit_msg_tmp
    echo "------------------------"

    # Prompt for confirmation
    read -p "Proceed with this commit message? (y/n) " confirm
    if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
        git commit -F /tmp/commit_msg_tmp
        echo "Changes committed successfully!"
    else
        echo "Commit canceled."
    fi

    rm /tmp/git_diff_tmp /tmp/commit_prompt_tmp /tmp/commit_msg_tmp