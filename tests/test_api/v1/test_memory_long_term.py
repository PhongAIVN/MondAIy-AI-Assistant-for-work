"""Kiểm đường API của bộ nhớ dài hạn: hiện ra, xác nhận, từ chối, xoá, cách ly."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from src.db import SessionLocal
from src.models.conversation import Conversation, ConversationMessage
from src.models.learning import AssistantContextRef
from src.models.user_memory import UserMemory
from src.services.auth import decode_token
from src.services.memory_store import EvidenceRef, record_memory


async def _register(client, prefix: str) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{prefix}-{uuid.uuid4().hex[:12]}@example.com",
            "password": "correct-horse-1",
        },
    )
    assert response.status_code == 201
    return response.json()["accessToken"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _hoi(client, token: str, message: str, agent) -> dict:
    conversation_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"message": message},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _agent_ghi_lai_state(store: dict):
    async def fake_agent(state):
        store.update(state)
        return {"response": "ok", "analysis": ""}

    return AsyncMock(side_effect=fake_agent)


@pytest.mark.asyncio
async def test_long_term_memory_can_xac_thuc(client):
    assert (await client.get("/api/v1/memory/long-term")).status_code == 401


@pytest.mark.asyncio
async def test_fact_suy_ra_duoc_ghi_nho_va_su_dung_ngay(client):
    token = await _register(client, "ltm")
    state: dict = {}
    with patch("src.api.conversations.agent.ainvoke", _agent_ghi_lai_state(state)):
        await _hoi(client, token, "Tôi đang làm dự án mondaiy.", None)

    rows = (await client.get("/api/v1/memory/long-term", headers=_auth(token))).json()["memories"]
    du_an = [row for row in rows if row["predicate"] == "workingOn" or row["predicate"] == "working_on"]
    assert du_an, rows
    assert du_an[0]["status"] == "confirmed"
    assert du_an[0]["source"] == "inferred"


@pytest.mark.asyncio
async def test_fact_suy_ra_duoc_injected_without_user_confirmation(client):
    token = await _register(client, "ltm-recall")
    state: dict = {}
    agent = _agent_ghi_lai_state(state)
    with patch("src.api.conversations.agent.ainvoke", agent):
        await _hoi(client, token, "Tôi đang làm dự án mondaiy.", None)
        await _hoi(client, token, "Dự án của tôi đang tới đâu rồi?", None)

        await _hoi(client, token, "Dự án của tôi đang tới đâu rồi?", None)

    assert [item["value"] for item in state["long_term_memories"]] == ["mondaiy"]


@pytest.mark.asyncio
async def test_xung_dot_giu_hai_phien_ban_de_propose_cho_user(client):
    token = await _register(client, "ltm-conflict")
    user_id = int(decode_token(token, "access"))
    with SessionLocal() as db:
        first = record_memory(
            db,
            user_id,
            kind="profile",
            subject="user",
            predicate="working_on",
            object_value="P004",
            evidence=[EvidenceRef("user_input", "test:first")],
            source_authority="inferred",
        )
        second = record_memory(
            db,
            user_id,
            kind="profile",
            subject="user",
            predicate="working_on",
            object_value="P005",
            evidence=[EvidenceRef("user_input", "test:second")],
            source_authority="inferred",
        )
        db.commit()
        assert first.id != second.id
        assert first.status == "disputed"
        assert second.status == "disputed"

    rows = (await client.get("/api/v1/memory/long-term", headers=_auth(token))).json()["memories"]
    values = {row["value"] for row in rows if row["predicate"] in {"workingOn", "working_on"}}
    assert values == {"P004", "P005"}


@pytest.mark.asyncio
async def test_memory_graph_exposes_versions_conflict_and_provenance(client):
    token = await _register(client, "ltm-graph")
    user_id = int(decode_token(token, "access"))
    with SessionLocal() as db:
        first = record_memory(
            db, user_id, kind="profile", subject="user", predicate="working_on",
            object_value="P004", evidence=[EvidenceRef("user_input", "graph:first")],
        )
        second = record_memory(
            db, user_id, kind="profile", subject="user", predicate="working_on",
            object_value="P005", evidence=[EvidenceRef("user_input", "graph:second")],
        )
        db.commit()
        first_id, second_id = first.id, second.id

    response = await client.get("/api/v1/memory/graph", headers=_auth(token))
    assert response.status_code == 200, response.text
    graph = response.json()
    node_ids = {node["id"] for node in graph["nodes"]}
    edge_types = {edge["type"] for edge in graph["edges"]}
    assert {f"memory:{first_id}", f"memory:{second_id}"} <= node_ids
    assert "evidence" in edge_types
    assert "conflict" in edge_types
    assert any(edge["type"] == "supersedes" for edge in graph["edges"])


@pytest.mark.asyncio
async def test_conflict_proposal_can_confirm_selected_version(client):
    token = await _register(client, "ltm-conflict-choice")
    user_id = int(decode_token(token, "access"))
    with SessionLocal() as db:
        record_memory(
            db, user_id, kind="profile", subject="user", predicate="working_on",
            object_value="P004", evidence=[EvidenceRef("user_input", "choice:first")],
        )
        record_memory(
            db, user_id, kind="profile", subject="user", predicate="working_on",
            object_value="P005", evidence=[EvidenceRef("user_input", "choice:second")],
        )
        db.commit()

    rows = (await client.get("/api/v1/memory/long-term", headers=_auth(token))).json()["memories"]
    key = next(row["key"] for row in rows if row["value"] == "P004")
    response = await client.post(
        f"/api/v1/memory/long-term/{key}/confirm?version=1", headers=_auth(token)
    )
    assert response.status_code == 200
    assert response.json()["value"] == "P004"


@pytest.mark.asyncio
async def test_context_ref_records_exact_confirmed_memory_versions(client):
    token = await _register(client, "ltm-context-ref")
    state: dict = {}
    with patch("src.api.conversations.agent.ainvoke", _agent_ghi_lai_state(state)):
        await _hoi(client, token, "Tôi đang làm dự án mondaiy.", None)
        rows = (await client.get("/api/v1/memory/long-term", headers=_auth(token))).json()["memories"]
        key = next(row["key"] for row in rows if row["predicate"] in {"workingOn", "working_on"})
        assert (await client.post(f"/api/v1/memory/long-term/{key}/confirm", headers=_auth(token))).status_code == 200
        await _hoi(client, token, "Dự án của tôi là gì?", None)

    user_id = int(decode_token(token, "access"))
    with SessionLocal() as db:
        assistant_ids = list(
            db.scalars(
                select(ConversationMessage.id)
                .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
                .where(Conversation.user_id == str(user_id), ConversationMessage.role == "assistant")
                .order_by(ConversationMessage.id)
            )
        )
        refs = list(
            db.scalars(
                select(AssistantContextRef)
                .where(AssistantContextRef.assistant_message_id.in_(assistant_ids))
                .order_by(AssistantContextRef.assistant_message_id)
            )
        )
        memory = db.scalar(
            select(UserMemory)
            .where(
                UserMemory.user_id == user_id,
                UserMemory.memory_key == key,
                UserMemory.status.in_(("confirmed", "disputed")),
            )
            .order_by(UserMemory.id.asc())
        )

    assert memory is not None
    assert len(refs) == len(assistant_ids) == 2
    assert refs[0].memory_version_ids == []
    assert refs[1].memory_version_ids == [memory.id]
    assert refs[1].style_version_ids == []
    assert refs[1].skill_version_ids == []


@pytest.mark.asyncio
async def test_khong_thay_memory_cua_user_khac(client):
    token_a = await _register(client, "ltm-a")
    token_b = await _register(client, "ltm-b")
    state: dict = {}
    with patch("src.api.conversations.agent.ainvoke", _agent_ghi_lai_state(state)):
        await _hoi(client, token_a, "Tôi đang làm dự án mondaiy.", None)
        await _hoi(client, token_b, "Hôm nay thế nào?", None)

    assert state["long_term_memories"] == []
    rows = (await client.get("/api/v1/memory/long-term", headers=_auth(token_b))).json()
    assert rows["memories"] == []


@pytest.mark.asyncio
async def test_xac_nhan_day_candidate_len_confirmed(client):
    token = await _register(client, "ltm-confirm")
    state: dict = {}
    with patch("src.api.conversations.agent.ainvoke", _agent_ghi_lai_state(state)):
        await _hoi(client, token, "Tôi đang làm dự án mondaiy.", None)

    rows = (await client.get("/api/v1/memory/long-term", headers=_auth(token))).json()["memories"]
    key = rows[0]["key"]

    response = await client.post(f"/api/v1/memory/long-term/{key}/confirm", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    assert response.json()["source"] == "user"


@pytest.mark.asyncio
async def test_edit_memory_creates_version_with_evidence_and_updates_prompt(client):
    token = await _register(client, "ltm-edit")
    state: dict = {}
    with patch("src.api.conversations.agent.ainvoke", _agent_ghi_lai_state(state)):
        await _hoi(client, token, "Tôi tên là An.", None)

        rows = (await client.get("/api/v1/memory/long-term", headers=_auth(token))).json()["memories"]
        memory = next(row for row in rows if row["predicate"] in {"displayName", "display_name"})
        response = await client.patch(
            f"/api/v1/memory/long-term/{memory['key']}",
            json={"value": "Bình"},
            headers=_auth(token),
        )
        assert response.status_code == 200, response.text
        assert response.json()["version"] == 2
        assert response.json()["value"] == "Bình"
        assert response.json()["evidence"] == [
            {
                "evidenceType": "user_input",
                "evidenceRef": f"memory-inspector:{memory['key']}",
            }
        ]

        await _hoi(client, token, "Bạn nhớ tên tôi không?", None)

    assert state["user_profile"]["display_name"] == "Bình"
    assert [item["value"] for item in state["long_term_memories"]] == ["Bình"]


@pytest.mark.asyncio
async def test_tu_choi_thi_memory_khong_con_vao_prompt(client):
    token = await _register(client, "ltm-reject")
    state: dict = {}
    agent = _agent_ghi_lai_state(state)
    with patch("src.api.conversations.agent.ainvoke", agent):
        await _hoi(client, token, "Tôi đang làm dự án mondaiy.", None)

        rows = (await client.get("/api/v1/memory/long-term", headers=_auth(token))).json()["memories"]
        key = rows[0]["key"]
        assert (await client.post(f"/api/v1/memory/long-term/{key}/reject", headers=_auth(token))).status_code == 200

        await _hoi(client, token, "Dự án của tôi đang tới đâu rồi?", None)

    assert [item["value"] for item in state["long_term_memories"]] == []


@pytest.mark.asyncio
async def test_khong_xac_nhan_duoc_memory_cua_nguoi_khac(client):
    token_a = await _register(client, "ltm-cross-a")
    token_b = await _register(client, "ltm-cross-b")
    state: dict = {}
    with patch("src.api.conversations.agent.ainvoke", _agent_ghi_lai_state(state)):
        await _hoi(client, token_a, "Tôi đang làm dự án mondaiy.", None)

    rows = (await client.get("/api/v1/memory/long-term", headers=_auth(token_a))).json()["memories"]
    key = rows[0]["key"]

    response = await client.post(f"/api/v1/memory/long-term/{key}/confirm", headers=_auth(token_b))
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_confirmed_memory_is_injected_and_cross_user_edit_is_denied(client):
    token_a = await _register(client, "ltm-edit-a")
    token_b = await _register(client, "ltm-edit-b")
    state: dict = {}
    with patch("src.api.conversations.agent.ainvoke", _agent_ghi_lai_state(state)):
        await _hoi(client, token_a, "Tôi đang làm dự án mondaiy.", None)
        rows = (await client.get("/api/v1/memory/long-term", headers=_auth(token_a))).json()["memories"]
        key = rows[0]["key"]
        assert (await client.post(f"/api/v1/memory/long-term/{key}/confirm", headers=_auth(token_a))).status_code == 200

        denied = await client.patch(
            f"/api/v1/memory/long-term/{key}",
            json={"value": "dự án của người khác"},
            headers=_auth(token_b),
        )
        assert denied.status_code == 404
        await _hoi(client, token_a, "Dự án của tôi là gì?", None)

    assert [item["value"] for item in state["long_term_memories"]] == ["mondaiy"]


@pytest.mark.asyncio
async def test_delete_single_memory_removes_profile_mirror(client):
    token = await _register(client, "ltm-delete-profile")
    state: dict = {}
    with patch("src.api.conversations.agent.ainvoke", _agent_ghi_lai_state(state)):
        await _hoi(client, token, "Tôi tên là An.", None)
        rows = (await client.get("/api/v1/memory/long-term", headers=_auth(token))).json()["memories"]
        memory = next(row for row in rows if row["predicate"] in {"displayName", "display_name"})
        assert (
            await client.delete(
                f"/api/v1/memory/long-term/{memory['key']}",
                headers=_auth(token),
            )
        ).status_code == 204
        await _hoi(client, token, "Bạn nhớ tên tôi không?", None)

    assert state["user_profile"] == {}
    assert state["long_term_memories"] == []


@pytest.mark.asyncio
async def test_reset_memory_clears_all_prompt_visible_layers(client):
    token = await _register(client, "ltm-clear")
    state: dict = {}
    with patch("src.api.conversations.agent.ainvoke", _agent_ghi_lai_state(state)):
        await _hoi(client, token, "Tôi tên là An và tôi đang làm dự án mondaiy.", None)

        assert (await client.delete("/api/v1/memory/long-term", headers=_auth(token))).status_code == 204
        await _hoi(client, token, "Bạn nhớ gì về tôi?", None)

    rows = (await client.get("/api/v1/memory/long-term", headers=_auth(token))).json()
    assert rows["memories"] == []
    assert state["user_profile"] == {}
    assert state["long_term_memories"] == []


@pytest.mark.asyncio
async def test_tom_tat_phien_duoc_truyen_vao_agent(client):
    token = await _register(client, "ltm-summary")
    state: dict = {}
    with patch("src.api.conversations.agent.ainvoke", _agent_ghi_lai_state(state)):
        await _hoi(client, token, "Chào bạn.", None)

    # Phiên mới chưa có gì để nén, nhưng trường vẫn phải có mặt trong state để
    # node không phải đoán xem key có tồn tại hay không.
    assert state["conversation_summary"] == ""
