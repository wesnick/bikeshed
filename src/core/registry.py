from typing import List
from pydantic import BaseModel, ValidationError, Field
from mcp.server.fastmcp.resources import ResourceManager
from mcp.server.fastmcp.prompts import (
    PromptManager,
    Prompt,
)
from mcp.server.fastmcp.tools import ToolManager
from fastapi_events.registry.payload_schema import registry as event_registry

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


class SchemaManager:
    def __init__(self, warn_on_duplicate_schemas: bool = True):
        self._schemas: dict[str, Schema] = {}
        self.warn_on_duplicate_schemas = warn_on_duplicate_schemas

    def schema(self, name: str) -> Schema | None:
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


class Registry:
    def __init__(self):
        self.resource_manager = ResourceManager()
        self.prompt_manager = PromptManager()
        self.tool_manager = ToolManager()
        self.event_registry = event_registry
        self.schema_manager = SchemaManager()

    def get_schema(self, name: str) -> Schema | None:
        """Get a schema by name."""
        return self.schema_manager.schema(name)

    def list_schemas(self) -> list[Schema]:
        """List all registered schemas."""
        return self.schema_manager.list_schemas()



