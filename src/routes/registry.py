import yaml
from pathlib import Path
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.service.mcp_client import MCPClient
from src.service.logging import logger
from src.dependencies import get_jinja, get_mcp_client

router = APIRouter(prefix="/registry", tags=["registry"])

jinja = get_jinja()

class ModelsSelectionRequest(BaseModel):
    selected_models: dict[str, bool]


@router.get("/")
@jinja.hx('components/registry/sidebar_widget.html.j2')
async def registry_component(request: Request) -> dict:
    """This route serves the registry sidebar widget for htmx requests."""
    registry = request.app.state.registry

    return {
        "prompts": registry.prompts,
        "tools": registry.tools,
        "resources": registry.resources,
        "resource_templates": registry.resource_templates,
        "schemas": registry.schemas,
        "mcp_servers": registry.mcp_servers,
        "models": registry.models,
    }

@router.get("/prompts")
@jinja.hx('components/registry/prompts_list.html.j2')
async def registry_prompts(request: Request) -> dict:
    """This route serves the prompts listing page."""
    registry = request.app.state.registry
    return {"prompts": registry.prompts}

@router.get("/tools")
@jinja.hx('components/registry/tools_list.html.j2')
async def registry_tools(request: Request) -> dict:
    """This route serves the tools listing page."""
    registry = request.app.state.registry
    return {"tools": registry.tools}

@router.get("/resources")
@jinja.hx('components/registry/resources_list.html.j2')
async def registry_resources(request: Request) -> dict:
    """This route serves the resources listing page."""
    registry = request.app.state.registry
    return {"resources": registry.resources}

@router.get("/resource-templates")
@jinja.hx('components/registry/resource_templates_list.html.j2')
async def registry_resource_templates(request: Request) -> dict:
    """This route serves the resource templates listing page."""
    registry = request.app.state.registry
    return {"resource_templates": registry.resource_templates}

@router.get("/schemas")
@jinja.hx('components/registry/schemas_list.html.j2')
async def registry_schemas(request: Request) -> dict:
    """This route serves the schemas listing page."""
    registry = request.app.state.registry
    return {"schemas": registry.schemas}

@router.get("/mcp-servers")
@jinja.hx('components/registry/mcp_servers_list.html.j2')
async def registry_mcp_servers(request: Request, mcp_client: MCPClient = Depends(get_mcp_client)) -> dict:
    """This route serves the MCP servers listing page."""
    registry = request.app.state.registry

    server_status = {}
    for name, server in mcp_client.sessions.items():
        server_status[name] = True

    return {
        "mcp_servers": registry.mcp_servers,
        "server_status": server_status
    }

@router.get("/models")
@jinja.hx('components/registry/models_list.html.j2')
async def registry_models(request: Request) -> dict:
    """This route serves the LLM models listing page."""
    registry = request.app.state.registry
    return {"models": registry.models}


# Define the fields to be saved in models.yaml
# Excludes tracking fields like 'selected', 'upstream_present', 'overrides'
MODEL_SAVE_FIELDS = [
    "id", "name", "provider", "context_length",
    "input_cost", "output_cost", "capabilities", "metadata"
]

@router.post("/models/save")
@jinja.hx('components/registry/models_list.html.j2')
async def save_models(request: Request, selected_models: ModelsSelectionRequest) -> dict:
    """Save selected models to config/models.yaml file."""
    registry = request.app.state.registry

    models_to_save = {}
    # Iterate through all models currently in the registry
    for model_id, model in registry.models.items():
        if model_id in selected_models.selected_models.keys():
            # If the model is selected in the form, prepare it for saving
            model_data = {}
            for field in MODEL_SAVE_FIELDS:
                value = getattr(model, field, None)
                if field == "capabilities" and isinstance(value, set):
                    # Convert capabilities set to sorted list for consistent YAML output
                    value = sorted(list(value))
                if value is not None: # Only save fields that have a value
                     # Special handling for default costs if they are 0.0 and not overridden
                    if field in ["input_cost", "output_cost"] and value == 0.0:
                        # Check if this cost was explicitly set in overrides or config
                        is_overridden = field in model.overrides
                        is_in_config_only = not model.upstream_present and field in model.model_dump(exclude={'selected', 'upstream_present', 'overrides'})

                        if not is_overridden and not is_in_config_only:
                             # Don't save default 0.0 cost unless it was explicitly set
                             continue

                    model_data[field] = value

            # Use the model's ID as the key in the YAML dictionary
            models_to_save[model_id] = model_data
            # Update the model's selected status in the live registry
            model.selected = True
        else:
             # If the model is not selected in the form, mark it as not selected in the live registry
             model.selected = False


    # Save the selected models data to YAML file
    config_path = Path("config/models.yaml")
    try:
        with open(config_path, "w") as f:
            yaml.dump({"models": models_to_save}, f, default_flow_style=False, sort_keys=False, indent=2)
        logger.info(f"Successfully saved {len(models_to_save)} models to {config_path}")
    except Exception as e:
        logger.error(f"Failed to save models to {config_path}: {str(e)}")
        # Consider returning an error response or message to the user

    # Return the updated models list (reflecting the new 'selected' status)
    # The template will re-render based on the registry's current state
    return {"models": registry.models}
