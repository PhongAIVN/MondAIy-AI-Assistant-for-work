"""Sinh >=100 case cho eval/golden_dataset/evidence_verification/fact_verification_cases.json.
Chạy 1 lần để tạo file, không phải code production. Đúng/sai của mỗi case
là definitional theo cách dựng: claim khớp thì nhúng nguyên văn (hoặc biến
thể hoa/thường + dấu) vào text; claim không khớp thì dùng cụm từ chắc chắn
không xuất hiện trong text — không cần chạy verify_node để suy luận ngược."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.pipeline.nodes.verify import _is_grounded  # noqa: E402

OUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "eval"
    / "golden_dataset"
    / "evidence_verification"
    / "fact_verification_cases.json"
)

NAMES = ["Minh", "Lananh", "Huy", "Khoa", "Namdo", "Trang", "Quang", "Linh", "Phong", "Yen", "Duc", "Chi"]
DAYS_EN = ["Friday", "Monday", "Tuesday", "Wednesday", "Thursday", "Saturday", "Sunday"]
DAYS_VI = ["thứ Sáu", "thứ Hai", "thứ Ba", "thứ Tư", "thứ Năm", "thứ Bảy", "Chủ nhật"]
TASKS_EN = ["the report", "the invoice", "the proposal", "the design doc", "the budget sheet", "the survey"]
TASKS_VI = ["báo cáo", "hóa đơn", "đề xuất", "bảng khảo sát", "biểu mẫu"]


def _case(case_id: int, description: str, *, provider: str, text: str, time_expression: str, assignee_hint: str, expected_time: str, expected_assignee: str) -> dict:
    # Guard: expected phải khớp CHÍNH XÁC hành vi thật của _is_grounded — bắt
    # collision kiểu tên ngắn vô tình là substring của từ khác trong câu
    # (đã gặp: "An" là substring của "handle").
    if provider == "jira":
        actual_time, actual_assignee = time_expression, assignee_hint
    else:
        actual_time = time_expression if _is_grounded(text, time_expression) else ""
        actual_assignee = assignee_hint if _is_grounded(text, assignee_hint) else ""
    assert actual_time == expected_time, f"VER-{case_id:03d} time_expression mismatch: {description}"
    assert actual_assignee == expected_assignee, f"VER-{case_id:03d} assignee_hint mismatch: {description}"
    return {
        "id": f"VER-{case_id:03d}",
        "description": description,
        "input": {
            "provider": provider,
            "text": text,
            "time_expression": time_expression,
            "assignee_hint": assignee_hint,
        },
        "expected": {"time_expression": expected_time, "assignee_hint": expected_assignee},
    }


def build_time_matches(start_id: int, count: int) -> list[dict]:
    cases = []
    for i in range(count):
        vi = i % 3 == 0
        day = DAYS_VI[i % len(DAYS_VI)] if vi else DAYS_EN[i % len(DAYS_EN)]
        task = TASKS_VI[i % len(TASKS_VI)] if vi else TASKS_EN[i % len(TASKS_EN)]
        text = f"Xin gửi {task}, cần xong trước {day} nhé." if vi else f"Please submit {task} before {day}."
        cases.append(
            _case(
                start_id + i,
                f"time_expression '{day}' khớp nguyên văn trong text #{i + 1} -> giữ nguyên",
                provider="google",
                text=text,
                time_expression=day,
                assignee_hint="",
                expected_time=day,
                expected_assignee="",
            )
        )
    return cases


def build_time_mismatch(start_id: int, count: int) -> list[dict]:
    cases = []
    for i in range(count):
        vi = i % 3 == 0
        day_in_text = DAYS_VI[i % len(DAYS_VI)] if vi else DAYS_EN[i % len(DAYS_EN)]
        claimed_day = DAYS_VI[(i + 3) % len(DAYS_VI)] if vi else DAYS_EN[(i + 3) % len(DAYS_EN)]
        task = TASKS_VI[i % len(TASKS_VI)] if vi else TASKS_EN[i % len(TASKS_EN)]
        text = f"Xin gửi {task}, cần xong trước {day_in_text} nhé." if vi else f"Please submit {task} before {day_in_text}."
        cases.append(
            _case(
                start_id + i,
                f"time_expression '{claimed_day}' KHÔNG có trong text #{i + 1} (LLM bịa) -> bị xóa",
                provider="google",
                text=text,
                time_expression=claimed_day,
                assignee_hint="",
                expected_time="",
                expected_assignee="",
            )
        )
    return cases


def build_assignee_matches(start_id: int, count: int) -> list[dict]:
    cases = []
    for i in range(count):
        name = NAMES[i % len(NAMES)]
        task = TASKS_VI[i % len(TASKS_VI)] if i % 2 else TASKS_EN[i % len(TASKS_EN)]
        variant = i % 3
        if variant == 0:
            text = f"{name} sẽ phụ trách phần {task} lần này."
            hint = name
        elif variant == 1:
            text = f"{name} sẽ phụ trách phần {task} lần này."
            hint = name.lower()
        else:
            text = f"{name} sẽ phụ trách phần {task} lần này."
            hint = name.upper()
        cases.append(
            _case(
                start_id + i,
                f"assignee_hint '{hint}' khớp text #{i + 1} (biến thể hoa/thường) -> giữ nguyên",
                provider="google",
                text=text,
                time_expression="",
                assignee_hint=hint,
                expected_time="",
                expected_assignee=hint,
            )
        )
    return cases


def build_assignee_mismatch(start_id: int, count: int) -> list[dict]:
    cases = []
    for i in range(count):
        name_in_text = NAMES[i % len(NAMES)]
        claimed_name = NAMES[(i + 5) % len(NAMES)]
        task = TASKS_EN[i % len(TASKS_EN)]
        text = f"{name_in_text} will handle {task} this time."
        cases.append(
            _case(
                start_id + i,
                f"assignee_hint '{claimed_name}' KHÔNG có trong text #{i + 1} -> bị xóa",
                provider="google",
                text=text,
                time_expression="",
                assignee_hint=claimed_name,
                expected_time="",
                expected_assignee="",
            )
        )
    return cases


def build_both_empty(start_id: int, count: int) -> list[dict]:
    texts = [
        "FYI, sharing the weekly newsletter.",
        "Just a heads up on the office schedule.",
        "Thanks for joining the call today.",
        "Sharing this update for your awareness.",
        "Here's a quick summary of the discussion.",
    ]
    cases = []
    for i in range(count):
        text = texts[i % len(texts)]
        cases.append(
            _case(
                start_id + i,
                f"Cả 2 field rỗng #{i + 1} -> không có gì để verify, hợp lệ",
                provider="google",
                text=text,
                time_expression="",
                assignee_hint="",
                expected_time="",
                expected_assignee="",
            )
        )
    return cases


def build_jira_passthrough(start_id: int, count: int) -> list[dict]:
    cases = []
    for i in range(count):
        claimed_day = DAYS_EN[i % len(DAYS_EN)]
        claimed_name = NAMES[i % len(NAMES)]
        text = "Đội cần nộp trước thứ Sáu."
        cases.append(
            _case(
                start_id + i,
                f"Jira #{i + 1}: bỏ qua verify hoàn toàn, giữ field kể cả không khớp text (rule-based, grounded theo thiết kế)",
                provider="jira",
                text=text,
                time_expression=f"{claimed_day} not in text",
                assignee_hint=f"{claimed_name} not in text",
                expected_time=f"{claimed_day} not in text",
                expected_assignee=f"{claimed_name} not in text",
            )
        )
    return cases


def build_diacritic_cross_match(start_id: int, count: int) -> list[dict]:
    """Claim có dấu khớp text không dấu (và ngược lại) -> vẫn giữ."""
    pairs = [
        ("thứ Sáu", "Doi can nop bao cao truoc thu Sau nay."),
        ("thứ Hai", "Xin hoan thanh truoc thu Hai tuan sau."),
        ("thứ Ba", "Vui long gui lai truoc thu Ba nay."),
        ("thứ Tư", "Can xong truoc thu Tu tuan nay."),
        ("thứ Năm", "Nop bao cao truoc thu Nam ban a."),
    ]
    cases = []
    for i in range(count):
        claim, text = pairs[i % len(pairs)]
        cases.append(
            _case(
                start_id + i,
                f"time_expression có dấu #{i + 1} khớp text không dấu -> chuẩn hóa 2 chiều vẫn khớp, giữ nguyên",
                provider="google",
                text=text,
                time_expression=claim,
                assignee_hint="",
                expected_time=claim,
                expected_assignee="",
            )
        )
    return cases


def main() -> None:
    cases: list[dict] = []
    cases += build_time_matches(1, 22)
    n = len(cases) + 1
    time_mismatch = build_time_mismatch(n, 22)
    cases += time_mismatch
    n += 22
    assignee_match = build_assignee_matches(n, 18)
    cases += assignee_match
    n += 18
    assignee_mismatch = build_assignee_mismatch(n, 15)
    cases += assignee_mismatch
    n += 15
    both_empty = build_both_empty(n, 8)
    cases += both_empty
    n += 8
    jira = build_jira_passthrough(n, 10)
    cases += jira
    n += 10
    diacritic = build_diacritic_cross_match(n, 8)
    cases += diacritic
    n += 8

    assert len(cases) >= 100, f"chỉ có {len(cases)} case"
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "id trùng"

    OUT_PATH.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {OUT_PATH}")


if __name__ == "__main__":
    main()
