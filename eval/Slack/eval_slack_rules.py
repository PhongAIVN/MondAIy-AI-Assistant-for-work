"""Eval/regression gate cho eval/Slack/cases.json — chạy THẬT
src/services/slack_rules.py (evaluate_message + extract_deadline_phrase) trên
từng case, so khớp với expected đã khoá lại lúc sinh dataset (xem gen_cases.py),
in bảng accuracy theo nhóm + tổng, thoát mã khác 0 nếu có case sai lệch.

Khác scripts/eval_task_classifiers.py (so sánh 3 hướng rule/LLM/hybrid vì
is_task_like có sai số): slack_rules.py 100% rule-based tất định, không có
"đúng ngưỡng chấp nhận được X%" — dataset này gate ở 100%, sai lệch nghĩa là
đổi rule engine làm hỏng hành vi cũ (regression thật), không phải rule chưa đủ
thông minh.

Chạy: PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe eval/Slack/eval_slack_rules.py
Cờ --verbose: in toàn bộ case bị sai (mặc định chỉ in tối đa 20 case đầu).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.services.slack_rules import (  # noqa: E402
    NormalizedMessage,
    RuleConfig,
    evaluate_message,
    extract_deadline_phrase,
)

_CASES_PATH = Path(__file__).resolve().parent / "cases.json"


@dataclass
class Mismatch:
    case_id: str
    group: str
    field: str
    expected: object
    actual: object
    text: str


def _load_cases() -> list[dict]:
    return json.loads(_CASES_PATH.read_text(encoding="utf-8"))


def _run_case(case: dict) -> tuple[dict, list[str]]:
    """Chạy 1 case qua real function, trả (actual_dict, list field bị sai)."""
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
    actual = {
        "decision": decision.decision,
        "score": decision.score,
        "reasons": sorted(decision.reasons),
        "title": title,
        "evidence": evidence,
        "deadline_phrase": extract_deadline_phrase(message),
    }

    expected = case["expected"]
    bad_fields = [field for field in expected if actual[field] != expected[field]]
    return actual, bad_fields


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="In toàn bộ case sai, không giới hạn 20 case đầu")
    args = parser.parse_args()

    cases = _load_cases()
    group_total: Counter[str] = Counter()
    group_correct: Counter[str] = Counter()
    mismatches: list[Mismatch] = []

    for case in cases:
        group = case["group"]
        group_total[group] += 1
        actual, bad_fields = _run_case(case)
        if not bad_fields:
            group_correct[group] += 1
            continue
        for field in bad_fields:
            mismatches.append(
                Mismatch(
                    case_id=case["id"],
                    group=group,
                    field=field,
                    expected=case["expected"][field],
                    actual=actual[field],
                    text=case["input"]["text"],
                )
            )

    total = len(cases)
    total_correct = sum(group_correct.values())
    print(f"Golden dataset: {total} case ({_CASES_PATH})\n")
    print(f"{'Nhóm':<42} {'Đúng/Tổng':<12} {'Accuracy':<10}")
    print("-" * 64)
    for group in group_total:
        correct, count = group_correct[group], group_total[group]
        print(f"{group:<42} {correct}/{count:<10} {correct / count:6.1%}")
    print("-" * 64)
    print(f"{'TỔNG':<42} {total_correct}/{total:<10} {total_correct / total:6.1%}\n")

    if mismatches:
        limit = len(mismatches) if args.verbose else 20
        print(f"=== {len(mismatches)} field sai lệch (hiện {min(limit, len(mismatches))}, dùng --verbose xem hết) ===")
        for m in mismatches[:limit]:
            print(f"  [{m.case_id}] {m.group}.{m.field}: expected={m.expected!r} actual={m.actual!r} — {m.text!r}")
        print(
            "\nSai lệch nghĩa là slack_rules.py vừa đổi hành vi so với lúc dataset được sinh — "
            "nếu đổi có chủ đích, chạy lại eval/Slack/gen_cases.py rồi review diff cases.json."
        )
        return 1

    print("Tất cả case khớp expected — không có regression.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
