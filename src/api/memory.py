"""API cho người dùng xem, xác nhận, sửa và xoá bộ nhớ của chính mình.

Mọi endpoint lọc theo user_id lấy từ token. `PRD` đòi người dùng nhìn thấy và
gỡ được thứ agent nhớ về mình, nên phần candidate cũng phải hiện ra chứ không
chỉ hiện những gì đã xác nhận.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user_id
from src.db import get_db
from src.models.schemas import (
    MemoryGraphEdge,
    MemoryGraphNode,
    MemoryGraphResponse,
    UserMemoryEvidenceItem,
    UserMemoryItem,
    UserMemoryListResponse,
    UserMemoryUpdateRequest,
    UserProfileMemoryResponse,
)
from src.models.user_memory import UserMemory
from src.services.memory_store import (
    EvidenceRef,
    clear_memories,
    confirm_memory,
    delete_memories_by_predicate,
    forget_memories,
    get_active_memory,
    list_memories,
    list_memory_evidence,
    reject_memory,
    revise_memory,
)
from src.services.profile_memory import (
    PROFILE_KEYS,
    clear_user_profile,
    delete_user_profile_keys,
    load_user_profile,
    set_user_profile_value,
)

router = APIRouter(prefix="/memory", tags=["memory"])


def _to_item(db: Session, memory: UserMemory) -> UserMemoryItem:
    """Chuyển sang dạng trả về, giữ nguyên status để giao diện phân biệt được."""
    return UserMemoryItem(
        key=memory.memory_key,
        version=memory.version,
        kind=memory.kind,
        subject=memory.subject,
        predicate=memory.predicate,
        value=(memory.object_json or {}).get("value"),
        status=memory.status,
        source=memory.source_authority,
        confidence=memory.confidence,
        reinforcement_count=memory.reinforcement_count,
        negative_feedback_count=memory.negative_feedback_count,
        first_observed_at=memory.first_observed_at,
        last_reinforced_at=memory.last_reinforced_at,
        evidence=[
            UserMemoryEvidenceItem(
                evidence_type=row.evidence_type,
                evidence_ref=row.evidence_ref,
            )
            for row in list_memory_evidence(db, memory.id)
        ],
    )


@router.get("/profile", response_model=UserProfileMemoryResponse)
def get_profile_memory(
    user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)
) -> UserProfileMemoryResponse:
    return UserProfileMemoryResponse(profile=load_user_profile(db, user_id))


@router.delete("/profile", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile_memory(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)) -> Response:
    delete_memories_by_predicate(db, user_id, PROFILE_KEYS)
    clear_user_profile(db, user_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/long-term", response_model=UserMemoryListResponse)
def list_long_term_memory(
    user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)
) -> UserMemoryListResponse:
    """Toàn bộ facts dài hạn, kể cả candidate đã nguội và bản đã bị thay thế."""
    rows = list_memories(db, user_id)
    return UserMemoryListResponse(memories=[_to_item(db, row) for row in rows])


@router.get("/graph", response_model=MemoryGraphResponse)
def get_memory_graph(
    user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)
) -> MemoryGraphResponse:
    """Trả graph cục bộ từ memory, version chain và evidence của đúng user."""
    rows = list_memories(db, user_id)
    nodes: dict[str, MemoryGraphNode] = {}
    edges: dict[str, MemoryGraphEdge] = {}
    by_key: dict[str, list[UserMemory]] = {}

    for memory in rows:
        memory_id = f"memory:{memory.id}"
        value = (memory.object_json or {}).get("value")
        nodes[memory_id] = MemoryGraphNode(
            id=memory_id,
            label=f"{memory.predicate}: {value}",
            node_type="memory",
            status=memory.status,
            metadata={"key": memory.memory_key, "version": memory.version, "kind": memory.kind},
        )
        by_key.setdefault(memory.memory_key, []).append(memory)
        for evidence in list_memory_evidence(db, memory.id):
            source_id = f"source:{evidence.evidence_type}:{evidence.evidence_ref}"
            nodes.setdefault(
                source_id,
                MemoryGraphNode(
                    id=source_id,
                    label=evidence.evidence_ref,
                    node_type="source",
                    metadata={"evidenceType": evidence.evidence_type},
                ),
            )
            edge_id = f"evidence:{memory.id}:{evidence.evidence_type}:{evidence.evidence_ref}"
            edges[edge_id] = MemoryGraphEdge(
                id=edge_id, source=memory_id, target=source_id, type="evidence", label="evidence"
            )
        if memory.supersedes_id is not None:
            edge_id = f"supersedes:{memory.id}:{memory.supersedes_id}"
            edges[edge_id] = MemoryGraphEdge(
                id=edge_id,
                source=memory_id,
                target=f"memory:{memory.supersedes_id}",
                type="supersedes",
                label="version mới",
            )

    for versions in by_key.values():
        disputed = [row for row in versions if row.status == "disputed"]
        for index, left in enumerate(disputed):
            for right in disputed[index + 1 :]:
                edge_id = f"conflict:{left.id}:{right.id}"
                edges[edge_id] = MemoryGraphEdge(
                    id=edge_id,
                    source=f"memory:{left.id}",
                    target=f"memory:{right.id}",
                    type="conflict",
                    label="xung đột",
                )

    return MemoryGraphResponse(nodes=list(nodes.values()), edges=list(edges.values()))


@router.post("/long-term/{memory_key}/confirm", response_model=UserMemoryItem)
def confirm_long_term_memory(
    memory_key: str,
    version: int | None = Query(default=None, ge=1),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserMemoryItem:
    """Người dùng xác nhận một fact suy ra là đúng."""
    memory = confirm_memory(db, user_id, memory_key, version=version)
    if memory is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy memory.")
    value = (memory.object_json or {}).get("value")
    if memory.predicate in PROFILE_KEYS and isinstance(value, str):
        set_user_profile_value(db, user_id, memory.predicate, value)
    db.commit()
    db.refresh(memory)
    return _to_item(db, memory)


@router.post("/long-term/{memory_key}/reject", response_model=UserMemoryItem)
def reject_long_term_memory(
    memory_key: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserMemoryItem:
    """Người dùng nói fact này sai; nó rời khỏi truy hồi ngay lượt sau."""
    memory = reject_memory(db, user_id, memory_key)
    if memory is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy memory.")
    if memory.predicate in PROFILE_KEYS:
        delete_user_profile_keys(db, user_id, {memory.predicate})
    db.commit()
    db.refresh(memory)
    return _to_item(db, memory)


@router.patch("/long-term/{memory_key}", response_model=UserMemoryItem)
def edit_long_term_memory(
    memory_key: str,
    payload: UserMemoryUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserMemoryItem:
    """User sửa fact bằng một version mới có provenance từ Memory Inspector."""
    memory = revise_memory(
        db,
        user_id,
        memory_key,
        payload.value.strip(),
        evidence=[EvidenceRef("user_input", f"memory-inspector:{memory_key}")],
    )
    if memory is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy memory.")
    if memory.predicate in PROFILE_KEYS:
        try:
            set_user_profile_value(db, user_id, memory.predicate, payload.value.strip())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(memory)
    return _to_item(db, memory)


@router.delete("/long-term/{memory_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_long_term_memory(
    memory_key: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> Response:
    """Xoá cứng mọi phiên bản của một fact, theo quyền xoá dữ liệu ở §9."""
    memory = get_active_memory(db, user_id, memory_key)
    if memory is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy memory.")
    if not forget_memories(db, user_id, [memory_key]):
        raise HTTPException(status_code=404, detail="Không tìm thấy memory.")
    if memory.predicate in PROFILE_KEYS:
        delete_user_profile_keys(db, user_id, {memory.predicate})
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/long-term", status_code=status.HTTP_204_NO_CONTENT)
def clear_long_term_memory(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)) -> Response:
    clear_memories(db, user_id)
    clear_user_profile(db, user_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
