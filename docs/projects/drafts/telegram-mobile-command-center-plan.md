# Proposal — Telegram mobile command center

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Partially approved — summary/reminder promoted to ADR-012; phần còn lại vẫn Draft |
| Owner | Thái Hoài An (PM) |
| Author | Thái Hoài An (PM) + Codex |
| Reviewers | Technical Lead, UI/UX Lead, PO/QC, Privacy/Security DRI |
| Last updated | 2026-08-13 |
| Source of truth | Không — cần ADR, PRD/feature spec và Jira trước khi build |
| Related | [Mobile chat channel spike](../engineering/mobile-chat-channel-spike.md) · [ADR-012](../engineering/adr/adr-012-telegram-p0-cho-tom-tat-va-nhac-viec.md) · [PRD](../product/prd.md) · [Pilot plan](../product/pilot-plan.md) · [ADR-002](../engineering/adr/adr-002-connector-first-p0-scope.md) · [ADR-004](../engineering/adr/adr-004-lien-ket-danh-tinh-qua-discord-oauth.md) · [ADR-007](../engineering/adr/adr-007-lich-tuong-tac-truc-tiep-va-lop-nhac-viec.md) |

## 1. Quyết định cần kiểm chứng

Xây Telegram thành **mobile command center**, không phải bản sao của web app.
Người dùng phải làm được ba việc cốt lõi ngay trên điện thoại:

1. biết việc gì vừa thay đổi, việc gì cần xử lý và tiến độ hiện tại;
2. phản hồi nhanh: `Đã làm`, `Nhắc lại`, `Bỏ qua`, `Xem nguồn`;
3. giao một việc mới hoặc yêu cầu tạo lịch bằng hội thoại, nhưng hệ thống chỉ
   thực thi sau khi người dùng xem và xác nhận bản nháp.

Giả thuyết sản phẩm:

> Nếu mondaiy đưa đúng việc cần chú ý và cho phép xử lý ngay trong Telegram,
> người dùng sẽ hoàn thành nhiều công việc đến hạn hơn, phản ứng nhanh hơn và
> giảm số lần phải mở web app hoặc từng nguồn trên laptop.

Telegram chỉ là **kênh giao tiếp**. Bot không đọc group Telegram, không tìm tin
trên Internet và không biến Telegram thành nguồn dữ liệu mới trong proposal
này.

## 2. Phạm vi theo thứ tự giá trị

### P0 — phải có để kiểm chứng giả thuyết

- Liên kết tài khoản bằng deep link + nonce dùng một lần.
- Bản tin đầu ngày hoặc cuối ngày theo giờ người dùng tự bật.
- Nhắc việc sắp hạn, task mới cần xác nhận và cảnh báo mâu thuẫn.
- Xem danh sách `Hôm nay`, `Việc của tôi`, `Đang chờ` và trạng thái tiến độ.
- Thao tác `Đã làm`, `Nhắc lại`, `Bỏ qua`, `Xem nguồn` ngay trên tin nhắn.
- Người dùng giao việc bằng câu tự nhiên; bot dựng preview, hỏi trường còn thiếu
  và chỉ tạo sau nút `Chấp nhận`.
- Triage Gmail chỉ đọc: email cần xử lý, hạn chót/sự kiện rút ra từ email và
  nút mở email gốc.
- Cấu hình loại thông báo, giờ nhận, giờ yên lặng và tạm dừng.

### P1 — chỉ làm sau khi P0 có tín hiệu

- Mini App cho lịch tuần, chỉnh draft nhiều trường và so sánh hai nguồn mâu
  thuẫn cạnh nhau.
- `Cơ hội`: sự kiện, chương trình, học bổng hoặc hoạt động lấy từ **nguồn đã
  kết nối và được cấp quyền**.
- `Tin tức`: cập nhật có liên quan từ các nguồn đã cam kết, không phải news
  feed tổng quát.
- Bộ lọc tag, tìm kiếm và lịch sử đã xử lý trong Mini App.

