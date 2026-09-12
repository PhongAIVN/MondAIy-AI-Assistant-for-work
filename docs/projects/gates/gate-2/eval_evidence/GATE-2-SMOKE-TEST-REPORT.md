# Gate 2 — Smoke, Node, Graph Flow & Coverage Evidence

**Execution date:** 2026-08-15  
**Repository:** `P-004`  
**Environment:** Windows, Python 3.13.12, `.venv`, pytest 9.1.1, Node 22.16.0, npm 11.6.4

## Executive result

The pipeline node suite and the dedicated tool-flow suite pass. The complete
backend suite, graph-flow suite, frontend test suite, and frontend build do not
pass yet. This report records the observed state; no source-code fix was made
during this evaluation.

| Area | Result |
|---|---:|
| Pipeline nodes | **23 passed** |
| Graph-flow tests | **40 passed, 1 skipped, 2 failed** |
| Agent/tool-flow tests | **79 passed** |
| Full backend suite | **1062 passed, 6 skipped, 12 failed** |
| Backend pipeline coverage | **87.47%**, threshold 80% met |
| Frontend Node smoke tests | **73 passed, 1 failed** |
| Frontend Vitest | **failed**: 1 assertion failure plus missing frontend packages in 7 suites |
| Frontend lint | **pass**, warnings only |
| Frontend build/typecheck | **failed**: missing frontend packages/types |

## Commands and evidence

All command output is preserved beside this report:

| Check | Command | Evidence |
|---|---|---|
| Initial global-Python smoke | `python -m pytest ...` | [01-backend-smoke-pipeline.log](./01-backend-smoke-pipeline.log) |
| Backend pipeline/API smoke | `.venv\Scripts\python.exe -m pytest tests/test_agents/v1/pipeline tests/test_agents/v1/test_graph.py tests/test_agents/v1/test_agent_loop_hardening.py tests/test_api/v1/test_runs.py -q` | [02-backend-smoke-pipeline.log](./02-backend-smoke-pipeline.log) |
| Full backend regression | `.venv\Scripts\python.exe -m pytest tests/ -q` | [03-backend-full.log](./03-backend-full.log) |
| Individual pipeline nodes | `.venv\Scripts\python.exe -m pytest tests/test_agents/v1/pipeline/nodes -q` | [04-pipeline-node-tests.log](./04-pipeline-node-tests.log) |
| Graph flows and routing | `.venv\Scripts\python.exe -m pytest tests/test_agents/v1/pipeline/test_graph_e2e.py tests/test_agents/v1/pipeline/test_conditional_routing.py tests/test_agents/v1/test_graph.py tests/test_agents/v1/test_agent_loop_hardening.py -q` | [05-graph-flow-tests.log](./05-graph-flow-tests.log) |
| Agent/tool flows | `.venv\Scripts\python.exe -m pytest` on conversation, productivity, task, Gmail, Calendar, Jira, program-calendar, time and web-search tests | [06-agent-tool-flow-tests.log](./06-agent-tool-flow-tests.log) |
| Frontend Node smoke | `npm test` in `client/web-app` | [07-frontend-tests.log](./07-frontend-tests.log) |
| Frontend build | `npm run build` in `client/web-app` | [08-frontend-build.log](./08-frontend-build.log) |
| Frontend lint | `npm run lint` in `client/web-app` | [12-frontend-lint-result.log](./12-frontend-lint-result.log) |
| Frontend Vitest | `npx vitest run` in `client/web-app` | [10-frontend-vitest.log](./10-frontend-vitest.log) |
| Pipeline coverage | pytest with `--cov=src.agents.pipeline --cov-branch --cov-fail-under=80` | [11-backend-pipeline-coverage.log](./11-backend-pipeline-coverage.log), [XML](./backend-pipeline-coverage.xml), [JSON](./backend-pipeline-coverage.json) |

## Failed checks and observed causes

### Backend / graph

1. Two agent-loop hardening tests expect only `gmail_deadline_sweep`, while the
   current planner returns `gmail_deadline_sweep` and `gmail_bridge_search`.
2. Google login creates a user with `password_hash = NULL`, but the current
   SQLite schema/test fixture rejects that value as `NOT NULL`.
3. Meeting-note audio responses contain an additional `remainingMs` field,
   while two tests assert the older response shape.
4. The Hugging Face fail-closed test observes an environment token and therefore
   reaches the mocked HTTP client instead of returning before HTTP.
5. Reminder snooze assertion has a naive/UTC-aware datetime mismatch.
6. Gmail filter gold case `GML-F-021` is not rejected as expected.
7. Three LangSmith/Grafana dashboard tests cannot find `targets` in the parsed
   dashboard panels.

### Frontend

1. `npm test` has one failing published-extension test because the environment
   does not provide the `unzip` executable (`spawnSync unzip ENOENT`).
2. Vitest has one failing quota-feedback assertion in
   `tests/DailyBriefingStreaming.test.tsx`.
3. Several Vitest suites and the TypeScript build cannot resolve packages used by
   the app, including `gsap`, `driver.js`, and `vite-plugin-pwa`. The installed
   `node_modules` is incomplete relative to the project source.
4. Lint exits successfully but reports existing fast-refresh and one
   `react-hooks/exhaustive-deps` warning.

## Coverage detail

The dedicated filter evidence has an additional broader V1 benchmark: the
100-case Gmail workbook passes with **precision 1.0000, recall 1.0000 and F1
1.0000**. This is recorded in [FILTER-GOLDEN-DATASET-REPORT.md](./FILTER-GOLDEN-DATASET-REPORT.md)
and sourced from [mail-filter-v1-dataset-report.md](../../../../test-results/mail-filter-v1-dataset-report.md).

Backend pipeline coverage passed the configured gate:

- Statements/branch-aware total: **87.47%**
- Required minimum: **80%**
- Tests: **33 passed**
- Lowest notable modules: `time_resolve.py` 46%, `extract_batch.py` 70%

Frontend coverage was not generated because the frontend test command does not
expose a coverage script in the current package configuration, and Vitest does
not complete successfully. The backend coverage XML and JSON files are included
for CI/Gate 2 review.

## Gate conclusion

**Gate 2 evaluation: CONDITIONAL / NOT GREEN.** The core pipeline nodes,
tool-flow tests, lint, and backend coverage threshold are green. The gate should
not be marked fully passing until the 12 backend regressions, frontend dependency
installation/build issues, and frontend test failures are triaged and rerun.
