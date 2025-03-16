


T = TypeVar('T', bound=BaseModel)


class YAMLLoadError(Exception):
    """Exception raised when there's an error loading a YAML file."""
    pass


class SessionConfigService:
    """Service for loading and validating session configuration YAML files."""

    @staticmethod
    def load_yaml(file_path: Union[str, Path]) -> Dict:
        """
        Load a YAML file into a dictionary.

        Args:
            file_path: Path to the YAML file

        Returns:
            Dictionary containing the parsed YAML

        Raises:
            YAMLLoadError: If the file cannot be read or parsed
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise YAMLLoadError(f"File not found: {file_path}")

            with open(file_path, 'r') as file:
                return yaml.safe_load(file)
        except yaml.YAMLError as e:
            raise YAMLLoadError(f"Failed to parse YAML: {e}")
        except Exception as e:
            raise YAMLLoadError(f"Error loading YAML file: {e}")

    @classmethod
    def load_session_config(cls, file_path: Union[str, Path]) -> list[SessionTemplate]:
        """
        Load and validate a session configuration YAML file into a list[SessionTemplate] object.

        Args:
            file_path: Path to the session configuration YAML file

        Returns:
            list[SessionTemplate] object

        Raises:
            YAMLLoadError: If the file cannot be loaded or the configuration is invalid
        """
        try:
            yaml_data = cls.load_yaml(file_path)
            templates = []
            for name, struct in yaml_data.get('session_templates'):
                templates.append(SessionTemplate.model_validate(struct))

            return templates
        except ValidationError as e:
            raise YAMLLoadError(f"Invalid session configuration: {e}")

    @classmethod
    def discover_session_configs(cls, directory: Union[str, Path]) -> List[Path]:
        """
        Discover all session configuration YAML files in a directory.

        Args:
            directory: Directory to search for YAML files

        Returns:
            List of paths to YAML files
        """
        directory = Path(directory)
        if not directory.exists() or not directory.is_dir():
            raise YAMLLoadError(f"Directory not found: {directory}")

        return list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))

    @staticmethod
    def get_step_from_dict(step_data: Dict) -> Step:
        """
        Create the appropriate Step subclass instance based on the step type.

        Args:
            step_data: Dictionary containing step data

        Returns:
            Instance of the appropriate Step subclass

        Raises:
            ValueError: If the step type is invalid
        """
        step_type = step_data.get("type")
        if not step_type:
            raise ValueError("Step missing required 'type' field")

        step_classes = {
            "message": MessageStep,
            "prompt": PromptStep,
            "user_input": UserInputStep,
            "invoke": InvokeStep,
        }

        if step_type not in step_classes:
            raise ValueError(f"Unknown step type: {step_type}")

        step_class = step_classes[step_type]
        return step_class.model_validate(step_data)
