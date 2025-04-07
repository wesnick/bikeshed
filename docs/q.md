# BikeShed Quickie Implementation Specification

## Overview

This specification outlines the implementation of a new "Quickie" concept in the BikeShed project. A Quickie represents a single request-response interaction with an LLM, designed for quick, targeted operations like generating commit messages or performing text transformations.

## Database Schema

Add the following table to your PostgreSQL database:

```sql
create table quickies
(
    id            uuid         not null primary key,
    template_name varchar(255) not null,     -- References YAML template by name
    prompt_text   text         not null,     -- Actual prompt text used (after variable substitution)
    prompt_hash   varchar(32)  not null,     -- MD5 hash of the template before substitution
    input_params  jsonb        not null,     -- Input parameters passed to the template
    output        jsonb,                     -- Generated output
    status        varchar(50)  not null default 'pending', -- Status: pending, running, complete, error
    error         text,                      -- Error message if failed
    model         varchar(100),              -- Model used for generation
    created_at    timestamp    not null default current_timestamp,
    updated_at    timestamp    not null default current_timestamp,
    metadata      jsonb                      -- Additional runtime metadata
);

-- Apply timestamp trigger
CREATE TRIGGER update_timestamp_quickies
    BEFORE UPDATE
    ON quickies
    FOR EACH ROW
EXECUTE FUNCTION update_timestamp();

-- Create indexes for common query patterns
CREATE INDEX idx_quickies_template_name ON quickies(template_name);
CREATE INDEX idx_quickies_prompt_hash ON quickies(prompt_hash);
CREATE INDEX idx_quickies_status ON quickies(status);
CREATE INDEX idx_quickies_created_at ON quickies(created_at);
```

## Configuration Format

Create a new YAML configuration file at `config/quickie_templates.yaml`:

```yaml
quickie_templates:
  commit_message_generator:  # template name (used as template_name in quickies table)
    description: "Generates concise git commit messages from diff output"
    model: "default:small"
    prompt: '@system/git_commit_message_generator.md'
    input_schema:
      diff:
        type: "string"
        description: "Git diff output to analyze"
        required: true

    output_schema:
      commit_message:
        type: "string"
        description: "Generated commit message"
```

## Python Model Classes

Create these Pydantic models in `src/models/quickie.py`:

```python
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Union
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum
import hashlib
import json

from .models import DBModelMixin


class QuickieStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


class QuickieInputParam(BaseModel):
    """Schema definition for a single input parameter in a quickie template"""
    type: str
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[str]] = None


class QuickieOutputParam(BaseModel):
    """Schema definition for a single output parameter in a quickie template"""
    type: str
    description: str


class QuickieExample(BaseModel):
    """Example for few-shot learning in a quickie template"""
    input: Dict[str, Any]
    output: Dict[str, Any]


class QuickieTemplateConfig(BaseModel):
    """Configuration options for a quickie template"""
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    format: str = "json"  # json, text, markdown
    stop_sequences: Optional[List[str]] = None


class QuickieTemplate(BaseModel):
    """Definition of a quickie template from YAML config"""
    name: str
    description: str
    model: str
    prompt: str
    input_schema: Dict[str, QuickieInputParam]
    output_schema: Dict[str, QuickieOutputParam]
    config: QuickieTemplateConfig
    examples: Optional[List[QuickieExample]] = None

    def get_prompt_hash(self) -> str:
        """Calculate MD5 hash of the prompt template"""
        return hashlib.md5(self.prompt.encode('utf-8')).hexdigest()

    def render_prompt(self, input_params: Dict[str, Any]) -> str:
        """Render the prompt template with input parameters"""
        # Simple template rendering - in a real implementation,
        # you might use Jinja2 or another templating engine
        rendered = self.prompt
        for key, value in input_params.items():
            placeholder = "{{" + key + "}}"
            if placeholder in rendered:
                # Handle different types of values, including blob references
                if isinstance(value, dict) and value.get("type") == "blob":
                    # This would need to be implemented to fetch blob content
                    blob_content = "[Blob content would be inserted here]"
                    rendered = rendered.replace(placeholder, blob_content)
                else:
                    rendered = rendered.replace(placeholder, str(value))
        return rendered


class Quickie(DBModelMixin, BaseModel):
    """Database model for a quickie execution instance"""
    id: UUID = Field(default_factory=uuid4)
    template_name: str
    prompt_text: str
    prompt_hash: str
    input_params: Dict[str, Any]
    output: Optional[Dict[str, Any]] = None
    status: QuickieStatus = QuickieStatus.PENDING
    error: Optional[str] = None
    model: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    __db_table__ = "quickies"
    __non_persisted_fields__ = set()
    __unique_fields__ = {"id"}
```

