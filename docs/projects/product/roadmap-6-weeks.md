# Roadmap sáu tuần — mondaiy MVP

| Thuộc tính | Giá trị |
| --- | --- |
| Status | In review |
| Owner | Thái Hoài An (PM) + Nguyễn Văn Phong (Technical Lead) |
| Reviewers | Workstream Leads, QA Lead |
| Last updated | 2026-08-02 |
| Related | [PRD](prd.md) · [PM operations](../pm/PM_TEAM_ASSISTANT.md) · [Evaluation](../qa/evaluation-plan.md) |

## Outcome

Sau sáu tuần, một user trong cohort pilot phải hoàn thành được:

```text
Calendar / Jira / Discord / VLearn / Gmail
→ evidence + memory/version
→ personalized Brief
→ grounded Ask
→ confirmed reminder/Calendar handoff
```

Không đánh giá thành công bằng số connector hoặc số dòng code.

## Workstreams

| Lane | Ownership |
| --- | --- |
| Integrator/Architecture | Contracts, ADR, integration, CI và release gates |
| Product UI | Web app, nguồn kết nối, Brief, Ask, Memory và Act |
| Platform | Connector, FastAPI, Supabase/RLS, ingestion, jobs, audit và deploy |
| Memory/AI | Extraction, memory lifecycle, retrieval, Pydantic AI và evaluation |

Từ tuần 4, xoay một slot sang integration/product QA cho các connector đạt gate và adversarial E2E.

## Weekly plan

| Tuần | Outcome | Exit gate | Demo |
| --- | --- | --- | --- |
| 1 — Contract | Scope/ADR, monorepo, OpenAPI/event/data schema, RLS, golden set v0; một connector đọc tới backend | Evidence có provenance; cross-user bị chặn | Source item → backend → citation |
| 2 — Evidence | Ít nhất hai connector, durable ingestion, hash/version, receipt và worker | Restart không mất item; retry không duplicate | Nguồn thay đổi → phiên bản mới |
| 3 — Memory | Candidate/promotion/version/conflict, hybrid retrieval, Program Frame, Memory Inspector basic | Canonical memory evidence coverage 100% | Hai nguồn tạo candidate/conflict |
| 4 — Brief/Ask | Daily Brief, contextual/global Ask, structured claims và citation validator | Citation 100%; unsupported fact 0; abstain pass | Source change → Brief → Ask |
| 5 — Act/Hardening | Action Draft, reminder, Calendar/ICS, source-change warning, accessibility, load/cost test, dogfood | Unsafe action 0; p95 targets; full E2E | Full killer journey |
| 6 — Pilot | 5–10 users, daily quality review, only P0 fixes, metric/failure report, Demo Day | No Sev-0/1; guardrail pass; completion rate tăng | Pilot evidence + fallback demo |

## Scope-cut order

Nếu trễ đường găng, cắt theo thứ tự:

1. Gmail connector.
2. Connector thứ ba trở lên; giữ hai nguồn ổn định nhất.
3. Calendar OAuth/write → template/ICS.
4. Hindsight → Postgres provider.
5. Admin self-serve → seed/import.
6. Push notification → in-app.

Không cắt provenance, durable outbox, versioning, citation validator, abstention, permission hoặc action confirmation.

## Multi-agent execution rules

- Mỗi task 0,5–1,5 ngày, có input/output/verify command.
- Contract và fixture merge trước parallel implementation.
- Một schema có một owner.
- Dùng worktree/branch riêng; không sửa chồng module.
- Một agent khác review.
- Merge thin vertical slice hằng ngày.
- Live model chỉ smoke/nightly; CI dùng mock/record-replay.
- Mỗi tuần dành một vòng adversarial review thay vì chỉ thêm feature.

## Release blockers

1. Permission leak.
2. Event loss hoặc duplicate do retry.
3. Canonical memory không có evidence.
4. Candidate được trình bày như confirmed.
5. Factual claim thiếu/sai citation.
6. Deadline/assignee unsupported.
7. Action trước confirm.
8. Coverage complete khi source lỗi.

## Pilot readiness

- Cohort/testers/admin DRI xác nhận.
- Consent/retention copy approved.
- Golden set human-adjudicated.
- Full connector → Brief → Ask → Act E2E pass.
- Source health/queue/model observability hoạt động.
- Rollback, delete/revoke và incident runbook có owner.
- Code freeze cuối tuần 5.
