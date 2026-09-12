import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agents.graph import agent
from src.api.deps import get_current_user_id
from src.api.rate_limit import limiter
from src.db import get_db
from src.models.connection import Connection
from src.models.evidence import SourceScope
from src.models.schemas import ChatRequest, ChatResponse
from src.services.agent_stream import stream_agent_execution
from src.services.profile_memory import apply_profile_memory, load_user_profile
from src.services.scope import apply_search_scope, reset_agent_scope
from src.services.task_planning import build_task_planning_reply, is_task_planning_request
from src.services.usage_quota import consume_llm_question

router = APIRouter()
logger = logging.getLogger(__name__)


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _scope_ids_for_user(db: Session, user_id: str) -> list[int]:
    """Return connected-provider scope IDs for compatibility and diagnostics."""
    providers = select(Connection.provider).where(
        Connection.user_id == str(user_id),
        Connection.status.notin_(["error", "disconnected"]),
    )
    return list(db.scalars(select(SourceScope.id).where(SourceScope.provider.in_(providers))).all())


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    payload: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """Hỏi agent một câu rời, không gắn vào phiên nào.

    Muốn có lịch sử hội thoại thì dùng /conversations/{id}/messages. Endpoint này
    giữ lại cho các lời gọi một lượt, và nay đã xác thực nên phạm vi truy hồi
    được giải theo đúng user thay vì mở toàn kho.
    """
    consume_llm_question(db, user_id)
    apply_search_scope(
        user_id,
        db,
        action_request_id=f"chat:{uuid.uuid4()}",
        current_query=payload.message,
    )
    try:
        result = (
            await build_task_planning_reply(db, user_id)
            if is_task_planning_request(payload.message)
            else await agent.ainvoke(
                {
                    "query": payload.message,
                    "user_profile": load_user_profile(db, user_id),
                }
            )
        )
        if not result.get("error"):
            apply_profile_memory(db, user_id, payload.message)
            db.commit()
        return ChatResponse(
            response=result.get("response", ""),
            analysis=result.get("analysis", ""),
            sources=(result.get("metadata") or {}).get("sources") or [],
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        reset_agent_scope()


@router.post("/chat/stream")
@limiter.limit("30/minute")
def chat_stream(
    request: Request,
    payload: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream câu trả lời một lượt qua SSE, không lưu conversation."""
    consume_llm_question(db, user_id)

    async def generate():
        apply_search_scope(
            user_id,
            db,
            action_request_id=f"chat-stream:{uuid.uuid4()}",
            current_query=payload.message,
        )
        try:
            result: dict = {}
            if is_task_planning_request(payload.message):
                yield _sse("progress", {"phase": "thinking"})
                result = await build_task_planning_reply(db, user_id)
                yield _sse("progress", {"phase": "responding"})
                yield _sse("token", {"delta": result["response"]})
            else:
                async for item in stream_agent_execution(
                    agent,
                    {
                        "query": payload.message,
                        "user_profile": load_user_profile(db, user_id),
                    },
                ):
                    if item["event"] in {"progress", "token"}:
                        yield _sse(item["event"], item["data"])
                    elif item["event"] == "result":
                        result = item["data"]

            if result.get("error"):
                yield _sse("error", {"message": result["error"]})
                return
            apply_profile_memory(db, user_id, payload.message)
            db.commit()
            response = result.get("response", "")
            yield _sse(
                "done",
                {
                    "response": response,
                    "analysis": result.get("analysis", ""),
                    "sources": (result.get("metadata") or {}).get("sources") or [],
                },
            )
        except Exception as exc:
            logger.exception("Streaming chat hỏng")
            yield _sse("error", {"message": "Trợ lý chưa trả lời được.", "code": type(exc).__name__})
        finally:
            reset_agent_scope()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get("/status")
async def agent_status():
    """Kiểm tra trạng thái agent."""
    return {"status": "ready", "agent": "LangGraph Agent v1.0"}
