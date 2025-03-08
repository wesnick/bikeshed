
fastapi-dev:
    uvicorn main:app --reload

frontend-dev:
    npm run dev

build:
    npm run build

dev: build
    uvicorn main:app --reload

