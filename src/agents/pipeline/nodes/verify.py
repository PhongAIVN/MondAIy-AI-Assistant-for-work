from __future__ import annotations

import re
import unicodedata

from src.agents.pipeline.state import PipelineState


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower()).strip()


def _is_grounded(source_text: str, claim: str) -> bool:
    """Claim rỗng = không có gì để verify -> coi như hợp lệ. Có claim thì
    phải là substring của source_text sau khi chuẩn hóa dấu/hoa-thường (LLM
    có thể đổi hoa/thường hoặc dấu câu so với bản gốc)."""
    if not claim:
        return True
    return _normalize(claim) in _normalize(source_text)


def verify_node(state: PipelineState) -> dict:
    """Fact Verification — không tin thẳng field LLM sinh ra (time_expression,
    assignee_hint). Field nào không xuất hiện trong text gốc của message thì
    bị xóa (coi như "không có thông tin"), KHÔNG loại bỏ cả item — loại cả
    item vì 1 field lệch sẽ làm giảm recall, trong khi field đó vốn không
    phải điều kiện quyết định email có phải việc-cần-làm hay không (filter_node
    đã quyết định điều đó ở bước trước).

    Jira/Slack đi rule-based (jira_rules.py/slack_rules.py), evidence lấy
    trực tiếp từ description/text bằng regex match -> grounded theo thiết
    kế, bỏ qua bước này."""
    verified: list[dict] = []
    stats = {"total": 0, "time_expression_cleared": 0, "assignee_hint_cleared": 0}

    for item in state.get("extracted", []):
        stats["total"] += 1
        message = item.get("message", {})
        if message.get("provider") in ("jira", "slack"):
            verified.append(item)
            continue

        source_text = message.get("text", "")
        checked = dict(item)

        if not _is_grounded(source_text, checked.get("time_expression", "")):
            checked["time_expression"] = ""
            stats["time_expression_cleared"] += 1

        if not _is_grounded(source_text, checked.get("assignee_hint", "")):
            checked["assignee_hint"] = ""
            stats["assignee_hint_cleared"] += 1

        checked["fact_verified"] = True
        verified.append(checked)

    return {"extracted": verified, "verification_stats": stats}
