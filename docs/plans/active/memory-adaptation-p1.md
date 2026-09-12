# Execution Plan: P1 adaptive memory

Date: 2026-08-21

## Status

Active — planning package approved; Slice 0 implementation not started.

## Outcome

Mondaiy learns bounded, reviewable behavior from consented chat history and
user outcomes without allowing inferred data to silently change the agent.
The first usable release lets a user:

1. opt in separately to chat learning;
2. review and accept a bounded communication-style candidate;
3. observe the accepted style on the next response;
4. inspect the evidence and context versions used for that response; and
5. reset the learned behavior and immediately return to the core baseline.

Learned workflow skills and routine/schedule learning follow as separate release
trains. They do not share an all-or-nothing rollout switch.

## Context And Authority

- Product authority: PRD FR-001..005, FR-015, FR-030..035, FR-055, FR-070..073
  and BR-01..04, BR-08, BR-10, BR-13.
- Architecture authority: `memory-lifecycle.md` and the P1 sequencing document
  `adaptive-agent-learning-plan.md`.
- Validation authority: `evaluation-plan.md` and `pilot-plan.md`.
- User decision: Thái approved the P1 direction on 2026-08-21.
- Repository base: `origin/main` @ `42bd84d8d4995cbb6addfc1db9db3182a5ffa429`.
- Required dependency: P0 candidate
  `a73620600894421763e22d2b468be35feadc7140` must be integrated and revalidated
  before the first P1 code slice. P1 must not reimplement or bypass its trusted
  candidate, evidence, edit, delete and reset boundaries.

The current repository has no persisted adaptive-learning consent, no bounded
chat-review cursor, no learning-candidate store, no attribution from an
assistant message to the memory/style/skill versions used, and no accepted
retention period for chat history (`OD-02`). The onboarding privacy toggle is
not authority for chat learning.

## Release Strategy

Implement in this order:

1. **Adaptive Style MVP** — smallest end-to-end proof that history can improve
   a response while remaining visible, reversible and lower precedence than
   current instructions.
2. **Learned Skills MVP** — declarative workflows only, offline evaluation and
   manual activation; no generated executable code.
3. **Routine Learning** — structured observations and candidate review first;
   weekly schedule proposals and Calendar writes remain later gates.

Style precedes skills and routines because it can prove the complete consent →
evidence → candidate → review → behavior → feedback → rollback loop without
granting a new tool permission or creating an external side effect.

## Non-Negotiable Invariants

- Every learning capability is default-off globally and per user.
- Chat learning has consent separate from connector/source consent.
- Only user messages and observable user actions count as learning evidence.
  Assistant text may reconstruct context for evaluation but never reinforce a
  candidate.
- Raw chat is not copied into a candidate, skill, prompt log or analytics event.
- One-off behavior creates no inferred style or skill candidate.
- A candidate cannot influence an ordinary response before explicit acceptance.
- Current explicit user instruction overrides accepted style/skill for that turn.
- Core persona, safety, permission, citation, abstention and external-write
  confirmation rules are immutable from the learning loop.
- Learned skills are declarative and cannot expand the system tool allowlist.
- Conversation deletion or consent revocation excludes its evidence from the
  next review and makes dependent artifacts stale pending re-evaluation.
- Every response influenced by P1 records version references, not raw prompts,
  so feedback can be attributed and rollback can be audited.
- Cross-user access, secret/PII persistence, unsafe activation or changed
  external-write behavior are release blockers with threshold zero.

## Slice 0 Decision Package

No migration or worker implementation starts until these decisions are accepted
in a new ADR and reflected in the PRD/evaluation plan. The recommended v1
defaults are:

| Decision | Recommended v1 default |
| --- | --- |
| Consent | Separate switches for `chat_learning`, `adaptive_style`, `learned_skills`, `routine_learning`; all off |
| Review scope | User messages from explicitly included conversations only; assistant messages are context-only |
| Review cadence | On-demand first, then at most once per 24 hours after opt-in |
| Pending retention | 30 days for unreviewed candidates; then expire and leave retrieval immediately |
| Accepted artifact retention | Until reset/delete/account deletion; evidence references remain subject to source retention |
| Raw transcript handling | No copy; bounded reads from canonical conversation rows, then redacted structured signals only |
| Activation | Manual acceptance for style and every skill version during P1 pilot |
| Style allowlist | verbosity, tone, structure, initiative, clarification, language, notification style |
| Learned skill form | Declarative trigger/input/steps/output/verification; no code, shell or new tools |
| Candidate cap | Maximum 3 new suggestions per user per week and 5 pending total |
| Rejection latch | 30-day cooldown for the same stable candidate key unless the user explicitly asks to reconsider |
| Reset | Separate reset for style, skills and routines plus one reset-all action |
| Delete contract | Immediate retrieval exclusion; derived rows hard-delete within the accepted SLA |

