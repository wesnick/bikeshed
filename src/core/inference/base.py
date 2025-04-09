from abc import ABC, abstractmethod
from typing import Optional, Callable, Awaitable, List
from src.core.models import Dialog, Message

class LLMException(Exception):
    """Base exception for LLM service errors"""
    pass

class CompletionService(ABC):
    @abstractmethod
    async def complete(
        self,
        dialog: Dialog,
        broadcast: Optional[Callable[[Message], Awaitable[None]]] = None
    ) -> Message:
        """
        Process a conversation dialog and generate a completion.

        Args:
            dialog: The dialog with conversation history
            broadcast: Optional callback for streaming updates

        Returns:
            The assistant Message with completion
        """
        pass

    @abstractmethod
    def supports(self, dialog: Dialog) -> bool:
        """
        Determine if this completion service supports the given dialog.

        Args:
            dialog: The dialog to check

        Returns:
            True if this service can handle the dialog, False otherwise
        """
        pass

    def _prepare_messages(self, dialog: Dialog) -> list[dict]:
        """Convert dialog messages to LLM message format"""
        return [{
            "role": msg.role,
            "content": msg.text
        } for msg in dialog.messages[:-1]]  # Exclude last message (assistant stub)

class ChainedCompletionService(CompletionService):
    """
    A completion service that chains multiple services together and uses the first one that supports the dialog.
    """

    def __init__(self, services: List[CompletionService]):
        """
        Initialize with a list of completion services to try in order.

        Args:
            services: List of CompletionService implementations to try
        """
        self.services = services

    def supports(self, dialog: Dialog) -> bool:
        """Always returns True as long as there's at least one service"""
        return len(self.services) > 0

    async def complete(
        self,
        dialog: Dialog,
        broadcast: Optional[Callable[[Message], Awaitable[None]]] = None
    ) -> Message:
        """
        Find the first service that supports the dialog and use it to complete.

        Args:
            dialog: The dialog with conversation history
            broadcast: Optional callback for streaming updates

        Returns:
            The assistant Message with completion

        Raises:
            LLMException: If no service supports the dialog
        """
        for service in self.services:
            if service.supports(dialog):
                return await service.complete(dialog, broadcast)

        raise LLMException("No completion service supports this dialog")
