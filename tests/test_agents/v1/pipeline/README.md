# Agent pipeline tests

The test suite is intentionally split by execution boundary:

- `nodes/`: unit tests for every pipeline node. Each test uses an in-memory
  SQLite database, fake connector data, and a mocked LLM path only.
- `test_graph_e2e.py`: graph-level tests. They verify the complete node order
  and that a summary request exits after evidence filtering without entering
  task extraction, resolution, clustering, reduction, or persistence.
- `test_conditional_routing.py`: focused routing tests for summary versus the
  backwards-compatible task-extraction flow.
- `conftest.py`: shared isolated database and deterministic Gmail message
  fixture; no mailbox, OAuth token, OpenRouter request, or external service is
  used.

Run this layer with:

```powershell
python -m pytest -q tests/test_agents/v1/pipeline
```

Coverage gate (branch coverage, default minimum 80%):

```powershell
./scripts/test_agent_coverage.ps1
```

The command prints missing lines and writes an HTML report to `htmlcov/`.
Override the gate when auditing locally, for example
`./scripts/test_agent_coverage.ps1 -MinCoverage 70`.

For the broader quality suite (API, agents, connectors, services, guardrails
and Gmail filtering), use `./scripts/test_quality.ps1`. It also writes
`test-results/summary.json`, `pytest.xml`, `pytest.log`, `failures.log`, and
`coverage.xml`.

After the suite, `eval/evaluation-evidence.md` is generated from those
artifacts. Optional RAG/performance/user-feedback inputs follow the schema in
`eval/evaluation_metrics.example.json` and can be supplied as
`eval/evaluation_metrics.json`.

The production graph receives `mode="summary"` for Gmail briefing runs. A
missing mode defaults to `task_extraction`, preserving existing sync behavior.
