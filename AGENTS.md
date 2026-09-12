# P-004 — Agent operating contract

`AGENTS.md` is the shared contract for Codex, Claude Code and other coding
agents. `CLAUDE.md` only imports this file; do not maintain a second rule set.

## Working relationship

The decision loop is the user and the lead agent. No external approval, PR
approval, reviewer sign-off or Jira transition is required before acting, unless
the user asks for it or a platform policy requires it.

Before any material action: research the relevant code, source of truth, current
remote/runtime state and constraints, then state scope, risks and verification
plan to the user. After that, implement, merge, push or deploy within that scope.

Research is not a ceremony — use the smallest set of primary sources, tests and
live checks that can change the decision. Never assert from stale docs; this repo
has several, and they have caused real false alarms. Record assumptions and
unresolved risks.

## Source of truth and decision boundaries

- Start at `docs/projects/README.md`. `docs/README.md` is the full map.
- `docs/WORKFLOW.md` (installed by repository-harness) describes work shape, the authority
  gate and the completion standard. It never overrides this file, the PRDs or `docs/ADR/`;
  decisions still go to `docs/ADR/`, not `docs/decisions/`.
- Read the relevant PRD before changing requirements, business rules, privacy,
  metrics or acceptance criteria.
- Read relevant ADRs and architecture before changing contracts, data flow,
  schemas or architecture.
- Jira is backlog/status/assignee/deadline context; do not create a competing
  backlog Markdown file.
- Do not silently change scope, metrics, privacy, timeline, data sources or
  architecture. Discuss material changes with the user first and record the
  resulting decision in the appropriate project source.

## AI workspace and memory

When present, `../Guidebook-Agent-Deploy/` is the control plane:

- **Local-only, tuyệt đối không lên remote.** Toàn bộ harness/control-plane
  (`Guidebook-Agent-Deploy`, memory, agent/lane config, handoff và evidence vận
  hành) chỉ tồn tại trên máy của Thái. Không copy/vendor vào P-004, không add
  submodule, không đóng vào artifact và không push repo/nội dung harness lên
  GitHub hay bất kỳ remote nào. `P-004/AGENTS.md` là hợp đồng dùng chung được
  track trong product repo; nó không biến harness local thành nội dung được
  phép publish.

- `docs/playbooks/`: orchestration, integration and deploy procedures.
- `memory/P-004/`: verified operating state, never a copy of the PRD.
- `changes/`: one evidence record per meaningful task.
- `skills/` and `claude-plugin/`: reusable workflows loaded when relevant.

Memory may not outrank PRD, ADR, Jira or executable code. Only the lead Codex
agent promotes verified facts, with source and date. Never store secrets, raw
transcripts, PII or production data.

## Research, planning and parallel work

For non-trivial work, first identify independent research, implementation,
review and test lanes. Run lanes in parallel when this reduces time without
creating conflicting writers; otherwise keep one writer and parallelize review
or validation. Multi-agent use is a tool, not an approval gate.

- Every lane has a bounded goal, acceptance criteria, owned paths and handoff.
- One file/glob has one writer at a time.
- Write agents use isolated branches/worktrees where practical.
- Agents may implement and test their lane, but only the lead integrates,
  resolves cross-lane conflicts, merges, pushes and deploys.
- No agent may expose or copy production credentials.

### Antigravity reviewer and test author

- **Antigravity is the independent reviewer for P-004.** It may read the full
  repository, inspect production-code diffs, run checks, and report correctness,
  security, regression and test-coverage findings.
- **Antigravity may write tests, but no production code.** Its write scope is
  limited to test files and test fixtures under `tests/**`,
  `client/**/tests/**` and `apps/**/tests/**`. Test-only support files must stay
  inside one of these directories.
- It may add, edit or delete a test only when the change is tied to the stated
  acceptance criteria, an invariant, a regression or a review finding. It must
  not weaken, skip, delete or broadly loosen an existing test merely to make a
  suite pass.
- Antigravity must not modify `src/**`, runtime code under `apps/**` or
  `client/**`, deployment/config/workflow files, ADRs, PRDs, or production
  data. When a test exposes a product defect, it reports the exact file,
  command and failure; Codex owns the production fix.
- Antigravity may commit its test-only branch/worktree for handoff, but it may
  not merge, push, deploy, handle credentials or resolve conflicts. Codex
  verifies the test diff and integrates it.

### Branch/worktree hygiene — required, avoid integration debt

Lesson from 2026-08-18: agent branches sat unmerged for days, one base diverged
129 commits, and 4 worktrees held their real work as uncommitted diffs — the
result was one merge resolving 87 conflicting files including auth/db code.

- **Count unmerged work with `git cherry`, not `git branch --merged`.** This repo
  squash-merges, so `--merged` reports merged branches as unmerged and inflates
  the backlog. `git cherry origin/main <branch>` marks already-landed commits
  with `-`; only `+` is real work. On 2026-08-25 a "24 branches, 14 stale" panic
  turned out to be 21 already in `main` and 2 deliberately parked. Measure before
  planning an integration sprint.
