from typing import Optional, List
from pydantic import BaseModel


class Intents(BaseModel):
    permitted: List[str]
    restricted: Optional[List[str]] = []


class Agent(BaseModel):
    overall_business_scope: str
    intents: Intents
    more_info: Optional[str] = ""
