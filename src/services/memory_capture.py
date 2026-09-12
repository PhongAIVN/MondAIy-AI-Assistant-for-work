"""Rút fact dài hạn từ một lượt nói của người dùng.

Chia đúng hai đường của memory-lifecycle §5. Fact người dùng tự khai — tên, cách
xưng hô, vai trò, múi giờ, ngôn ngữ, kiểu trả lời — đi qua `profile_memory` và
vào thẳng `confirmed`. Fact suy ra từ cách người dùng kể chuyện — mục tiêu, dự
án đang làm, chủ đề quan tâm — chỉ vào `candidate` và phải chờ xác nhận.

Vẫn không dùng LLM để quyết định lưu gì, cùng lý do đã ghi ở `profile_memory`:
một prompt hay một đoạn nội dung từ nguồn ngoài không được tự biến thành trí nhớ
lâu dài của agent. Chỉ các mẫu hẹp bên dưới mới ghi được.

Chỉ đọc lượt của người dùng. Câu trả lời của trợ lý không phải bằng chứng — để
nó tự nuôi trí nhớ của chính mình là mở đường cho ảo giác đóng rắn thành fact.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.services.memory_store import (
    EvidenceRef,
    clear_memories,
    forget_by_predicate,
    record_memory,
)
from src.services.profile_memory import (
    ProfileMutation,
    apply_profile_memory,
    set_user_profile_value,
)

logger = logging.getLogger(__name__)

# Ánh xạ key profile sang bộ ba của §4. `predicate` là tên khoá ổn định, đừng
# đổi khi đổi nhãn hiển thị: nó là danh tính của fact trong bảng.
_PROFILE_KIND = {
    "display_name": "profile",
    "preferred_name": "profile",
    "role": "profile",
    "timezone": "profile",
    "language": "preference",
    "response_style": "preference",
}

# Mục tiêu và dự án: người dùng kể ra chứ không khai như một khai báo hồ sơ, nên
# đây là suy luận và chỉ được vào `candidate`.
_GOAL_PATTERNS = (
    re.compile(r"(?i)\bmục\s+tiêu\s+(?:của\s+)?(?:tôi|mình|em)\s+là\s+([^.!?\n;]{3,120})"),
    re.compile(r"(?i)\b(?:tôi|mình|em)\s+(?:đang\s+)?muốn\s+(?:đạt|hoàn thành)\s+([^.!?\n;]{3,120})"),
)
_PROJECT_PATTERNS = (
    re.compile(r"(?i)\b(?:tôi|mình|em)\s+đang\s+làm\s+(?:dự\s+án|project)\s+([^.!?\n;,]{2,80})"),
    re.compile(r"(?i)\bdự\s+án\s+(?:của\s+)?(?:tôi|mình|em)\s+(?:tên\s+)?là\s+([^.!?\n;,]{2,80})"),
)
_INTEREST_PATTERNS = (
    re.compile(r"(?i)\b(?:tôi|mình|em)\s+(?:rất\s+)?quan\s+tâm\s+(?:tới|đến)\s+([^.!?\n;,]{2,80})"),
    re.compile(r"(?i)\b(?:tôi|mình|em)\s+(?:rất\s+)?thích\s+(?:học|tìm hiểu)\s+([^.!?\n;,]{2,80})"),
)
_FORGET_INFERRED_PATTERNS = (
    (
        re.compile(r"(?i)\b(?:đừng\s+nhớ|quên|xóa|xoá|forget|delete)\b.{0,40}\b(?:mục\s+tiêu|goal)\b"),
        frozenset({"goal"}),
    ),
    (
        re.compile(r"(?i)\b(?:đừng\s+nhớ|quên|xóa|xoá|forget|delete)\b.{0,40}\b(?:dự\s+án|project|đang\s+làm)\b"),
        frozenset({"working_on"}),
    ),
    (
        re.compile(
            r"(?i)\b(?:đừng\s+nhớ|quên|xóa|xoá|forget|delete)\b.{0,40}"
            r"\b(?:chủ\s+đề\s+quan\s+tâm|mối\s+quan\s+tâm|sở\s+thích|interest|interested)\b"
        ),
        frozenset({"interested_in"}),
    ),
)


@dataclass(frozen=True)
class CaptureResult:
    """Những gì một lượt nói đã ghi vào bộ nhớ dài hạn."""

    profile: ProfileMutation
    confirmed_keys: tuple[str, ...] = ()
    candidate_keys: tuple[str, ...] = ()
    cleared_all: bool = False
    notes: list[str] = field(default_factory=list)


def _clean_phrase(raw: str) -> str | None:
    """Cắt mệnh đề thừa và chặn chuỗi quá dài trước khi lưu."""
    value = re.split(r"(?i)\s+(?:và|nhưng|vì|bởi vì|and|but|because)\s+", raw, maxsplit=1)[0]
    value = " ".join(value.strip(" \t\"'“”‘’.,;:").split())
    if not 2 <= len(value) <= 120:
        return None
    return value


def _first_match(text: str, patterns: tuple[re.Pattern[str], ...]) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match and (value := _clean_phrase(match.group(1))):
            return value
    return None


def extract_inferred_facts(text: str) -> list[tuple[str, str, str]]:
    """Trả về các bộ (kind, predicate, value) suy ra được từ một lượt nói.

    Cơ chế: chạy lần lượt từng nhóm mẫu hẹp trên văn bản đã chuẩn hoá khoảng
    trắng, mỗi nhóm lấy kết quả khớp đầu tiên. Không khớp thì không đoán thêm —
    thà thiếu trí nhớ còn hơn nhớ sai.
    """
    normalized = " ".join((text or "").strip().split())
    if not normalized:
        return []

    facts: list[tuple[str, str, str]] = []
    if goal := _first_match(normalized, _GOAL_PATTERNS):
        facts.append(("goal", "goal", goal))
    if project := _first_match(normalized, _PROJECT_PATTERNS):
        facts.append(("project", "working_on", project))
    if interest := _first_match(normalized, _INTEREST_PATTERNS):
        facts.append(("topic_interest", "interested_in", interest))
    return facts


def extract_inferred_forget_predicates(text: str) -> frozenset[str]:
    """Nhận lệnh quên có phạm vi cho các fact inferred đã hỗ trợ."""
    normalized = " ".join((text or "").strip().split())
    deleted: set[str] = set()
    for pattern, predicates in _FORGET_INFERRED_PATTERNS:
        if pattern.search(normalized):
            deleted.update(predicates)
    return frozenset(deleted)


def capture_long_term_memory(
    db: Session,
    user_id: str,
    text: str,
    *,
    source_conversation_id: int | None = None,
    source_message_id: int | None = None,
) -> CaptureResult:
    """Ghi trí nhớ dài hạn từ một lượt nói, trong transaction của caller.

    Cơ chế: trước hết chạy `apply_profile_memory` để lớp profile explicit vẫn
    hoạt động y như cũ; kết quả của nó được chiếu sang bảng `user_memories` với
    thẩm quyền `user`. Sau đó chạy các mẫu suy luận, ghi vào cùng bảng nhưng với
    thẩm quyền `inferred` nên chúng dừng ở `candidate`. Lệnh xoá bộ nhớ của
    người dùng xoá cả hai lớp, không để sót lớp nào.

    Không commit. Caller quyết định commit hay rollback cùng lượt trả lời, để
    một câu trả lời hỏng không để lại trí nhớ mồ côi.
    """
    mutation = apply_profile_memory(db, user_id, text, source_conversation_id=source_conversation_id)

    if mutation.cleared_all:
        clear_memories(db, user_id)
        return CaptureResult(profile=mutation, cleared_all=True)

    # Bằng chứng trỏ về đúng lượt nói đã sinh ra fact. Chưa flush được id thì
    # lùi về conversation — vẫn mở lại được nguồn, chỉ kém chính xác một mức.
    if source_message_id is not None:
        evidence = [EvidenceRef("conversation_message", str(source_message_id))]
    elif source_conversation_id is not None:
        evidence = [EvidenceRef("conversation", str(source_conversation_id))]
    else:
        evidence = [EvidenceRef("user_input", "unknown")]

    # Lệnh quên có phạm vi phải dội sang cả lớp semantic, không thì fact vẫn
    # sống ở bảng kia và quay lại prompt ngay lượt sau.
    forget_by_predicate(
        db,
        user_id,
        mutation.deleted_keys | extract_inferred_forget_predicates(text),
    )

    confirmed: list[str] = []
    for key, value in mutation.updates.items():
        memory = record_memory(
            db,
            user_id,
            kind=_PROFILE_KIND.get(key, "profile"),
            subject="user",
            predicate=key,
            object_value=value,
            source_authority="user",
            created_by="user",
            evidence=evidence,
            confidence=1.0,
            importance=0.8,
            source_conversation_id=source_conversation_id,
        )
        confirmed.append(memory.memory_key)

    candidates: list[str] = []
    for kind, predicate, value in extract_inferred_facts(text):
        memory = record_memory(
            db,
            user_id,
            kind=kind,
            subject="user",
            predicate=predicate,
            object_value=value,
            source_authority="inferred",
            created_by="rule",
            evidence=evidence,
            confidence=0.5,
            importance=0.5,
            source_conversation_id=source_conversation_id,
        )
        candidates.append(memory.memory_key)

    return CaptureResult(
        profile=mutation,
        confirmed_keys=tuple(confirmed),
        candidate_keys=tuple(candidates),
    )


def _evidence_refs(
    source_conversation_id: int | None,
    source_message_id: int | None,
) -> list[EvidenceRef]:
    if source_message_id is not None:
        return [EvidenceRef("conversation_message", str(source_message_id))]
    if source_conversation_id is not None:
        return [EvidenceRef("conversation", str(source_conversation_id))]
    return [EvidenceRef("user_input", "unknown")]


def capture_regex_facts(
    db: Session,
    user_id: str,
    text: str,
    *,
    source_conversation_id: int | None = None,
    source_message_id: int | None = None,
) -> tuple[CaptureResult, frozenset[str]]:
    """Phần deterministic của capture — không gọi mạng nên chạy được inline.

    Trả về kết quả cùng tập predicate đã ghi trong lượt này để đường LLM
    enrichment chạy sau không ghi trùng hai phiên bản cùng một fact.
    """
    mutation = apply_profile_memory(db, user_id, text, source_conversation_id=source_conversation_id)

    if mutation.cleared_all:
        clear_memories(db, user_id)
        return CaptureResult(profile=mutation, cleared_all=True), frozenset()

    evidence = _evidence_refs(source_conversation_id, source_message_id)

    forget_by_predicate(
        db,
        user_id,
        mutation.deleted_keys | extract_inferred_forget_predicates(text),
    )

    confirmed: list[str] = []
    written_predicates: set[str] = set()
    for key, value in mutation.updates.items():
        memory = record_memory(
            db,
            user_id,
            kind=_PROFILE_KIND.get(key, "profile"),
            subject="user",
            predicate=key,
            object_value=value,
            source_authority="user",
            created_by="user",
            evidence=evidence,
            confidence=1.0,
            importance=0.8,
            source_conversation_id=source_conversation_id,
        )
        confirmed.append(memory.memory_key)
        written_predicates.add(key)

    candidates: list[str] = []
    for kind, predicate, value in extract_inferred_facts(text):
        memory = record_memory(
            db,
            user_id,
            kind=kind,
            subject="user",
            predicate=predicate,
            object_value=value,
            source_authority="inferred",
            created_by="rule",
            evidence=evidence,
            confidence=0.5,
            importance=0.5,
            source_conversation_id=source_conversation_id,
        )
        candidates.append(memory.memory_key)
        written_predicates.add(predicate)

    return (
        CaptureResult(
            profile=mutation,
            confirmed_keys=tuple(confirmed),
            candidate_keys=tuple(candidates),
        ),
        frozenset(written_predicates),
    )


async def aenrich_long_term_memory(
    db: Session,
    user_id: str,
    text: str,
    *,
    skip_predicates: frozenset[str] = frozenset(),
    source_conversation_id: int | None = None,
    source_message_id: int | None = None,
) -> tuple[str, ...]:
    """LLM bổ sung fact regex không bắt được; nuốt mọi lỗi thành log rỗng.

    Được thiết kế để chạy NỀN sau khi phản hồi đã tới user với session DB riêng:
    provider chậm không được kéo độ trễ vào lượt chat (sự cố ReadTimeout
    24/08). Ghi kèm ``exc_info`` ở lớp memory_intent nên log đủ để chẩn đoán.
    """
    from src.services import memory_intent as memory_intent_module

    try:
        intents = await memory_intent_module.extract_memory_intents(text)
    except Exception:  # noqa: BLE001 — fallback đã xử lý bên trong, đây chỉ là đai bụng
        logger.warning("memory_intent raised unexpectedly; skipping enrichment", exc_info=True)
        return ()

    if not intents:
        return ()

    evidence = _evidence_refs(source_conversation_id, source_message_id)
    confirmed: list[str] = []
    for intent in intents:
        if intent.predicate in skip_predicates:
            continue
        if intent.category == "identity":
            set_user_profile_value(
                db,
                user_id,
                "display_name",
                intent.value,
                source_conversation_id=source_conversation_id,
            )
            importance = 0.8
        else:
            # relationship/affiliation: fact verbatim do user khai → thẩm
            # quyền user, confirmed; kind="profile" theo ràng buộc
            # MEMORY_KINDS của record_memory.
            importance = 0.7
        memory = record_memory(
            db,
            user_id,
            kind=_PROFILE_KIND.get(intent.predicate, "profile"),
            subject="user",
            predicate=intent.predicate,
            object_value=intent.value,
            source_authority="user",
            created_by="user",
            evidence=evidence,
            confidence=1.0,
            importance=importance,
            source_conversation_id=source_conversation_id,
        )
        confirmed.append(memory.memory_key)
    return tuple(confirmed)


async def acapture_long_term_memory(
    db: Session,
    user_id: str,
    text: str,
    *,
    source_conversation_id: int | None = None,
    source_message_id: int | None = None,
) -> CaptureResult:
    """Bản async LLM-first của capture, dùng cho các caller đang trong event loop.

    Thành phần và thứ tự:
    1. Regex đã vá chạy trước cho lớp explicit profile + lệnh quên/xoá (deterministic).
    2. Regex suy luận goal/project/interest như bản sync.
    3. LLM nhỏ bổ sung các fact regex không bắt được — relationship/affiliation
       là khoảng trống gây 2 bug prod 22/08 — với validation allowlist chặt.
    Model tắt cờ/lỗi/timeout thì kết quả trùng khớp capture_long_term_memory:
    degradation an toàn, không bao giờ ném exception ra đường chat.

    Caller mới trên đường phản hồi chat nên tách bước: ``capture_regex_facts``
    chạy inline, ``aenrich_long_term_memory`` chạy nền — xem conversations.py.
    """
    result, written_predicates = capture_regex_facts(
        db,
        user_id,
        text,
        source_conversation_id=source_conversation_id,
        source_message_id=source_message_id,
    )
    if result.cleared_all:
        return result

    llm_confirmed = await aenrich_long_term_memory(
        db,
        user_id,
        text,
        skip_predicates=written_predicates,
        source_conversation_id=source_conversation_id,
        source_message_id=source_message_id,
    )
    return CaptureResult(
        profile=result.profile,
        confirmed_keys=result.confirmed_keys + llm_confirmed,
        candidate_keys=result.candidate_keys,
    )
