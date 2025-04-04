from typing import Any, Dict, List, Literal, Optional, Union, Set

from pydantic import BaseModel, Field, model_validator


## Dialog Template Configuration classes

class ErrorHandling(BaseModel):
    """Error handling configuration."""
    strategy: Literal["fail", "retry", "continue", "fallback"] = Field(
        default="fail",
        description="Error handling strategy to use when a step fails"
    )
    max_retries: Optional[int] = Field(
        default=None,
        description="Maximum number of retry attempts"
    )
    fallback_step: Optional[str] = Field(
        default=None,
        description="Step ID to jump to on failure"
    )


class StepConfig(BaseModel):
    """Configuration overrides for a specific step."""
    model: Optional[str] = Field(
        default=None,
        description="Override default model for this step"
    )
    temperature: Optional[float] = Field(
        default=None,
        description="Override default temperature for this step"
    )
    max_tokens: Optional[int] = Field(
        default=None,
        description="Override default max tokens for this step"
    )
    tools: Optional[List[Union[str, Dict[str, Any]]]] = Field(
        default=None,
        description="Override or extend available tools for this step"
    )
    resources: Optional[List[Union[str, Dict[str, Any]]]] = Field(
        default=None,
        description="Override or extend available resources for this step"
    )


class BaseStep(BaseModel):
    """Base class for all step types."""
    name: str = Field(
        description="Concise descriptive name for the step"
    )
    type: str = Field(
        description="Type of step to execute"
    )
    enabled: bool = Field(
        default=True,
        description="Whether the step is active"
    )
    error_handling: Optional[ErrorHandling] = Field(
        default_factory=lambda: ErrorHandling(),
        description="Error handling configuration for this step"
    )
    config: Optional[StepConfig] = Field(
        default_factory=lambda: StepConfig(),
        description="Additional model configuration for this step"
    )


class MessageStep(BaseStep):
    """Step to output a message with a specified role."""
    type: Literal["message"] = Field(
        default="message",
        description="Step type for adding a message to the conversation"
    )
    role: Literal["system", "user", "assistant"] = Field(
        description="Role of the message sender"
    )
    content: Optional[str] = Field(
        default=None,
        description="Text content of the message"
    )
    template: Optional[str] = Field(
        default=None,
        description="Registered template name to use"
    )
    template_defaults: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Arguments to pass to the template"
    )

    @model_validator(mode='after')
    def validate_content_or_template(self) -> 'MessageStep':
        """Validate that either content or template is provided, but not both."""
        if self.content is not None and self.template is not None:
            raise ValueError("Only one of 'content' or 'template' can be provided")
        if self.content is None and self.template is None:
            raise ValueError("Either 'content' or 'template' must be provided")
        if self.template_defaults is not None and self.template is None:
            raise ValueError("'template_defaults' can only be provided when 'template' is specified")
        return self


class PromptStep(BaseStep):
    """Step to generate a completion from an LLM."""
    type: Literal["prompt"] = Field(
        default="prompt",
        description="Step type for generating completion from LLM"
    )
    content: Optional[str] = Field(
        default=None,
        description="Direct content to use as prompt"
    )
    template: Optional[str] = Field(
        default=None,
        description="Registered template name to use"
    )
    template_defaults: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Arguments to pass to the template"
    )
    response_schema: Optional[str] = Field(
        default=None,
        description="Schema to validate LLM response"
    )


    @model_validator(mode='after')
    def validate_content_or_template(self) -> 'PromptStep':
        """Validate that either content or template is provided, but not both."""
        if self.content is not None and self.template is not None:
            raise ValueError("Only one of 'content' or 'template' can be provided")
        if self.content is None and self.template is None:
            raise ValueError("Either 'content' or 'template' must be provided")
        if self.template_defaults is not None and self.template is None:
            raise ValueError("'template_defaults' can only be provided when 'template' is specified")
        return self

class UserInputStep(BaseStep):
    """Step to wait for manual input from the user."""
    type: Literal["user_input"] = Field(
        default="user_input",
        description="Step type for waiting for manual user input"
    )
    prompt: Optional[str] = Field(
        default=None,
        description="Text to display to user when requesting input"
    )
    template: Optional[str] = Field(
        default=None,
        description="Template to format user input"
    )
    template_defaults: Optional[Dict[str, Any]] = Field(
        default={},
        description="Arguments to pass to the template, as defaults, they will be overridden by context"
    )
    response_schema: Optional[str] = Field(
        default=None,
        description="Schema to validate processed input"
    )


    @model_validator(mode='after')
    def validate_template_defaults(self) -> 'UserInputStep':
        """Validate that template_defaults is only provided with template."""
        if len(self.template_defaults) > 0 and self.template is None:
            raise ValueError("'template_defaults' can only be provided when 'template' is specified")
        return self