### Không thuộc pilot

- Gửi, archive, xóa, đổi label hoặc trả lời Gmail.
- Bot tự tạo task/event, tự giao việc cho người khác hoặc tự đổi deadline.
- Đọc lịch sử group/private chat Telegram.
- Tổng hợp web/news toàn Internet.
- Native mobile app hoặc Zalo adapter.

## 3. Taxonomy tag

Tag là metadata điều hướng, không phải nguồn sự thật. Mỗi item có tối đa một
`topic_tag`, một `state_tag` và một `priority`; không nhét nhiều hashtag vào
nội dung tin nhắn. UI hiển thị chip tiếng Việt, API lưu enum ổn định.

### Topic tag — item nói về việc gì

| Enum | Chip | Nội dung |
| --- | --- | --- |
| `task` | `#việc` | Task của người dùng hoặc task cần xác nhận |
| `reminder` | `#nhắc-nhở` | Một mốc nhắc đã lên lịch |
| `calendar` | `#lịch` | Sự kiện, lịch tuần hoặc xung đột lịch |
| `email` | `#email` | Nội dung cần xử lý được rút từ Gmail read-only |
| `opportunity` | `#cơ-hội` | Cơ hội từ nguồn đã cấp quyền |
| `news` | `#tin-tức` | Thay đổi/thông báo có liên quan từ nguồn đã cấp quyền |
| `conflict` | `#mâu-thuẫn` | Hai nguồn hoặc hai lịch không khớp |

### State tag — người dùng cần làm gì

| Enum | Chip | Ý nghĩa |
| --- | --- | --- |
| `action_required` | `Cần xử lý` | Cần một hành động của người dùng |
| `due_soon` | `Sắp hạn` | Đang tới một mốc thời gian gần |
| `waiting` | `Đang chờ` | Chưa có hành động tiếp theo từ người dùng |
| `needs_confirmation` | `Chờ xác nhận` | Draft hoặc task đề xuất chưa được duyệt |
| `changed` | `Vừa đổi` | Nguồn có phiên bản mới |
| `completed` | `Đã xong` | Công việc đã hoàn thành |

`priority = critical | high | normal | low` tiếp tục được tính bằng luật theo
ADR-007. Không cho mô hình tự nâng mức ưu tiên. Các view `Hôm nay`, `Việc của
tôi`, `Cơ hội` là truy vấn kết hợp tag + thời gian + ownership, không tạo thêm
trạng thái nghiệp vụ.

## 4. Trải nghiệm Telegram

### 4.1. Navigation

Menu cố định:

- `Hôm nay` — tối đa 5 item quan trọng, có nút xem tiếp;
- `Việc của tôi` — task theo trạng thái và hạn;
- `Lịch` — lịch hôm nay/tuần và xung đột;
- `Email` — email cần xử lý, không phải toàn bộ inbox;
- `Cơ hội & tin tức` — P1, mặc định tắt;
- `Cài đặt` — loại thông báo, giờ nhận, giờ yên lặng, tạm dừng, ngắt liên kết.

Chat xử lý nội dung ngắn và quyết định một chạm. Mini App chỉ mở cho lịch tuần,
form nhiều trường, evidence dài và màn hình so sánh mâu thuẫn.

### 4.2. Luồng nhắc việc

```text
Bot gửi nhắc → [Đã làm] [Nhắc lại] [Bỏ qua] [Xem nguồn]
              ├─ Đã làm: hoàn thành task của chính user
              ├─ Nhắc lại: chọn 15 phút / 1 giờ / ngày mai
              ├─ Bỏ qua: chọn lý do, chỉ hủy reminder
              └─ Xem nguồn: mở evidence được phép truy cập
```

`Bỏ qua` không hủy task. Callback phải idempotent để bấm lại hoặc Telegram gửi
lại update không tạo tác động trùng.

### 4.3. Luồng người dùng giao việc

