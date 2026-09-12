# Cold-start onboarding funnel

- Objective: expose proven image/calendar and reminder actions before a new user connects sources.
- Research: `BRIEF.md`; `docs/projects/design/wireframe-ui-flow.md`; `client/web-app/src/pages/DailyBriefingPage.tsx`; `OnboardingPage.tsx`; `TasksPage.tsx`; `chatHandoff.ts`.
- Scope/ownership: lead Codex; frontend only in `client/web-app`, plus regression tests and `BAOCAO.md`.
- Base/head: `origin/main` / working tree `feat/cold-start-onboarding` (uncommitted by instruction).
- Observable behavior: image picker reuses `acceptImageFile`; onboarding image/prompt handoffs enter `/briefing`; cold-start card is gated by loaded empty connections/tasks and per-user dismiss storage.
- Files: `src/pages/DailyBriefingPage.tsx`, `src/pages/OnboardingPage.tsx`, `src/lib/chatHandoff.ts`, `src/stores/usePipelineRunStore.ts`, translations, two test files.
- Commands/results: baseline Vitest 401 pass; final `npx vitest run` 410 pass/94 files; `npx tsc --noEmit` pass; `npx oxlint` pass with pre-existing warnings; `npm run build` pass.
- Negative proof: deliberately inverted `connectionsLoaded` condition; targeted cold-start test failed; condition restored and full suite passed.
- Skipped: production/runtime/deploy checks; out of brief scope and no deploy requested.
- Risk: File in router history state is one-shot and not reload-persistent; dismiss storage failure may allow invite to reappear in private mode.
- Migration/config: none. Rollback: revert the listed frontend/test/docs diff.
- Merge/deploy: not committed, merged, pushed, or deployed.
