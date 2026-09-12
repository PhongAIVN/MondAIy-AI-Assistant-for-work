"""Chạy golden dataset eval/outlook/ qua code thật của
OutlookConnector.normalize() -> filter_and_classify() -> select_evidence()
(3 stage deterministic đầu của docs/projects/engineering/outlook-detail.drawio)."""

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.agents.pipeline.nodes.evidence import select_evidence
from src.connectors.base import Source
from src.connectors.outlook import OutlookConnector
from src.models.connection import Connection
from src.services.filter_classify import FilterConfig, filter_and_classify

_DATASET_DIR = Path(__file__).resolve().parents[3] / "eval" / "outlook"
_SOURCE = Source(id="inbox", name="Hộp thư chính")

# Bom thời gian nổ 24/08/2026: fixture ghi ngày cố định 2026-08-10 trong khi
# lookback 14 ngày của filter tính theo đồng hồ thật — đúng chiều chiều hôm đó
# mail rơi khỏi cửa sổ và 47 golden cùng lúc đỏ dù code không đổi. Neo "bây giờ"
# vào ngày mới nhất của chính dataset (+1h) để bộ ba stage chạy trên timeline
# của fixture mãi mãi, không phụ thuộc ngày chạy test.
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")


def _iter_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)


def _fixture_now(cases: list[dict]) -> datetime:
    stamps: list[datetime] = []
    for case in cases:
        for text in _iter_strings(case.get("input", {})):
            for match in _ISO_RE.findall(text):
                try:
                    stamps.append(datetime.fromisoformat(match.replace("Z", "+00:00")))
                except ValueError:
                    continue  # chuỗi rác chủ ý ("2026-13-40…") cho case ngày lỗi
    if not stamps:
        return datetime.now(UTC)
    return max(stamps) + timedelta(hours=1)


def _load(name: str) -> list[dict]:
    return json.loads((_DATASET_DIR / name).read_text(encoding="utf-8"))


_FIXTURE_NOW = _fixture_now(_load("cases.json"))


def _normalize(case: dict) -> dict:
    connection = Connection(provider_user_id=case["input"]["provider_user_id"])
    connector = OutlookConnector(connection, db=None)
    return connector.normalize(case["input"]["raw_item"], _SOURCE)


@pytest.mark.parametrize("case", _load("cases.json"), ids=lambda c: c["id"])
def test_outlook_pipeline_case(case):
    normalized = _normalize(case)
    expected = case["expected"]

    if "normalized" in expected:
        exp_norm = expected["normalized"]
        if "id" in exp_norm:
            assert normalized["id"] == exp_norm["id"], case["description"]
        if "provider" in exp_norm:
            assert normalized["provider"] == exp_norm["provider"], case["description"]
        if "author_id" in exp_norm:
            assert normalized["author_id"] == exp_norm["author_id"], case["description"]
        if "text_equals" in exp_norm:
            # _extract_body_text() để lại khoảng trắng thừa khi thay thẻ HTML
            # bằng " " (chưa collapse) — so sánh sau khi gộp whitespace, vì đó
            # mới là phần có ý nghĩa (nội dung sạch), không khoá cứng artifact
            # whitespace vào golden case.
            assert " ".join(normalized["text"].split()) == exp_norm["text_equals"], case["description"]
        if "text_excludes" in exp_norm:
            for snippet in exp_norm["text_excludes"]:
                assert snippet not in normalized["text"], case["description"]
        if "text_contains" in exp_norm:
            collapsed = " ".join(normalized["text"].split())
            for snippet in exp_norm["text_contains"]:
                assert snippet in collapsed or snippet in normalized["text"], case["description"]
        if "is_self" in exp_norm:
            assert normalized["is_self"] == exp_norm["is_self"], case["description"]
        if "is_unread" in exp_norm:
            assert normalized["is_unread"] == exp_norm["is_unread"], case["description"]
        if "sent_at_resolved" in exp_norm:
            is_resolved = normalized["sent_at"] != "unknown"
            assert is_resolved == exp_norm["sent_at_resolved"], case["description"]
        if "sent_at_equals" in exp_norm:
            assert normalized["sent_at"] == exp_norm["sent_at_equals"], case["description"]
        if "deep_link" in exp_norm:
            assert normalized["deep_link"] == exp_norm["deep_link"], case["description"]
        if "attachments_equals" in exp_norm:
            assert normalized["attachments"] == exp_norm["attachments_equals"], case["description"]

    if "filter" not in expected and "evidence_contains" not in expected:
        return

    config = FilterConfig(user_email=case["input"]["provider_user_id"])
    result = filter_and_classify([normalized], config, now=_FIXTURE_NOW)
    exp_filter = expected.get("filter", {})

    if exp_filter.get("status") == "accepted":
        assert len(result["items"]) == 1, case["description"]
        if "must_not_miss" in exp_filter:
            assert result["items"][0]["must_not_miss"] == exp_filter["must_not_miss"], case["description"]
    elif exp_filter.get("status") == "rejected":
        assert len(result["items"]) == 0, case["description"]
        assert len(result["rejected"]) == 1, case["description"]

    if "evidence_contains" in expected:
        # Cùng lý do whitespace ở text_equals — evidence_node đọc field
        # "text" thô (chưa collapse), so khớp sau khi gộp whitespace.
        evidence_text = " ".join(select_evidence(normalized["text"]).split())
        for snippet in expected["evidence_contains"]:
            assert snippet in evidence_text, case["description"]
