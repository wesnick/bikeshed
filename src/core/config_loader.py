import inspect
import os
import sys
import jinja2
from jinja2 import meta
from typing import Any, Dict, List, Type, Optional, Callable

from mcp.server.fastmcp.prompts.base import PromptArgument

from pydantic import BaseModel
import importlib
from functools import wraps

from src.core.registry import Registry, Schema, TemplatePrompt
from src.service.logging import logger


def register_schema(description: str = ""):
    """
    Decorator to register a Pydantic model as a schema.

    Args:
        description: Optional description for the schema

    Example:
        @register_schema("A user profile schema")
        class UserProfile(BaseModel):
            name: str
            email: str
    """
    def decorator(cls):
        # Store the registration info on the class for later processing
        setattr(cls, "__register_schema__", True)
        if description:
            setattr(cls, "__schema_description__", description)
        return cls
    return decorator


class SchemaLoader:
    """
    Loads Pydantic models from specified modules and registers them as schemas in the Registry.
    """

    def __init__(self, registry: Registry):
        """
        Initialize the schema loader with a registry.

        Args:
            registry: The registry to populate with schemas
        """
        self.registry = registry


class TemplateLoader:
    """
    Loads Jinja templates from specified directories and registers them as prompts in the Registry.
    """

    def __init__(self, registry: Registry, jinja_env: jinja2.Environment):
        """
        Initialize the template loader with a registry and Jinja environment.

        Args:
            registry: The registry to populate with prompts
            jinja_env: The Jinja environment to use for parsing templates
        """
        self.registry = registry
        self.jinja_env = jinja_env

    def load_from_directory(self, directory: str, alias: str) -> List[TemplatePrompt]:
        """
        Load all Jinja templates from a directory and register them as prompts.

        Args:
            directory: The directory path to load templates from
            alias: The namespace/alias for templates in this directory

        Returns:
            List of registered prompts
        """
        if not os.path.isdir(directory):
            logger.error(f"Directory not found: {directory}")
            return []

        logger.info(f"Loading templates from directory {directory} with alias {alias}")

        prompts = []

        # Scan for all .j2 files in the directory
        for filename in os.listdir(directory):
            if not filename.endswith('.j2'):
                continue

            template_path = os.path.join(directory, filename)
            template_name = os.path.splitext(filename)[0]
            qualified_name = f"{alias}/{template_name}"

            try:
                # Read the template file
                with open(template_path, 'r') as f:
                    template_content = f.read()

                # Parse the template to extract variables
                ast = self.jinja_env.parse(template_content)
                variables = meta.find_undeclared_variables(ast)

                # Convert parameters to PromptArguments
                arguments = []
                for param_name in variables:
                    arguments.append(
                        PromptArgument(
                            name=param_name,
                            required=True,
                        )
                    )


                def render_fn(**kwargs):
                    # Create a template environment
                    # Render the template with the provided arguments
                    return self.jinja_env.from_string(template_content).render(**kwargs)

                # Create a prompt object
                prompt = TemplatePrompt(
                    name=qualified_name,
                    template=qualified_name,
                    description=f"Template from {qualified_name}",
                    arguments=arguments,
                    fn=render_fn
                )

                # Register the prompt
                self.registry.prompt_manager.add_prompt(prompt)
                prompts.append(prompt)

                logger.info(f"Loaded template: {qualified_name} with variables: {arguments}")

            except Exception as e:
                logger.error(f"Failed to load template {template_path}: {str(e)}")

        logger.info(f"Loaded {len(prompts)} templates from directory {directory} with alias {alias}")
        return prompts

    def load_from_directories(self, directory_configs: List[Dict[str, str]]) -> List[TemplatePrompt]:
        """
        Load templates from multiple directories.

        Args:
            directory_configs: List of dicts with 'path' and 'alias' keys

        Returns:
            List of all registered prompts
        """
        all_prompts = []
        for config in directory_configs:
            if 'path' not in config or 'alias' not in config:
                logger.error(f"Invalid directory config: {config}, must contain 'path' and 'alias'")
                continue

            prompts = self.load_from_directory(config['path'], config['alias'])
            all_prompts.extend(prompts)

        return all_prompts

    def load_from_module(self, module_name: str, scan_all: bool = False) -> List[Schema]:
        """
        Load all Pydantic models from a module and register them as schemas.

        This will load:
        1. Models explicitly decorated with @register_schema
        2. All BaseModel subclasses if scan_all=True

        Args:
            module_name: The name of the module to load schemas from
            scan_all: If True, scan all BaseModel subclasses, otherwise only decorated ones

        Returns:
            List of registered schemas
        """
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            logger.error(f"Failed to import module: {module_name}")
            return []

        schemas = []

        # Find all classes in the module
        for name, obj in inspect.getmembers(module):
            if not inspect.isclass(obj) or obj.__module__ != module_name:
                continue

            # Check if class is decorated with register_schema
            is_decorated = hasattr(obj, "__register_schema__") and getattr(obj, "__register_schema__")

            # Check if class is a BaseModel subclass (for scan_all mode)
            is_pydantic_model = (issubclass(obj, BaseModel) and obj != BaseModel)

            if is_decorated or (scan_all and is_pydantic_model):
                # Get custom description if provided via decorator
                custom_description = ""
                if is_decorated and hasattr(obj, "__schema_description__"):
                    custom_description = getattr(obj, "__schema_description__", "")

                schema = self._create_schema_from_model(obj, custom_description)
                if schema:
                    self.registry.schema_manager.add_schema(schema)
                    schemas.append(schema)

        logger.info(f"Loaded {len(schemas)} schemas from module {module_name}")
        return schemas

    def load_from_modules(self, module_names: List[str], scan_all: bool = False) -> List[Schema]:
        """
        Load schemas from multiple modules.

        Args:
            module_names: List of module names to load schemas from
            scan_all: If True, scan all BaseModel subclasses, otherwise only decorated ones

        Returns:
            List of all registered schemas
        """
        all_schemas = []
        for module_name in module_names:
            schemas = self.load_from_module(module_name, scan_all)
            all_schemas.extend(schemas)

        return all_schemas

    def _create_schema_from_model(self, model_class: Type[BaseModel], custom_description: str = "") -> Optional[Schema]:
        """
        Create a Schema object from a Pydantic model class.

        Args:
            model_class: The Pydantic model class to convert
            custom_description: Optional custom description to override the class docstring

        Returns:
            A Schema object or None if conversion fails
        """
        try:
            # Get the model's JSON schema
            json_schema = model_class.model_json_schema()

            # Use custom description if provided, otherwise use docstring
            description = custom_description
            if not description:
                description = inspect.getdoc(model_class) or ""

                # remove pydantic class description, if exists
                if 'A base class for creating Pydantic models.' in description:
                    description = ""

            # Create and return the Schema
            return Schema(
                name=model_class.__name__,
                json_schema=json_schema,
                description=description,
                source_class=f"{model_class.__module__}.{model_class.__name__}"
            )
        except Exception as e:
            logger.error(f"Failed to create schema from {model_class.__name__}: {str(e)}")
            return None


