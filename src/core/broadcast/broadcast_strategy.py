from typing import Any, List, Protocol

from pydantic import BaseModel
from typing_extensions import TypeVar

from src.core.models import Message, Dialog, MessageStatus, DialogStatus

T = TypeVar('T', bound=BaseModel)


class BroadcastStrategy(Protocol):
    """Protocol for model broadcast strategies"""

    async def should_broadcast(self, model: T) -> bool:
        """Determine if the model should trigger a broadcast"""
        ...

    async def get_events(self, model: T) -> List[tuple[str, Any]]:
        """Get list of events to broadcast (event_name, data)"""
        ...


class MessageBroadcastStrategy:
    """Strategy for broadcasting Message model updates"""

    async def should_broadcast(self, model: Message) -> bool:
        """Broadcast for all message statuses except CREATED"""
        return model.status != MessageStatus.CREATED

    async def get_events(self, model: Message) -> List[tuple[str, Any]]:
        """Get events based on message status"""
        events = []

        # Basic message update event
        events.append(("message_update", {
            "id": str(model.id),
            "dialog_id": str(model.dialog_id),
            "status": model.status,
            "role": model.role,
            "text": model.text,
            "timestamp": model.timestamp.isoformat(),
        }))

        # Additional events based on status
        if model.status == MessageStatus.DELIVERED and model.role == "assistant":
            events.append(("completion_finished", {
                "message_id": str(model.id),
                "dialog_id": str(model.dialog_id)
            }))
        elif model.status == MessageStatus.FAILED:
            events.append(("message_error", {
                "message_id": str(model.id),
                "dialog_id": str(model.dialog_id),
                "error": model.extra.get("error", "Unknown error") if model.extra else "Unknown error"
            }))

        return events


class DialogBroadcastStrategy:
    """Strategy for broadcasting Dialog model updates"""

    async def should_broadcast(self, model: Dialog) -> bool:
        """Always broadcast dialog updates"""
        return True

    async def get_events(self, model: Dialog) -> List[tuple[str, Any]]:
        """Get events based on dialog status"""
        events = []

        # Basic dialog update event
        dialog_data = {
            "id": str(model.id),
            "status": model.status,
            "current_state": model.current_state,
            "description": model.description,
            "created_at": model.created_at.isoformat(),
        }

        events.append(("dialog.update", dialog_data))

        # Additional events based on status
        if model.status == DialogStatus.WAITING_FOR_INPUT:
            events.append(("user_input_required", {
                "dialog_id": str(model.id),
                "prompt": model.get_current_step().prompt if model.get_current_step() else "Input required"
            }))
        elif model.status == DialogStatus.COMPLETED:
            events.append(("dialog_completed", {
                "dialog_id": str(model.id)
            }))
        elif model.status == DialogStatus.FAILED:
            events.append(("dialog_error", {
                "dialog_id": str(model.id),
                "error": model.error or "Unknown error"
            }))

        return events

