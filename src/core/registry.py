from pydantic import BaseModel, ValidationError, Field
from mcp.server.fastmcp.resources import ResourceManager
from mcp.server.fastmcp.prompts import PromptManager
from mcp.server.fastmcp.tools import ToolManager
from fastapi_events.registry.payload_schema import registry

from src.service.logging import logger

from src.core.config_types import (
    SessionTemplate,
    Step,
    MessageStep,
    PromptStep,
    UserInputStep,
    InvokeStep
)


class Schema(BaseModel):
    """A schema that describes an input or output structure."""


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
        self.registry = registry
        self.schema_manager = SchemaManager()



