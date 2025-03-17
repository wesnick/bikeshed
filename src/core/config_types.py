from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


## Session Template Configuration classes

class Metadata(BaseModel):
    """Metadata for session execution."""
    tags: Optional[List[str]] = Field(
        default=None,
        description="List of categorization tags for the session"
    )
    owner: Optional[str] = Field(
        default=None,
        description="Owner or creator of the session"
    )
    version: Optional[Union[str, float]] = Field(
        default=None,
        description="Version of this specific session definition"
    )
    # Allow additional fields
    model_config = {
        "extra": "allow",
    }


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
    tool_merge_strategy: Optional[Literal["replace", "append", "prepend"]] = Field(
        default=None,
        description="Strategy for merging tools with the default set"
    )
    resources: Optional[List[Union[str, Dict[str, Any]]]] = Field(
        default=None,
        description="Override or extend available resources for this step"
    )
    resource_merge_strategy: Optional[Literal["replace", "append", "prepend"]] = Field(
        default=None,
        description="Strategy for merging resources with the default set"
    )


class BaseStep(BaseModel):
    """Base class for all step types."""
    name: str = Field(
        description="Concise descriptive name for the step"
    )
    description: Optional[str] = Field(
        default=None,
        description="Detailed purpose of the step"
    )
    type: str = Field(
        description="Type of step to execute"
    )
    enabled: bool = Field(
        default=True,
        description="Whether the step is active"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional information for tracking/debugging"
    )
    error_handling: Optional[ErrorHandling] = Field(
        default=None,
        description="Error handling configuration for this step"
    )
    config_extra: Optional[Dict[str, Any]] = Field(
        default=None,
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
    template_args: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Arguments to pass to the template"
    )


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
    template_args: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Arguments to pass to the template"
    )
    input_schema: Optional[str] = Field(
        default=None,
        description="Schema to validate template_args"
    )
    output_schema: Optional[str] = Field(
        default=None,
        description="Schema to validate LLM response"
    )
    config_extra: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Step-specific model configuration overrides"
    )

class UserInputStep(BaseStep):
    """Step to wait for manual input from the user."""
    type: Literal["user_input"] = Field(
        default="user_input",
        description="Step type for waiting for manual user input"
    )
    instructions: Optional[str] = Field(
        default=None,
        description="Instructions for the user"
    )
    prompt: Optional[str] = Field(
        default=None,
        description="Text to display to user when requesting input"
    )
    template: Optional[str] = Field(
        default=None,
        description="Template to format user input"
    )
    template_args: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Arguments to pass to the template"
    )
    input_schema: Optional[str] = Field(
        default=None,
        description="Schema to validate user input"
    )
    output_schema: Optional[str] = Field(
        default=None,
        description="Schema to validate processed input"
    )
    config_extra: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Step-specific model configuration"
    )

class InvokeStep(BaseStep):
    """Step to call a code function."""
    type: Literal["invoke"] = Field(
        default="invoke",
        description="Step type for calling a code function"
    )
    callable: str = Field(
        description="Function identifier to call, use '@' for tool lookup"
    )
    args: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Arguments to pass to function"
    )
    input_schema: Optional[str] = Field(
        default=None,
        description="Schema to validate args"
    )
    output_schema: Optional[str] = Field(
        default=None,
        description="Schema to validate function result"
    )


# Union type for all possible steps
Step = Union[MessageStep, PromptStep, UserInputStep, InvokeStep]


class SessionTemplate(BaseModel):
    """Core session configuration."""
    name: str = Field(
        description="Unique identifier for the session template"
    )
    model: str = Field(
        description="Default LLM model to use"
    )
    steps: List[Step] = Field(
        description="Ordered list of execution steps"
    )
    description: Optional[str] = Field(
        default=None,
        description="Brief description of the session"
    )
    goal: Optional[str] = Field(
        default=None,
        description="Desired outcome of the session"
    )
    metadata: Optional[Metadata] = Field(
        default=None,
        description="Additional metadata for the session"
    )
    config_extra: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Dictionary of model configuration options"
    )
    tools: Optional[List[str]] = Field(
        default=None,
        description="List of tool identifiers"
    )
    resources: Optional[List[str]] = Field(
        default=None,
        description="List of resource identifiers"
    )
    roots: Optional[List[str]] = Field(
        default=None,
        description="List of root identifiers"
    )
    input_schema: Optional[str] = Field(
        default=None,
        description="Registered schema name for session input"
    )
    output_schema: Optional[str] = Field(
        default=None,
        description="Registered schema name for session output"
    )
    error_handling: Optional[ErrorHandling] = Field(
        default=None,
        description="Default error handling strategy"
    )


SessionTemplate.model_json_schema()
