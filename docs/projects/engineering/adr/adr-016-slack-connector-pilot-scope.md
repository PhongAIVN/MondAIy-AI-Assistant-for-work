# ADR-016 — Slack connector vào phạm vi pilot

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Approved |
| Owner | PM (quyết định qua phiên làm việc với agent, 2026-08-17) |
| Author | Agent (Claude Code), ghi lại quyết định PM |
| Related | [ADR-002](adr-002-connector-first-p0-scope.md) · [slack-detail.drawio](../slack-detail.drawio) (DRAFT) |

## Bối cảnh

ADR-002 giới hạn P0 còn 5 nguồn (Calendar, Jira, Discord, VLearn, Gmail).
Backend connector Slack (`src/connectors/slack.py`, `src/services/slack_rules.py`,
`src/services/connections/slack.py`) đã build xong theo thiết kế DRAFT ở
`slack-detail.drawio`, nhưng bị khoá khỏi UI (`ENABLED_PROVIDERS` ở
`client/web-app/src/types/pipeline.ts`) vì 5 câu hỏi mở trong tài liệu đó
chưa có quyết định, đặc biệt về phạm vi channel và privacy DM.

PM yêu cầu bật Slack lên `/sources`. Trước khi bật, agent nêu lại 3 trong 5
câu hỏi mở còn ảnh hưởng trực tiếp tới thiết kế/consent và để PM quyết định
tại chỗ.

## Quyết định

Trả lời 5 câu hỏi mở trong `slack-detail.drawio`:

1. **App có tính "internal" để giữ Tier 3 rate limit không?** → Có. App chỉ
   cài nội bộ 1 workspace do mondaiy tự quản trị (xem quyết định #3), không
   phân phối ngoài — thoả điều kiện "internal" theo tài liệu Slack đọc được
   tại thời điểm quyết định.
2. **Ngưỡng tin cậy deadline suy luận hiện trên UI thế nào?** → Chưa quyết ở
   ADR này — là chi tiết UX của bước Extraction, để lại cho lúc thực thi
   `slack_rules.py`/UI hiển thị task, không chặn việc bật connector.
3. **Phạm vi channel: tất cả channel bot join hay user tự chọn?** → User tự
   chọn channel/DM, giống cơ chế source picker đang dùng cho Jira/Gmail.
   `SlackConnector.list_sources()` đã trả về danh sách channel/DM/group DM
   để UI cho chọn — không cần connector tự ingest toàn bộ.
4. **DM/private channel có cần review privacy riêng trước khi bật không?**
   → Không chặn — bật ingest DM ngay từ đầu, chấp nhận mức nhạy cảm cao hơn
   Jira/email công việc. Không giới hạn còn public channel trước.
5. **Có cần qua Slack App Directory review không?** → Không. Phạm vi pilot
   chỉ cài app vào 1 workspace nội bộ do mondaiy quản trị.

Theo đó:

- Thêm `'slack'` vào `ENABLED_PROVIDERS` (`client/web-app/src/types/pipeline.ts`)
  và `INTEGRATION_CATALOG` (`client/web-app/src/pages/SourceLibraryPage.tsx`).
- Không thay đổi hành vi connector — `list_sources()`/`fetch_range()` đã
  đúng tinh thần quyết định #3/#4 (liệt kê channel+DM để chọn, không lọc DM).
- `SLACK_CLIENT_ID`/`SLACK_CLIENT_SECRET` (`src/config.py`) vẫn rỗng — nút
  Connect Slack hiện lên nhưng chưa chạy được tới khi có Slack App thật và
  credentials thật, giống tình trạng Jira/Outlook trước khi có app đăng ký.

## Hệ quả

- `/sources` hiện Slack trong danh sách nguồn có thể kết nối.
- Câu hỏi #2 (hiển thị độ tin cậy deadline suy luận trên UI) vẫn mở — cần
  quyết định trước khi UI extraction hiển thị task Slack cho user thật.
- Cần đăng ký Slack App thật (Slack API dashboard) và điền
  `SLACK_CLIENT_ID`/`SLACK_CLIENT_SECRET` trước khi connector chạy end-to-end
  ngoài môi trường dev.
- Quyết định "internal app" ràng buộc: nếu sau này cần phân phối Slack app
  ra workspace ngoài mondaiy quản trị, phải revisit câu hỏi #1/#5 (rate
  limit siết còn 1 req/phút, cần App Directory review).
