"""Lớp bộ nhớ dài hạn: ghi nhận, thăng cấp, giải mâu thuẫn và truy hồi.

Bám memory-lifecycle §3–§9. Ba luật không được phá:

Không ghi đè. Fact mới mâu thuẫn fact cũ thì tạo phiên bản mới và đóng khoảng
hiệu lực của bản cũ, chứ không sửa giá trị tại chỗ (§6).

Không tự phong canonical. Mọi thứ suy ra từ hoạt động quan sát được vào ở trạng
thái `candidate`; chỉ người dùng xác nhận hoặc luật thăng cấp đã duyệt mới đẩy
lên `confirmed` (§5).

Không có memory rỗng bằng chứng. Mỗi phiên bản ghi kèm ít nhất một tham chiếu
bằng chứng, đó là bất biến §11.

Ở đây không gọi LLM. Quyết định lưu gì thuộc về luật trích xuất phía trên; module
này chỉ nhận fact đã có cấu trúc, nên một đoạn văn bản từ nguồn ngoài không thể
tự biến thành trí nhớ của agent.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.user_memory import UserMemory, UserMemoryEvidence

logger = logging.getLogger(__name__)

# Hằng số RRF dùng chung với truy hồi chunk. Hai lớp phải cùng một hằng số thì
# điểm mới so sánh được với nhau khi sau này gộp bằng chứng và trí nhớ vào một
# evidence pack.
RRF_K = 60
GENERIC_CONTEXT_SUBJECTS = frozenset({"user", "me", "person", "student", "employee"})

# Số ứng viên lấy từ nhánh vector. Rộng hơn `limit` của recall để RRF có chỗ
# xoay, hẹp đủ để không kéo cả kho memory của user về.
VECTOR_CANDIDATE_LIMIT = 50

# Các kind P0 theo memory-lifecycle §4. Kind ngoài danh sách này bị từ chối ngay
# lúc ghi: thêm một loại trí nhớ là đổi hành vi sản phẩm, phải qua tài liệu.
MEMORY_KINDS = frozenset(
    {
        "profile",
        "preference",
        "goal",
        "project",
        "topic_interest",
        "decision",
        "commitment",
        "deadline",
        "task",
        "episode",
    }
)

# Các trạng thái của state machine §3.
MEMORY_STATUSES = frozenset({"candidate", "confirmed", "disputed", "superseded", "rejected", "forgotten"})

# Trạng thái còn được truy hồi mặc định. `superseded` và `rejected` giữ lại để
# đối chiếu lịch sử chứ không đưa vào ngữ cảnh của agent nữa.
ACTIVE_STATUSES = frozenset({"candidate", "confirmed", "disputed"})

# Chuyển trạng thái hợp lệ, chép từ sơ đồ §3. Ai gọi sai đường thì lỗi ngay chứ
# không âm thầm tạo ra một trạng thái không có trong tài liệu.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "candidate": frozenset({"confirmed", "rejected", "forgotten"}),
    "confirmed": frozenset({"disputed", "superseded", "forgotten"}),
    "disputed": frozenset({"confirmed", "superseded", "forgotten"}),
    "rejected": frozenset(),
    "superseded": frozenset(),
    "forgotten": frozenset(),
}

# Thứ hạng thẩm quyền nguồn. Người dùng tự khai thắng nguồn chính thức, nguồn
# chính thức thắng suy luận — §5. Đây là thứ tự để so sánh khi mâu thuẫn, không
# phải điểm số.
AUTHORITY_RANK = {"user": 3, "official": 2, "inferred": 1}

# Trọng số xếp hạng của §7. Thẩm quyền cao được ưu tiên khi trả lời, nhưng nó chỉ
# đổi thứ tự chứ không loại bằng chứng thấp hơn khỏi kết quả — QT-04.
AUTHORITY_WEIGHT = {"user": 1.3, "official": 1.15, "inferred": 1.0}

# Candidate bị hạ điểm mạnh để không bao giờ đứng trên một fact đã xác nhận, còn
# disputed hạ thêm vì bản thân nó là dấu hiệu đang có mâu thuẫn chưa xử.
# `superseded` để 1.0 vì nó chỉ lọt vào kết quả khi câu hỏi hỏi về một mốc quá
# khứ mà tại mốc đó nó đang là bản hiệu lực — xem `recall`.
STATUS_WEIGHT = {"confirmed": 1.0, "superseded": 1.0, "disputed": 0.7, "candidate": 0.55}

# Nửa đời của độ mới, tính bằng ngày. Dài hơn của chunk bằng chứng
# (retrieval.HALF_LIFE_DAYS = 21) vì một sở thích hay vai trò không cũ đi nhanh
# như một tin nhắn.
HALF_LIFE_DAYS = 90.0

# Trần của thừa số lặp lại. Không cho một fact được nhắc trăm lần đè bẹp mọi thứ
# còn lại chỉ vì nó lặp.
MAX_REINFORCEMENT_BOOST = 1.5

# Candidate không được nhắc lại trong ngần này ngày thì rơi khỏi truy hồi mặc
# định. Đây là "decay" của §9, không phải xoá: dòng vẫn còn để kiểm chứng.
CANDIDATE_DECAY_DAYS = 60

# Số bằng chứng độc lập tối thiểu để luật tự thăng cấp một fact suy ra. Dưới
# ngưỡng này thì chỉ người dùng mới xác nhận được.
PROMOTION_MIN_EVIDENCE = 3

# Độ liên quan tối thiểu của một fact không khớp từ khoá nào. Không có sàn này
# thì agent chỉ nhớ khi người dùng hỏi trúng đúng chữ đã lưu, mà người ta hỏi
# "dự án tới đâu rồi" chứ không hỏi "working_on". Sàn cố ý thấp: fact khớp chữ
# luôn xếp trên, và `limit` của `recall` mới là thứ chặn khối lượng.
BASELINE_RELEVANCE = 0.15

# Nhãn tiếng Việt của từng kind, ghép vào chuỗi tìm kiếm để câu hỏi hỏi bằng
# tiếng Việt vẫn khớp được fact có predicate đặt tên bằng tiếng Anh.
KIND_KEYWORDS = {
    "profile": "hồ sơ thông tin cá nhân",
    "preference": "sở thích tuỳ chọn cách trả lời",
    "goal": "mục tiêu",
    "project": "dự án",
    "topic_interest": "quan tâm chủ đề",
    "decision": "quyết định",
    "commitment": "cam kết",
    "deadline": "hạn chót thời hạn",
    "task": "việc công việc nhiệm vụ",
    "episode": "sự kiện",
}

EXTRACTOR_VERSION = "memory-store-1"


def _now() -> datetime:
    return datetime.now(UTC)


def _as_aware(value: datetime | None) -> datetime | None:
    """Gán UTC cho datetime naive đọc từ sqlite.

    Postgres trả về datetime có múi giờ, còn sqlite bỏ mất phần đó khi ghi. So
    sánh một naive với một aware là ném TypeError, nên chuẩn hoá trước khi tính.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