class InvokeStep(BaseStep):
    """Step to call a code function."""
    type: Literal["invoke"] = Field(
        default="invoke",
        description="Step type for calling a code function"
    )
    callable: str = Field(
        description="Function identifier to call, use '@' for tool lookup"
    )
    response_schema: Optional[str] = Field(
        default=None,
        description="Schema to validate function result"
    )

    @model_validator(mode='after')
    def validate_callable(self) -> 'InvokeStep':
        """Validate that callable is provided and properly formatted."""
        if not self.callable:
            raise ValueError("'callable' must be provided for invoke steps")
        return self


# Union type for all possible steps
Step = Union[MessageStep, PromptStep, UserInputStep, InvokeStep]


class DialogTemplate(BaseModel):
    """Core dialog configuration."""
    name: str = Field(
        description="Unique identifier for the dialog template"
    )
    model: str = Field(
        description="Default LLM model to use"
    )
    steps: List[Step] = Field(
        description="Ordered list of execution steps"
    )
    description: Optional[str] = Field(
        default=None,
        description="Brief description of the dialog"
    )
    tools: Optional[List[str]] = Field(
        default=None,
        description="List of tool identifiers"
    )
    resources: Optional[List[str]] = Field(
        default=None,
        description="List of resource identifiers"
    )
    response_schema: Optional[str] = Field(
        default=None,
        description="Registered schema name for dialog output"
    )
    error_handling: Optional[ErrorHandling] = Field(
        default=None,
        description="Default error handling strategy"
    )

    @model_validator(mode='after')
    def validate_steps(self) -> 'DialogTemplate':
        """Validate that steps are properly configured."""
        if not self.steps:
            raise ValueError("At least one step must be provided")

        # Check for fallback steps that don't exist
        step_names = {step.name for step in self.steps}
        for step in self.steps:
            if step.error_handling and step.error_handling.fallback_step:
                if step.error_handling.fallback_step not in step_names:
                    raise ValueError(
                        f"Fallback step '{step.error_handling.fallback_step}' "
                        f"referenced in step '{step.name}' does not exist"
                    )

        # Check dialog-level error handling
        if self.error_handling and self.error_handling.fallback_step:
            if self.error_handling.fallback_step not in step_names:
                raise ValueError(
                    f"Dialog-level fallback step '{self.error_handling.fallback_step}' does not exist"
                )

        return self


class Model(BaseModel):
    """Represents an LLM model."""
    id: str = Field(description="Unique identifier for the model")
    name: str = Field(description="Display name of the model")
    provider: str = Field(description="Provider of the model (e.g., 'ollama', 'openai', 'anthropic')")
    context_length: Optional[int] = Field(
        default=None,
        description="Maximum context length in tokens"
    )
    input_cost: Optional[float] = Field(
        default=0.0,
        description="Cost per input token"
    )
    output_cost: Optional[float] = Field(
        default=0.0,
        description="Cost per output token"
    )
    capabilities: Optional[Set[str]] = Field(
        default_factory=set,
        description="Set of capabilities this model supports (e.g., 'chat', 'embedding', 'vision')"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata about the model"
    )
    # Tracking fields added by RegistryBuilder
    selected: bool = Field(
        default=False,
        description="Indicates if the model is selected (present in models.yaml)"
    )
    upstream_present: bool = Field(
        default=True,
        description="Indicates if the model was found in upstream sources (Ollama, LiteLLM)"
    )
    overrides: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Fields overridden by models.yaml compared to upstream source"
    )

    @property
    def model_filterable_capabilities(self):
        core = ['chat', 'vision', 'tools', 'embedding']
        caps = []
        for capability in self.capabilities:
            if capability in core:
                caps.append(capability)
            elif capability == 'function_calling':
                caps.append('tools')
        return caps


    @model_validator(mode='after')
    def ensure_id_format(self) -> 'Model':
        """Ensure the ID is properly formatted."""
        if not self.id:
            # If no ID is provided, create one from provider and name
            self.id = f"{self.provider}/{self.name}"
        return self