- **Do not create a worktree/branch without a clear base.** Base off the
  latest `origin/main`, or an explicitly lead-confirmed foundation branch.
  Never branch off a local "checkpoint WIP" without recording in WHAT_CHANGED
  that dependent lanes will build on it.
- **Commit before ending a session — never leave a dirty worktree.** An agent
  may not call a task done or hand it off with uncommitted changes in its
  worktree. Commit messages and branch names must match what actually
  changed — do not name a branch A while feature B's content sits uncommitted
  in it.
- **Cap divergence**: an agent branch/worktree should not live longer than
  ~3 days or drift more than ~20 commits from `origin/main` without being
  integrated or rebased. The lead must proactively scan
  (`git worktree list`, `git branch -vv`) and prompt early integration instead
  of letting work pile up into one giant merge.
- **Do not stack lanes on a long-lived local base branch.** If multiple agents
  need the same checkpoint, push it to `origin/main` (or a short-lived,
  announced integration branch) first, so child lanes diverge from
  `origin/main`, not from a local branch drifting further from it every day.
- **Integrate often, in small batches** rather than gathering everything at
  once: merge each lane as soon as it is ready instead of waiting on every
  other lane.
- Before reporting "task done", an agent should quickly self-check:
  `git status` (must be clean), `git log --oneline origin/main..HEAD` (matches
  what the branch name claims), and confirm no worktree of its own was left
  behind.

## Measure the thing you are about to claim

On 2026-08-25 the lead raised three false alarms in one session — a fake deploy
blocker, a fake 14-day production lag, a fake routing anomaly. All three came
from the same move: reading a convenient proxy and reporting it as the fact.
Before stating a number, check that the unit you counted is the unit you are
claiming, and confirm it against the authority for that fact.

Known traps in this repo:

- **Model columns are per `__tablename__`, not per file.** `src/models/*.py` may
  hold several classes (`user_memory.py` holds three), so `grep -c mapped_column`
  on a file sums unrelated tables. Build the real map from
  `Base.metadata.tables` after importing every module under `src/models/` —
  `src/models/__init__.py` does not import them all.
- **On the VM, neither the image tag nor `localhost:<port>` means what it looks
  like.** Both have burned a lead already; `RUNBOOK.local.md` carries the current
  traps and the commands that give a straight answer. Read it before asserting
  anything about what production is running.
- **Schema state lives in the database, not in the models.** Alembic now owns
  migrations (adopted 2026-08-26 from an intentionally empty baseline), but the
  25 `ensure_runtime_schema()` hand patches still run alongside it. Before any
  deploy that could touch schema, diff the real thing: dump
  `table_name|column_name` from `information_schema.columns` on production, dump
  the same from `Base.metadata`, and `comm` the two sorted lists.
- **`pytest --collect-only` passing does not mean the suite passes.** Collection
  succeeds without the settings a run needs, so a broken environment reads as
  healthy. On 2026-08-27 that misread turned 298 failing tests into "the suite is
  fine". Run the suite; never infer it from collection.
- **Check the measuring tool against the thing it claims to measure.** A guardrail
  probe asked `is_tool_allowed(phase="read")` while `action_node` allows read
  **or** compute **or** draft, and it reported five production tools as blocked
  when none were. The defect was in the instrument — written minutes earlier to
  catch exactly this class of error. Verify instruments the way you verify
  systems: break them deliberately and confirm they go red for the right reason.

A finding is not big enough to change architecture until a second, independent
measurement agrees. Do not let an unverified number reach an ADR — on 2026-08-25
a miscount became a proposal to adopt Alembic and had to be withdrawn after the
user had already approved it.

## Required evidence

Every code, config, workflow, operational-doc or deploy-state change gets a
Markdown record at `../Guidebook-Agent-Deploy/changes/YYYY-MM-DD/<task>.md` when
that workspace exists, otherwise under `docs/changes/`.

Record objective, research sources, scope, agents/ownership, base/head SHA,
observable behavior, files, commands and real results, skipped checks and why,
risk, migration/config impact, merge/deploy status, rollback and follow-up.

## Tests and completion

- New or changed code gets an observable test; bug fixes get a regression test.
- Frontend changes require affected interaction/state tests plus typecheck,
  lint and build. `client/web-app` uses npm; `client/extension` uses pnpm.
- API/auth/security changes cover success and denial paths.
- Runtime/deploy/workflow changes validate YAML, Compose and scripts.
- Documentation-only changes run relevant link/config/plugin checks.
- Do not claim completion until the final diff is reviewed, user changes are
  preserved and commands/results/limitations are recorded.

**A pass count only means something against a baseline from the same
environment.** A fresh worktree lacks the gitignored `.env` and any dependency
missing from `.venv`, which silently removes hundreds of tests from the run — on
2026-08-25 a lane reported "2299 passed before and after" from a worktree where
315 tests could not execute at all. Establish the before/after baseline in one
environment, compare the **set of failing test names** rather than the count, and
state which checks were skipped and why. Do not load the production `.env` into a
test run; the suite is built to run without it.