Open policy decisions that require explicit PM/Tech Lead authority before Slice
1 are the chat-history retention period (`OD-02`), hard-delete SLA, pilot cohort,
and final evaluation thresholds. Defaults above are proposals, not hidden policy.

## Target Architecture

```text
consented conversations
  -> bounded review cursor
  -> redact + classify structured user signals
  -> dedupe/cluster across independent sessions
  -> versioned candidate + evidence references
  -> static policy/privacy validation
  -> user review
  -> accepted style profile OR offline-evaluated learned skill
  -> relevance/budget-aware context assembly
  -> response context-version references
  -> attributed user feedback
  -> bounded reinforcement, stale, rollback or reset
```

The background reviewer is a data-processing worker with structured output. It
does not run a tool-capable agent and does not share the conversation response
critical path.

## Proposed Data Contracts

Final names are owned by the Slice 0 ADR/schema review.

- `learning_consents`: one row per user and capability, state, scope, policy
  version, consented/revoked timestamps and actor.
- `learning_review_cursors`: per-user/capability high-water mark, lease, last
  success/error and extractor version; retries are idempotent.
- `learning_signals`: minimal structured signal, source message reference,
  signal type, value allowlist, outcome code and redaction version. No raw text.
- `learning_candidates` + `learning_evidence`: stable key, version, type,
  status, confidence, payload schema version, expiry, evidence references and
  rejection cooldown.
- `adaptive_style_versions`: one versioned row per dimension with authority,
  confidence, lock state and current/superseded interval.
- `learned_skills` + `learned_skill_versions`: declarative contract, evaluation
  report reference, activation/rollback state and pinned allowed-tool subset.
- `assistant_context_refs`: assistant message id plus the exact memory, style
  and learned-skill versions injected. This is the only safe basis for mapping
  answer feedback back to personalization.
- `learning_audit_events`: append-only ids/version/reason codes; no raw chat or
  compiled prompt.
- All new P1 tables use integer `user_id` foreign keys to `users.id`; the API
  converts the authenticated string claim once at its boundary. Do not repeat
  the existing mixed integer/string model convention in new schema.
- Learned routine entities use the domain names `habit_patterns` and
  `habit_candidates` (or `learning_candidates` with type `routine`) so they
  cannot be confused with the existing `routines` table of user-authored,
  scheduled automations.

New P1 tables can be created by the repository's existing `create_all` path,
but the Slice 0 ADR must define an idempotent production SQL/dry-run/rollback
procedure. Do not add more ad-hoc column migration logic to `src/db.py` without
an explicit schema-delivery decision.

## API And UX Boundaries

Proposed API family:

- `GET/PATCH /adaptive-learning/consent`
- `POST /adaptive-learning/review` for an explicit on-demand review
- `GET /adaptive-learning/candidates`
- `POST /adaptive-learning/candidates/{key}/accept|reject`
- `GET/PATCH /adaptive-learning/style`
- `GET /adaptive-learning/skills`
- `POST /adaptive-learning/skills/{key}/rollback`
- `DELETE /adaptive-learning?scope=style|skills|routines|all`

All ownership comes from the authenticated session. Mutations require candidate
version/optimistic concurrency, never a client-supplied user id.

Extend `/data-privacy/memory` into “Mondaiy đã học gì” with three explicit
sections: `Phong cách`, `Cách làm việc`, `Routine`. Every card shows evidence
summary, confidence/status, behavior diff, version and reset/rollback controls.
Consent and pause live on the same privacy surface; no onboarding checkbox may
silently enable chat learning.

## Implementation Slices

Each slice is a small branch from fresh `origin/main`, after its prerequisites
are integrated. No long-lived local stack.

### S0 — Authority and evaluation contract

- Promote the approved P1 direction into PRD requirements and a new accepted
  ADR covering consent, retention, schemas, precedence, worker isolation and
  deletion propagation.
- Pre-register a synthetic/redacted golden set and thresholds before observing
  model results.
- Produce threat model for prompt injection, PII/secret persistence, cross-user
  access, model self-reinforcement and deletion/revoke races.
- Gate: all Slice 0 decisions resolved; P0 integrated; no runtime change.

### S1 — Consent, storage and attribution foundation

- Add consent, cursor, signal, candidate/evidence, audit and context-reference
  models plus idempotent schema delivery.
- Implement user-scoped consent API, immediate revoke exclusion, reset/delete
  orchestration and audit events.
- Persist exact context version references with every assistant message.
- Persist assistant context refs in the same transaction as the assistant
  message in both regular and streaming paths. An interrupted, uncommitted SSE
  response is not feedback-eligible and cannot create orphan attribution.