## Repository Implementation

Create a QuickieRepository in `src/repositories/quickie_repository.py`:

```python
from typing import List, Dict, Any, Optional
from uuid import UUID
import hashlib

from .base_repository import BaseRepository
from ..models.quickie import Quickie, QuickieStatus


class QuickieRepository(BaseRepository):
    """Repository for managing Quickie instances in the database"""

    def __init__(self, db_pool):
        super().__init__(db_pool, Quickie)

    async def create_quickie(
        self, 
        template_name: str, 
        input_params: Dict[str, Any], 
        prompt_text: str,
        prompt_hash: str,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Quickie:
        """Create a new Quickie instance"""
        quickie = Quickie(
            template_name=template_name,
            prompt_text=prompt_text,
            prompt_hash=prompt_hash,
            input_params=input_params,
            model=model,
            status=QuickieStatus.PENDING,
            metadata=metadata or {}
        )
        return await self.create(quickie)

    async def update_status(self, id: UUID, status: QuickieStatus, error: Optional[str] = None) -> Quickie:
        """Update the status of a Quickie"""
        quickie = await self.get_by_id(id)
        quickie.status = status
        if error:
            quickie.error = error
        return await self.update(quickie)

    async def update_output(self, id: UUID, output: Dict[str, Any]) -> Quickie:
        """Set the output for a completed Quickie"""
        quickie = await self.get_by_id(id)
        quickie.output = output
        quickie.status = QuickieStatus.COMPLETE
        return await self.update(quickie)

    async def get_by_template(self, template_name: str, limit: int = 100) -> List[Quickie]:
        """Get Quickies by template name"""
        query = f"SELECT * FROM {self.table_name} WHERE template_name = $1 ORDER BY created_at DESC LIMIT $2"
        rows = await self.db_pool.fetch(query, template_name, limit)
        return [self.model_class.parse_obj(dict(row)) for row in rows]
    
    async def get_by_prompt_hash(self, prompt_hash: str, limit: int = 100) -> List[Quickie]:
        """Get Quickies by prompt hash"""
        query = f"SELECT * FROM {self.table_name} WHERE prompt_hash = $1 ORDER BY created_at DESC LIMIT $2"
        rows = await self.db_pool.fetch(query, prompt_hash, limit)
        return [self.model_class.parse_obj(dict(row)) for row in rows]
```

## Template Service

Create a service to manage quickie templates in `src/services/quickie_template_service.py`:

