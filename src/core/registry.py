import asyncio
from typing import Set

from mcp import StdioServerParameters
from pydantic import BaseModel, Field
from mcp.server.fastmcp.prompts import Prompt
from mcp.server.fastmcp.tools import Tool
from mcp.server.fastmcp.resources import Resource, ResourceTemplate
from fastapi_events.registry.payload_schema import registry as event_registry
from watchfiles import awatch

from src.core.config_types import SessionTemplate
from src.service.logging import logger

class TemplatePrompt(Prompt):
    """A prompt that can be rendered with arguments."""
    template: str = Field(description="Path to template, prefixed with alias")
    template_content: str = Field(default="", description="Raw template content")
    template_path: str = Field(default="", description="Full filesystem path to template")


class Schema(BaseModel):
    """A schema that describes an input or output structure."""
    name: str
    json_schema: dict
    description: str = ""
    source_class: str = ""

class Registry:
    def __init__(self, warn_on_duplicate: bool = True):
        self.schemas: dict[str, Schema] = {}
        self.resources: dict[str, Resource] = {}
        self.resource_templates: dict[str, ResourceTemplate] = {}
        self.prompts: dict[str, Prompt] = {}
        self.tools: dict[str, Tool] = {}
        self.event_registry = event_registry
        self.session_templates: dict[str, SessionTemplate] = {}
        self.mcp_servers: dict[str, StdioServerParameters] = {}
        self.warn_on_duplicate_schemas = warn_on_duplicate
        self.active_root_watchers: dict[str, asyncio.Task] = {}
        self.watched_root_paths: Set[str] = set()
        self.watcher_task = None  # Store the watcher task here

    def get_schema(self, name: str) -> Schema | None:
        """Get schema by name."""
        return self.schemas.get(name)

    def list_schemas(self) -> list[Schema]:
        """List all registered schemas."""
        return list(self.schemas.values())

    def add_schema(
        self,
        schema: Schema,
    ) -> Schema:
        """Add a schema to the manager."""

        # Check for duplicates
        existing = self.schemas.get(schema.name)
        if existing:
            if self.warn_on_duplicate_schemas:
                logger.warning(f"Schema already exists: {schema.name}")
            return existing

        self.schemas[schema.name] = schema
        return schema

    # Resource methods
    def get_resource(self, name: str) -> Resource | None:
        """Get resource by URI."""
        return self.resources.get(name)

    def list_resources(self) -> list[Resource]:
        """List all registered resources."""
        return list(self.resources.values())

    def add_resource(self, resource: Resource) -> Resource:
        """Add a resource to the registry."""
        # Check for duplicates
        existing = self.resources.get(resource.name)
        if existing:
            if self.warn_on_duplicate_schemas:
                logger.warning(f"Resource already exists: {resource.name}")
            return existing

        self.resources[resource.name] = resource
        return resource

    # Resource template methods
    def get_resource_template(self, uri_template: str) -> ResourceTemplate | None:
        """Get resource template by URI template."""
        return self.resource_templates.get(uri_template)

    def list_resource_templates(self) -> list[ResourceTemplate]:
        """List all registered resource templates."""
        return list(self.resource_templates.values())

    def add_resource_template(self, uri_template: str, template: ResourceTemplate) -> ResourceTemplate:
        """Add a resource template to the registry."""
        # Check for duplicates
        existing = self.resource_templates.get(uri_template)
        if existing:
            if self.warn_on_duplicate_schemas:
                logger.warning(f"Resource template already exists: {uri_template}")
            return existing

        self.resource_templates[uri_template] = template
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
        return self.tools.get(name)

    def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return list(self.tools.values())

    def add_tool(self, name: str, tool: Tool) -> Tool:
        """Add a tool to the registry."""
        # Check for duplicates
        existing = self.tools.get(name)
        if existing:
            if self.warn_on_duplicate_schemas:
                logger.warning(f"Tool already exists: {name}")
            return existing

        self.tools[name] = tool
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

    async def watch_directory(self, directory_path: str):
        """Watch a directory for changes."""
        from src.service.logging import logger
        try:
            async for changes in awatch(directory_path):
                for change_type, file_path in changes:
                    logger.info(f"Root: change detected in {directory_path}: {change_type} - {file_path}")
                    # Process the change here
        except Exception as e:
            logger.error(f"Root: error watching directory {directory_path}: {e}")
        finally:
            # Clean up when the task ends for any reason
            if directory_path in self.watched_root_paths:
                self.watched_root_paths.remove(directory_path)
            if directory_path in self.active_root_watchers:
                del self.active_root_watchers[directory_path]
            logger.info(f"Root: stopped watching {directory_path}")

    async def stop_watching(self):
        """Stop watching all directories."""
        from src.service.logging import logger

        if self.watcher_task:
            self.watcher_task.cancel()
            try:
                await self.watcher_task  # Ensure task is fully cleaned up
            except asyncio.CancelledError:
                logger.info("File watcher task cancelled successfully.")
        else:
            logger.info("No file watcher task to cancel.")

        self.active_root_watchers.clear()
        self.watched_root_paths.clear()