- Flags: `adaptive_learning_enabled=false`, `chat_learning_worker_enabled=false`,
  plus per-capability user consent.
- Gate: success and cross-user denial tests; retry dedupe; revoke/delete drill;
  zero raw text in new derived tables/logs.

### S2 — Chat review in shadow mode

- Review bounded user-message windows behind a lease/cursor outside the response
  path.
- Redact, parse as untrusted data, emit allowlisted structured signals and
  abstain by default.
- Cluster only across independent conversations; one-off, quoted third-party
  statements and assistant messages are counterexamples.
- Shadow output is visible only to internal QA; no candidate UI or prompt use.
- Gate: injection/PII/secret suite passes; no duplicate signals on retry;
  golden-set threshold accepted in S0 is met.

### S3 — Adaptive Style MVP

- Compile eligible signals into versioned style candidates.
- Add candidate review, edit, reject, lock, pause and reset UX/API.
- Add a single context assembler used by both regular and streaming chat paths;
  inject confirmed allowlist fields only and record versions used.
- Map `helpful|partly|incorrect` feedback only to the exact context refs used;
  feedback is bounded evidence, never automatic deletion or opposite-value
  promotion.
- Gate: accepted style changes next response; candidate does not; explicit turn
  instruction wins; reset removes every P1 context fragment and restores the
  same baseline behavior contract; safety,
  citation, abstention, permission and confirmation regression deltas are zero.

### S4 — Learned Skills MVP

- Cluster repeated workflow/correction signals into a declarative candidate.
- Static scanner rejects secrets, raw ids/dates, external instructions,
  destructive steps and tools outside the existing allowlist.
- Replay each candidate on positive and counterexample fixtures; store a
  versioned immutable evaluation report reference.
- Manual acceptance activates one relevant top skill per turn within a fixed
  token budget; conflict goes to review.
- Provide diff, deactivate and one-click rollback to last-known-good.
- Gate: failing candidate cannot activate; one-off does not create a skill;
  rollback removes the skill from the next context assembly; no task-success
  or safety regression beyond the S0 threshold.

### S5 — Routine learning without Calendar write

- Normalize consented task/calendar/proposal outcomes into minimal structured
  observations and use a deterministic, versioned detector.
- Candidate requires at least 3 observations across 2 independent weeks and an
  allowlisted non-sensitive category.
- Add accept/edit/dismiss/pause/forget controls and stable rejection latch.
- Gate: one-off and sensitive cases create no candidate; source revoke removes
  eligibility; Calendar conflict is not negative preference feedback.

### S6 — Weekly proposals and explicit Calendar execution

- Build a one-week proposal from accepted routines using hard timezone, busy
  interval, deadline, quiet-hour, buffer and daily-load constraints.
- Preview and edit locally; reuse the existing Calendar executor only after
  explicit item selection and confirmation.
- Gate: no write before confirmation, retry creates no duplicate, partial
  failure is recoverable and every item has reason codes.

### S7 — Pilot and expansion decision

- Internal shadow → dogfood → small opt-in canary; style, skills and routines
  have independent flags and rollback.
- Run deletion/revoke, worker-stop, provider-timeout and rollback drills.
- Publish aggregate metrics only; no raw conversation/title content.
- Proceed, iterate or stop each release train independently.

## Pre-Registered Evaluation Matrix

The S0 owners must finalize numbers before running the models. Recommended
starting gates:

| Dimension | Proposed gate |
| --- | --- |
| Canonical/accepted artifact evidence coverage | 100% accessible evidence |
| Cross-user leak, unsafe activation, raw secret/PII persistence | 0 |
| One-off/assistant-only candidate creation | 0 on bounded negative set |
| Style candidate precision | ≥90% on adjudicated set |
| Style adherence after acceptance | ≥90%, with safety/citation/permission delta = 0 |
| Skill candidate precision | ≥85% on adjudicated repeated-workflow set |
| Skill security/counterexample evaluation | 100% pass required for activation |
| Retry duplicates | 0 |
| Candidate volume | ≤3 new suggestions/user/week; ≤5 pending |
| Revoked evidence used after revoke | 0 |

Minimum new golden fixtures:

- repeated explicit concise preference across sessions;
- one-off formatting request;
- explicit current-turn instruction conflicting with accepted style;
- assistant hallucination followed by no user endorsement;
- quote about another person's preference;
- prompt injection and fake system instruction inside history;
- secret/API key and sensitive-category text;
- repeated workflow with observable positive outcomes;
- same words but different task class;
- skill that passes positives but fails a destructive counterexample;
- concurrent candidate edits and stale version;
- delete/revoke between extraction and activation;
- feedback on a response using multiple memories but no skill;
- style/skill reset followed by baseline response;
- user A candidate read/edit attempt by user B;
- worker retry, timeout and restart at each persisted boundary.

