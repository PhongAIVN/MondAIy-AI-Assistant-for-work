# Memory adaptation P0 — trustworthy recall and user control

| Field | Value |
| --- | --- |
| Status | Completed |
| Owner | Tatejo / lead Codex |
| Started | 2026-08-21 |
| Completed | 2026-08-21 |
| Base | `origin/main` @ `f20ecb8` |
| Validated candidate | `5bea78f` |

## Outcome

The existing P0 memory loop adapts only from memories the user has confirmed
or explicitly stated, and every control shown in `/data-privacy/memory` changes
the context used by the agent on the next turn.

## Authority and boundary

- PRD FR-030..035 and BR-01..04 authorize candidate review, evidence, versioned
  edit, reject and delete.
- `memory-lifecycle.md` authorizes evidence-backed confirmed/disputed recall.
- `adaptive-agent-learning-plan.md` remains Draft. Chat-history skill learning,
  routine learning and personality inference remain non-goals for this change.

## Acceptance criteria

- Unconfirmed candidates remain visible for review but never enter an ordinary
  agent prompt.
- Confirmed and disputed memories still enter relevant prompts with status and
  provenance metadata.
- Delete/reset remove the mirrored explicit profile so the agent cannot retain
  a value through a second table.
- Scoped forget commands remove supported inferred goal, project and interest
  predicates from recall.
- A user can inspect evidence references and make a versioned edit from the
  Memory Inspector; the new value is used on the next turn.
- API operations remain user-scoped and include cross-user denial tests.
- Frontend covers loading, mutation failure, edit, evidence and reset states.

## Plan

- [x] Capture independent pre-implementation test matrix.
- [x] Add regression dossier and WHAT_CHANGED record.
- [x] Fix prompt eligibility and profile/semantic consistency boundaries.
- [x] Add evidence and versioned-edit API contract.
- [x] Complete Memory Inspector controls and interaction states.
- [x] Run targeted backend/frontend gates and review final diff.
- [x] Obtain independent Antigravity validation on the exact candidate SHA.

## Validation

- Backend memory suite: 50 passed.
- Frontend Node suite: 119 passed.
- Frontend Vitest suite: 343 passed across 82 files, including 7 Memory Inspector tests.
- Ruff, TypeScript and production Vite build: passed.
- Antigravity independently reviewed exact candidate `5bea78f`; no blocker, high or medium finding.

## Risks and rollback

- Existing users may see fewer inferred facts in responses until they confirm
  them; this is intentional and required by the trust boundary.
- API additions are backward compatible. Rollback is a revert of the candidate
  commit; no migration or destructive data operation is planned.