@dataclass(frozen=True)
class EvidenceRef:
    """Một tham chiếu bằng chứng, đủ để mở lại nguồn gốc của fact."""

    evidence_type: str
    evidence_ref: str


@dataclass(frozen=True)
class ScoredMemory:
    """Một memory kèm điểm và các thừa số đã tạo ra điểm đó.

    Giữ đủ thừa số để giải thích được vì sao một fact lên đầu — không có phần
    này thì mọi tranh cãi về thứ tự đều thành đoán mò. Hai trường thứ hạng cho
    biết fact lên được là nhờ nhánh nào, đó là thứ duy nhất phân biệt được
    "vector kéo lên" với "trùng chữ".
    """

    memory: UserMemory
    score: float
    relevance: float
    authority_weight: float
    status_weight: float
    recency_weight: float
    reinforcement_weight: float
    negative_feedback_penalty: float
    keyword_rank: int | None = None
    vector_rank: int | None = None


def _normalize(text: str) -> str:
    """Bỏ dấu và hạ chữ thường để so khớp không phụ thuộc cách gõ tiếng Việt."""
    folded = unicodedata.normalize("NFD", text or "")
    stripped = "".join(char for char in folded if unicodedata.category(char) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "D").casefold()


def _tokens(text: str) -> set[str]:
    """Tách token dùng cho khớp từ khoá; bỏ token 1 ký tự vì chúng khớp bừa."""
    return {token for token in re.findall(r"[a-z0-9]+", _normalize(text)) if len(token) > 1}


def build_search_text(subject: str, predicate: str, object_value: object, kind: str = "") -> str:
    """Dựng chuỗi phẳng để khớp từ khoá, luôn dựng lại từ bộ ba gốc.

    Ghép thêm nhãn tiếng Việt của kind vì predicate là định danh tiếng Anh theo
    quy ước đặt tên, còn câu hỏi thì bằng tiếng Việt.
    """
    parts = (subject, predicate, str(object_value), KIND_KEYWORDS.get(kind, ""))
    return " ".join(part for part in parts if part).strip()


def _overlap(query_tokens: set[str], memory: UserMemory) -> float:
    """Tỉ lệ token của câu hỏi tìm thấy trong memory, chưa áp sàn."""
    if not query_tokens:
        return 1.0
    memory_tokens = _tokens(memory.search_text or "")
    if not memory_tokens:
        return 0.0
    return len(query_tokens & memory_tokens) / len(query_tokens)


def _relevance(query_tokens: set[str], memory: UserMemory) -> float:
    """Độ liên quan của chế độ từ khoá thuần, có sàn tối thiểu.

    Sàn `BASELINE_RELEVANCE` chỉ tồn tại ở chế độ này: không có nhánh vector thì
    mọi câu hỏi diễn đạt khác chữ đã lưu đều làm agent quên sạch. Ở chế độ lai,
    mọi fact đều có thứ hạng từ khoá nên sàn không còn cần — ADR-006 §10.
    """
    if not query_tokens:
        return 1.0
    return max(_overlap(query_tokens, memory), BASELINE_RELEVANCE)


def _recency_weight(memory: UserMemory, at: datetime) -> float:
    """Giảm theo hàm mũ tính từ lần được nhắc gần nhất."""
    last = _as_aware(memory.last_reinforced_at) or at
    age_days = max((at - last).total_seconds() / 86400.0, 0.0)
    return math.pow(0.5, age_days / HALF_LIFE_DAYS)


def _reinforcement_weight(memory: UserMemory) -> float:
    """Tăng theo log số lần lặp lại, chặn trên để không nuốt các thừa số khác."""
    return min(1.0 + math.log1p(max(memory.reinforcement_count, 1) - 1) / 4.0, MAX_REINFORCEMENT_BOOST)


