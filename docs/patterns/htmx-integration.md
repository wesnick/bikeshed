## HTMX Integration

These are the common patterns for how this application integrates FastAPI with HTMX to create a Single Page Application feel.

### FastAPI Routes

Main pages are served blank, they usually contain several regions that can be targeted by the component, like a form, a table, etc.

```python
from fastapi import APIRouter

from src.dependencies import get_jinja

router = APIRouter(prefix="/my-component", tags=["my-component"])
jinja = get_jinja()

@router.get("/")
@jinja.hx('components/my-component/index.html.j2', no_data=True)
async def my_component_page():
    pass
```

When creating POST forms, use `form-json` HTMX extension in the HTML, pydantic models for Request inputs, and repositories to store items.


```html
<form class="my-form"
      hx-ext="form-json"
      hx-post="/my-component/create"
      hx-target=".my-area"
      hx-on::after-request="this.reset();">
  <div class="field">
    <div class="control">
      <label>Text Field</label>
      <div class="control">
        <input name="my_attribute" class="input" type="text" placeholder="Name">
      </div>
    </div>
  </div>
</form>
```

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from psycopg import AsyncConnection

from src.dependencies import get_db, get_jinja, get_my_repository
from src.repository import MyRepository

router = APIRouter(prefix="/tags", tags=["tags"])
jinja = get_jinja()

class MyComponentCreateRequest(BaseModel):
    name: str

@router.post("/create")
@jinja.hx('components/my-component/index.html.j2', no_data=True)
async def my_component_page(request: MyComponentCreateRequest,
                            db: AsyncConnection = Depends(get_db),
                            repo: MyRepository = Depends(get_my_repository)):
    ... # Do Stuff
```