Ví dụ: “Nhắc tôi gửi báo cáo cho mentor lúc 17h thứ sáu”.

1. Bot phân tích `title`, `due_at`, `timezone`, assignee và loại hành động.
2. Trường thiếu hoặc mơ hồ được hỏi lại; không tự đoán.
3. Bot gửi draft có nguồn là chính câu lệnh của người dùng.
4. Người dùng chọn `Sửa`, `Chấp nhận` hoặc `Hủy`.
5. Chỉ `Chấp nhận` mới gọi executor; retry dùng idempotency key.

Nếu câu lệnh giao việc cho người khác, P0 chỉ tạo draft cá nhân hoặc từ chối
rõ ràng. Không gửi tin hay tạo task cho bên thứ ba.

### 4.4. Luồng Gmail và lịch email

`Email` là một inbox ưu tiên đã lọc, gồm:

- email có khả năng giao việc cho user;
- hạn chót/sự kiện được trích xuất có evidence;
- thread có thay đổi ảnh hưởng task đã biết;
- email đang chờ user xác nhận thành task/reminder/calendar draft.

Hành động được phép: `Mở email`, `Tạo task`, `Nhắc tôi`, `Thêm vào lịch`.
Không tuyên bố “đã thêm lịch” trước khi có bằng chứng ghi thành công.

### 4.5. Cơ hội và tin tức

Hai tag này dễ tạo nhiều nội dung nhưng chưa chắc tạo giá trị. Vì vậy P1 chỉ
bật khi P0 chứng minh người dùng xử lý task/reminder trên Telegram, và mỗi item
phải có:

- nguồn mở lại được và thời điểm nguồn cập nhật;
- lý do liên quan tới vai trò/mục tiêu đã xác nhận của user;
- nút `Quan tâm`, `Ẩn loại này`, `Xem nguồn`;
- giới hạn tần suất riêng, mặc định tắt.

Không dùng lượt gửi hoặc lượt click làm bằng chứng giá trị duy nhất. Phải đo xem
item có dẫn tới hành động đã xác nhận hay không.

## 5. Kiến trúc triển khai

```text
Telegram webhook
  → verify secret + dedupe update_id
  → channel identity link → user_id
  → command/callback router
  → existing conversation/task/reminder/calendar services
  → channel presenter (text + inline keyboard)
  → Telegram Bot API

Reminder/daily-brief scheduler
  → channel preference + quiet hours/rate cap
  → Telegram outbox
  → delivery worker → Telegram Bot API
  → delivery receipt/idempotency record
```

### Thành phần mới

- `telegram webhook adapter`: xác minh, normalize update và trả response nhanh;
- `channel identity service`: nonce một lần, link/unlink và revoke;
- `channel presenter`: cắt độ dài, escape format và tạo inline keyboard;
- `channel outbox/delivery worker`: retry có backoff, chống gửi trùng và ghi
  trạng thái lỗi;
- `channel preferences`: opt-in theo topic, giờ nhận, quiet hours, pause;
- `Telegram Mini App shell` ở P1, dùng chung API hiện có.

### Phần dùng lại

- conversation core và agent graph cho hỏi đáp;
- `scope.py`/retrieval cho phân quyền;
- task lifecycle và action preview/confirm;
- reminder priority, snooze/dismiss, batching và quiet hours;
- calendar cache/handoff và Gmail read-only tools;
- brief/evidence/citation validator.

Không nên biến `Reminder.kind` thành taxonomy cho mọi nội dung. `kind` tiếp tục
biểu diễn sự kiện giao thông báo; `topic_tag/state_tag` là view model được dựng
từ Task, Brief, Reminder và Evidence. Chỉ thêm cột canonical nếu một tag thực
sự có vòng đời nghiệp vụ độc lập sau pilot.

### Contract tối thiểu đề xuất

