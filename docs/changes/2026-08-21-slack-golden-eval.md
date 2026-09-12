# WHAT_CHANGED — Slack rule engine golden dataset + eval

| Field | Value |
| --- | --- |
| Task ID | `slack-golden-eval-20260821` |
| Status | New files only, chưa merge/deploy — chờ user review |
| Date | `2026-08-21` |
| Lead | Claude Code (theo yêu cầu trực tiếp trong chat) |
| Agents / lanes | 1 lane duy nhất, không song song |
| Base SHA | `42bd84d8d4995cbb6addfc1db9db3182a5ffa429` |
| Head SHA | chưa commit — working tree |
| PR / issue / ADR | không |

## Intent and acceptance criteria

- Intent: bổ sung golden dataset (~200 case) cho rule engine Slack
  (`src/services/slack_rules.py` — 100% rule-based, không LLM) và code eval
  đọc/chạy dataset đó, theo đúng convention đã có ở
  `eval/golden_dataset/task_extraction/` và `eval/outlook/` (JSON tự chứa
  input/expected, không phải fixture mồ côi).
- Observable acceptance criteria:
  - `eval/Slack/cases.json` tồn tại, 201 case, mỗi case có `id/group/
    description/input/expected` tự chứa.
  - `eval/Slack/eval_slack_rules.py` chạy độc lập, in bảng accuracy theo
    nhóm, exit code 0 khi không regression.
  - `tests/test_services/v1/test_slack_rules_golden.py` (pytest thật, gate
    CI) parametrize toàn bộ case, pass 100%.
  - `ruff check`/`ruff format --check` sạch trên cả 3 file mới.
- Non-goals: không đổi hành vi `slack_rules.py`/`filter_classify.py`, không
  đụng connector Slack, không commit/push.

## Changes

- Observable behavior: dataset mới, không ảnh hưởng runtime production.
- Components/files (toàn bộ file mới, không sửa file có sẵn):
  - `eval/Slack/gen_cases.py` — sinh `cases.json` bằng cách dựng
    `NormalizedMessage`/`RuleConfig` rồi gọi `evaluate_message()`/
    `extract_deadline_phrase()` **thật** để tính `expected` (không đoán tay),
    cùng cách tiếp cận `scripts/gen_outlook_pipeline_cases.py`.
  - `eval/Slack/cases.json` — 201 case, 22 nhóm bao phủ hard_filter (subtype
    hệ thống/message_changed/empty_text), từng tín hiệu scoring cô lập
    (mention/DM/thread-reply/pinned/action/deadline/urgency/program/
    newsletter), tích hợp KEEP/REVIEW/DROP thực tế, ranh giới ngưỡng chính
    xác (35/30/15/10), hành vi extract_title/extract_evidence/
    extract_deadline_phrase, và override `RuleConfig`.
  - `eval/Slack/eval_slack_rules.py` — script độc lập in bảng accuracy theo
    nhóm, dùng làm regression gate (100%, khác `task_extraction` gate 90% vì
    rule engine Slack tất định).
  - `eval/Slack/README.md` — mô tả cấu trúc, bảng nhóm case, quy tắc sửa
    dataset (luôn qua `gen_cases.py`, không sửa tay JSON).
  - `tests/test_services/v1/test_slack_rules_golden.py` — gate CI thật, đọc
    `cases.json`, parametrize assert qua `evaluate_message()` thật.
- Config/migration/API compatibility: không đổi.

## Phát hiện đáng chú ý khi sinh dataset

Vì `expected` được tính bằng cách chạy code thật (không đoán tay), phát hiện
2 hành vi thật của rule engine không lường trước lúc viết case đầu tiên —
không phải bug, ghi nhận lại trong `eval/Slack/README.md`:

- `PROGRAM_RE` (`src/services/filter_classify.py`) cũng chứa từ khoá
  `deadline`, trùng với `DEADLINE_RE` — câu có "deadline" cộng cả
  `HAS_DEADLINE_INFERRED` lẫn `PROGRAM_RELEVANCE`.
- `URGENCY_RE` khớp thuần regex trên chuỗi con "gấp" trong "không gấp đâu"
  dù câu đang phủ định tính khẩn cấp — rule engine không hiểu phủ định
  (case `SLK-124`, giữ nguyên trong dataset làm case minh hoạ giới hạn thật).

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe eval/Slack/gen_cases.py` | 201 case sinh thành công | 2026-08-21 |
| `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe eval/Slack/eval_slack_rules.py` | `201/201 100.0%`, exit 0 | 2026-08-21 |
| `.venv/Scripts/python.exe -m pytest tests/test_services/v1/test_slack_rules_golden.py -q` | `203 passed` | 2026-08-21 |
| `.venv/Scripts/python.exe -m pytest tests/test_services/v1/test_slack_rules.py tests/test_services/v1/test_slack_rules_golden.py -q` | `232 passed` (không phá test cũ) | 2026-08-21 |
| `.venv/Scripts/python.exe -m ruff check eval/Slack/gen_cases.py eval/Slack/eval_slack_rules.py tests/test_services/v1/test_slack_rules_golden.py` | `All checks passed!` | 2026-08-21 |
| `.venv/Scripts/python.exe -m ruff format --check ...` (3 file trên) | sạch sau khi chạy `ruff format` | 2026-08-21 |

## Risk / rollback / follow-up

- Risk: thấp — chỉ thêm file mới, không sửa code production, không sửa test
  cũ, không đổi migration/config.
- Rollback: xoá `eval/Slack/`, `docs/changes/2026-08-21-slack-golden-eval.md`
  và `tests/test_services/v1/test_slack_rules_golden.py`.
- Follow-up: chưa `git add`/commit — theo yêu cầu trong AGENTS.md, chỉ commit
  khi user yêu cầu rõ ràng. Khi `slack_rules.py`/`filter_classify.py` đổi
  regex/threshold, chạy lại `gen_cases.py` để cập nhật dataset thay vì sửa
  tay `cases.json`.