```python
from typing import Dict, List, Optional, Any
import os
import yaml
import hashlib

from ..models.quickie import QuickieTemplate, QuickieTemplateConfig, QuickieInputParam, QuickieOutputParam


class QuickieTemplateService:
    """Service for managing quickie templates"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join('src', 'config', 'quickie_templates.yaml')
        self.templates: Dict[str, QuickieTemplate] = {}
        self.load_templates()
    
    def load_templates(self):
        """Load templates from YAML config file"""
        if not os.path.exists(self.config_path):
            # Create empty config if it doesn't exist
            with open(self.config_path, 'w') as f:
                yaml.dump({'quickie_templates': {}}, f)
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        templates_dict = config.get('quickie_templates', {})
        for name, template_data in templates_dict.items():
            # Process input schema
            input_schema = {}
            for param_name, param_data in template_data.get('input_schema', {}).items():
                input_schema[param_name] = QuickieInputParam(**param_data)
            
            # Process output schema
            output_schema = {}
            for param_name, param_data in template_data.get('output_schema', {}).items():
                output_schema[param_name] = QuickieOutputParam(**param_data)
            
            # Create template config
            config_data = template_data.get('config', {})
            config = QuickieTemplateConfig(**config_data)
            
            # Create the template
            template = QuickieTemplate(
                name=name,
                description=template_data.get('description', ''),
                model=template_data.get('model', ''),
                prompt=template_data.get('prompt', ''),
                input_schema=input_schema,
                output_schema=output_schema,
                config=config,
                examples=template_data.get('examples', [])
            )
            
            self.templates[name] = template
    
    def get_template(self, name: str) -> Optional[QuickieTemplate]:
        """Get a template by name"""
        return self.templates.get(name)
    
    def get_all_templates(self) -> List[QuickieTemplate]:
        """Get all templates"""
        return list(self.templates.values())
    
    def validate_input(self, template_name: str, input_params: Dict[str, Any]) -> Dict[str, str]:
        """
        Validate input parameters against template schema
        Returns a dict of error messages if validation fails
        """
        template = self.get_template(template_name)
        if not template:
            return {"template": f"Template '{template_name}' not found"}
        
        errors = {}
        
        # Check for required parameters
        for param_name, param_schema in template.input_schema.items():
            if param_schema.required and param_name not in input_params:
                errors[param_name] = f"Required parameter '{param_name}' is missing"
        
        # Check parameter types and constraints
        for param_name, param_value in input_params.items():
            if param_name in template.input_schema:
                schema = template.input_schema[param_name]
                
                # Check enum values if applicable
                if schema.enum and param_value not in schema.enum:
                    errors[param_name] = f"Value must be one of: {', '.join(schema.enum)}"
                
                # Could add more type validation here
        
        return errors
```

## Quickie Service

Create a service to execute quickies in `src/services/quickie_service.py`:

