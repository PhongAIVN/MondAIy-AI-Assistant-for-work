# ADR-014 — Mở rộng Telegram để hỗ trợ chat tự do qua agent

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Proposed |
| Ngày | 2026-08-15 |
| Tác giả | AI Agent (draft for Technical Lead review) |
| DRI (Decision Maker) | Nguyễn Văn Phong (Technical Lead) |
| Reviewers | Technical Lead, Product Manager, Privacy/Security DRI |
| Related | [ADR-012](adr-012-telegram-p0-cho-tom-tat-va-nhac-viec.md) (Telegram P0 brief và reminder) · [ADR-002](adr-002-connector-first-p0-scope.md) (Privacy boundary) · [Mobile chat spike](../mobile-chat-channel-spike.md) · [PRD](../../product/prd.md) (FR-054, FR-068) |

## Bối cảnh

### ADR-012 hiện cấm free-form LLM

[ADR-012](adr-012-telegram-p0-cho-tom-tat-va-nhac-viec.md) mục 3, dòng 52 nêu rõ: **"nội dung khác: trả danh sách lệnh được hỗ trợ, không đưa vào agent/LLM"**. Lý do tại thời điểm đó là cần chứng minh giá trị read/push delivery (tóm tắt và nhắc việc) trước khi mở rộng. P0 hiện đã production-ready với `/today`, `/tasks`, `/inbox`, `/settings` (lệnh cố định) + snooze/dismiss callback.

### Motivation mở rộng

[Spike `mobile-chat-channel-spike.md`](../mobile-chat-channel-spike.md) khảo sát khả năng mở luồng chat tự do qua Telegram, và kết luận rõ ràng đây là **material change** vì:
- Thay đổi ranh giới riêng tư: nội dung tóm lược nội bộ + câu trả lời của agent sẽ chảy qua hạ tầng Telegram (bên thứ ba).
- Thay đổi phạm vi quyết định: mở rộng từ "kênh giao tiếp" (channel) sang "kênh hội thoại có khả năng xử lý" (interactive channel with LLM capability).
- Theo AGENTS.md, không được tự chốt quyết định architecture/scope — cần decision record + DRI duyệt.

User feedback yêu cầu có thể chat tự do từ Telegram thay vì chỉ chạy lệnh cố định. FR-054 (hội thoại nối tiếp) và FR-068 (tạo event/task bằng hội thoại) trong PRD cũng gợi ý conversational flow là định hướng product.

## Quyết định đề xuất

### 1. Mở route free-text message qua Telegram webhook

**Phạm vi chính xác:**
- Telegram webhook `POST /api/v1/channels/telegram/webhook` nhận message text từ user.
- Message được xử lý như một câu hỏi/yêu cầu tới agent pipeline hiện có:
  - Tạo hoặc reuse Conversation session per user
  - Gửi message vào `Conversation.messages` (ORM model hiện có)
  - Gọi `stream_agent_execution()` từ `src/services/agent_stream.py` (hoặc `gui_tin_nhan_stream` endpoint logic)
  - Agent pipeline (`src/agents/graph.py`): think → action → observe → respond
  - Câu trả lời stream về và render thành plain text (hoặc rich Telegram format nếu có) qua Bot API

**Không đi qua từ đường:**
- Không tạo conversation mới nếu message là short-lived echo test; chỉ log.
- Không lưu raw Telegram message payload; chỉ lưu message content vào `ConversationMessage.content`.

### 2. Tái dùng pipeline hiện có

| Thành phần | Tình trạng | Ghi chú |
| --- | --- | --- |
| `src/api/conversations.py` | Tái dùng | Endpoint `gui_tin_nhan_stream` logic hoặc tương tự |
| `src/models/conversation.py` | Tái dùng | `Conversation`, `ConversationMessage` models |
| `src/agents/graph.py` | Tái dùng | Think/action/observe/respond nodes |
| `src/services/agent_stream.py` | Tái dùng | Streaming response handling |
| `src/services/scope.py` | Bắt buộc | Phải gọi `apply_search_scope()` trước agent pipeline |
| `src/services/llm.py` | Tái dùng | LLM client (OpenRouter provider) |
| Webhook handler | Viết mới | Adapter từ Telegram update → Conversation core |