| Endpoint | Mục đích |
| --- | --- |
| `POST /api/v1/channels/telegram/webhook` | Nhận update/callback, verify và dedupe |
| `POST /api/v1/channels/telegram/link-token` | User đã đăng nhập tạo nonce ngắn hạn |
| `DELETE /api/v1/channels/telegram/link` | Ngắt liên kết và dừng push |
| `GET/PATCH /api/v1/channels/telegram/preferences` | Opt-in, tag, giờ nhận, quiet hours |
| `GET /api/v1/mobile-feed?view=today|tasks|email|calendar` | DTO gọn dùng chung cho bot/Mini App |
| `POST /api/v1/channel-actions/{token}/confirm` | Confirm callback ký, scoped, idempotent |

Tên contract chỉ là đề xuất. Contract chính thức phải được review trước schema
hoặc frontend implementation.

## 6. Bảo mật, riêng tư và độ tin cậy

- Telegram user chưa liên kết nhận 0 nội dung nội bộ.
- Link bằng nonce dùng một lần, hết hạn ngắn; không gõ mã học viên trong chat.
- Mọi truy vấn dùng `user_id` sau scope check; callback không tin `user_id`
  hoặc task id do client gửi.
- Webhook kiểm `X-Telegram-Bot-Api-Secret-Token`; update được dedupe.
- Mini App verify `initData` HMAC và thời gian phát hành ở server.
- Callback token ký, hết hạn và buộc vào user/action/version cụ thể.
- Không log raw message, email body, answer hoặc bot token trong analytics.
- Tin nhạy cảm chỉ hiện tóm tắt tối thiểu; evidence dài mở trong bề mặt đã xác
  thực.
- Revoke nguồn hoặc unlink Telegram phải chặn retrieval/push mới ngay lập tức.
- Mọi send failure, rate limit và block bot được quan sát nhưng không chứa nội
  dung người dùng.

## 7. Kế hoạch triển khai theo lát cắt

Mỗi lát cắt chỉ vào Jira sau khi ADR và product acceptance được duyệt.

| Phase | Outcome | Phạm vi ước lượng | Exit gate |
| --- | --- | --- | --- |
| 0 — Quyết định | ADR-012, privacy copy, feature spec, event schema và pilot protocol | 1–2 ngày | PM + Tech + UI/UX + QA/Privacy duyệt |
| 1 — Kết nối an toàn | Webhook, nonce link/unlink, identity scope, update dedupe, echo | 2 ngày | Unlinked/cross-user/replay đều bị chặn |
| 2 — Theo dõi mobile | `Hôm nay`, tag/view, daily brief opt-in, reminder push, source link | 2–3 ngày | Gửi đúng user, không trùng, quiet hours/cap đúng |
| 3 — Xử lý công việc | Done/snooze/dismiss, giao việc bằng chat, draft/confirm | 2–3 ngày | Không action trước confirm; retry không tạo trùng |
| 4 — Email và lịch | Gmail triage, task/reminder/calendar draft, lịch hôm nay | 2–3 ngày | Read-only được giữ; evidence và trạng thái ghi đúng |
| 5 — Mini App có điều kiện | Lịch tuần, edit draft, compare conflict, settings | 3–5 ngày | Mobile E2E, accessibility, typecheck/lint/build pass |
| 6 — Pilot | Baseline + pilot 5–10 user, review hằng ngày | 10–14 ngày lịch | Có evidence đủ cho Proceed/Iterate/Stop |

Không bắt đầu `Cơ hội` và `Tin tức` trước review giữa pilot. Nếu P0 không tạo
mobile resolution, thêm feed sẽ chỉ tăng nhiễu.

## 8. Test và release gate

Mọi thay đổi code phải có regression test theo `AGENTS.md`.

### Backend/API

