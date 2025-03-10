## Flibberflow Project

A playground for experimenting with LLM completions using the Model Context Protocol.  The goal of the project is to be able to experiment with LLM calls and workflows to ultimately be able to compile for use in another project.

The application uses:

Python:
 - Packages are managed with uv
 - FastAPI
Frontend:
 - HTMX v2
 - Bulma v2

Whenever you make a fundamental change to architectural approach or establish a new pattern that should be followed through the whole application, be sure to update this document.

## Backend

- Prefer a modular structure.  The goal is for core functionality to be available via the CLI as well as the UI.

### Python

- When creating requests and responses, use HTMX
- When a request has the potential to last for longer than a second, return a queue id as the response response and update the UI with the SSE connection
- When creating command line tools, create a click command in `src/cli.py` and add a shortcut in the `justfile`

## Frontend

This application is a singleton intended for local use.  The goal is for it to be a SPA-like application, but managing only a single session.
There will only ever be a single instance of the server and a lone user.  So the app state is global state.

### Javascript

- Use plain old javascript.  When adding custom javascript, prefer to add it to a `component/mycomponent.js` file in the `js` folder, and be sure to import it in `js/app.js`

### CSS Styling

The UI uses Bulma CSS framework.

- When adding CSS, always prefer to add the CSS as sass to custom section files, eg `/style/sections/_mysection.scss` rather than using inline styles.  If the styles correspond to a component, use a component sass file, eg, `styles/components/_mycomponent.scss`

### Shell commands

All shell commands should be run through `just` using the `justfile` in root.