def _negative_feedback_penalty(memory: UserMemory) -> float:
    """Mỗi lần bị người dùng nói sai thì còn một nửa điểm."""
    return math.pow(0.5, max(memory.negative_feedback_count, 0))


def score_memory(
    memory: UserMemory,
    query_tokens: set[str],
    at: datetime,
    *,
    relevance: float | None = None,
    keyword_rank: int | None = None,
    vector_rank: int | None = None,
) -> ScoredMemory:
    """Nhân sáu thừa số của memory-lifecycle §7 thành một điểm.

    `relevance` truyền vào là điểm RRF đã chuẩn hoá của chế độ lai; bỏ trống thì
    hàm tự tính bằng khớp từ khoá. Năm thừa số còn lại không đổi theo chế độ —
    ADR-006 §3 chốt rằng vector chỉ được đổi thứ tự ứng viên, không được đụng
    tới thẩm quyền nguồn hay trạng thái.
    """
    final_relevance = _relevance(query_tokens, memory) if relevance is None else relevance
    authority = AUTHORITY_WEIGHT.get(memory.source_authority, 1.0)
    status = STATUS_WEIGHT.get(memory.status, 0.5)
    recency = _recency_weight(memory, at)
    reinforcement = _reinforcement_weight(memory)
    penalty = _negative_feedback_penalty(memory)
    return ScoredMemory(
        memory=memory,
        score=final_relevance * authority * status * recency * reinforcement * penalty,
        relevance=final_relevance,
        authority_weight=authority,
        status_weight=status,
        recency_weight=recency,
        reinforcement_weight=reinforcement,
        negative_feedback_penalty=penalty,
        keyword_rank=keyword_rank,
        vector_rank=vector_rank,
    )


def _model_dang_dung() -> str:
    """Nhãn model phải là model THẬT SỰ sinh ra vector, không phải hằng cấu hình."""
    from src.services.retrieval import active_embedding_model

    return active_embedding_model()


def embed_memory_text(text_value: str) -> list[float] | None:
    """Nhúng một đoạn văn bản của lớp memory, trả None khi không nhúng được.

    Cơ chế: tái dùng `embed_query` của retrieval để memory và chunk luôn nằm
    trong cùng một không gian nhúng — ADR-006 §1. Mọi lỗi đều nuốt và trả None
    vì nhúng chỉ là nhánh phụ: mất nó thì truy hồi kém đi, còn ném lỗi lên thì
    hỏng cả lượt trả lời.
    """
    if not (text_value or "").strip():
        return None
    settings = get_settings()
    if not settings.memory_semantic_recall_enabled:
        return None
    try:
        from src.services.retrieval import embed_query

        return embed_query(text_value)
    except Exception:
        logger.warning("Không nhúng được văn bản memory, lùi về khớp từ khoá", exc_info=True)
        return None


def _semantic_enabled(db: Session) -> bool:
    """Nhánh vector cần đủ ba điều kiện của ADR-006 §8.

    Cột `Vector` tạo được trên sqlite nhưng toán tử `<=>` thì không, nên dialect
    là điều kiện cứng chứ không phải tuỳ chọn: dev và test vẫn chạy nhánh từ
    khoá và vẫn phải xanh.
    """
    if not get_settings().memory_semantic_recall_enabled:
        return False
    bind = db.get_bind()
    return getattr(bind, "dialect", None) is not None and bind.dialect.name == "postgresql"


def _vector_ranks(db: Session, candidate_ids: list[int], query_embedding: list[float] | None) -> dict[int, int]:
    """Thứ hạng theo khoảng cách cosine, chỉ trong tập ứng viên đã lọc quyền.

    Cơ chế: giới hạn KNN vào đúng các id đã qua bộ lọc user và thời gian ở
    `recall`, nên không có đường nào để memory của người khác lọt vào — ADR-006
    §7. Lọc sau khi lấy k dòng gần nhất thì k suất đó đã bị người khác chiếm
    mất, đó là lý do điều kiện nằm trong câu SQL.
    """
    if not query_embedding or not candidate_ids or not _semantic_enabled(db):
        return {}
    try:
        rows = db.execute(
            text(
                """
                SELECT id
                FROM user_memories
                WHERE id = ANY(:ids) AND embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT :n
                """
            ),
            {
                "ids": candidate_ids,
                "vec": str(query_embedding),
                "n": VECTOR_CANDIDATE_LIMIT,
            },
        ).all()
    except Exception:
        logger.warning("Truy vấn vector memory hỏng, lùi về khớp từ khoá", exc_info=True)
        return {}
    return {row.id: index + 1 for index, row in enumerate(rows)}


def _keyword_ranks(memories: list[UserMemory], query_tokens: set[str], at: datetime) -> dict[int, int]:
    """Thứ hạng theo khớp từ khoá, mọi ứng viên đều có một hạng.

    Cơ chế: xếp theo tỉ lệ token trùng, hoà nhau thì fact được nhắc gần đây hơn
    đứng trước. Chấm điểm trong tiến trình chứ không dùng Postgres FTS: một user
    có vài chục tới vài trăm memory, không phải hàng triệu chunk — ADR-006 §4.
    """
    ordered = sorted(
        memories,
        key=lambda memory: (
            _overlap(query_tokens, memory),
            (_as_aware(memory.last_reinforced_at) or at).timestamp(),
        ),
        reverse=True,
    )
    return {memory.id: index + 1 for index, memory in enumerate(ordered)}


