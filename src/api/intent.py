from fastapi import APIRouter

from src.models.intent_schemas import IntentRequest, IntentResponse
from src.services.intent_router import route_calendar_intent, route_gmail_intent

router = APIRouter(prefix="/intent", tags=["intent"])


@router.post("/recognize", response_model=IntentResponse)
def recognize_intent(payload: IntentRequest) -> IntentResponse:
    calendar_plan = route_calendar_intent(payload.message)
    plan = calendar_plan if calendar_plan.intent.value != "none" else route_gmail_intent(payload.message)
    return IntentResponse(
        intent=plan.intent.value,
        tool=plan.tool,
        fallback_tool=plan.fallback_tool,
        confidence=plan.confidence,
        needs_clarification=plan.needs_clarification,
        risk=plan.risk.value,
        query=plan.query,
        reason=plan.reason,
    )