- webhook secret đúng/sai, update trùng và payload malformed;
- nonce hết hạn, reuse nonce, unlink và Telegram identity chưa liên kết;
- user A không đọc/confirm task, reminder, brief hoặc evidence của user B;
- callback hợp lệ, hết hạn, sửa payload và bấm lặp;
- send retry/429/timeout không tạo delivery trùng;
- revoke source/unlink ngăn push và retrieval mới;
- create-by-chat thiếu trường, ambiguous assignee/timezone và confirm idempotent;
- dismiss reminder không cancel task; done mới complete task;
- Gmail action chỉ tạo draft, không gửi/sửa email;
- quiet hours, batching, hourly cap và opt-out theo tag.

### Frontend/Mini App

- filter tag/view, empty/loading/partial/source-error state;
- draft edit/confirm/cancel và stale-version conflict;
- lịch timezone, source link và conflict comparison;
- keyboard navigation, focus, touch target và màn hình hẹp;
- verify Mini App auth failure; không render dữ liệu trước auth.

### Lệnh gate dự kiến

- backend test liên quan và full regression phù hợp;
- frontend unit/integration test;
- frontend typecheck, lint và production build;
- config validation cho webhook/worker/deploy;
- synthetic E2E: Telegram update → scoped data → action → delivery receipt.

Không dùng live bot/token thật trong CI. Fixture phải synthetic/redacted.

## 9. Chứng minh giá trị cho người dùng

### 9.1. Đừng dùng “số tin đã gửi” làm outcome

Telegram Bot API không cung cấp read receipt đáng tin cho bot chat. Vì vậy
không dùng `message_sent` hoặc “đã đọc” suy diễn làm bằng chứng. Cần đo hành vi
có chủ đích sau thông báo và kết quả công việc.

### 9.2. Chuỗi bằng chứng

```text
Đúng thông tin, đúng người
  → user nhận biết sớm hơn
  → xử lý ngay trên Telegram/Mini App
  → ít phải mở web/nguồn để thao tác lại
  → nhiều task đến hạn được hoàn thành hơn
```

Mỗi mắt xích cần một loại evidence:

| Câu hỏi | Chỉ số | Cách đo không chứa nội dung nhạy cảm |
| --- | --- | --- |
| Bot có gửi đúng không? | Delivery success, duplicate, permission failure | IDs băm, kind, status, latency |
| User có phản ứng không? | `acknowledged/actioned x/n`, thời gian tới hành động đầu tiên | Event button/command + timestamp |
| Có tránh mở web không? | `Telegram-only resolution` | Action hoàn tất trong Telegram/Mini App và không có web-app event trong cửa sổ 30 phút |
| Có giảm công sức không? | Số bước và thời gian từ alert → done/confirm; self-report theo tình huống | Event sequence + micro-survey 1 câu |
| Có cải thiện kết quả không? | Tỷ lệ hoàn thành task đến hạn trong tuần | Công thức PRD §4.2, so với baseline cùng user |
| Có gây phiền không? | Snooze/dismiss, pause/unsubscribe, block/send failure | Event type + reason enum, không lưu text |
| Có đáng tin không? | Mở evidence, phản hồi sai/thiếu nguồn, unsafe action | Count theo event và test suite |

`Telegram-only resolution` là proxy có giới hạn: nó chứng minh không mở web app
mondaiy trong cửa sổ đo, không thể chứng minh user không dùng một laptop/app
khác. Vì vậy phải ghép với phỏng vấn và câu hỏi theo tình huống: “Với việc vừa
xử lý, nếu không có bot bạn sẽ phải mở đâu?”.

### 9.3. Thiết kế pilot trong-subject

Với 5–10 người, không chia A/B vì mỗi nhóm quá nhỏ. Dùng mỗi người làm đối chứng
cho chính họ:

1. **Baseline 3–5 ngày:** dùng luồng hiện tại; ghi completion, thời gian phản
   hồi, lượt mở web/nguồn và nhật ký ngắn.
2. **Telegram 7 ngày:** cùng loại task/nguồn; bật P0, không bật news/opportunity.
3. **Review hằng ngày:** kiểm trust blocker, duplicate, notification fatigue và
   case user vẫn phải mở laptop.