```python
from typing import Dict, Any, Optional, List
from uuid import UUID
import hashlib
import asyncio

from ..repositories.quickie_repository import QuickieRepository
from ..models.quickie import Quickie, QuickieStatus
from .quickie_template_service import QuickieTemplateService
from .llm_service import LLMService  # You'll need to integrate with your existing LLM service


class QuickieService:
    """Service for creating and running quickies"""
    
    def __init__(
        self, 
        quickie_repo: QuickieRepository,
        template_service: QuickieTemplateService,
        llm_service: LLMService
    ):
        self.repo = quickie_repo
        self.template_service = template_service
        self.llm_service = llm_service
    
    async def create_quickie(
        self, 
        template_name: str, 
        input_params: Dict[str, Any],
        model_override: Optional[str] = None,
        run_immediately: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Quickie:
        """Create a new quickie and optionally run it immediately"""
        # Get the template
        template = self.template_service.get_template(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' not found")
        
        # Validate input params
        validation_errors = self.template_service.validate_input(template_name, input_params)
        if validation_errors:
            error_msg = "; ".join(f"{k}: {v}" for k, v in validation_errors.items())
            raise ValueError(f"Invalid input parameters: {error_msg}")
        
        # Calculate prompt hash
        prompt_hash = template.get_prompt_hash()
        
        # Render the prompt
        prompt_text = template.render_prompt(input_params)
        
        # Determine model to use
        model = model_override or template.model
        
        # Create the quickie record
        quickie = await self.repo.create_quickie(
            template_name=template_name,
            input_params=input_params,
            prompt_text=prompt_text,
            prompt_hash=prompt_hash,
            model=model,
            metadata=metadata or {}
        )
        
        # Run immediately if requested
        if run_immediately:
            # Run in background task to not block the response
            asyncio.create_task(self.run_quickie(quickie.id))
        
        return quickie
    
    async def run_quickie(self, quickie_id: UUID) -> Quickie:
        """Execute a quickie by sending it to the LLM service"""
        # Get the quickie
        quickie = await self.repo.get_by_id(quickie_id)
        if not quickie:
            raise ValueError(f"Quickie with ID {quickie_id} not found")
        
        # Get the template
        template = self.template_service.get_template(quickie.template_name)
        if not template:
            await self.repo.update_status(
                quickie.id, 
                QuickieStatus.ERROR, 
                f"Template '{quickie.template_name}' not found"
            )
            return quickie
        
        # Update status to running
        quickie = await self.repo.update_status(quickie.id, QuickieStatus.RUNNING)
        
        try:
            # Call the LLM service
            llm_response = await self.llm_service.generate_completion(
                prompt=quickie.prompt_text,
                model=quickie.model,
                temperature=template.config.temperature,
                max_tokens=template.config.max_tokens,
                format=template.config.format,
                stop_sequences=template.config.stop_sequences
            )
            
            # Update the quickie with the response
            quickie = await self.repo.update_output(quickie.id, llm_response)
            
        except Exception as e:
            # Handle errors
            await self.repo.update_status(
                quickie.id,
                QuickieStatus.ERROR,
                str(e)
            )
            quickie = await self.repo.get_by_id(quickie_id)
        
        return quickie
    
    async def get_quickie(self, quickie_id: UUID) -> Optional[Quickie]:
        """Get a quickie by ID"""
        return await self.repo.get_by_id(quickie_id)
    
    async def get_by_template(self, template_name: str, limit: int = 100) -> List[Quickie]:
        """Get quickies by template name"""
        return await self.repo.get_by_template(template_name, limit)
    
    async def get_by_prompt_hash(self, prompt_hash: str, limit: int = 100) -> List[Quickie]:
        """Get quickies by prompt hash"""
        return await self.repo.get_by_prompt_hash(prompt_hash, limit)
```

## API Endpoints

Create API endpoints in `src/api/quickie.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from uuid import UUID
import json

from ..services.quickie_service import QuickieService
from ..services.quickie_template_service import QuickieTemplateService
from ..models.quickie import Quickie, QuickieTemplate
from ..dependencies import get_quickie_service, get_template_service
from ..broadcast import BroadcastService, get_broadcast_service


router = APIRouter(prefix="/api/quickies", tags=["quickies"])


@router.post("/", response_model=Quickie)
async def create_quickie(
    template_name: str,
    input_params: Dict[str, Any],
    model_override: Optional[str] = None,
    run_immediately: bool = True,
    background_tasks: BackgroundTasks = None,
    quickie_service: QuickieService = Depends(get_quickie_service),
    broadcast: BroadcastService = Depends(get_broadcast_service)
):
    """Create a new quickie"""
    try:
        quickie = await quickie_service.create_quickie(
            template_name=template_name,
            input_params=input_params,
            model_override=model_override,
            run_immediately=run_immediately
        )
        
        # Broadcast the created quickie
        await broadcast.broadcast(f"quickie.{quickie.id}.created", quickie.dict())
        
        return quickie
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/templates", response_model=List[Dict[str, Any]])
async def get_templates(
    template_service: QuickieTemplateService = Depends(get_template_service)
):
    """Get all available quickie templates"""
    templates = template_service.get_all_templates()
    return [
        {
            "name": t.name,
            "description": t.description,
            "model": t.model,
            "input_schema": {k: v.dict() for k, v in t.input_schema.items()},
            "config": t.config.dict()
        }
        for t in templates
    ]


@router.get("/{quickie_id}", response_model=Quickie)
async def get_quickie(
    quickie_id: UUID,
    quickie_service: QuickieService = Depends(get_quickie_service)
):
    """Get a quickie by ID"""
    quickie = await quickie_service.get_quickie(quickie_id)
    if not quickie:
        raise HTTPException(status_code=404, detail=f"Quickie {quickie_id} not found")
    return quickie


@router.get("/by-template/{template_name}", response_model=List[Quickie])
async def get_by_template(
    template_name: str,
    limit: int = 100,
    quickie_service: QuickieService = Depends(get_quickie_service)
):
    """Get quickies by template name"""
    return await quickie_service.get_by_template(template_name, limit)


@router.get("/by-prompt-hash/{prompt_hash}", response_model=List[Quickie])
async def get_by_prompt_hash(
    prompt_hash: str,
    limit: int = 100,
    quickie_service: QuickieService = Depends(get_quickie_service)
):
    """Get quickies by prompt hash"""
    return await quickie_service.get_by_prompt_hash(prompt_hash, limit)


@router.post("/{quickie_id}/run", response_model=Quickie)
async def run_quickie(
    quickie_id: UUID,
    background_tasks: BackgroundTasks,
    quickie_service: QuickieService = Depends(get_quickie_service),
    broadcast: BroadcastService = Depends(get_broadcast_service)
):
    """Run a pending quickie"""
    quickie = await quickie_service.get_quickie(quickie_id)
    if not quickie:
        raise HTTPException(status_code=404, detail=f"Quickie {quickie_id} not found")
    
    background_tasks.add_task(quickie_service.run_quickie, quickie_id)
    
    await broadcast.broadcast(f"quickie.{quickie_id}.running", {"id": str(quickie_id)})
    
    return quickie
```

