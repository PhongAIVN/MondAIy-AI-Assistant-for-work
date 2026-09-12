# 2026-08-23 · Antigravity reviewer and test-author policy

## Objective

Make the P-004 agent boundary explicit: Antigravity reviews the full codebase
and may create or update tests, while Codex remains the only production-code
writer and integration owner.

## Authority and sources

- `AGENTS.md`
- `docs/WORKFLOW.md`
- `tests/test_agent_instructions.py`
- `tools/herdr/AGENTS.md` in the Tatejo control plane

## Scope and ownership

- Changed: `AGENTS.md` for the operating contract, plus the briefing/task-card,
  sidebar peek and memory-graph UI changes listed below.
- Added: this evidence record.
- UI/runtime files: `client/web-app/src/components/briefing/ChatTaskDraftCard.tsx`,
  `client/web-app/src/components/layout/AppShell.tsx`,
  `client/web-app/src/components/privacy/MemoryGraphView.tsx`,
  `client/web-app/src/pages/DailyBriefingPage.tsx`,
  `client/web-app/src/pages/RoutinesPage.tsx`.
- Test files: `client/web-app/tests/ChatTaskDraftCard.test.tsx`,
  `client/web-app/tests/DailyBriefingStreaming.test.tsx`,
  `client/web-app/tests/MemoryGraphView.test.tsx`.
- Antigravity may write only under `tests/**`, `client/**/tests/**` and
  `apps/**/tests/**`, including test-only fixtures/support files there.
- Antigravity may not modify production code, deployment/config/workflow files,
  ADRs, PRDs or production data.
- Codex owns production fixes, conflict resolution, integration, push and
  deploy.

## Verification

`npm exec vitest run tests/ChatTaskDraftCard.test.tsx tests/DailyBriefingStreaming.test.tsx tests/MemoryGraphView.test.tsx`
→ **3 files, 16 tests passed**.
`git diff --check` → **pass**.

The global Python 3.13 environment was not used for the final result because
its installed `langgraph`/`langchain-core` pair fails during collection
(`Reviver.__init__()` does not accept `allowed_objects`).

## Status

## Integration handoff

- Base: `origin/main` at `f5bd47e`.
- Integrated locally on `main` at merge commit `7a766a2`; the checkout is clean
  and currently ahead of `origin/main` by 10 commits.
- Final candidate validation: six Vitest files, 36 tests passed; `npm run build`
  passed; `npm run lint` exited successfully with existing warnings only.
- A duplicate React key warning remains in `RoutineDetailPage` test output; it
  is non-blocking but should be cleaned in a follow-up.
- Push/deploy: not performed. Remote fetch was blocked by the sandbox's inability
  to write `.git/FETCH_HEAD`; production deploy was not requested.