### 3. Enforce permission scope per user — không có đường tắt

**Bắt buộc:**
- Mỗi Telegram text message phải map sang user_id qua Telegram Login Widget + `provider_user_id` (giống ADR-012).
- Trước khi gọi agent, gọi `apply_search_scope(user_id, db)` từ `src/services/scope.py`.
- Agent tool access được kiểm soát bởi:
  - Search tool: chỉ truy hồi bằng chứng/memory của user này
  - Calendar tool: chỉ đọc lịch của user này
  - Gmail tool: chỉ đọc email của user này
  - Jira tool: chỉ đọc task của user này (hoặc quyền được assign)
  - Productivity tool: chỉ tạo action cho user này
  
**Test obligation:**
- Viết test: user A gửi message qua Telegram, agent không được truy hồi bằng chứng/memory/calendar của user B.
- Test: user chưa liên kết Telegram (không có provider_user_id) gửi message → webhook từ chối với lỗi 401, không có Conversation được tạo, không có bằng chứng nào được truy hồi.

## Privacy & Security Impact

### Data flow và attack surface

```text
User (Telegram client)
  ↓ (HTTPS)
  Telegram Bot API
  ↓ (HTTPS, webhook signed by X-Telegram-Bot-Api-Secret-Token)
  /api/v1/channels/telegram/webhook
  ↓ verify provider_user_id → user_id mapping
  apply_search_scope(user_id) [permission boundary]
  ↓
  agent pipeline (think/action/observe/respond)
  ↓ (tool access filtered by scope)
  ConversationMessage storage
  ↓ (render response as plain text)
  send_message() via Telegram Bot API
  ↓ (HTTPS)
  User (Telegram client)
```

### Rủi ro cụ thể

| Rủi ro | Mitigration |
| --- | --- |
| **Telegram chat_id bị lộ/chiếm** | Webhook verify secret header (`X-Telegram-Bot-Api-Secret-Token` constant-time compare như ADR-012 mục 3). Message của attacker không có `from.id` = legitimate user Telegram ID. Attacker không thể forge Telegram update. |
| **Cross-user data leak** | `apply_search_scope()` set task scope, calendar scope, gmail scope v.v. per user_id. Tool từ chối truy hồi nếu scope chưa được set. Test: user B không được truy hồi dữ liệu user A qua Telegram chat. |
| **LLM injection via Telegram message** | Message content được send qua agent pipeline; prompt injection có thể xảy ra. **Mitigation:** scope restriction = agent không thể access data user khác, không thể escape permission boundary. Prompt injection chỉ ảnh hưởng tới dữ liệu của user gửi message. Rate-limit (xem mục Risk) giảm damage. |
| **Telegram nội dung bị lưu trữ ở Telegram** | Message content lưu trong `ConversationMessage.content` ở database của ứng dụng, **không** lưu trong Telegram tài khoản bot. Telegram Bot API không lưu incoming message content. Chỉ lưu outgoing `sendMessage()` call metadata (thời điểm, status), không lưu reply content. |
| **Amplification: agent spawn nhiều tool call từ Telegram message** | Agent có thể think → action → action → observe nhiều lần. Mỗi tool call tính LLM cost. **Mitigation:** per-user rate-limit trước agent pipeline; per-conversation token budget (configuration). |

### Consent & Opt-in

- Daily brief qua Telegram mặc định tắt, dùng `NotificationPreference.daily_brief_hour` (ADR-012).
- Free-text chat qua Telegram **là separate feature flag** (hoặc extend existing flag):
  - Option: `NotificationPreference.telegram_free_chat_enabled` (new field, default `false`)
  - Hoặc dùng chung flag nhưng track preference riêng
- User kết nối Telegram qua Telegram Login Widget (ADR-012 mục 2) → same consent model.
- User có thể unlink Telegram → webhook từ chối lại, không nhận free-text qua Telegram.

