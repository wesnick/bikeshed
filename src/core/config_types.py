from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


## Session Template Configuration classes

class Metadata(BaseModel):
    """Metadata for session execution."""
    tags: Optional[List[str]] = None
    owner: Optional[str] = None
    # Allow additional fields
    model_config = {
        "extra": "allow",
    }


class ErrorHandling(BaseModel):
    """Error handling configuration."""
    strategy: Literal["fail", "retry", "continue", "fallback"] = "fail"
    max_retries: Optional[int] = None
    fallback_step: Optional[str] = None


class StepConfig(BaseModel):
    """Configuration overrides for a specific step."""
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: Optional[List[str]] = None
    resources: Optional[List[str]] = None


class BaseStep(BaseModel):
    """Base class for all step types."""
    name: str
    description: Optional[str] = None
    type: str
    enabled: bool = True
    metadata: Optional[Dict[str, Any]] = None
    error_handling: Optional[ErrorHandling] = None
    config: Optional[StepConfig] = None


class MessageStep(BaseStep):
    """Step to output a message with a specified role."""
    type: Literal["message"] = "message"
    role: Literal["system", "user", "assistant"]
    content: Optional[str] = None
    template: Optional[str] = None
    template_args: Optional[Dict[str, Any]] = None


class PromptStep(BaseStep):
    """Step to generate a completion from an LLM."""
    type: Literal["prompt"] = "prompt"
    content: Optional[str] = None
    template: Optional[str] = None
    template_args: Optional[Dict[str, Any]] = None
    input_schema: Optional[str] = None
    output_schema: Optional[str] = None


class UserInputStep(BaseStep):
    """Step to wait for manual input from the user."""
    type: Literal["user_input"] = "user_input"
    prompt: Optional[str] = None
    template: Optional[str] = None
    input_schema: Optional[str] = None
    output_schema: Optional[str] = None


class InvokeStep(BaseStep):
    """Step to call a code function."""
    type: Literal["invoke"] = "invoke"
    callable: str
    args: Optional[Dict[str, Any]] = None
    input_schema: Optional[str] = None
    output_schema: Optional[str] = None


# Union type for all possible steps
Step = Union[MessageStep, PromptStep, UserInputStep, InvokeStep]


class SessionTemplate(BaseModel):
    """Core session configuration."""
    model: str
    steps: List[Step]
    description: Optional[str] = None
    metadata: Optional[Metadata] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: Optional[List[Union[str, Dict[str, Any]]]] = None
    resources: Optional[List[Union[str, Dict[str, Any]]]] = None
    input_schema: Optional[str] = None
    output_schema: Optional[str] = None
    error_handling: Optional[ErrorHandling] = None


SessionTemplate.model_json_schema()
