# Use case — Web context to confirmed action

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Superseded — ngoài P0 theo ADR-002 |
| Owner | Thái Hoài An (PM) + Nguyễn Văn Phong (Technical Lead; acting owner) |
| Reviewers | QA Lead, AI/Memory Lead |
| Last updated | 2026-08-02 |
| Related | [PRD](../prd.md) · [Capture protocol](../../engineering/capture-sync-protocol.md) |

## Actor và preconditions

- User đã đăng nhập.
- Domain nằm trong allow-list hoặc user chọn `Lưu trang này`.
- Capture đang active.

## Main flow

1. User mở trang chứa yêu cầu/deadline.
2. Extension extract clean content và enqueue.
3. Backend persist evidence/version và ACK.
4. Worker extract action/deadline candidate.
5. Candidate xuất hiện trong Brief hoặc Memory Inspector với citation.
6. User hỏi để làm rõ.
7. Answer có citation tới document version.
8. User chọn `Thêm vào lịch`.
9. Draft có title/time/timezone/source; user edit/confirm.
10. System mở Calendar template hoặc tải `.ics`.

## Alternative/failure

- Offline → outbox retry.
- Cùng hash → observation mới, không version mới.
- Hash mới → document version mới.
- Deadline mơ hồ → time để trống.
- Source revoked → event/retrieval bị chặn.
- Unsupported extraction → candidate không promotion; Ask abstain.

## Acceptance

- Không mất/duplicate event.
- Evidence/source/version mở được.
- Candidate không hiển thị như confirmed nếu chưa promotion.
- Factual answer có citation.
- Không action trước confirm.