4. **Phỏng vấn cuối pilot:** replay 2–3 event thật theo ID đã redacted, không hỏi
   chung chung “có thích không”.
5. **Báo cáo paired:** trước/sau theo từng user và task đủ điều kiện; báo `x/n`
   người thay vì phần trăm tổng hợp gây hiểu nhầm.

### 9.4. Event analytics tối thiểu

| Event | Thuộc tính được phép |
| --- | --- |
| `tg_delivery_attempted/succeeded/failed` | user hash, kind, tag, latency, error class |
| `tg_action_clicked/completed/failed` | action enum, item type, elapsed time, status |
| `tg_draft_created/confirmed/cancelled` | action type, missing-field count, elapsed time |
| `tg_source_opened` | provider enum, item type; không lưu URL/content |
| `tg_preferences_changed` | topic enum, enabled/disabled, quiet-hours changed |
| `web_surface_opened` | surface enum, timestamp để ghép cửa sổ resolution |
| `task_completed` | source enum, due bucket, completion timestamp |

Không ghi raw Telegram text, email subject/body, task title, answer hoặc source
URL vào product analytics.

### 9.5. Decision rule trước khi pilot

Sau khi biết chính xác `n`, PM phải đổi tiêu chí dưới đây thành số nguyên trước
khi xem kết quả, ví dụ `5/8 user`, không đổi gate sau pilot:

- **Trust gate:** 0 cross-user leak, 0 unsupported factual claim trong bộ kiểm
  thử, 0 system action trước confirm, 0 duplicate side effect.
- **Outcome:** completion rate task đến hạn tăng so với baseline theo PRD §4.2.
- **Behavior:** đa số user đủ điều kiện có ít nhất 3 `Telegram-only resolution`
  trên ít nhất 3 ngày khác nhau.
- **Qualitative:** mỗi user được tính là “có giá trị” phải đưa ra ít nhất một
  tình huống cụ thể bot giúp họ tránh tìm/nhập lại hoặc phản ứng sớm hơn.
- **Cost of value:** notification fatigue không tăng tới mức user pause,
  unsubscribe hoặc liên tục dismiss vì không liên quan.

Kết luận:

- `Proceed P1` khi trust gate đạt, outcome tăng và behavior + interview cùng
  chỉ về một cơ chế giá trị;
- `Iterate` khi trust đạt nhưng user đọc mà không xử lý, hoặc vẫn phải mở web để
  hoàn thành;
- `Stop/pivot` khi trust không đạt, completion không cải thiện, hoặc phần lớn
  tín hiệu chỉ là click tò mò/notification noise.

## 10. Các quyết định phải chốt trước build

1. Telegram có được phép nhận nội dung tóm lược nội bộ ở mức chi tiết nào?
2. Mục tiêu pilot chính là completion rate hay giảm phụ thuộc laptop? PRD hiện
   đặt completion rate làm chỉ số quan trọng nhất; giảm mở laptop là chỉ số dẫn.
3. User tự bật loại push nào và giá trị mặc định ra sao?
4. `Đã làm` trên Telegram có đủ được coi là thao tác trực tiếp của user theo
   ADR-007 hay vẫn cần preview cho một số loại task?
5. Có cho P0 hiển thị snippet email trong Telegram hay chỉ metadata + deep link?
6. Sau pilot có thiết kế adapter đa kênh hay chấp nhận Telegram-specific?

## 11. Tài liệu cần promote đồng bộ

Nếu proposal được chấp nhận:

1. tạo ADR-012 cho kênh Telegram, privacy boundary, identity và delivery;
2. cập nhật PRD với actor, scope, acceptance, empty/error/consent state và
   metrics;
3. tạo feature spec cho Telegram mobile command center;
4. cập nhật wireframe/UI flow cho bot và Mini App;
5. cập nhật pilot/evaluation plan và event dictionary;
6. tạo Jira epic/stories từ các lát cắt đã duyệt, không dùng file này làm task
   tracker.
