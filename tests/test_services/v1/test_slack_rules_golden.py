"""Gate CI cho rule engine Slack (src/services/slack_rules.py) dựa trên golden
dataset dùng chung ở eval/Slack/ (JSON, theo đúng convention
"ml/model for extension/data/" và eval/outlook/).

Bộ golden đó cũng được eval/Slack/eval_slack_rules.py dùng để in bảng accuracy
theo nhóm — sửa dataset ở một chỗ duy nhất (eval/Slack/gen_cases.py sinh lại
cases.json, KHÔNG sửa tay JSON).
"""

import json
from pathlib import Path

import pytest

from src.services.slack_rules import NormalizedMessage, RuleConfig, evaluate_message, extract_deadline_phrase

_DATASET_DIR = Path(__file__).resolve().parents[3] / "eval" / "Slack"
_CASES = json.loads((_DATASET_DIR / "cases.json").read_text(encoding="utf-8"))


def test_golden_dataset_has_expected_size():
    """Chốt kích thước bộ dữ liệu — sửa JSON mà quên cập nhật số lượng dự kiến
    thì test này báo ngay."""
    assert len(_CASES) == 201
    assert len({c["id"] for c in _CASES}) == len(_CASES)


def _actual_result(case: dict) -> dict:
    raw = case["input"]
    message = NormalizedMessage(
        message_id=raw["message_id"],
        channel_id=raw["channel_id"],
        channel_type=raw["channel_type"],
        thread_ts=raw["thread_ts"],
        subtype=raw["subtype"],
        text=raw["text"],
        author_id=raw["author_id"],
        is_self=raw["is_self"],
        mentions_current_user=raw["mentions_current_user"],
        reactions=tuple(raw["reactions"]),
        is_pinned=raw["is_pinned"],
        is_thread_reply_to_self=raw["is_thread_reply_to_self"],
    )
    config = RuleConfig(**raw.get("config_overrides", {}))
    decision, title, evidence = evaluate_message(message, config)
    return {
        "decision": decision.decision,
        "score": decision.score,
        "reasons": sorted(decision.reasons),
        "title": title,
        "evidence": evidence,
        "deadline_phrase": extract_deadline_phrase(message),
    }


@pytest.mark.parametrize("case", _CASES, ids=lambda c: c["id"])
def test_golden_case_matches_expected(case: dict):
    actual = _actual_result(case)
    expected = case["expected"]
    for field, expected_value in expected.items():
        assert actual[field] == expected_value, (
            f"{case['id']} ({case['group']}).{field}: kỳ vọng {expected_value!r} nhưng rule trả "
            f"{actual[field]!r} — {case['input']['text']!r}"
        )


def test_golden_dataset_overall_accuracy_is_100_percent():
    """Rule engine 100% rule-based, tất định — khác task_extraction (is_task_like
    có sai số nên chỉ gate 90%), ở đây sai lệch bất kỳ case nào cũng là
    regression thật, không phải rule chưa đủ thông minh."""

    def _case_is_correct(case: dict) -> bool:
        actual = _actual_result(case)
        return all(actual[field] == value for field, value in case["expected"].items())

    total = len(_CASES)
    correct = sum(1 for c in _CASES if _case_is_correct(c))
    assert correct == total, (
        f"{total - correct}/{total} case sai lệch — chạy eval/Slack/eval_slack_rules.py để xem chi tiết"
    )
