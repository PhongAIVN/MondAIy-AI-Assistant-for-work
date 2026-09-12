# Repository setup — mondaiy

| Thuộc tính | Giá trị |
| --- | --- |
| Status | In review |
| Owner | Nguyễn Văn Phong (Technical Lead) |
| Author | Thái Hoài An (PM) |
| Reviewers | Workstream Leads, PO/QC |
| Last updated | 2026-08-01 |
| Source of truth | Có — target repo layout, ownership và delivery rules |
| Related | [Architecture](architecture.md) · [Roadmap](../product/roadmap-6-weeks.md) · [Jira TAPB](https://vinait004.atlassian.net/jira/software/projects/TAPB/boards/2/backlog?atlOrigin=eyJpIjoiMzY5ODc1NjNiNzkyNGI5OGJlYWE3MGE5NzFhNDhmMTMiLCJwIjoiaiJ9) |

## Repository đề xuất

Monorepo:

```text
personal-contextual-assistant/
├── apps/
│   └── extension/                 # WXT + TypeScript Chrome MV3
├── services/
│   ├── api/                       # FastAPI
│   └── worker/                    # ingestion/memory/brief jobs
├── packages/
│   ├── contracts/                 # OpenAPI-generated TS types + JSON schemas
│   └── fixtures/                  # synthetic/redacted shared fixtures
├── evals/                         # golden-set runner và reports
├── infra/
│   ├── migrations/                # Supabase/Postgres migrations
│   ├── docker/
│   └── scripts/
├── tests/
│   ├── contract/
│   ├── integration/
│   └── e2e/
├── docs/
│   ├── context/
│   ├── product/
│   ├── engineering/
│   ├── design/
│   ├── qa/
│   ├── competitive/
│   └── usecases/
├── .github/
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── CODEOWNERS
│   └── workflows/
├── AGENTS.md
├── CONTRIBUTING.md
└── README.md
```

`mvp-extension/` hiện tại được giữ như technical spike cho tới khi behavior quan trọng đã có contract test trong `apps/extension/`. Không rewrite mù hoặc xóa spike trước migration.

## Ownership

| Path | Owner |
| --- | --- |
| `apps/extension/` | Extension Lead |
| `services/api/`, `infra/migrations/` | Backend/Platform Lead |
| `services/worker/`, `evals/` | AI/Memory Lead |
| `packages/contracts/` | Integrator/Tech Lead |
| `tests/e2e/`, `docs/qa/` | QA Lead |
| `docs/context/`, `docs/product/` | PM |

Shared contract/schema chỉ được merge bởi owner sau review của affected lanes.

## Branch và multi-agent workflow

- Mỗi agent dùng branch/worktree riêng.
- Task dài tối đa 0,5–1,5 ngày.
- Contract/fixture được merge trước parallel implementation.
- Không có hai agent cùng sửa migration, OpenAPI hoặc một UI component.
- PR merge theo vertical slice, không theo “backend done” riêng biệt.
- Mỗi PR được một agent/người không phải tác giả review.
- Integrator chạy full contract/E2E sau mỗi daily merge.

Branch naming luôn kèm Jira key:

```text
feat/TAPB-79-ext-durable-outbox
feat/TAPB-80-api-capture-batch
feat/TAPB-81-memory-versioning
test/TAPB-90-e2e-source-conflict
docs/TAPB-87-prd-memory-lifecycle
```

## CI bắt buộc

### Mọi PR

- Format/lint/typecheck.
- Secret/PII scan.
- Unit/property tests.
- OpenAPI/JSON Schema compatibility.
- Migration + RLS integration tests.
- Docs broken-link/duplicate-source check.
- Changed AI component → golden subset regression.

### Nightly

- Full golden set.
- Chrome E2E với unpacked extension.
- Live OpenRouter smoke có cost cap.
- Dependency/license/SBOM scan.
- Load/queue soak ở fixture scale.

### Release

- Full E2E killer journey.
- Backup/restore và rollback check.
- Permission/revoke/delete tests.
- Performance 50-user load.
- Pilot blockers = 0.

## Required repository files

- `AGENTS.md`: scope, verify commands, ownership và forbidden changes.
- `.env.example`: chỉ tên biến; không secret.
- `CODEOWNERS`: theo bảng ownership.
- PR template: PRD/ADR link, behavior, failure state, tests, analytics, migration/rollback.
- Jira templates/required fields: Story, Task, Bug/privacy incident, evaluation
  failure và material decision.
- Dependabot/Renovate và license policy.

## Initial Jira epics

1. `[Platform] Auth, RLS và canonical schema`
2. `[Capture] Durable browser outbox và versioned evidence`
3. `[Meeting] Transcript import và Vexa adapter`
4. `[Memory] Candidate, promotion, version và retrieval`
5. `[Vertical] Program Frame và Daily Brief`
6. `[Ask] Structured claims và citation validator`
7. `[Act] Action Draft, reminder và Calendar handoff`
8. `[Quality] Golden set, Chrome E2E và pilot runbook`

Mỗi issue phải có outcome, owner, due date, dependency, acceptance criteria, failure/empty states, analytics và command/evidence kiểm thử.

Không dùng GitHub Issues/Projects làm backlog thứ hai. GitHub quản lý code,
pull request và CI; Jira quản lý Epic/Story/Task/Bug, sprint, assignee,
dependency và trạng thái.

## OSS policy

- Không copy NativeMind code vào proprietary core nếu chưa xử lý AGPL implications.
- MIT/Apache code có thể reuse theo license/NOTICE.
- Ưu tiên SDK/service dependency hoặc adapter hơn fork toàn repo.
- Pin version/commit cho Hindsight, Vexa và provider integrations.
- `draft/` không được import trực tiếp vào production build.