## Alternatives considered

| Phương án | Kết luận | Lý do |
| --- | --- | --- |
| **Polling model:** Agent check Telegram update mỗi 30 giây thay vì webhook | Rejected | Latency kém (30s delay), tốn compute khi không có message, không phù hợp interactive chat. |
| **Separate LLM integration cho Telegram** | Rejected | Codebase đã có conversation + agent pipeline mature, tái dùng tốt hơn rebuild. Risk introduced: second pipeline = second permission model = double audit. |
| **Lưu Telegram message content trong bot account** | Rejected | Privacy boundary per ADR-002. Avoid third-party storage. Telegram Terms of Service: bot không nên lưu trữ user message để analyze ngoài mục đích serving user. |
| **Mini App + bot chat song song ngay từ đầu** | Rejected (hoãn sang pha 4) | Mini App phức tạp (HTML/CSS/JS, SecureStorage, DeviceStorage). Pha 1-3 chỉ cần bot text + inline keyboard để verify permission model trước. |
| **Chat tự do cho Discord hoặc kênh khác** | Out of scope | ADR-014 chỉ quyết định Telegram (pilot platform). Discord, Zalo qua ADR mới nếu pilot thành công. |

## Risk & Rollback Plan

### Risk

| Rủi ro | Tác động | Mitigation | Rollback |
| --- | --- | --- | --- |
| **LLM cost tăng** | Mỗi Telegram message user gửi = 1 LLM call (think node ≥ 1 token). Pilot 5-10 người × 5 message/ngày × 30 ngày = 750-1500 LLM call/tháng. OpenRouter cost phụ thuộc model (Claude 3 Haiku rẻ nhất). | Rate-limit: 5 message/phút per user; disable nếu quota month exceeded. Monitor OpenRouter usage dashboard hằng ngày. Config `TELEGRAM_FREECHAT_RATE_LIMIT_PER_MIN=5`, adjustable. | Set `TELEGRAM_FREECHAT_ENABLED=false` → webhook trả về "feature tạm tắt". |
| **Spam / DoS từ Telegram** | Attacker spam 1000 message trong 1 phút để trigger 1000 LLM call. | Rate-limit + chat_id based quota. Per-user quota: max 10 conversation turns/hour (giãn giãn hơn rate-limit để không block legitimate user bận). Log thành "abuse_pattern" nếu vượt limit. | Tắt kênh Telegram, investigate logs. |
| **Prompt injection / jailbreak** | User inject prompt để agent bypass tool permission hoặc trả lời điều không supposed. | Scope restriction enforce ở tool level (scope.py), không rely on prompt. Audit log LLM input/output từ Telegram (flag `channel=telegram`). Model instruction không nên nêu "tuân theo scope.py rule" — permission là constraint kỹ thuật, không instruction. | Rollback model hoặc add prompt guard. |
| **Memory leakage: working memory cache** | Agent working_memory có thể chứa fragment dữ liệu từ user A, sau đó reuse cho user B nếu scope reset sai. | Reset scope sau mỗi Telegram request (`reset_agent_scope()` ở finally block). Unit test: mỗi new request set scope lại. | Code review trước deploy. |
| **Telegram Bot API lỗi / 429 rate-limit** | Telegram từ chối `sendMessage` vì 429 (rate-limit) hoặc 500 (outage). User không nhận reply. | Không retry ngay; ghi log structured, monitor dashboard. Fallback: ghi message vào queue (not implemented in pha 1) hoặc return error để user retry sau. | Pause webhook accept, tắt feature flag. |

### Rollback plan

**Tắt immediate:** Config flag `TELEGRAM_FREECHAT_ENABLED=false` hoặc `TELEGRAM_FREECHAT_ROUTE=disabled` tại runtime.
- Webhook vẫn verify signature, nhưng return 200 OK + log "feature disabled", không forward tới agent.
- Hoặc comment-out route handler trong `src/api/telegram_channel.py`.

**Dữ liệu:** Conversation record trong database được giữ lại để audit (không xóa). Nếu cần rollback code, conversation cũ vẫn readable nếu user quay lại web app sau.

