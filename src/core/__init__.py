from __future__ import annotations as _annotations

from dataclasses import dataclass, field
from typing import Generic, Any

from typing_extensions import TypeVar


SessionDepsT = TypeVar('SessionDepsT', default=None, contravariant=True)
"""Type variable for sessions dependencies."""


@dataclass
class RunContext(Generic[SessionDepsT]):
    """Information about the current session."""
    deps: SessionDepsT
    """Dependencies for the session."""
    model: str
    """The model used in this run."""
    lookup: dict[str, Any] = field(default_factory=dict)
    """Flattened dictionary of variables"""
    # usage: Usage
    # """LLM usage associated with the run."""
    # prompt: str
    # """The original user prompt passed to the run."""
    # messages: list[Message] = field(default_factory=list)
    # """Messages exchanged in the conversation so far."""
    retry: int = 0
    """Number of retries so far."""
    run_step: int = 0
    """The current step in the run."""


__all__ = [
    'RunContext',
]