def _rrf_relevance(keyword_rank: int | None, vector_rank: int | None) -> float:
    """Hợp nhất hai thứ hạng thành một `relevance` trong khoảng (0, 1].

    Chuẩn hoá bằng điểm tối đa có thể đạt — hạng 1 ở cả hai nhánh — để giá trị
    trả về vẫn là một tỉ lệ, nhân được với năm thừa số còn lại của §7 mà không
    làm lệch thang điểm.
    """
    best = 2.0 / (RRF_K + 1)
    raw = 0.0
    for rank in (keyword_rank, vector_rank):
        if rank is not None:
            raw += 1.0 / (RRF_K + rank)
    return raw / best


def backfill_memory_embeddings(db: Session, user_id: str | int, limit: int | None = None) -> int:
    """Nhúng các memory chưa có vector, chạy nền sau khi đã trả lời.

    Cơ chế: chọn những dòng còn hiệu lực mà `embedding` rỗng hoặc được nhúng
    bằng model khác model đang cấu hình, nhúng từng dòng rồi commit. Ghi kèm tên
    model vì so cosine giữa hai không gian nhúng khác nhau cho ra số vô nghĩa
    chứ không báo lỗi — ADR-006 §1.

    Trả về số dòng đã nhúng. Không nằm trên đường ghi memory: một provider nhúng
    chậm không được phép giữ transaction của lượt chat.
    """
    settings = get_settings()
    if not _semantic_enabled(db):
        return 0
    batch = limit or settings.memory_embedding_batch_limit
    rows = list(
        db.execute(
            select(UserMemory)
            .where(
                UserMemory.user_id == int(user_id),
                UserMemory.status.in_(tuple(ACTIVE_STATUSES)),
                (UserMemory.embedding.is_(None)) | (UserMemory.embedding_model != _model_dang_dung()),
            )
            .order_by(UserMemory.last_reinforced_at.desc())
            .limit(batch)
        ).scalars()
    )

    done = 0
    for memory in rows:
        vector = embed_memory_text(memory.search_text)
        if vector is None:
            # Provider đang hỏng thì dừng cả lượt: thử tiếp chỉ tốn thêm thời
            # gian chờ, và lượt nền sau sẽ nhặt lại đúng các dòng này.
            break
        memory.embedding = vector
        memory.embedding_model = _model_dang_dung()
        done += 1
    if done:
        db.commit()
    return done


def _attach_evidence(db: Session, memory: UserMemory, evidence: list[EvidenceRef]) -> None:
    """Gắn bằng chứng, bỏ qua bản trùng để lần quan sát lại không nhân đôi."""
    if not evidence:
        return
    db.flush()
    existing = {
        (row.evidence_type, row.evidence_ref)
        for row in db.execute(select(UserMemoryEvidence).where(UserMemoryEvidence.memory_id == memory.id)).scalars()
    }
    for ref in evidence:
        key = (ref.evidence_type, ref.evidence_ref)
        if key in existing:
            continue
        existing.add(key)
        db.add(
            UserMemoryEvidence(
                memory_id=memory.id,
                evidence_type=ref.evidence_type,
                evidence_ref=ref.evidence_ref,
            )
        )


def count_evidence(db: Session, memory: UserMemory) -> int:
    """Đếm bằng chứng độc lập của một phiên bản memory."""
    db.flush()
    rows = db.execute(select(UserMemoryEvidence).where(UserMemoryEvidence.memory_id == memory.id)).scalars()
    return len({(row.evidence_type, row.evidence_ref) for row in rows})


def _initial_status(source_authority: str, created_by: str) -> str:
    """Memory mới được dùng ngay; quyền kiểm soát nằm ở sửa/xoá và conflict.

    `source_authority` vẫn được giữ nguyên để giải thích nguồn, nhưng không còn
    dùng trạng thái `candidate` làm cổng chặn recall. Người dùng thấy memory
    ngay trong inspector và có thể xoá nếu nhận diện sai.
    """
    return "confirmed"


def _active_version(db: Session, user_id: int, kind: str, subject: str, predicate: str) -> UserMemory | None:
    """Phiên bản còn hiệu lực của cùng một bộ ba, nếu có."""
    rows = db.execute(
        select(UserMemory)
        .where(
            UserMemory.user_id == user_id,
            UserMemory.kind == kind,
            UserMemory.subject == subject,
            UserMemory.predicate == predicate,
            UserMemory.status.in_(tuple(ACTIVE_STATUSES)),
        )
        .order_by(UserMemory.version.desc())
    ).scalars()
    for row in rows:
        if row.valid_to is None:
            return row
    return None


