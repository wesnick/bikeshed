from typing import List, Dict, Any, Optional, Union, Protocol, ClassVar
from abc import ABC, abstractmethod
import asyncio
import uuid
from faker import Faker
from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from enum import Enum

from src.models import Session, Message

# Try to import litellm, but don't fail if it's not available
try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False


class MessageContent(BaseModel):
    """Content of a message with type and text"""
    type: str = "text"
    text: str


class MessagePart(BaseModel):
    """Part of a multi-part message"""
    role: str
    content: MessageContent


class MessageRole(str, Enum):
    """Enum for message roles"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    FUNCTION = "function"


class LLMMessage(BaseModel):
    """Standardized message format for LLM communication"""
    role: MessageRole
    content: str
    name: Optional[str] = None
    model: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None
    
    @classmethod
    def system(cls, content: str, **kwargs) -> "LLMMessage":
        """Create a system message"""
        return cls(role=MessageRole.SYSTEM, content=content, **kwargs)
    
    @classmethod
    def user(cls, content: str, **kwargs) -> "LLMMessage":
        """Create a user message"""
        return cls(role=MessageRole.USER, content=content, **kwargs)
    
    @classmethod
    def assistant(cls, content: str, **kwargs) -> "LLMMessage":
        """Create an assistant message"""
        return cls(role=MessageRole.ASSISTANT, content=content, **kwargs)
    
    @classmethod
    def tool(cls, content: str, name: str, **kwargs) -> "LLMMessage":
        """Create a tool message"""
        return cls(role=MessageRole.TOOL, content=content, name=name, **kwargs)
    
    @classmethod
    def function(cls, content: str, name: str, **kwargs) -> "LLMMessage":
        """Create a function message"""
        return cls(role=MessageRole.FUNCTION, content=content, name=name, **kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary format suitable for LLM APIs"""
        result = {
            "role": self.role.value,
            "content": self.content
        }
        if self.name:
            result["name"] = self.name
        return result


class LLMMessageFactory:
    """Factory for creating LLM message sequences"""
    
    @staticmethod
    def from_session_messages(session: Session) -> List[LLMMessage]:
        """
        Create a list of LLMMessages from session messages
        
        Args:
            session: Session object
            messages: List of Message objects from the session
            
        Returns:
            List of LLMMessage objects
        """
        result = []


        for msg in session.messages:
            msg: Message
            # Determine the role
            try:
                role = MessageRole(msg.role)
            except ValueError:
                # Default to user if role is not recognized
                role = MessageRole.USER

            if msg.role == 'system':
                result.insert(0, LLMMessage.system(msg.text))
            else:
                llm_msg = LLMMessage(
                    role=role,
                    content=msg.text,
                    model=getattr(msg, 'model', None),
                    metadata=getattr(msg, 'extra', None)
                )
                result.append(llm_msg)
        
        return result
    
    @staticmethod
    def from_conversation_history(
        conversation: List[Dict[str, str]], 
        system_prompt: Optional[str] = None
    ) -> List[LLMMessage]:
        """
        Create a list of LLMMessages from a simple conversation history
        
        Args:
            conversation: List of dicts with 'role' and 'content' keys
            system_prompt: Optional system prompt to prepend
            
        Returns:
            List of LLMMessage objects
        """
        result = []
        
        # Add system prompt if provided
        if system_prompt:
            result.append(LLMMessage.system(system_prompt))
        
        # Convert conversation dicts to LLMMessages
        for msg in conversation:
            if 'role' in msg and 'content' in msg:
                try:
                    role = MessageRole(msg['role'])
                except ValueError:
                    # Default to user if role is not recognized
                    role = MessageRole.USER
                
                # Create the message
                llm_msg = LLMMessage(
                    role=role,
                    content=msg['content'],
                    name=msg.get('name'),
                    metadata=msg.get('metadata')
                )
                result.append(llm_msg)
        
        return result
    
    @staticmethod
    def build_prompt(
        user_query: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
        history: Optional[List[LLMMessage]] = None
    ) -> List[LLMMessage]:
        """
        Build a prompt with optional context and history
        
        Args:
            user_query: The user's query
            context: Optional context to include
            system_prompt: Optional system prompt
            history: Optional conversation history
            
        Returns:
            List of LLMMessage objects
        """
        result = []
        
        # Add system prompt if provided
        if system_prompt:
            result.append(LLMMessage.system(system_prompt))
        
        # Add history if provided
        if history:
            result.extend(history)
        
        # Add context as a system message if provided
        if context:
            result.append(LLMMessage.system(f"Context information:\n{context}"))
        
        # Add the user query
        result.append(LLMMessage.user(user_query))
        
        return result


class LLMService(ABC):
    """Abstract base class for LLM services"""
    
    @abstractmethod
    async def generate_response(self, messages: List[LLMMessage]) -> str:
        """Generate a response from the LLM based on the provided messages"""
        pass


class DummyLLMService(LLMService):
    """Dummy LLM service that generates fake responses"""
    
    def __init__(self):
        self.faker = Faker()
    
    async def generate_response(self, messages: List[LLMMessage]) -> str:
        """Generate a fake response"""
        # Simulate a delay to mimic real LLM response time
        await asyncio.sleep(0.5)
        
        # Get the last message to determine context
        last_message = messages[-1] if messages else None
        
        if last_message:
            # Generate a response based on the last message
            text = last_message.content.lower()
            
            if "hello" in text or "hi" in text:
                return self.faker.sentence(nb_words=10, variable_nb_words=True)
            elif "?" in text:
                return self.faker.paragraph(nb_sentences=3, variable_nb_sentences=True)
            elif "list" in text or "steps" in text:
                steps = [f"{i+1}. {self.faker.sentence()}" for i in range(self.faker.random_int(min=3, max=5))]
                return "\n".join(steps)
            elif "code" in text:
                return f"```python\ndef example_function():\n    return \"{self.faker.word()}\"\n```"
        
        # Default response
        return self.faker.paragraph(nb_sentences=2, variable_nb_sentences=True)


class LiteLLMService(LLMService):
    """LLM service that uses LiteLLM to interact with various LLM providers"""
    
    def __init__(self):
        if not LITELLM_AVAILABLE:
            raise ImportError("LiteLLM is not installed. Please install it with 'uv pip install litellm'")
    
    async def generate_response(self, messages: List[LLMMessage]) -> str:
        """Generate a response using LiteLLM"""
        # Convert our message objects to the format expected by LiteLLM
        litellm_messages = [msg.to_dict() for msg in messages]
        
        # Get model from the first message with a model specified, or use default
        model = next((msg.model for msg in messages if msg.model), "gpt-3.5-turbo")
        
        # Call LiteLLM
        response = await litellm.acompletion(
            model=model,
            messages=litellm_messages,
            temperature=0.7,
        )
        
        # Extract and return the response text
        if response and response.choices and len(response.choices) > 0:
            return response.choices[0].message.content
        
        return "No response generated"


def get_llm_service(service_type: str = "dummy") -> LLMService:
    """Factory function to get an LLM service instance"""
    if service_type == "dummy":
        return DummyLLMService()
    elif service_type == "litellm":
        return LiteLLMService()
    else:
        raise ValueError(f"Unknown LLM service type: {service_type}")
