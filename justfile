
fastapi-dev:
    uvicorn main:app --reload

frontend-dev:
    npm run dev

build:
    npm run build
    
favicon:
    # Convert SVG to various favicon formats
    # Install required tools if needed: npm install -g svgo
    svgo -i public/favicon.svg -o public/favicon.svg
    # Generate .ico and .png files from the SVG

aider *args:
    aider --file docs/project.md --file justfile {{args}}
