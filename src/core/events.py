
# event names
# prompt.interpolate
# prompt.[prompt name].interpolate

from pydantic import BaseModel


class BasePromptEvent(BaseModel):
    __event_name__ = "prompt.interpolate"

    name: str = 'Test'



