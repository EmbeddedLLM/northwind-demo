from pydantic import BaseModel


class RunRequest(BaseModel):
    level: int
    question: str