**Data cleanup (nếu cần rollback toàn bộ):** Có script để xóa conversation được tạo từ Telegram (flag `source='telegram'` hoặc dựa trên thời gian deploy). Script này **không tự động chạy** — yêu cầu manual approval từ operator.

## Note về discrepancy hiện có

ADR-012 mục 5 nói **"P0 chưa có callback `Đã làm`, `Nhắc lại`, `Bỏ qua`"**, nhưng code hiện tại trong `src/api/telegram_channel.py` (xem `apply_reminder_action`, line ~113-115) **đã implement snooze/dismiss callback** kèm `edit_message_text` hoặc fallback gửi tin nhắn mới.

**Giải thích gap:**
- ADR-012 được viết trước khi implement callback → doc không sync với code.
- Hoặc callback được implement sau ADR-012 duyệt, nhưng doc không được cập nhật.

**ADR-014 không sửa lại ADR-012** (không thuộc scope, để avoid edit conflict). Khuyến nghị **follow-up decision:**
- Hoặc update ADR-012 mục 5 để reflect code hiện tại (snooze/dismiss callback là Approved).
- Hoặc tạo ADR riêng để chốt "snooze/dismiss callback" status nếu cần formal approval.
- Hoặc đơn giản là: callback đã ở production, ADR-012 doc outdated nhưng không ảnh hưởng ADR-014.

## Acceptance Criteria (nếu ADR được approve)

Khi quyết định "Approved" được chốt, các điều kiện dưới là bắt buộc trước deploy production:

1. **Pha 1 (Echo spike):** Webhook + echo back user message (không LLM), đã tested locally.

2. **Pha 2 (Wire conversation core):**
   - `gui_tin_nhan_stream` hoặc tương tự được gọi từ Telegram webhook.
   - Response stream từ agent, render qua `send_message`, user nhận được reply.
   - Test: user gửi "hôm nay tôi có gì" → agent trả lời base trên working memory.

3. **Pha 3 (Permission enforcement test):**
   - User A gửi message qua Telegram → `apply_search_scope(user_a_id)` được gọi.
   - Agent không access bằng chứng/memory/calendar của user B.
   - User B gửi message qua Telegram → User A không nhận được User B's message.
   - Test: user chưa liên kết gửi message → webhook return 401, không có Conversation được tạo.

4. **Rate-limit & monitoring:**
   - Config `TELEGRAM_FREECHAT_RATE_LIMIT_PER_MIN=5` (or adjustable).
   - Monitoring dashboard: số message/ngày, số LLM call/ngày, error rate, latency.
   - Log structured: timestamp, user_id, message length, agent response length, cost, channel=telegram.

5. **Cost monitoring set up:**
   - Daily report: OpenRouter API usage from Telegram (distinct from web app).
   - Alert nếu cost > threshold / quota.

6. **Compliance:**
   - Privacy consent copy updated để ghi "agent reply sẽ chảy qua Telegram" nếu user bật free-chat.
   - PII redaction: audit log không chứa message content, chỉ hash hoặc length.

## Thích hợp cho phạm vi nào

- **Tiến độ product:** FR-054 (conversational continuity) và FR-068 (create action bằng hội thoại) đã nằm trong PRD/P0, nhưng chỉ build cho web app. Mở Telegram chat là phối họp kênh thứ hai cho same features.
- **Timeline:** Không vượt phạm vi sáu tuần đã duyệt nếu pha 1-3 ước lượng 4-5 ngày (spike 1 ngày + wire 1.5 ngày + test 0.5 ngày + deploy 1 ngày). Pha 4 (Mini App) thực hiện sau pilot feedback.

## Kế tiếp

- Nếu Approved: Technical Lead schedule pha 1-3, assign lane.
- Nếu Rejected: Telegram P0 (brief + reminder) vẫn hoạt động bình thường, user chỉ dùng lệnh cố định.
- Nếu Hoãn: Soạn OD (Open Decision) record, nêu điều kiện ưu tiên deployment (pilot feedback, cost budget, user request count).