## Frontend Components

Create a basic UI component for Quickies in `templates/components/quickie_form.html`:

```html
<div class="box quickie-form" id="quickie-form-{{ template.name }}">
  <h3 class="title is-4">{{ template.description }}</h3>
  
  <form hx-ext="form-json" hx-post="/api/quickies/" hx-swap="none" hx-vals='{"template_name": "{{ template.name }}", "run_immediately": true}'>
    <input type="hidden" name="template_name" value="{{ template.name }}">
    
    {% for name, schema in template.input_schema.items() %}
    <div class="field">
      <label class="label">{{ schema.description }}</label>
      <div class="control">
        {% if schema.type == "string" %}
          {% if schema.enum %}
            <div class="select">
              <select name="input_params.{{ name }}" required="{{ schema.required }}">
                {% for option in schema.enum %}
                <option value="{{ option }}">{{ option }}</option>
                {% endfor %}
              </select>
            </div>
          {% else %}
            <textarea class="textarea" name="input_params.{{ name }}" required="{{ schema.required }}" placeholder="{{ schema.description }}"></textarea>
          {% endif %}
        {% elif schema.type == "blob" %}
          <div class="file has-name">
            <label class="file-label">
              <input class="file-input" type="file" name="input_params.{{ name }}.file">
              <span class="file-cta">
                <span class="file-icon">
                  <i class="fas fa-upload"></i>
                </span>
                <span class="file-label">
                  Choose a file…
                </span>
              </span>
              <span class="file-name">
                No file chosen
              </span>
            </label>
          </div>
        {% endif %}
      </div>
    </div>
    {% endfor %}
    
    <div class="field">
      <div class="control">
        <button class="button is-primary" type="submit">
          Run Quickie
        </button>
      </div>
    </div>
  </form>
  
  <div class="quickie-result is-hidden" id="quickie-result-container">
    <div class="notification is-info">
      <h4 class="title is-5">Result</h4>
      <pre id="quickie-result-output"></pre>
    </div>
  </div>
</div>

<script>
  document.addEventListener('htmx:afterRequest', function(event) {
    if (event.detail.elt.closest('.quickie-form') && event.detail.xhr.status === 200) {
      const response = JSON.parse(event.detail.xhr.responseText);
      const quickieId = response.id;
      
      // Subscribe to SSE events for this quickie
      const source = new EventSource(`/api/sse/subscribe?channels=quickie.${quickieId}.complete,quickie.${quickieId}.error`);
      
      source.addEventListener('quickie.' + quickieId + '.complete', function(e) {
        const data = JSON.parse(e.data);
        const resultContainer = document.getElementById('quickie-result-container');
        const resultOutput = document.getElementById('quickie-result-output');
        resultContainer.classList.remove('is-hidden');
        resultOutput.textContent = JSON.stringify(data.output, null, 2);
        source.close();
      });
      
      source.addEventListener('quickie.' + quickieId + '.error', function(e) {
        const data = JSON.parse(e.data);
        const resultContainer = document.getElementById('quickie-result-container');
        const resultOutput = document.getElementById('quickie-result-output');
        resultContainer.classList.remove('is-hidden');
        resultContainer.querySelector('.notification').classList.remove('is-info');
        resultContainer.querySelector('.notification').classList.add('is-danger');
        resultOutput.textContent = "Error: " + data.error;
        source.close();
      });
    }
  });
</script>
```

