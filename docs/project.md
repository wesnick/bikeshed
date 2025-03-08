## Flibberflow Project

A playground for experimenting with LLM completions.

The application uses:

Python:
 - FastAPI
Frontend:
 - HTMX v2
 - Bulma v2

Whenever you update or establish a pattern, be sure to update this document.

### Python

- When creating requests and responses, use HTMX
- When a request has the potential to last for longer than a second, return a queue id as the response response and update the UI with the SSE connection

### Frontend

This application is a singleton intended for local use.  The goal is for it to be a SPA-like application, but managing only a single session.
There will only ever be a single instance of the server and a lone user.  So the app state is global state.

### CSS Styling

The UI uses Bulma CSS framework.

- When adding CSS, always prefer to add the CSS as sass to custom section files, eg `/style/sections/_mysection.scss` rather than using inline styles.  If the styles correspond to a component, use a component sass file, eg, `styles/components/_mycomponent.scss`

### Favicon

The application uses an SVG favicon stored in the public directory. The SVG is converted to various formats (.ico, .png) for cross-browser compatibility. The favicon represents the Flibberflow logo with an "F" shape and a circle.

### Shell commands

All shell commands should be run through `just` using the `justfile` in root.
