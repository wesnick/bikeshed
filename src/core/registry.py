from typing import List, Any, Dict

from mcp import StdioServerParameters
from pydantic import BaseModel, ValidationError, Field
from mcp.server.fastmcp.resources import ResourceManager
from mcp.server.fastmcp.prompts import Prompt
from mcp.server.fastmcp.tools import Tool
from mcp.server.fastmcp.resources import Resource, ResourceTemplate
from fastapi_events.registry.payload_schema import registry as event_registry

from src.core.config_types import SessionTemplate
from src.service.logging import logger

class TemplatePrompt(Prompt):
    """A prompt that can be rendered with arguments."""
    template: str = Field(description="Path to template, prefixed with alias")


class Schema(BaseModel):
    """A schema that describes an input or output structure."""
    name: str
    json_schema: dict
    description: str = ""
    source_class: str = ""

class Registry:
    def __init__(self, warn_on_duplicate: bool = True):
        self._schemas: dict[str, Schema] = {}
        self._resources: dict[str, Resource] = {}
        self._templates: dict[str, ResourceTemplate] = {}
        self._prompts: dict[str, Prompt] = {}
        self._tools: dict[str, Tool] = {}
        self.event_registry = event_registry
        self.session_templates: dict[str, SessionTemplate] = {}
        self.mcp_servers: dict[str, StdioServerParameters] = {}
        self.warn_on_duplicate_schemas = warn_on_duplicate

    def get_schema(self, name: str) -> Schema | None:
        """Get schema by name."""
        return self._schemas.get(name)

    def list_schemas(self) -> list[Schema]:
        """List all registered schemas."""
        return list(self._schemas.values())

    def add_schema(
        self,
        schema: Schema,
    ) -> Schema:
        """Add a schema to the manager."""

        # Check for duplicates
        existing = self._schemas.get(schema.name)
        if existing:
            if self.warn_on_duplicate_schemas:
                logger.warning(f"Schema already exists: {schema.name}")
            return existing

        self._schemas[schema.name] = schema
        return schema


    def add_session_template(self, name: str, template: SessionTemplate):
        """Add a session template to the registry."""
        self.session_templates[name] = template

    def get_session_template(self, name: str):
        """Get a session template by name."""
        return self.session_templates.get(name)