def record_memory(
    db: Session,
    user_id: str | int,
    *,
    kind: str,
    subject: str,
    predicate: str,
    object_value: object,
    source_authority: str = "inferred",
    created_by: str = "rule",
    evidence: list[EvidenceRef] | None = None,
    confidence: float = 0.5,
    importance: float = 0.5,
    source_conversation_id: int | None = None,
    at: datetime | None = None,
) -> UserMemory:
    """Ghi nhận một fact và trả về phiên bản đang hiệu lực sau khi ghi.

    Ba nhánh, theo đúng §5–§6. Chưa có fact cùng bộ ba thì tạo mới ở trạng thái
    do thẩm quyền quyết định. Đã có và giá trị y hệt thì củng cố bản cũ: tăng
    đếm lặp, dời `last_reinforced_at`, gắn thêm bằng chứng, và xét thăng cấp.
    Đã có nhưng giá trị khác thì đây là mâu thuẫn: bản mới luôn là một dòng
    riêng, `supersedes_id` trỏ về bản cũ. Thẩm quyền của bản mới cao hơn thì bản
    cũ đóng lại thành `superseded`; ngang nhau thì cả hai cùng `disputed` và
    việc phân xử để dành cho người dùng, không đoán hộ.
    """
    if kind not in MEMORY_KINDS:
        raise ValueError(f"kind không hợp lệ: {kind}")
    if source_authority not in AUTHORITY_RANK:
        raise ValueError(f"source_authority không hợp lệ: {source_authority}")

    numeric_user_id = int(user_id)
    moment = at or _now()
    evidence = evidence or []
    if not evidence:
        raise ValueError("Memory phải có ít nhất một bằng chứng (memory-lifecycle §11).")

    search_text = build_search_text(subject, predicate, object_value, kind)
    payload = {"value": object_value}
    current = _active_version(db, numeric_user_id, kind, subject, predicate)

    if current is None:
        fresh = UserMemory(
            memory_key=uuid.uuid4().hex,
            version=1,
            user_id=numeric_user_id,
            kind=kind,
            subject=subject,
            predicate=predicate,
            object_json=payload,
            search_text=search_text,
            status=_initial_status(source_authority, created_by),
            confidence=confidence,
            importance=importance,
            source_authority=source_authority,
            created_by=created_by,
            valid_from=moment,
            first_observed_at=moment,
            last_reinforced_at=moment,
            extractor_version=EXTRACTOR_VERSION,
            source_conversation_id=source_conversation_id,
        )
        db.add(fresh)
        _attach_evidence(db, fresh, evidence)
        return fresh

    if current.object_json == payload:
        current.reinforcement_count += 1
        current.last_reinforced_at = moment
        current.confidence = max(current.confidence, confidence)
        if AUTHORITY_RANK[source_authority] > AUTHORITY_RANK[current.source_authority]:
            current.source_authority = source_authority
        _attach_evidence(db, current, evidence)
        _maybe_promote(db, current, source_authority=source_authority, created_by=created_by)
        return current

    replacement = UserMemory(
        memory_key=current.memory_key,
        version=current.version + 1,
        user_id=numeric_user_id,
        kind=kind,
        subject=subject,
        predicate=predicate,
        object_json=payload,
        search_text=search_text,
        status=_initial_status(source_authority, created_by),
        confidence=confidence,
        importance=max(importance, current.importance),
        source_authority=source_authority,
        created_by=created_by,
        valid_from=moment,
        first_observed_at=moment,
        last_reinforced_at=moment,
        supersedes_id=current.id,
        extractor_version=EXTRACTOR_VERSION,
        source_conversation_id=source_conversation_id,
    )

    # Không tự chọn giá trị khi cùng một fact xuất hiện với object khác. Cả hai
    # version vẫn truy hồi được để UI propose cho người dùng; thao tác confirm
    # hoặc edit của user mới đóng conflict.
    current.status = "disputed"
    replacement.status = "disputed"

    db.add(replacement)
    _attach_evidence(db, replacement, evidence)
    return replacement


def _maybe_promote(db: Session, memory: UserMemory, *, source_authority: str, created_by: str) -> None:
    """Compatibility hook cho callers cũ; memory mới không chờ promotion."""
    if memory.status != "candidate":
        return
    if source_authority == "user" and created_by in {"user", "import"}:
        memory.status = "confirmed"
        memory.source_authority = "user"
        return
    if source_authority == "official":
        memory.status = "confirmed"
        return
    if memory.negative_feedback_count == 0 and count_evidence(db, memory) >= PROMOTION_MIN_EVIDENCE:
        memory.status = "confirmed"


def set_status(db: Session, memory: UserMemory, new_status: str, *, at: datetime | None = None) -> UserMemory:
    """Đổi trạng thái theo đúng các cạnh của state machine §3."""
    if new_status not in MEMORY_STATUSES:
        raise ValueError(f"status không hợp lệ: {new_status}")
    if new_status not in ALLOWED_TRANSITIONS[memory.status]:
        raise ValueError(f"Không được chuyển {memory.status} sang {new_status}.")
    memory.status = new_status
    if new_status in {"superseded", "rejected", "forgotten"}:
        memory.valid_to = at or _now()
    db.add(memory)
    return memory


def confirm_memory(
    db: Session, user_id: str | int, memory_key: str, *, version: int | None = None
) -> UserMemory | None:
    """Người dùng xác nhận một fact. Đây là đường thăng cấp mạnh nhất của §5."""
    memory = _latest_active_by_key(db, int(user_id), memory_key, version=version)
    if memory is None:
        return None
    if memory.status in {"candidate", "disputed"}:
        set_status(db, memory, "confirmed")
    memory.source_authority = "user"
    memory.confidence = 1.0
    memory.last_reinforced_at = _now()
    _close_other_disputed_versions(db, memory)
    return memory


