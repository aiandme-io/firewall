from typing import Optional
from pydantic import BaseModel


class Integration(BaseModel):
    endpoint: str
    api_key: str


class Firewall(BaseModel):
    id: str
    status: bool
    fail_category: Optional[str] = ""
