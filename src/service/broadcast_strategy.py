from typing import Dict, Type, Callable, Any, Optional, List, Protocol, TypeVar, Generic, cast

from pydantic import BaseModel

from src.models.models import Message, Session, MessageStatus, SessionStatus
from src.service.broadcast import BroadcastService
from src.service.logging import logger


T = TypeVar('T', bound=BaseModel)


class BroadcastStrategy(Protocol, Generic[T]):
    """Protocol for model broadcast strategies"""
    
    def should_broadcast(self, model: T) -> bool:
        """Determine if the model should trigger a broadcast"""
        ...
    
    def get_events(self, model: T) -> List[tuple[str, Any]]:
        """Get list of events to broadcast (event_name, data)"""
        ...


class MessageBroadcastStrategy:
    """Strategy for broadcasting Message model updates"""
    
    def should_broadcast(self, model: Message) -> bool:
        """Broadcast for all message statuses except CREATED"""
        return model.status != MessageStatus.CREATED
    
    def get_events(self, model: Message) -> List[tuple[str, Any]]:
        """Get events based on message status"""
        events = []
        
        # Basic message update event
        events.append(("message_update", {
            "id": str(model.id),
            "session_id": str(model.session_id),
            "status": model.status,
            "role": model.role,
            "text": model.text,
            "timestamp": model.timestamp.isoformat(),
        }))
        
        # Additional events based on status
        if model.status == MessageStatus.DELIVERED and model.role == "assistant":
            events.append(("completion_finished", {
                "message_id": str(model.id),
                "session_id": str(model.session_id)
            }))
        elif model.status == MessageStatus.FAILED:
            events.append(("message_error", {
                "message_id": str(model.id),
                "session_id": str(model.session_id),
                "error": model.extra.get("error", "Unknown error") if model.extra else "Unknown error"
            }))
            
        return events


class SessionBroadcastStrategy:
    """Strategy for broadcasting Session model updates"""
    
    def should_broadcast(self, model: Session) -> bool:
        """Always broadcast session updates"""
        return True
    
    def get_events(self, model: Session) -> List[tuple[str, Any]]:
        """Get events based on session status"""
        events = []
        
        # Basic session update event
        session_data = {
            "id": str(model.id),
            "status": model.status,
            "current_state": model.current_state,
            "description": model.description,
            "created_at": model.created_at.isoformat(),
        }
        
        events.append(("session_update", session_data))
        
        # Additional events based on status
        if model.status == SessionStatus.WAITING_FOR_INPUT:
            events.append(("user_input_required", {
                "session_id": str(model.id),
                "prompt": model.get_current_step().prompt if model.get_current_step() else "Input required"
            }))
        elif model.status == SessionStatus.COMPLETED:
            events.append(("session_completed", {
                "session_id": str(model.id)
            }))
        elif model.status == SessionStatus.FAILED:
            events.append(("session_error", {
                "session_id": str(model.id),
                "error": model.error or "Unknown error"
            }))
            
        return events


class ModelUpdates:
    """Handler for broadcasting model updates"""
    
    def __init__(self, broadcast_service: BroadcastService):
        self.broadcast_service = broadcast_service
        self._strategies: Dict[Type[BaseModel], BroadcastStrategy] = {}
        
        # Register default strategies
        self.register_strategy(Message, MessageBroadcastStrategy())
        self.register_strategy(Session, SessionBroadcastStrategy())
    
    def register_strategy(self, model_class: Type[BaseModel], strategy: BroadcastStrategy) -> None:
        """Register a broadcast strategy for a model class"""
        self._strategies[model_class] = strategy
        logger.info(f"Registered broadcast strategy for {model_class.__name__}")
    
    async def broadcast_update(self, model: BaseModel) -> None:
        """Broadcast updates for a model if it has an id field and a registered strategy"""
        # Skip if model doesn't have an id
        if not hasattr(model, "id"):
            return
            
        model_class = type(model)
        strategy = self._strategies.get(model_class)
        
        if not strategy:
            # No strategy registered for this model type
            return
            
        # Use the appropriate strategy to determine if and what to broadcast
        if strategy.should_broadcast(model):
            events = strategy.get_events(model)
            
            for event_name, data in events:
                await self.broadcast_service.broadcast(event_name, data)
                logger.debug(f"Broadcast {event_name} for {model_class.__name__} {model.id}")
