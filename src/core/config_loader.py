import inspect
import os
import yaml
import jinja2
from jinja2 import meta
from typing import Any, Dict, List, Type, Optional, Union
from pathlib import Path

from mcp.server.fastmcp.prompts.base import PromptArgument

from pydantic import BaseModel
import importlib

from src.core.registry import Registry, Schema, TemplatePrompt
from src.core.config_types import SessionTemplate
from src.service.logging import logger


def register_schema(alias: str = ""):
    """
    Decorator to register a Pydantic model as a schema.

    Args:
        alias: Optional alias for the schema

    Example:
        @register_schema("my_schema")
        class UserProfile(BaseModel):
            name: str
            email: str
    """
    def decorator(cls):
        # Store the registration info on the class for later processing
        setattr(cls, "__register_schema__", True)
        if alias:
            setattr(cls, "__schema_alias__", alias)
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
                # Get custom alias if provided via decorator
                custom_alias = ""
                if is_decorated and hasattr(obj, "__schema_alias__"):
                    custom_alias = getattr(obj, "__schema_alias__", "")

                schema = self._create_schema_from_model(obj, custom_alias)
                if schema:
                    self.registry.add_schema(schema)
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

    def _create_schema_from_model(self, model_class: Type[BaseModel], custom_alias: str = "") -> Optional[Schema]:
        """
        Create a Schema object from a Pydantic model class.

        Args:
            model_class: The Pydantic model class to convert
            custom_alias: Optional custom description to override the class docstring

        Returns:
            A Schema object or None if conversion fails
        """
        try:
            # Get the model's JSON schema
            json_schema = model_class.model_json_schema()

            # Use docstring
            description = inspect.getdoc(model_class) or ""
                
            # remove pydantic class description, if exists
            if 'A base class for creating Pydantic models.' in description:
                description = ""

            # Create and return the Schema
            return Schema(
                name=custom_alias or model_class.__name__,
                json_schema=json_schema,
                description=description,
                source_class=f"{model_class.__module__}.{model_class.__name__}"
            )
        except Exception as e:
            logger.error(f"Failed to create schema from {model_class.__name__}: {str(e)}")
            return None


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
            qualified_name = f"{alias}/{filename}"

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
                self.registry.add_prompt(qualified_name, prompt)
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

class SessionTemplateLoader:
    """
    Loads session templates from YAML files and hydrates SessionTemplate Pydantic models.
    """

    def __init__(self, registry: Registry):
        """
        Initialize the session template loader with a registry.

        Args:
            registry: The registry to populate with session templates
        """
        self.registry = registry

    def validate_template(self, template_name: str, template_data: Dict[str, Any]) -> tuple[bool, Optional[SessionTemplate], List[str]]:
        """
        Validate a session template against the schema.

        Args:
            template_name: Name of the template
            template_data: Dictionary of template data

        Returns:
            Tuple of (is_valid, template_object, error_messages)
        """
        errors = []
        template_obj = None

        try:
            # Try to create a SessionTemplate object
            template_data['name'] = template_name
            template_obj = SessionTemplate(**template_data)
            return True, template_obj, []
        except Exception as e:
            # If validation fails, collect all errors
            if hasattr(e, 'errors'):
                for error in e.errors():
                    # Format error message with location and message
                    location = ".".join(str(loc) for loc in error["loc"])
                    message = error["msg"]
                    errors.append(f"{location}: {message}")
            else:
                errors.append(str(e))

            return False, None, errors

    def load_from_file(self, file_path: Union[str, Path]) -> Dict[str, SessionTemplate]:
        """
        Load session templates from a YAML file.

        Args:
            file_path: Path to the YAML file containing session templates

        Returns:
            Dictionary of template name to SessionTemplate objects
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"Session template file not found: {file_path}")
            return {}

        logger.info(f"Loading session templates from file: {file_path}")

        try:
            # Load the YAML file
            with open(file_path, 'r') as f:
                yaml_content = yaml.safe_load(f)

            if not yaml_content or 'session_templates' not in yaml_content:
                logger.warning(f"No session_templates found in {file_path}")
                return {}

            templates_dict = yaml_content['session_templates']
            loaded_templates = {}
            validation_errors = {}

            # Process each template
            for template_name, template_data in templates_dict.items():
                is_valid, template_obj, errors = self.validate_template(template_name, template_data)

                if is_valid:
                    loaded_templates[template_name] = template_obj
                    logger.info(f"Loaded session template: {template_name}")
                else:
                    validation_errors[template_name] = errors
                    error_list = "\n  - ".join([""] + errors)
                    logger.error(f"Failed to validate session template '{template_name}':{error_list}")

            # If there were validation errors, print a summary
            if validation_errors:
                logger.error(f"Validation failed for {len(validation_errors)} templates in {file_path}")
                for template_name, errors in validation_errors.items():
                    error_list = "\n  - ".join([""] + errors)
                    logger.error(f"Template '{template_name}' has {len(errors)} errors:{error_list}")

            logger.info(f"Loaded {len(loaded_templates)} session templates from {file_path}")
            return loaded_templates
        except Exception as e:
            logger.error(f"Failed to load session templates from {file_path}: {str(e)}")
            return {}

    def load_from_directory(self, directory: Union[str, Path]) -> Dict[str, SessionTemplate]:
        """
        Load all session templates from YAML files in a directory.

        Args:
            directory: Directory path containing YAML files

        Returns:
            Dictionary of template name to SessionTemplate objects
        """
        directory = Path(directory)
        if not directory.is_dir():
            logger.error(f"Directory not found: {directory}")
            return {}

        logger.info(f"Loading session templates from directory: {directory}")

        all_templates = {}
        yaml_extensions = ['.yaml', '.yml']

        # Scan for all YAML files in the directory
        for file_path in directory.iterdir():
            if file_path.suffix.lower() in yaml_extensions:
                templates = self.load_from_file(file_path)
                all_templates.update(templates)

        logger.info(f"Loaded a total of {len(all_templates)} session templates from directory {directory}")
        return all_templates

    def register_templates(self, templates: Dict[str, SessionTemplate]) -> List[str]:
        """
        Register loaded session templates in the registry.

        Args:
            templates: Dictionary of template name to SessionTemplate objects

        Returns:
            List of registered template names
        """
        # This is a placeholder for future registry integration
        # Currently, the registry doesn't have a dedicated place for session templates
        # You might want to add a session_template_manager to the Registry class

        registered_names = []
        for name, template in templates.items():
            # Future: self.registry.session_template_manager.add_template(name, template)
            registered_names.append(name)

        return registered_names


