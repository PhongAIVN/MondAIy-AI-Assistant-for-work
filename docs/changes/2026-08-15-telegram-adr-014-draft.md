# WHAT_CHANGED — Lane B: ADR-014 Draft for Free-Form Telegram Chat

## Tóm tắt

Soạn draft ADR mới (ADR-014) để đề xuất mở tính năng free-form chat qua Telegram. Đây là **document-only change**, không có code modification.

## Metadata

| Thuộc tính | Giá trị |
| --- | --- |
| Task | Lane B từ plan async-tinkering-sutton.md |
| Agent | Claude Code (document-only agent) |
| Base commit | e14772f (feat: integrate calendar and voice workflows) |
| Date | 2026-08-15 |
| Status | Ready for Technical Lead review |

## Mục tiêu

Soạn proposal ADR để chốt kiến trúc, privacy boundary và rollout plan cho việc mở route free-text message qua Telegram webhook, sử dụng lại conversation pipeline hiện có (`src/api/conversations.py`, `src/agents/graph.py`, `src/services/scope.py`). ADR này cần DRI (Nguyễn Văn Phong, Technical Lead) duyệt trước khi build feature.

## Điều kiện hoàn tất

### Path ownership (exclusive, không chạm file khác)

- File mới: `docs/projects/engineering/adr/adr-014-telegram-free-form-chat-mo-rong.md` ✅

### Tài liệu tham khảo đã đọc (read-only, không sửa)

- `docs/projects/engineering/adr/adr-012-telegram-p0-cho-tom-tat-va-nhac-viec.md` — template cùng domain, cấu trúc ADR ✅
- `docs/projects/engineering/adr/adr-002-connector-first-p0-scope.md` — privacy boundary, cấu trúc ADR ✅
- `docs/projects/engineering/mobile-chat-channel-spike.md` — spike gợi ý, rollout plan, risk, material change statement ✅
- `docs/projects/product/prd.md` — FR-054, FR-068, conversational features ✅

### Code references đã audit (read-only, không sửa)

- `src/api/conversations.py` — `gui_tin_nhan`, `gui_tin_nhan_stream` endpoints, conversation pipeline ✅
- `src/models/conversation.py` — `Conversation`, `ConversationMessage` ORM models ✅
- `src/agents/graph.py` — agent think/action/observe/respond nodes ✅
- `src/services/agent_stream.py` — streaming response handling ✅
- `src/services/scope.py` — `apply_search_scope()`, permission enforcement per user ✅
- `src/services/llm.py` — LLM client, OpenRouter provider config ✅

### ADR draft content checklist

- ✅ Metadata table (Status=Proposed, Author, DRI)
- ✅ Bối cảnh: ADR-012 cấm, lý do spike recommend, motivation từ user + PRD (FR-054, FR-068)
- ✅ Quyết định đề xuất: webhook → Conversation core, tái dùng pipeline, scope enforcement
- ✅ Privacy & Security impact: data flow, rủi ro (chat_id leak, cross-user, injection), mitigation cụ thể
- ✅ Alternatives considered: polling, separate integration, Mini App, Discord/Zalo (rejected + lý do)
- ✅ Risk & Rollback: cost, spam, injection, memory leakage; mitigation + rollback plan chi tiết
- ✅ Note discrepancy: snooze/dismiss callback implemented nhưng ADR-012 doc outdated (không tự sửa)
- ✅ Acceptance criteria: Pha 1-3 test, rate-limit, cost monitoring, compliance
- ✅ Related references: ADR-002, ADR-012, spike doc

### Format & quality

- ✅ Markdown syntax valid, no orphan headers
- ✅ Table format correct (lời | giá trị)
- ✅ Tiếng Việt consistent, code snippets in backticks
- ✅ References tới file khác use relative paths (../../product/prd.md)
- ✅ No hardcoded credentials, no sensitive data

## Verification

```bash
# Check file exists
ls -la docs/projects/engineering/adr/adr-014-*.md
# Expected: 1 file, ~4KB

# Check diff
git diff --stat docs/
# Expected: only docs/projects/engineering/adr/adr-014-* (1 new file)
#          AND docs/changes/2026-08-15-telegram-adr-014-draft.md (this file)

# Check no src/ changes
git diff --name-only src/
# Expected: (empty output)
```

## Observable changes

1. **New file:** `/docs/projects/engineering/adr/adr-014-telegram-free-form-chat-mo-rong.md`
   - Status: **Proposed** (not Approved)
   - Size: ~5.5 KB
   - Sections: Context, Proposed Decision, Privacy, Alternatives, Risk, Acceptance, Followup

2. **Change record:** This file (`/docs/changes/2026-08-15-telegram-adr-014-draft.md`)
   - Size: ~1.8 KB
   - Documents Lane B output

## Test & verification performed

- ✅ Markdown syntax validation (no broken links in local refs, table format)
- ✅ Content completeness: all 7 required sections present
- ✅ Reference consistency: ADR-012, ADR-002, spike doc all correctly cited
- ✅ Privacy impact explicit: data flow diagram + threat table + mitigation
- ✅ Rollback plan concrete: config flag to disable, no data deletion automatic
- ✅ No code changes in diff

## Output & handoff

- **For Technical Lead review:** File path `docs/projects/engineering/adr/adr-014-telegram-free-form-chat-mo-rong.md`
- **Status:** Proposed (waiting for Nguyễn Văn Phong decision)
- **Next step:** 
  - If Approved: Assign Lane A + Lane B implementation, create Jira task
  - If Rejected: Document reason in ADR Status, close related spike
  - If Hoãn: Create OD (Open Decision) record with decision criteria

## Limitations & not in scope

- No code implementation (ADR is proposal only)
- No changes to ADR-012 (that would be separate update task)
- No changes to `src/api/telegram_channel.py` free-text stub (waits for approval)
- No test code for feature (happens after approval in pha 1-3)
- Mini App (pha 4) design not included (will be separate ADR or design doc)

## Risk & dependencies

- **Zero code risk:** ADR is document only, no production impact
- **No merge/push needed:** File is ready for user/orchestrator to review, branch, and integrate per their approval workflow
- **No follow-up code yet:** Waiting for DRI decision before any implementation branch/PR is created

---

**Prepared by:** AI Agent (Claude Code)  
**Date:** 2026-08-15  
**Task:** Lane B from `async-tinkering-sutton.md` plan
