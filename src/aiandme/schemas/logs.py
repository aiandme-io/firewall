import uuid
from typing import Optional
from pydantic import BaseModel


class Logs(BaseModel):
    id: Optional[str] = str(uuid.uuid4())
    prompt: str
    result: str
    explanation: Optional[str] = ""
    fail_category: Optional[str] = ""