Prefer executable sources (`Makefile`, package scripts and CI workflows) over
copied commands in old documentation. If `.codegraph/` exists, use it before
grep/find for code understanding.

## Code and Git conventions

- Code identifiers and function names are English.
- Comments/docstrings are short Vietnamese explanations of intent or reason;
  do not comment obvious variables or use decorative numbered separators.
- Use type hints, Pydantic and SQLAlchemy conventions already established by
  the project.
- Keep LLM/provider configuration centralized in `src/config.py`.
- Use conventional commits: `feat|fix|refactor|test|docs|chore: <description>`.
- PRs are optional workflow artifacts, not an approval prerequisite. If a PR is
  useful for traceability, create it; the user and lead decide whether/when to
  merge.

## Safety and known drift

- Never commit secrets, real data or unredacted fixtures.
- Treat historical leaked keys as compromised; never reproduce them.
- Datetimes are timezone-aware; caches are permission-scoped; retries preserve
  user-edited drafts.
- Telegram vs ADR-002, custom JWT vs PRD Supabase and runtime LLM/provider vs
  OpenRouter/OD-03 are known drifts. Mention them when the task touches them;
  do not silently convert drift into a decision.

## Merge and deploy

Thái cấp **standing authorization** cho lead Codex/Tatejo được integrate, push
và deploy repo P-004 trong phạm vi công việc đã trao đổi; không cần xin lại một
phê duyệt bên ngoài hay một câu xác nhận lặp lại. Quyền này luôn đi kèm cổng
tích hợp bắt buộc dưới đây — có quyền deploy không có nghĩa là được bỏ qua nó.

### Cổng bắt buộc trước khi merge vào `main` hoặc deploy

Cổng này áp cho **thay đổi `main` và cho production action**. Push một nhánh phụ
rồi mở draft PR không kích hoạt nó: việc đó làm công việc *hiện ra*, đúng ngược
với kiểu nợ mà cổng sinh ra để chặn. Nhánh phụ chỉ cần base rõ ràng, diff sạch và
gate của chính nó. (Trước 2026-08-25 cổng ghi "mọi push", khiến lead phải lập luận
vòng quanh nó để mở một draft PR — luật bị lách là luật đặt sai phạm vi.)

1. Fetch/prune remote, rồi quét **toàn bộ** branch và worktree local/remote bằng
   `git worktree list --porcelain`, `git branch -vv --all` và `git status` trong
   từng worktree. Không chỉ kiểm tra checkout đang đứng.
2. Tìm mọi commit và diff chưa nằm trong `origin/main`, kể cả thay đổi chưa
   commit. Worktree dirty phải được chủ lane commit và handoff; lead không được
   chép hoặc ghi đè mù để làm cho sạch.
3. Thu hoạch **mọi thay đổi hợp lệ chưa tích hợp** vào một integration worktree
   sạch dựng từ `origin/main` mới nhất. Lane chỉ được loại nếu chứng minh là
   trùng, lỗi thời hoặc không hợp lệ; ghi quyết định loại và bằng chứng vào
   WHAT_CHANGED. Không được im lặng bỏ sót một lane đang dở.
4. Review conflict theo ownership, chạy đủ gate trên kết quả đã gộp, và tạo
   đúng **một SHA tích hợp**. Chỉ push SHA đó; deploy đúng artifact/SHA đã kiểm
   chứng, không deploy trực tiếp từ agent branch hay checkout dirty.
5. Nếu còn worktree không rõ trạng thái, diff chưa có chủ, conflict chưa giải
   thích hoặc test đỏ thì cổng chưa qua: dừng push/deploy và báo Thái phần còn
   thiếu. Không dùng quyền standing authorization để suy đoán hay bỏ qua nợ
   tích hợp.

Sau khi qua cổng, production action vẫn yêu cầu clean `main`, ff-only sync,
research runtime hiện tại, dry-run, rollback target và health evidence.
Production `.env` trên VM là authoritative.

Never sync secrets/data/backups/Git metadata, run `docker compose down`, or
restart database/shared proxy/other stacks on the fast path. Local VM deploy
may touch only `p004-backend` and `worker`; frontend is Vercel-managed.

**Local VM deploy is the normal path for this project, not an exception.** Thái
ships this way daily and org CI runners are slow, so waiting on GitHub Actions
before deploying is the wrong default: run `scripts/deploy_vm_local.sh` via the
deploy skill once local gates pass. No waiver, no ceremony, no asking again —
this is the standing arrangement.

CI is confirmatory, not blocking. Two limits stay hard:

- A **failed** check is a stop. Only `queued`/`pending` may be moved past, and the
  local equivalent of that check must have been run and reported instead.
- Whatever gates the change needs (`pytest`, `ruff`, `tsc`, build) must actually
  run somewhere and their real results recorded. "CI is slow" licenses skipping
  the wait, never skipping the check.

Read `../Guidebook-Agent-Deploy/docs/playbooks/integration-deploy.md` and the
deploy skill before production action.
