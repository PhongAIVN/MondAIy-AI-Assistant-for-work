from pydantic import BaseModel


class IntentRequest(BaseModel):
    message: str


class IntentResponse(BaseModel):
    intent: str
    tool: str | None
    fallback_tool: str | None
    confidence: float
    needs_clarification: bool
    risk: str
    query: str | None
    reason: str
