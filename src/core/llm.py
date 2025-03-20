from typing import List, Dict, Any, Optional, Union, Protocol
from abc import ABC, abstractmethod
import asyncio
import uuid
from faker import Faker
from pydantic import BaseModel

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


class LLMService(ABC):
    """Abstract base class for LLM services"""
    
    @abstractmethod
    async def generate_response(self, messages: List[Any]) -> str:
        """Generate a response from the LLM based on the provided messages"""
        pass


class DummyLLMService(LLMService):
    """Dummy LLM service that generates fake responses"""
    
    def __init__(self):
        self.faker = Faker()
    
    async def generate_response(self, messages: List[Any]) -> str:
        """Generate a fake response"""
        # Simulate a delay to mimic real LLM response time
        await asyncio.sleep(0.5)
        
        # Get the last message to determine context
        last_message = messages[-1] if messages else None
        
        if last_message and hasattr(last_message, 'text'):
            # Generate a response based on the last message
            text = last_message.text.lower()
            
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
    
    async def generate_response(self, messages: List[Any]) -> str:
        """Generate a response using LiteLLM"""
        # Convert our message objects to the format expected by LiteLLM
        litellm_messages = []
        
        for msg in messages:
            if hasattr(msg, 'role') and hasattr(msg, 'text'):
                litellm_messages.append({
                    "role": msg.role,
                    "content": msg.text
                })
        
        # Get model from the message metadata if available
        model = "gpt-3.5-turbo"  # Default model
        if messages and hasattr(messages[0], 'metadata') and messages[0].metadata:
            if isinstance(messages[0].metadata, dict) and 'model' in messages[0].metadata:
                model = messages[0].metadata['model']
        
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
