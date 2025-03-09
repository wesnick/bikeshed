
fastapi-dev:
    uvicorn main:app --reload

frontend-dev:
    npm run dev

build:
    npm run build
    
aider *args:
    aider --file docs/project.md --file justfile {{args}}
