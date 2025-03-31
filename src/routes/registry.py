import yaml
from pathlib import Path
from fastapi import APIRouter, Depends, Request, Form
from typing import List
from pydantic import BaseModel
from src.service.mcp_client import MCPClient
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

@router.post("/models/save")
@jinja.hx('components/registry/models_list.html.j2')
async def save_models(request: Request, selection: ModelsSelectionRequest) -> dict:
    """Save selected models to config/models.yaml file."""
    registry = request.app.state.registry

    # Get the selected models
    selected_models = {}
    for model_id in selection.selected_models.keys():
        if model_id in registry.models:
            model = registry.models[model_id]
            selected_models[model_id] = {
                "id": model.id,
                "name": model.name,
                "provider": model.provider,
                "context_length": model.context_length,
                "input_cost": model.input_cost,
                "output_cost": model.output_cost,
                "capabilities": list(model.capabilities) if model.capabilities else [],
                "metadata": model.metadata
            }

    # Save to YAML file
    config_path = Path("config/models.yaml")
    with open(config_path, "w") as f:
        yaml.dump({"models": selected_models}, f, default_flow_style=False, sort_keys=False)

    # Return the updated models list
    return {"models": registry.models}
