# WHAT_CHANGED — Google Sheets/Docs routing

| Field | Value |
|---|---|
| Objective | Nhận diện đúng Google Sheets và Google Docs trong source routing và chat handoff |
| Base SHA | `51c3f4a` |
| Scope | Backend source routing + frontend chat/Sources handoff; không đổi schema |
| Ownership | Lead Codex/Tatejo; một writer |
| Status | Đang kiểm thử tích hợp |

## Research and acceptance

- `src/services/source_routing.py` chỉ có Jira/Gmail/Calendar/Discord/Tasks.
- Chat chỉ trích xuất URL Google Sheets; Google Docs bị rơi về luồng generic.
- Chấp nhận khi từ khóa hoặc URL Docs/Sheets trả về source explicit, không lẫn loại; chat hiển thị handoff đúng loại và giữ URL khi mở Sources.

## Changes

- Thêm canonical sources `google_sheets` và `google_docs`, nhận diện từ khóa tiếng Việt/Anh và URL Google.
- Thêm `googleDocsIntent` và `GoogleDocsConnectCard`; nối Daily Briefing và Sources query handoff.
- Thêm regression tests backend/frontend.

## Validation

- `.venv/bin/pytest tests/test_services/v1/test_source_routing.py tests/test_agents/v1/test_source_confirmation.py -q` — 10 passed.
- `npm test` — 119 passed (Vitest phase bị sandbox chặn ghi `.vite-temp`; đã chạy build/typecheck riêng).
- `npm run lint` — pass, chỉ warnings tồn tại trước đó.
- `npm run build` — pass.

## Deployment notification

| Item | Value |
|---|---|
| Batch / date | routing-fix / 2026-08-21 |
| User-visible update | Chat nhận diện và mở đúng Google Sheets/Docs |
| Scope | backend + frontend |
| Source | Chưa tích hợp |
| Validation | Local gates ở trên |
| Status | Planned |
| Rollback | `51c3f4a` |

## Risks / follow-up

- Google Docs handoff đưa người dùng tới Google Drive picker để chọn file trước khi quét; không tự đọc tài liệu ngoài quyền OAuth hiện có.
