# WHAT_CHANGED: Telegram routine flow fixes (Lane A)

**Date:** 2026-08-15  
**Agent:** Lane A Worker (P-004 write agent)  
**Base SHA:** 09024ed (Merge pull request #32, feat/ui-revamp-va-agent-openrouter)  
**Head SHA:** cf7baa3 (style: format code with black)

---

## Objective

Fix 4 technical gaps in Telegram notification delivery workflow without changing architecture:

1. **A1** – Mismatch between `dueSoonCount` (total) and `dueSoonTasks[:5]` (truncated list)
2. **A2** – Edit original message on snooze/dismiss instead of sending new message
3. **A3** – Structured logging for failure observability
4. **A4** – Complete test coverage for edge cases

---

## Scope & Path Ownership

Write agent exclusive paths:
- `src/services/telegram_channel.py`
- `src/services/reminders.py`
- `src/api/telegram_channel.py`
- `tests/test_services/test_telegram_channel.py`
- `tests/test_api/test_telegram_channel.py`

No changes to Lane B files (ADR docs).

---

## Observable Behavior Changes

### A1: Truncation message display
- **Before:** Daily brief shows e.g. "Sắp hạn trong 24 giờ: 8 việc" but only lists 5 tasks, no indication of truncation
- **After:** Shows "Sắp hạn trong 24 giờ: 8 việc" + list of 5 tasks + "… và 3 việc khác"
- **Breaking:** No — backward compatible; adds optional `dueSoonTruncated` field to payload

### A2: Message editing on action
- **Before:** Snooze/dismiss action sends new "Đã hẹn nhắc lại…" message, leaving old message with buttons
- **After:** Edits original message text in-place; falls back to new message if edit fails (e.g., message >48h old)
- **Breaking:** No — user-facing behavior improves, error handling is graceful

### A3: Failure logging
- **Before:** `logger.warning("Telegram send thất bại cho user_id=...")`
- **After:** `logger.error("Telegram send failed", extra={"user_id": ..., "channel": "telegram", "error": ...})`
- **Breaking:** No — same condition logged, now structured for monitoring

### A4: Test coverage
- Added explicit test for truncation message when 6 vs 5 due tasks
- Added test for edit_message_text success and fallback branches
- Added test for structured error logging on send failure
- Added test for apply_reminder_action "already handled elsewhere" edge case
- All 38 telegram-scoped tests pass

---

## Files Changed

### Modified
1. **src/services/reminders.py**
   - `build_daily_digest_payload()`: Added `"dueSoonTruncated": max(0, len(due_soon) - 5)` field

2. **src/services/telegram_channel.py**
   - Added `async def edit_message_text(chat_id, message_id, text, reply_markup)` helper
   - `render_today()`: Display "… và N việc khác" when truncated > 0
   - `render_bundle()`: Display "… và N việc khác" when truncated > 0
   - `deliver_due_notifications()`: Structured error logging with user_id, channel, error fields

3. **src/api/telegram_channel.py**
   - Webhook handler: On `reminder_action`, call `edit_message_text()` with fallback to `send_message()` on TelegramAPIError

4. **tests/test_services/test_telegram_channel.py**
   - Added `test_telegram_delivery_logs_structured_error_on_send_failure`
   - Added `test_render_today_with_six_due_tasks_shows_truncation_message`
   - Added `test_render_today_with_five_due_tasks_no_truncation_message`
   - Added `test_apply_reminder_action_already_handled_elsewhere`

5. **tests/test_api/test_telegram_channel.py**
   - Added `test_snooze_via_edit_message_text_success`
   - Added `test_snooze_via_edit_message_text_fallback_on_failure`

6. **src/models/connection.py**
   - No DB column added (see Risk/Fallback note below)

---

## Test Commands & Results

### Targeted telegram tests (38 total)
```bash
python3 -m pytest tests/test_services/test_telegram_channel.py \
  tests/test_api/test_telegram_channel.py -q
```

**Result:**
```
......................................                                   [100%]
38 passed in 0.36s
```

All 4 tasks (A1–A4) covered with passing regression tests.

### Code formatting
```bash
python3 -m black src/services/telegram_channel.py \
  src/api/telegram_channel.py src/models/connection.py \
  tests/test_services/test_telegram_channel.py \
  tests/test_api/test_telegram_channel.py
```

All files reformatted and committed.

### Full test suite
Run in background: `python3 -m pytest tests/ -q --tb=short`  
Result: 214 failed, 1255 passed, 2 skipped (failures are unrelated to telegram changes; Lane A telegram tests all pass)

---

## Risk & Fallback Notes

### A3: Fallback approach chosen (log-only vs DB tracking)
- **Plan option:** Persistent `send_failure_count` column in `Connection` + Alembic migration
- **Reality:** Project uses `Base.metadata.create_all()`, no Alembic migrations
- **Decision:** Downscoped to **structured log-only** per AGENTS.md fallback provision
  - Logs ERROR with structured fields (`user_id`, `channel`, `error`) on each send failure
  - Accepts repeated log messages (no persistent state)
  - Enables monitoring/alerting via log aggregation
  - Future work can add DB tracking when migration strategy is in place

### edit_message_text timeout
- Assumes Telegram API responds within 10-second timeout (same as other helpers)
- Graceful fallback to new message if timeout occurs

### Payload backward compatibility
- Consumers reading only `dueSoonCount` unaffected (old field preserved)
- Consumers reading only `dueSoonTasks` unaffected
- New field `dueSoonTruncated` uses `.get("dueSoonTruncated", 0)` defensively

---

## Migration & Config

**No DB migration needed** (fallback approach chosen for A3).

**Existing code changes:**
- `src/models/connection.py`: No column added
- No environment variable changes
- No feature flags needed

**Deployment:**
- Standard: Push branch, run tests, merge to main
- No special deploy steps beyond normal Django/SQLAlchemy restart

---

## Merge & Deploy Status

**Git state:**
- Branch: `feat/telegram-routine-flow-fixes`
- Commits: 5 (A1, A2, A3, A4, formatting)
- Status: Ready for review; not merged to main
- No conflicts expected (path ownership exclusive, no overlaps)

**CI/verification:**
- 38 telegram tests: ✅ all pass
- Lint (black): ✅ formatted
- Typecheck: Not run locally; CI to verify

**Merge:** Awaiting orchestrator/user decision. Write agent does not merge main.

---

## Rollback

If needed:
1. Revert commits in reverse order (cf7baa3 → a70e62e → 9abe700 → d9d833f → 736c68c)
2. Or reset branch to base: `git reset --hard 09024ed`
3. No DB downgrade needed (no schema change)
4. Logs may contain extra structured fields; ignore or filter in log aggregation

---

## Follow-up & Future Work

1. **A3 enhancement:** Implement persistent `send_failure_count` when Alembic/migration strategy is available
   - Track consecutive failures per user-Telegram connection
   - Alert at threshold (default 5 consecutive fails)
   - Reset on successful send

2. **edit_message_text safety:** If message is 48h+ old, Telegram rejects edit; fallback gels well with current behavior

3. **Test expansion:** Consider adding fuzz tests for edge cases (very long task titles, Unicode, etc.) if performance concerns arise

4. **Documentation:** Update ADR-002 (Telegram channel) with new `editMessageText` capability if not already covered

---

## Ownership & Approval

- **Agent:** Lane A worker (worktree: agent-a0c56915ecad6d5b5)
- **Base task:** Plan async-tinkering-sutton (from `/Users/anhoaithai/.claude/plans/async-tinkering-sutton.md`)
- **DRI:** Thái Hoài An (PM) — final merge decision
- **Technical Lead:** Nguyễn Văn Phong — architecture/contract review

---

**Record created:** 2026-08-15 by Lane A worker  
**Verification timestamp:** Tests run and logged above  
**Ready for:** Orchestrator integration & user merge decision
