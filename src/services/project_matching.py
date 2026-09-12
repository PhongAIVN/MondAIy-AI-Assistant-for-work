"""Gợi ý "hội thoại này thuộc dự án nào".

Chạy trên MỌI hội thoại chưa được xếp, nên phải rẻ và không được sập. Hai tầng:

1. Nhúng vector (tái dùng `embed_query` của lớp retrieval, cùng không gian
   nhúng với memory/chunk — ADR-006 §1). Chất lượng tốt hơn hẳn vì bắt được
   quan hệ ngữ nghĩa không trùng từ.
2. Trùng lặp từ khoá. Chạy khi chưa bật semantic recall, chưa cài pgvector,
   hoặc lần nhúng bị lỗi.

Tầng 2 KHÔNG phải phương án dự phòng cho có: nếu chỉ có tầng 1 thì cả tính năng
tắt lịm ở mọi môi trường chưa bật cờ — đúng lỗi đã gặp nhiều lần trong dự án
này (LangExtract, structured extraction) khi một nhánh mới nằm sau cờ tắt.

Đây chỉ là GỢI Ý: người dùng luôn là người bấm đồng ý. Nên ngưỡng đặt hơi cao,
thà im lặng còn hơn hỏi sai liên tục rồi bị bỏ qua như thông báo rác.
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.conversation import Conversation, ConversationMessage
from src.models.project import Project

logger = logging.getLogger(__name__)

# Dưới ngưỡng này thì không gợi ý. Cao hơn ngưỡng truy hồi thông thường vì gợi
# ý sai làm phiền người dùng ngay trên màn hình chat.
_MIN_SEMANTIC_SCORE = 0.62
_MIN_KEYWORD_SCORE = 0.28

# Hội thoại quá ngắn chưa đủ nội dung để so — hỏi lúc này chỉ là đoán mò.
_MIN_CHARS_TO_MATCH = 60

# Số lượt chat lấy làm đại diện cho hội thoại. Lấy hết thì một phiên dài sẽ
# loãng chủ đề và kéo điểm về giữa.
_MAX_TURNS = 6
_MAX_TITLES_PER_PROJECT = 8

_TOKEN_RE = re.compile(r"[\wÀ-ỹ]{3,}")

# Từ quá phổ biến, có mặt ở mọi hội thoại nên không phân biệt được dự án nào.
_STOPWORDS = frozenset(
    {
        "cho", "toi", "ban", "cua", "minh", "nay", "khong", "duoc", "voi", "nhu",
        "the", "nao", "gi", "co", "la", "va", "hay", "khi", "them", "lam",
        "the", "that", "this", "with", "have", "your", "you", "for", "and",
        "the", "can", "how", "what", "please", "would", "about",
    }
)


@dataclass(frozen=True)
class ProjectSuggestion:
    project_id: int
    project_name: str
    score: float
    method: str


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).replace("đ", "d").replace("Đ", "d")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold()


def _tokens(value: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(_fold(value)) if token not in _STOPWORDS}


def _keyword_score(left: str, right: str) -> float:
    """Jaccard có trọng số nghiêng về phía HỘI THOẠI.

    Jaccard thuần phạt dự án có mô tả dài: mẫu số phình theo phần mô tả mà hội
    thoại không nhắc tới. Ở đây câu hỏi đúng là "bao nhiêu phần nội dung hội
    thoại đã được dự án này nói tới", nên chia cho số từ của hội thoại.
    """
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def conversation_text(db: Session, conversation: Conversation) -> str:
    """Tiêu đề + vài lượt đầu — đủ để nhận ra chủ đề, không cần cả phiên."""
    turns = (
        db.execute(
            select(ConversationMessage.content)
            .where(ConversationMessage.conversation_id == conversation.id)
            .order_by(ConversationMessage.id)
            .limit(_MAX_TURNS)
        )
        .scalars()
        .all()
    )
    return " ".join([conversation.title or "", *(turn or "" for turn in turns)]).strip()


def project_text(db: Session, project: Project) -> str:
    """Mô tả dự án + tiêu đề các hội thoại đã nằm trong đó.

    Chỉ dùng mô tả thì dự án để trống mô tả sẽ không bao giờ khớp được gì —
    mà đó lại là cách phần lớn người dùng tạo dự án.
    """
    titles = (
        db.execute(
            select(Conversation.title)
            .where(Conversation.project_id == project.id)
            .order_by(Conversation.updated_at.desc())
            .limit(_MAX_TITLES_PER_PROJECT)
        )
        .scalars()
        .all()
    )
    return " ".join([project.name or "", project.description or "", *(title or "" for title in titles)]).strip()


def _embed(text: str) -> list[float] | None:
    if not text.strip():
        return None
    try:
        from src.services.memory_store import embed_memory_text

        return embed_memory_text(text)
    except Exception:  # noqa: BLE001 - nhúng hỏng thì lùi về từ khoá, không sập
        logger.info("Không nhúng được văn bản để gợi ý dự án, dùng khớp từ khoá", exc_info=True)
        return None


def suggest_project(
    db: Session, user_id: str, conversation: Conversation
) -> ProjectSuggestion | None:
    """Dự án khớp nhất cho hội thoại này, hoặc None khi không đủ chắc.

    Trả None (chứ không raise) ở mọi nhánh không chắc: hội thoại quá ngắn, chưa
    có dự án nào, hoặc điểm dưới ngưỡng.
    """
    if conversation.project_id is not None:
        return None

    projects = (
        db.execute(select(Project).where(Project.user_id == str(user_id))).scalars().all()
    )
    if not projects:
        return None

    haystack = conversation_text(db, conversation)
    if len(haystack) < _MIN_CHARS_TO_MATCH:
        return None

    candidates = [(project, project_text(db, project)) for project in projects]
    candidates = [(project, text) for project, text in candidates if text]
    if not candidates:
        return None

    conversation_vector = _embed(haystack)
    if conversation_vector:
        best: ProjectSuggestion | None = None
        for project, text in candidates:
            vector = _embed(text)
            if not vector:
                continue
            score = _cosine(conversation_vector, vector)
            if score >= _MIN_SEMANTIC_SCORE and (best is None or score > best.score):
                best = ProjectSuggestion(project.id, project.name, round(score, 4), "semantic")
        if best is not None:
            return best

    best_keyword: ProjectSuggestion | None = None
    for project, text in candidates:
        score = _keyword_score(haystack, text)
        if score >= _MIN_KEYWORD_SCORE and (best_keyword is None or score > best_keyword.score):
            best_keyword = ProjectSuggestion(project.id, project.name, round(score, 4), "keyword")
    return best_keyword
