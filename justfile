
fastapi-dev:
    uvicorn main:app --reload --timeout-graceful-shutdown 5

frontend-dev:
    npm run dev

build:
    npm run build
    
aider *args:
    aider --file docs/project.md --file justfile {{args}}