def revise_memory(
    db: Session,
    user_id: str | int,
    memory_key: str,
    object_value: object,
    *,
    evidence: list[EvidenceRef],
) -> UserMemory | None:
    """Tạo phiên bản mới từ chỉnh sửa tường minh của user, không ghi đè lịch sử."""
    current = _latest_active_by_key(db, int(user_id), memory_key)
    if current is None:
        return None
    replacement = record_memory(
        db,
        user_id,
        kind=current.kind,
        subject=current.subject,
        predicate=current.predicate,
        object_value=object_value,
        source_authority="user",
        created_by="user",
        evidence=evidence,
        confidence=1.0,
        importance=current.importance,
        source_conversation_id=current.source_conversation_id,
    )
    # Đây là quyết định explicit của user, nên không để nó treo như auto
    # conflict: version mới thắng, version cũ chỉ còn trong lịch sử.
    if replacement.id != current.id:
        current.status = "superseded"
        current.valid_to = _now()
        replacement.status = "confirmed"
        replacement.source_authority = "user"
        replacement.confidence = 1.0
    return replacement


def reject_memory(db: Session, user_id: str | int, memory_key: str) -> UserMemory | None:
    """Người dùng nói fact này sai.

    §11 đòi sửa chữa tường minh phải thắng trí nhớ suy ra, nên bản bị từ chối
    đóng lại ngay và không quay lại truy hồi mặc định nữa. Dòng vẫn còn để lần
    sau luật trích không dựng lại đúng fact đó rồi coi như mới.
    """
    memory = _latest_active_by_key(db, int(user_id), memory_key)
    if memory is None:
        return None
    memory.negative_feedback_count += 1
    if memory.status == "candidate":
        set_status(db, memory, "rejected")
    else:
        set_status(db, memory, "forgotten")
    return memory


def _latest_active_by_key(
    db: Session, user_id: int, memory_key: str, *, version: int | None = None
) -> UserMemory | None:
    rows = db.execute(
        select(UserMemory)
        .where(
            UserMemory.user_id == user_id,
            UserMemory.memory_key == memory_key,
            UserMemory.status.in_(tuple(ACTIVE_STATUSES)),
            *( [UserMemory.version == version] if version is not None else [] ),
        )
        .order_by(UserMemory.version.desc())
    ).scalars()
    return next(iter(rows), None)


def get_active_memory(db: Session, user_id: str | int, memory_key: str) -> UserMemory | None:
    """Public user-scoped lookup cho API mutation orchestration."""
    return _latest_active_by_key(db, int(user_id), memory_key)


def _close_other_disputed_versions(db: Session, winner: UserMemory) -> None:
    """Sau khi người dùng phân xử, các bản disputed cùng key phải đóng lại."""
    rows = db.execute(
        select(UserMemory).where(
            UserMemory.user_id == winner.user_id,
            UserMemory.memory_key == winner.memory_key,
            UserMemory.status == "disputed",
        )
    ).scalars()
    now = _now()
    for row in rows:
        if row.id == winner.id:
            continue
        row.status = "superseded"
        row.valid_to = now


def recall(
    db: Session,
    user_id: str | int,
    query: str = "",
    *,
    kinds: list[str] | None = None,
    limit: int = 8,
    at: datetime | None = None,
    include_candidates: bool = True,
    min_score: float = 0.0,
    query_embedding: list[float] | None = None,
) -> list[ScoredMemory]:
    """Truy hồi memory của đúng user, xếp theo công thức §7.

    Lọc theo user và theo thời gian trước rồi mới tính điểm, đúng thứ tự §7
    bước 1. `at` mặc định là bây giờ; truyền mốc quá khứ thì hàm trả về giá trị
    đã hiệu lực tại mốc đó, nên câu hỏi về quá khứ không bị fact mới đè lên.

    Truyền `query_embedding` thì hàm chạy chế độ lai của ADR-006: một nhánh khớp
    từ khoá, một nhánh vector, hợp nhất bằng RRF. Bỏ trống — hoặc DB không phải
    PostgreSQL, hoặc cờ tắt — thì chạy nhánh từ khoá như cũ. Hàm này không tự
    nhúng: nhúng là lời gọi mạng có chặn, để caller quyết định chạy ở đâu.

    `user_id` luôn đến từ token đã xác thực ở tầng API. Không có tham số nào cho
    model tự chọn user, và cũng không nên thêm.
    """
    numeric_user_id = int(user_id)
    moment = at or _now()
    statuses = ACTIVE_STATUSES if include_candidates else ACTIVE_STATUSES - {"candidate"}
    # `superseded` phải vào truy vấn, không thì câu hỏi về quá khứ mất phiên bản
    # đúng của quá khứ (§6). Nó tự rơi ra ở bộ lọc khoảng hiệu lực bên dưới khi
    # câu hỏi là về hiện tại, vì valid_to của nó luôn nằm trước bây giờ.
    # `rejected` và `forgotten` thì không: chúng đã bị người dùng gỡ đi.
    statuses = statuses | {"superseded"}

    stmt = select(UserMemory).where(
        UserMemory.user_id == numeric_user_id,
        UserMemory.status.in_(tuple(statuses)),
    )
    if kinds:
        stmt = stmt.where(UserMemory.kind.in_(tuple(kinds)))

    query_tokens = _tokens(query)
    decay_cutoff = moment - timedelta(days=CANDIDATE_DECAY_DAYS)

    # Bước 1 của §7: lọc trước, chấm điểm sau. Mọi bộ lọc quyền và thời gian
    # phải xong ở đây, để hai nhánh tìm bên dưới không bao giờ nhìn thấy dòng
    # mà người dùng không được thấy.
    candidates: list[UserMemory] = []
    for memory in db.execute(stmt).scalars():
        valid_from = _as_aware(memory.valid_from)
        valid_to = _as_aware(memory.valid_to)
        if valid_from is not None and valid_from > moment:
            continue
        if valid_to is not None and valid_to <= moment:
            continue
        # Candidate nguội quá lâu thì rơi khỏi truy hồi mặc định (§9). Nó vẫn
        # nằm trong DB và vẫn xem được qua API danh sách memory.
        if memory.status == "candidate" and (_as_aware(memory.last_reinforced_at) or moment) < decay_cutoff:
            continue
        candidates.append(memory)

    if not candidates:
        return []

    vector_rank = _vector_ranks(db, [row.id for row in candidates], query_embedding)
    keyword_rank = _keyword_ranks(candidates, query_tokens, moment)

    scored: list[ScoredMemory] = []
    for memory in candidates:
        if vector_rank:
            # Chế độ lai: điểm RRF chuẩn hoá thay chỗ cho khớp từ khoá, đúng
            # bước 4 và bước 5 của §7.
            relevance = _rrf_relevance(keyword_rank.get(memory.id), vector_rank.get(memory.id))
        else:
            relevance = None
        item = score_memory(
            memory,
            query_tokens,
            moment,
            relevance=relevance,
            keyword_rank=keyword_rank.get(memory.id),
            vector_rank=vector_rank.get(memory.id),
        )
        if item.score <= min_score:
            continue
        scored.append(item)

    scored.sort(key=lambda item: (item.score, item.memory.id), reverse=True)
    return scored[:limit]


