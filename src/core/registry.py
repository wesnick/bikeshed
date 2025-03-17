from typing import List, Any, Dict

from mcp import StdioServerParameters
from pydantic import BaseModel, ValidationError, Field
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
        self._resource_templates: dict[str, ResourceTemplate] = {}
        self.prompts: dict[str, Prompt] = {}
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

    # Resource methods
    def get_resource(self, name: str) -> Resource | None:
        """Get resource by URI."""
        return self._resources.get(name)

    def list_resources(self) -> list[Resource]:
        """List all registered resources."""
        return list(self._resources.values())

    def add_resource(self, resource: Resource) -> Resource:
        """Add a resource to the registry."""
        # Check for duplicates
        existing = self._resources.get(resource.name)
        if existing:
            if self.warn_on_duplicate_schemas:
                logger.warning(f"Resource already exists: {resource.name}")
            return existing

        self._resources[resource.name] = resource
        return resource

    # Resource template methods
    def get_resource_template(self, uri_template: str) -> ResourceTemplate | None:
        """Get resource template by URI template."""
        return self._resource_templates.get(uri_template)

    def list_resource_templates(self) -> list[ResourceTemplate]:
        """List all registered resource templates."""
        return list(self._resource_templates.values())

    def add_resource_template(self, uri_template: str, template: ResourceTemplate) -> ResourceTemplate:
        """Add a resource template to the registry."""
        # Check for duplicates
        existing = self._resource_templates.get(uri_template)
        if existing:
            if self.warn_on_duplicate_schemas:
                logger.warning(f"Resource template already exists: {uri_template}")
            return existing

        self._resource_templates[uri_template] = template
        return template

    # Prompt methods
    def get_prompt(self, name: str) -> Prompt | None:
        """Get prompt by name."""
        return self.prompts.get(name)

    def list_prompts(self) -> list[Prompt]:
        """List all registered prompts."""
        return list(self.prompts.values())

    def add_prompt(self, name: str, prompt: Prompt) -> Prompt:
        """Add a prompt to the registry."""
        # Check for duplicates
        existing = self.prompts.get(name)
        if existing:
            if self.warn_on_duplicate_schemas:
                logger.warning(f"Prompt already exists: {name}")
            return existing

        self.prompts[name] = prompt
        return prompt

    # Tool methods
    def get_tool(self, name: str) -> Tool | None:
        """Get tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def add_tool(self, name: str, tool: Tool) -> Tool:
        """Add a tool to the registry."""
        # Check for duplicates
        existing = self._tools.get(name)
        if existing:
            if self.warn_on_duplicate_schemas:
                logger.warning(f"Tool already exists: {name}")
            return existing

        self._tools[name] = tool
        return tool


    def add_session_template(self, name: str, template: SessionTemplate):
        """Add a session template to the registry."""
        # Check for duplicates
        existing = self.session_templates.get(name)
        if existing:
            if self.warn_on_duplicate_schemas:
                logger.warning(f"Session template already exists: {name}")
            return existing

        self.session_templates[name] = template

    def get_session_template(self, name: str):
        """Get a session template by name."""
        return self.session_templates.get(name)




