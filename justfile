
fastapi-dev:
    uvicorn src.main:app --reload --timeout-graceful-shutdown 2

frontend-dev:
    npm run dev

build:
    npm run build
    
aider *args:
    aider --file docs/project.md --file justfile {{args}}

docup:
    docker compose up -d

docdown:
    docker compose down

migrate:
    alembic upgrade head

migmake args:
    alembic revision -m "{{args}}"

alembic-current:
    alembic current
