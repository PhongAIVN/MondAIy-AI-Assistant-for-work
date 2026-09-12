from __future__ import annotations

import re

from src.agents.pipeline.state import PipelineState
from src.services.filter_classify import ACTION_RE, DEADLINE_RE, URGENCY_RE

# Email ngắn hơn ngưỡng này giữ nguyên toàn bộ — không có gì đáng để cắt bớt,
# cắt chỉ tổ mất ngữ cảnh cho câu ngắn.
_MIN_CHARS_TO_SELECT = 400
_MAX_EVIDENCE_SENTENCES = 6
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def _score_sentence(sentence: str) -> int:
    """Điểm càng cao càng đáng giữ lại — cùng bộ regex action/deadline/urgency
    dùng ở filter_classify.py, không phát minh tiêu chí mới."""
    score = 0
    if ACTION_RE.search(sentence):
        score += 2
    if DEADLINE_RE.search(sentence):
        score += 2
    if URGENCY_RE.search(sentence):
        score += 1
    return score


def select_evidence(text: str, max_sentences: int = _MAX_EVIDENCE_SENTENCES) -> str:
    """Chọn tối đa `max_sentences` câu có tín hiệu action/deadline/urgency cao
    nhất, giữ nguyên thứ tự xuất hiện gốc trong mail. Không dùng embedding —
    deterministic, rẻ, đủ để cắt bớt mail dài trước khi đưa vào LLM extract."""
    if len(text) < _MIN_CHARS_TO_SELECT:
        return text
    sentences = _split_sentences(text)
    if len(sentences) <= max_sentences:
        return text
    ranked = sorted(range(len(sentences)), key=lambda i: _score_sentence(sentences[i]), reverse=True)
    selected = sorted(ranked[:max_sentences])
    return " ".join(sentences[i] for i in selected)


def evidence_node(state: PipelineState) -> dict:
    """Evidence Selection — chọn câu có giá trị thông tin trước khi đưa vào
    extract_batch_node, thay vì đưa nguyên mail dài vào LLM.

    Ghi vào field mới `evidence_text`, KHÔNG ghi đè `text` gốc — extract_batch
    dùng evidence_text khi có, fallback về text khi không (Jira rule-based
    không qua field này, action_understanding vẫn đọc text gốc để giữ độ
    chính xác của deterministic_action_hint)."""
    filtered = state.get("filtered", [])
    for item in filtered:
        item["evidence_text"] = select_evidence(item.get("text", ""))
    return {"filtered": filtered}