async def arecall(db: Session, user_id: str | int, query: str = "", **kwargs) -> list[ScoredMemory]:
    """Bản async của `recall`, nhúng câu hỏi ngoài event loop.

    Cơ chế: đẩy lời gọi nhúng có chặn sang worker thread rồi truyền vector đã có
    vào `recall`. Gọi thẳng `embed_memory_text` trong một endpoint async sẽ giữ
    event loop suốt thời gian chờ HTTP, tức là chặn mọi request khác của tiến
    trình — ADR-006 §6.
    """
    embedding = await asyncio.to_thread(embed_memory_text, query)
    return recall(db, user_id, query, query_embedding=embedding, **kwargs)


def expand_related_memories(
    db: Session,
    user_id: str | int,
    seeds: list[ScoredMemory],
    *,
    limit: int = 4,
    at: datetime | None = None,
) -> list[tuple[UserMemory, str]]:
    """Mở rộng context bằng các cạnh giải thích được từ memory hiện có.

    Cùng version chain, subject, entity trong bộ ba hoặc evidence là các cạnh
    graph tối thiểu; không cần dịch vụ ngoài và không tạo candidate mới.
    """
    if not seeds or limit <= 0:
        return []
    moment = at or _now()
    seed_memories = [item.memory for item in seeds]
    seed_ids = {memory.id for memory in seed_memories}
    seed_keys = {memory.memory_key for memory in seed_memories}
    seed_subjects = {_normalize(memory.subject) for memory in seed_memories if memory.subject}
    seed_tokens = set().union(*(_tokens(f"{memory.subject} {(memory.object_json or {}).get('value', '')}") for memory in seed_memories))
    seed_evidence = {
        (row.evidence_type, row.evidence_ref)
        for memory in seed_memories
        for row in list_memory_evidence(db, memory.id)
    }
    rows = db.execute(
        select(UserMemory).where(
            UserMemory.user_id == int(user_id),
            UserMemory.status.in_(("confirmed", "disputed", "superseded")),
        )
    ).scalars()
    ranked: list[tuple[int, UserMemory, str]] = []
    for memory in rows:
        if memory.id in seed_ids:
            continue
        valid_from = _as_aware(memory.valid_from)
        valid_to = _as_aware(memory.valid_to)
        if (valid_from and valid_from > moment) or (valid_to and valid_to <= moment):
            continue
        score = 0
        reasons: list[str] = []
        if memory.memory_key in seed_keys:
            score += 4
            reasons.append("same_fact_version")
        normalized_subject = _normalize(memory.subject)
        if normalized_subject in seed_subjects and normalized_subject not in GENERIC_CONTEXT_SUBJECTS:
            score += 3
            reasons.append("same_subject")
        if seed_tokens & _tokens(f"{memory.subject} {(memory.object_json or {}).get('value', '')}"):
            score += 1
            reasons.append("shared_entity")
        memory_evidence = {(row.evidence_type, row.evidence_ref) for row in list_memory_evidence(db, memory.id)}
        if seed_evidence & memory_evidence:
            score += 2
            reasons.append("shared_evidence")
        if score:
            ranked.append((score, memory, ",".join(reasons)))
    ranked.sort(key=lambda item: (item[0], item[1].updated_at or item[1].created_at), reverse=True)
    return [(memory, reason) for _, memory, reason in ranked[:limit]]


