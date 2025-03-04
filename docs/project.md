## Flibberflow Project

A playground for experimenting with LLM completions.

The application uses:

Python:
 - FastAPI
 - mcp-agent
Javascript:
 - HTMX
CSS Styling:
 - Bulma

Whenever you update or establish a pattern, be sure to update this document.

### Python

- When creating requests and responses, use HTMX
- When a request has the potential to last for longer than a second, return a queue response and update the UI with the SSE connection

### Javascript


### CSS Styling

The UI uses Bulma CSS framework.

- When adding CSS, always prefer to add the CSS as sass to custom section files, eg `/style/sections/_mysection.scss` rather than using inline styles.  If the styles correspond to a component, use a component sass file, eg, `styles/components/_mycomponent.scss`
- When creating an HTMX compatible component, use skeletons

```html
<!--The skeleton block is a simple block element.-->
<div class="skeleton-block"></div>
<!--The skeleton lines element is a loading element which resembles a paragraph.-->
<div class="skeleton-lines">
  <div></div>
  <div></div>
</div>
<!--Using `is-skeleton` or `has-skeleton`-->
<span class="icon is-skeleton">
  <i class="fas fa-reply"></i>
</span>
```

