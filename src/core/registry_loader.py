import yaml
from typing import Dict, List, Any, Optional
import importlib.util

from mcp import StdioServerParameters

from src.core.registry import Registry
from src.core.config_loader import SchemaLoader, TemplateLoader, SessionTemplateLoader
from src.core.config_types import Model
from src.service.logging import logger



class RegistryBuilder:
    """
    Builds and populates a Registry instance from bs.yaml configuration.
    Factory pattern for creating a populated Registry singleton.
    """

    def __init__(self, registry: Registry, config_path: str = "config/bs.yaml"):
        """
        Initialize the registry builder with a Registry instance and path to the configuration file.

        Args:
            registry: The Registry instance to populate
            config_path: Path to the bs.yaml configuration file
        """
        self.config_path = config_path
        self.registry = registry
        self.config = {}

    def _load_config(self) -> Dict[str, Any]:
        """
        Load the configuration from the bs.yaml file.

        Returns:
            Dictionary containing the configuration
        """
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration from {self.config_path}: {str(e)}")
            return {}

    def _load_schemas(self, schema_modules: List[str]) -> None:
        """
        Load schemas from the specified modules.

        Args:
            schema_modules: List of module names to load schemas from
        """
        if not schema_modules:
            logger.warning("No schema modules specified in configuration")
            return

        logger.info(f"Loading schemas from modules: {schema_modules}")
        schema_loader = SchemaLoader(self.registry)
        for module_name in schema_modules:
            try:
                schema_loader.load_from_module(module_name)
            except Exception as e:
                logger.error(f"Failed to load schemas from module {module_name}: {str(e)}")

    def _load_templates(self, template_paths: Dict[str, str]) -> None:
        """
        Load templates from the specified paths.

        Args:
            template_paths: Dictionary mapping aliases to template directories
        """
        if not template_paths:
            logger.warning("No template paths specified in configuration")
            return
        from src.dependencies import get_jinja

        logger.info(f"Loading templates from paths: {template_paths}")
        template_loader = TemplateLoader(self.registry, get_jinja().templates.env)
        for alias, path in template_paths.items():
            try:
                template_loader.load_from_directory(path, alias)
            except Exception as e:
                logger.error(f"Failed to load templates from {path} with alias {alias}: {str(e)}")

    def _load_mcp_servers(self, mcp_servers: Dict[str, Dict[str, Any]]) -> None:
        """
        Load MCP server configurations.

        Args:
            mcp_servers: Dictionary mapping server names to server configurations
        """
        if not mcp_servers:
            logger.warning("No MCP servers specified in configuration")
            return

        logger.info(f"Loading MCP server configurations: {list(mcp_servers.keys())}")
        for name, config in mcp_servers.items():
            try:
                # Create StdioServerParameters from config
                server_params = StdioServerParameters(
                    command=config.get('command'),
                    args=config.get('args', []),
                    env=config.get('env', {})
                )
                self.registry.mcp_servers[name] = server_params
                logger.info(f"Loaded MCP server configuration: {name}")
            except Exception as e:
                logger.error(f"Failed to load MCP server configuration for {name}: {str(e)}")

    def _load_session_templates(self, templates_dir: str = "config") -> None:
        """
        Load session templates from the specified directory.

        Args:
            templates_dir: Directory containing session template YAML files
        """
        logger.info(f"Loading session templates from directory: {templates_dir}")
        template_loader = SessionTemplateLoader(self.registry)
        try:
            templates = template_loader.load_from_directory(templates_dir)
            for name, template in templates.items():
                self.registry.add_session_template(name, template)
            logger.info(f"Loaded {len(templates)} session templates")
        except Exception as e:
            logger.error(f"Failed to load session templates from {templates_dir}: {str(e)}")

    def _load_models(self) -> None:
        """
        Load available LLM models from Ollama and LiteLLM.
        """
        import litellm.utils
        import ollama
        logger.info("Loading available LLM models")

        # Load models from Ollama if available
        try:
            ollama_models = ollama.list()
            for model_data in ollama_models['models']:
                logger.warning(f"ollama model_data {model_data}")
                model_info = litellm.utils.get_model_info('ollama_chat/' + model_data['model'])
                model = self._load_model_from_litellm(model_info)
                # Fix ollama model id to use "chat" endpoint
                model.id = 'ollama_chat/' + model_data['model']
                self.registry.add_model(model)
                logger.debug(f"Added Ollama model: {model.name}")
        except Exception as e:
            logger.error(f"Failed to load Ollama models: {str(e)}")

        # Load models from LiteLLM if available
        try:
            import litellm.utils
            litellm_models = litellm.utils.get_valid_models()
            for model_name in litellm_models:
                try:
                    model_info = litellm.utils.get_model_info(model_name)
                except Exception as e:
                    continue

                model = self._load_model_from_litellm(model_info)
                self.registry.add_model(model)
                logger.debug(f"Added LiteLLM model: {model.name}")

        except Exception as e:
            logger.error(f"Failed to load LiteLLM models: {str(e)}")

    async def build(self) -> Registry:
        """
        Build and populate the registry with configuration.

        Returns:
            The populated Registry instance
        """
        # Load the configuration file
        self.config = self._load_config()
        if not self.config:
            logger.error("Failed to load configuration, using empty registry")
            return self.registry

        # Load schemas
        schema_modules = self.config.get('schema_modules', [])
        self._load_schemas(schema_modules)

        # Load templates
        template_paths = self.config.get('template_paths', {})
        self._load_templates(template_paths)

        # Load MCP servers
        mcp_servers = self.config.get('mcp_servers', {})
        self._load_mcp_servers(mcp_servers)

        # Connect to MCP servers
        await self.connect_mcp_servers()

        # Load session templates
        templates_dir = self.config.get('session_templates_dir', 'config')
        self._load_session_templates(templates_dir)

        # Load available LLM models
        self._load_models()

        logger.info("Registry building completed")
        return self.registry

    async def connect_mcp_servers(self) -> None:
        """
        Connect to all configured MCP servers.
        """
        logger.info("Connecting to MCP servers")
        from src.dependencies import get_mcp_client
        for name, server_params in self.registry.mcp_servers.items():
            try:
                # Get the singleton mcp_client instance
                async for mcp_client in get_mcp_client():
                    await mcp_client.connect_to_server(name, server_params)

                    session = await mcp_client.get_session(name)
                    if session and mcp_client.sessions.get(name) and mcp_client.sessions.get(name).has_tools():
                        tools_result = await session.list_tools()
                        for tool in tools_result.tools:
                            self.registry.add_tool(tool.name, tool)
                            logger.debug(f"Added tool: {tool.name}")
                    if session and mcp_client.sessions.get(name) and mcp_client.sessions.get(name).has_prompts():
                        prompts_result = await session.list_prompts()
                        for prompt in prompts_result.prompts:
                            self.registry.add_prompt(prompt.name, prompt)
                            logger.debug(f"Added prompt: {prompt.name}")
                    if session and mcp_client.sessions.get(name) and mcp_client.sessions.get(name).has_resources():
                        resources_result = await session.list_resources()
                        for resource in resources_result.resources:
                            self.registry.add_resource(resource)
                            logger.debug(f"Added resource: {resource.uri}")
                        templates_result = await session.list_resource_templates()
                        for template in templates_result.resourceTemplates:
                            self.registry.add_resource_template(template.uriTemplate, template)
                            logger.debug(f"Added resource template: {template.uriTemplate}")

                    logger.info(f"Connected to MCP server: {name}")
            except Exception as e:
                logger.error(f"Failed to connect to MCP server {name}: {str(e)}")

    def _load_model_from_litellm(self, model_info):

        capabilities = set()
        if model_info.get('supports_system_messages'):
            capabilities.add('system_message')
        if model_info.get('supports_response_schema'):
            capabilities.add('response_schema')
        if model_info.get('supports_tool_choice'):
            capabilities.add('tool_choice')
        if model_info.get('supports_function_calling'):
            capabilities.add('function_calling')
        if model_info.get('supports_vision'):
            capabilities.add('vision')
        if model_info.get('supports_audio_input'):
            capabilities.add('audio_input')
        if model_info.get('supports_audio_output'):
            capabilities.add('audio_output')
        if model_info.get('supports_native_streaming'):
            capabilities.add('native_streaming')
        if model_info.get('supports_parallel_function_calling'):
            capabilities.add('parallel_function_calling')
        if model_info.get('supports_embedding_image_input'):
            capabilities.add('embedding_image_input')
        if model_info.get('supports_pdf_input'):
            capabilities.add('pdf_input')
        if model_info.get('supports_prompt_caching'):
            capabilities.add('prompt_caching')
        if model_info.get('supports_assistant_prefill'):
            capabilities.add('assistant_prefill')
        if model_info.get('mode') == 'chat':
            capabilities.add('chat')
        if model_info.get('mode') == 'completion':
            capabilities.add('completion')
        if model_info.get('mode') == 'embedding':
            capabilities.add('embedding')
        if model_info.get('mode') == 'image_generation':
            capabilities.add('image_generation')
        if model_info.get('mode') == 'audio_transcription':
            capabilities.add('audio_transcription')

        if model_info.get('key').startswith(model_info.get('litellm_provider') + '/'):
            model_id = model_info.get('key')
        else:
            model_id = model_info.get('litellm_provider') + '/' + model_info.get('key')

        return Model(
            id=model_id,
            name=model_info.get('key'),
            provider=model_info.get('litellm_provider'),
            context_length=model_info.get('max_input_tokens'),
            input_cost=model_info.get('input_cost_per_token'),
            output_cost=model_info.get('output_cost_per_token'),
            capabilities=capabilities,
            metadata={"source": "litellm"}
        )