def to_prompt_payload(
    items: list[ScoredMemory],
    related: list[tuple[UserMemory, str]] | None = None,
) -> list[dict]:
    """Rút gọn cho prompt: chỉ những trường agent thật sự cần để nói cho đúng.

    Candidate chỉ tồn tại để user review, không điều khiển ordinary response.
    Lọc lại ở boundary cuối này để một caller quên đặt `include_candidates=False`
    cũng không vô tình biến suy luận chưa xác nhận thành ngữ cảnh hành vi.
    """
    payload = [
        {
            "key": item.memory.memory_key,
            "kind": item.memory.kind,
            "subject": item.memory.subject,
            "predicate": item.memory.predicate,
            "value": (item.memory.object_json or {}).get("value"),
            "status": item.memory.status,
            "source": item.memory.source_authority,
        }
        for item in items
        if item.memory.status in {"confirmed", "disputed"}
    ]
    direct_ids = {(item["key"], item["value"]) for item in payload}
    for memory, reason in related or []:
        value = (memory.object_json or {}).get("value")
        if memory.status not in {"confirmed", "disputed"} or (memory.memory_key, value) in direct_ids:
            continue
        payload.append({
            "key": memory.memory_key,
            "kind": memory.kind,
            "subject": memory.subject,
            "predicate": memory.predicate,
            "value": value,
            "status": memory.status,
            "source": memory.source_authority,
            "context_role": "related",
            "relation_reason": reason,
        })
    return payload


def list_memory_evidence(db: Session, memory_id: int) -> list[UserMemoryEvidence]:
    """Trả provenance của đúng một version để API cho user kiểm tra nguồn."""
    return list(
        db.execute(
            select(UserMemoryEvidence)
            .where(UserMemoryEvidence.memory_id == memory_id)
            .order_by(UserMemoryEvidence.id.asc())
        ).scalars()
    )


def list_memories(
    db: Session,
    user_id: str | int,
    *,
    statuses: frozenset[str] | None = None,
    limit: int = 100,
) -> list[UserMemory]:
    """Danh sách cho màn hình quản lý bộ nhớ, mới nhắc lại trước."""
    numeric_user_id = int(user_id)
    stmt = select(UserMemory).where(UserMemory.user_id == numeric_user_id)
    if statuses:
        stmt = stmt.where(UserMemory.status.in_(tuple(statuses)))
    stmt = stmt.order_by(UserMemory.last_reinforced_at.desc(), UserMemory.id.desc()).limit(limit)
    return list(db.execute(stmt).scalars())


def forget_memories(db: Session, user_id: str | int, memory_keys: list[str]) -> int:
    """Xoá cứng theo yêu cầu người dùng.

    §9 tách `forgotten` khỏi xoá cứng: trạng thái phục vụ kiểm chứng, còn khi
    người dùng đòi xoá thì dữ liệu phải biến mất, kể cả liên kết bằng chứng —
    cascade của FK lo phần đó.
    """
    if not memory_keys:
        return 0
    numeric_user_id = int(user_id)
    rows = list(
        db.execute(
            select(UserMemory).where(
                UserMemory.user_id == numeric_user_id,
                UserMemory.memory_key.in_(tuple(memory_keys)),
            )
        ).scalars()
    )
    for row in rows:
        db.delete(row)
    return len(rows)


def delete_memories_by_predicate(
    db: Session,
    user_id: str | int,
    predicates: frozenset[str] | set[str],
) -> int:
    """Xoá cứng mọi version thuộc các predicate được user yêu cầu xoá."""
    if not predicates:
        return 0
    rows = list(
        db.execute(
            select(UserMemory).where(
                UserMemory.user_id == int(user_id),
                UserMemory.predicate.in_(tuple(predicates)),
            )
        ).scalars()
    )
    for row in rows:
        db.delete(row)
    return len(rows)


def forget_by_predicate(db: Session, user_id: str | int, predicates: frozenset[str] | set[str]) -> int:
    """Đóng các memory đang hiệu lực theo tên khoá, dùng cho lệnh quên có phạm vi.

    Người dùng nói "đừng nhớ tên tôi nữa" thì fact phải rời khỏi truy hồi ngay,
    nhưng vẫn ở lại DB dưới trạng thái `forgotten` — §9 phân biệt quên với xoá
    cứng, và chỉ lệnh xoá tường minh mới được xoá hẳn.
    """
    if not predicates:
        return 0
    numeric_user_id = int(user_id)
    rows = db.execute(
        select(UserMemory).where(
            UserMemory.user_id == numeric_user_id,
            UserMemory.predicate.in_(tuple(predicates)),
            UserMemory.status.in_(tuple(ACTIVE_STATUSES)),
        )
    ).scalars()
    now = _now()
    count = 0
    for row in rows:
        row.status = "forgotten"
        row.valid_to = now
        count += 1
    return count


def clear_memories(db: Session, user_id: str | int) -> None:
    """Xoá toàn bộ memory dài hạn của một user, dùng cho lệnh quên tất cả."""
    numeric_user_id = int(user_id)
    memory_ids = [
        row.id for row in db.execute(select(UserMemory).where(UserMemory.user_id == numeric_user_id)).scalars()
    ]
    if not memory_ids:
        return
    # Xoá bằng chứng trước: sqlite không bật foreign_keys nên cascade của FK
    # không tự chạy ở môi trường test/dev.
    db.execute(delete(UserMemoryEvidence).where(UserMemoryEvidence.memory_id.in_(tuple(memory_ids))))
    db.execute(delete(UserMemory).where(UserMemory.id.in_(tuple(memory_ids))))