Human adjudication is required; the same agent may not author both every fixture
and its ground truth.

## Validation Commands Per Code Slice

- Focused backend tests for the changed slice with a configured test
  `APP_SECRET_KEY`.
- `ruff check src/ tests/`
- `mypy src/`
- `pytest tests/ -q` plus Postgres-specific isolation/migration tests.
- In `client/web-app`: `npm test`, `npm run lint`, `npm run build`.
- Exact-SHA Antigravity targeted matrix, repository regression and final
  privacy/security review before each integration batch.
- Authenticated E2E for consent → candidate → accept → next response → feedback
  → reset, and deletion/revoke drill before pilot.

## Telemetry

Only structured aggregate events already allowed by FR-071:

- consent changed by capability;
- review started/completed/abstained/failed with version and latency bucket;
- candidate created/accepted/edited/rejected/expired by type and confidence bucket;
- skill evaluation passed/failed and rollback count;
- context artifact type/version count, never prompt text;
- reset/delete/revoke completion and lag bucket.

Do not optimize engagement or number of candidates. `nothing_to_learn` is a
healthy outcome and must be measurable.

## Risks And Recovery

- **Privacy leakage:** fail closed before persistence; immediate global and
  per-capability kill switches; delete/revoke exclusion is synchronous.
- **Prompt injection persistence:** history is delimited data, structured output
  only, static scan before candidate persistence and again before activation.
- **Personality drift:** immutable core prompt precedes style fields; allowlist
  schema; next-turn reset proof.
- **Self-reinforcing hallucination:** assistant messages never count as evidence;
  feedback maps only through recorded context refs.
- **Worker cost/latency:** batch/cursor, daily cap, rule-first filtering and no
  learning call on the chat critical path.
- **Schema recovery:** additive tables first; flags off during migration; rollback
  disables reads/workers before any cleanup.
- **Deletion race:** conversation deletion and consent revoke invalidate
  dependent evidence/candidates in the same transaction before source rows are
  removed; a dangling string evidence reference is never treated as accessible.
- **P0 divergence:** integrate P0 first and rebase every P1 slice from current
  `origin/main`; never use a drifting local foundation branch.

Immediate rollback triggers: cross-user exposure, raw secret/PII in derived
state/logs, candidate affecting a response before acceptance, deleted/revoked
evidence still used, core safety/permission/citation behavior change, or any
external write without explicit confirmation.

## Progress

- [x] Record Thái's P1 planning approval and inspect current repository state.
- [x] Map current memory/chat/feedback/worker/privacy gaps against PRD and research plan.
- [x] Define release order, slices, proposed contracts, gates and rollback.
- [x] Obtain independent Antigravity architecture and evaluation review.
- [x] Reconcile documentation ordering, routine namespace, streaming attribution
  and new-table user-id findings.
- [x] Commit and obtain exact-SHA documentation attestation.
- [x] Slice 0: ADR-017 accepted 2026-08-22 (OD-02 retention, hard-delete SLA
  30 days, pilot cohort = opt-in nội bộ nhỏ — Thái chốt theo đề xuất mặc định).
- [x] Integrate and revalidate P0 prerequisite (`dd6f781`, 2026-08-22).
- [x] S1a foundation: consent/cursor/signal/candidate/evidence/context-ref/audit
  models + consent API + kill switches + 16 tests (Antigravity-reviewed, `24fbc94`).
- [ ] S1b: persist assistant context refs in regular + streaming chat paths.
- [ ] S2 onward: chat review shadow mode.

## Decisions

- 2026-08-21: Thái approved P1 direction and asked Tatejo to start implementation planning.
- 2026-08-21: Plan from latest `origin/main`; P0 is an explicit integration
  prerequisite, not a local stacked base.
- 2026-08-21: Ship style before skills and routines to prove the complete
  reversible learning loop with the smallest permission and side-effect surface.
- 2026-08-21: Keep all capabilities default-off and manual-activation during P1 pilot.
- 2026-08-21: No external memory provider, model fine-tuning or executable skill
  generation enters the P1 critical path.

## Validation

- Focused proof: Markdown structure, link targets and repository diff review.
- Independent proof: Antigravity architecture/evaluation review of exact plan commit.
- Integration or end-to-end proof: not applicable until S1 implementation.
- Repository-required checks: documentation-only validation and `git diff --check`.

## Result

The implementation plan, proposed decision defaults, release ordering,
architecture boundaries, evaluation matrix and recovery gates are complete.
Antigravity independently reviewed candidate `ed855e3` and reported no blocking,
high, medium or low finding after the four initial Low findings were reconciled.

Implementation has not started. No production behavior, schema or configuration
changed. Slice 1 remains blocked until Slice 0 accepts `OD-02` retention/delete
policy and the P0 prerequisite is integrated and revalidated on current main.
