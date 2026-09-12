# Gate 2 — Working MVP & feedback

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Planned |
| Owner | Thái Hoài An (PM) |
| Deadline | 2026-08-16 — cuối Sprint 3 |
| Snapshot | Git tag `p004-gate-2` — chưa tạo |
| Verdict | Chưa đánh giá |

## Submission checklist

- [ ] Demo được vertical slice Brief → Ask → Act trên dữ liệu
  synthetic/redacted.
- [ ] Capture/evidence/memory slice chứng minh không mất event, không duplicate
  và fact có provenance.
- [ ] Link commit/tag và hướng dẫn chạy tái lập.
- [ ] [PRD](../../product/prd.md), UI/design và kiến trúc phản ánh đúng bản đã
  demo.
- [ ] Có kết quả test/evaluation theo [QA plan](../../qa/evaluation-plan.md).
- [ ] Có feedback người dùng/mentor, known limitations và quyết định scope kế
  tiếp.
- [ ] Bug/blocker đã nằm trong Jira và được link từ manifest.
- [ ] Không có secret, PII hoặc raw transcript trong artifact nộp.

## Evidence

| Hạng mục | Link / trạng thái |
| --- | --- |
| Demo / recording | [Gate 2 architecture snapshot](./full.png) · [diagram index](../../../../README.md#gate-2-diagrams) |
| Git commit/tag | Git tag `p004-gate-2` — chưa tạo |
| Test/evaluation run | [Smoke, node, graph flow & coverage](./eval_evidence/GATE-2-SMOKE-TEST-REPORT.md) · [Filter golden dataset](./eval_evidence/FILTER-GOLDEN-DATASET-REPORT.md) · [Output vs expected](./eval_evidence/output_vs_expect%20response.md) |
| Feedback report | Chưa có artifact trong snapshot |
| Jira sprint/release | TBD |
| Decision / known limitations | TBD |

## Diagram index

- [Full architecture](./full.png)
- [Components](./diagram/components/overview.png) · [components flow](./diagram/components/flow.png)
- [Agent flow](./diagram/agent_flow/agent_flow.png)
- [Data flow](./diagram/data_flow/overview.png) · [full](./diagram/data_flow/full.png) · [sync](./diagram/data_flow/sync.png) · [task](./diagram/data_flow/task.png) · [agent](./diagram/data_flow/agent.png) · [brief](./diagram/data_flow/brief.png) · [action](./diagram/data_flow/action.png)
- [API contact](./diagram/contact/api_contact.png) · [intent registry](./diagram/contact/intent_reg.png)
- [Agent schema](./diagram/schema/agent_schema.png) · [tool schema](./diagram/schema/tool_schema.png) · [ERD](./diagram/schema/ERD.png)

## Eval evidence index

- [Smoke, node, graph flow & coverage report](./eval_evidence/GATE-2-SMOKE-TEST-REPORT.md)
- [Filter golden dataset report](./eval_evidence/FILTER-GOLDEN-DATASET-REPORT.md)
- [Output versus expected response review](./eval_evidence/output_vs_expect%20response.md)
- [Recent 10 question traces](./eval_evidence/recent_10_question_traces.json)
