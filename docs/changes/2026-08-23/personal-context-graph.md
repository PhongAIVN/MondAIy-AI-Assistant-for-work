# WHAT_CHANGED — Personal context graph foundation

| Item | Value |
| --- | --- |
| Status | Implemented; independent review blocked |
| Base SHA | `38f2440113b0ffccadf505ce7a91f0bd0518b589` |
| Owner | Lead Codex |
| Reviewer | Antigravity (independent review required; unavailable in this runtime) |
| Scope | General personal context graph for employees, students and project-based users |

## Intent

Make the graph useful to retrieval and planning, not only a frontend visualization. The graph must connect facts, entities, tasks, goals, events and evidence while preserving user ownership, versions, conflicts and temporal validity.

## Research basis

- Zep/Graphiti: temporal facts, episodes, provenance and hybrid graph search.
- Mem0 Graph: entity linking plus vector retrieval with related relations.
- Neo4j GraphRAG: vector/full-text retrieval followed by graph traversal and multi-hop context.

## Initial acceptance criteria

- Existing `user_memories` and evidence remain the source of truth.
- Add a general relationship layer without hardcoding P004, student or employee labels.
- Retrieval can expand relevant memories through trusted relationships while preserving status, authority and time filters.
- Planning/retro code can consume the expanded context with evidence paths.
- Existing memory lifecycle and privacy boundaries remain unchanged.

## Non-goals

- No Zep/Neo4j external service in this first pass.
- No frontend-only graph decoration.
- No automatic promotion of inferred facts to confirmed facts.

## Notification

| Item | Value |
| --- | --- |
| Batch / date | `personal-context-graph` / `2026-08-23` |
| User-visible update | Planned general memory relationships for retrieval and planning |
| Scope | Backend, worker, API; frontend only after contract is stable |
| Source | Pending commit |
| Validation | `pytest --noconftest -q tests/test_services/v1/test_memory_store.py -k graph_context` — 1 passed; `python3 -m compileall` — pass; `ruff check` — pass. Full backend suite not run because local `langgraph`/`orjson` dependency mismatch blocks `tests/conftest.py`. |
| Status | Implemented; independent review blocked |
| Rollback | Revert the change commit; no migration until schema is validated |

## Implementation

- `expand_related_memories()` derives explainable context edges from existing fact versions, non-generic subjects, shared entities and shared evidence.
- Conversation agent payload receives up to four related confirmed/disputed memories with `relation_reason`; candidates remain excluded.
- No new database table, external graph service or frontend-only behavior was added.

## Review gap

Antigravity is unavailable in this runtime, so the mandatory independent review and full candidate-SHA regression gate remain outstanding.