## Integration with Broadcast Service

Update your existing `BroadcastService` to handle quickie events in `src/broadcast.py`:

```python
# Add to your existing broadcast service

async def handle_quickie_status_change(self, quickie):
    """Handle status changes for quickies"""
    await self.broadcast(f"quickie.{quickie.id}.{quickie.status.value}", quickie.dict())
```

## Dependencies

Update your dependency injection in `src/dependencies.py`:

```python
from .services.quickie_service import QuickieService
from .services.quickie_template_service import QuickieTemplateService
from .repositories.quickie_repository import QuickieRepository

# Add these functions to your dependencies.py

async def get_quickie_repository():
    return QuickieRepository(get_db_pool())

async def get_template_service():
    return QuickieTemplateService()

async def get_quickie_service():
    return QuickieService(
        quickie_repo=await get_quickie_repository(),
        template_service=await get_template_service(),
        llm_service=await get_llm_service()
    )
```

## CLI Commands

Add CLI commands in `src/cli.py`:

```python
import click
import asyncio
import json
from uuid import UUID

from .services.quickie_service import QuickieService
from .services.quickie_template_service import QuickieTemplateService
from .repositories.quickie_repository import QuickieRepository
from .services.llm_service import LLMService

# Create a quickie command group
@click.group()
def quickie():
    """Commands for managing quickies"""
    pass

@quickie.command()
@click.argument('template_name')
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--model', help='Override the model specified in the template')
def run(template_name, input_file, model):
    """Run a quickie with input from a JSON file"""
    async def _run():
        # Initialize services
        template_service = QuickieTemplateService()
        quickie_repo = QuickieRepository(get_db_pool())
        llm_service = LLMService()
        quickie_service = QuickieService(quickie_repo, template_service, llm_service)
        
        # Load input from file
        with open(input_file, 'r') as f:
            input_params = json.load(f)
        
        # Create and run the quickie
        quickie = await quickie_service.create_quickie(
            template_name=template_name,
            input_params=input_params,
            model_override=model,
            run_immediately=True
        )
        
        click.echo(f"Created quickie with ID: {quickie.id}")
        
        # Wait for completion
        while True:
            quickie = await quickie_service.get_quickie(quickie.id)
            if quickie.status in ('complete', 'error'):
                break
            click.echo(".", nl=False)
            await asyncio.sleep(1)
        
        click.echo("\nStatus: " + quickie.status)
        
        if quickie.status == 'complete':
            click.echo("\nOutput:")
            click.echo(json.dumps(quickie.output, indent=2))
        else:
            click.echo("\nError: " + (quickie.error or "Unknown error"))
    
    asyncio.run(_run())

@quickie.command()
def list_templates():
    """List all available quickie templates"""
    template_service = QuickieTemplateService()
    templates = template_service.get_all_templates()
    
    for template in templates:
        click.echo(f"{template.name}: {template.description}")
        click.echo(f"  Model: {template.model}")
        click.echo("  Input parameters:")
        for name, schema in template.
