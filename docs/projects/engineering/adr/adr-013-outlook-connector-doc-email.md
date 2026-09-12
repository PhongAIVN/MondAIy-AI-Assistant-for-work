# ADR-013 — Outlook làm connector đọc email thứ hai, song song Gmail

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Approved |
| Owner | Thái Hoài An (PM) |
| Author | Nguyễn Văn Phong (Technical Lead) + Claude |
| Reviewers | PO/QC, Privacy/Security DRI |
| Last updated | 2026-08-13 |
| Related | [ADR-002](adr-002-connector-first-p0-scope.md) · [ADR-003](adr-003-gmail-va-discord-truoc-trong-hai-tuan-build.md) · [ADR-012](adr-012-telegram-p0-cho-tom-tat-va-nhac-viec.md) · [PRD](../../product/prd.md) |

## Bối cảnh

ADR-002 chốt phạm vi nguồn P0: Discord, VLearn, Gmail. Gmail là nguồn email
duy nhất. Có nhu cầu thực tế: một phần người dùng chương trình dùng hộp thư
Outlook/Microsoft 365 (trường học, doanh nghiệp cấp email `@outlook.com`,
`@hotmail.com` hoặc tenant Microsoft 365 riêng), không có Gmail hoặc dùng cả
hai. Pipeline trích task/deadline từ email hiện chỉ thấy được nửa hộp thư của
nhóm người dùng này.

ADR này **chỉ đề xuất**, chưa được duyệt. Thêm nguồn dữ liệu là material
change về scope và privacy theo đúng tinh thần ADR-002 — không tự triển khai
khi chưa có quyết định của PM.

## Quyết định (đề xuất)

### 1. Outlook là connector đọc, cùng vai trò với Gmail

Chỉ đọc mail qua Microsoft Graph API, không gửi/xoá/sửa gì trong hộp thư
người dùng. Cùng interface `BaseConnector` (`src/connectors/base.py`) Gmail
đang dùng — pipeline (`fetch → normalize → filter → extract_batch → cluster
→ persist`) không cần biết provider cụ thể, chỉ đọc field `provider` để tách
nhánh khi thật sự cần (như Jira rule-based hiện tại).

### 2. OAuth qua Microsoft identity platform, App Registration riêng

Đăng ký ứng dụng mới trên Azure Portal (Entra ID) — không dùng chung
credential với Google. Cần `MICROSOFT_CLIENT_ID`/`MICROSOFT_CLIENT_SECRET`
mới trong `.env`, do người có quyền tạo App Registration thực hiện thủ công
(bước này không tự động hoá được, giống Google Cloud Console cho Gmail).

Scope tối thiểu: `Mail.Read offline_access openid email profile`. Không xin
`Mail.ReadWrite` hay `Mail.Send` — P0 không cần và xin thừa quyền là rủi ro
privacy không cần thiết.

Endpoint: `https://login.microsoftonline.com/common/oauth2/v2.0/authorize`
(authorize) và `/token` (exchange/refresh) — cùng pattern `authorization_code`
+ `refresh_token` như `src/services/connections/google.py`, viết
`src/services/connections/microsoft.py` song song.

### 3. Đọc mail qua Microsoft Graph, không dùng IMAP

Dùng `GET /me/messages` (Graph API v1.0) với delta query
(`/me/messages/delta`) cho đồng bộ tăng dần, tương đương Gmail History API.
Không dùng IMAP: Microsoft đang tắt dần Basic Auth cho IMAP trên tenant
Microsoft 365, xác thực hiện đại (OAuth) chỉ được hỗ trợ đầy đủ qua Graph.

### 4. Normalize về đúng schema Gmail đang dùng

`OutlookConnector.normalize()` trả về cùng shape `GmailConnector.normalize()`
(`id`, `provider="outlook"`, `text`, `sent_at`, `deep_link`, `evidence`...).
Nhờ vậy `extract_batch_node` không cần nhánh riêng cho Outlook — đi thẳng
qua nhánh LLM hiện có (giống Gmail), không cần rule engine riêng như Jira.

### 5. UI: thêm vào danh sách provider hiện có, không tạo luồng riêng

`_PROVIDERS` trong `src/api/connections.py` thêm `"outlook"`. Frontend
(`SourceLibraryPage`, `connectionsApi.ts`, `BrandIcons.tsx`) thêm 1 mục
connect Outlook cạnh Gmail/Discord/Jira — dùng lại đúng luồng
intent/start/callback OAuth hiện có (`/connections/{provider}/intent` →
`/connections/{provider}/start` → `/connections/{provider}/callback`),
không cần thiết kế mới.

## Phương án đã cân nhắc

| Phương án | Kết luận |
| --- | --- |
| IMAP thay Graph API | Loại: Microsoft tắt dần Basic Auth IMAP, Graph là hướng chính thức |
| Gộp chung 1 provider "email" cho cả Gmail/Outlook | Loại: token/scope/refresh flow khác hẳn nhau giữa hai bên, gộp làm code phức tạp hơn không đơn giản hơn |
| Xin luôn `Mail.ReadWrite` để dành cho tính năng ghi sau này | Loại: xin thừa quyền ngay từ đầu vi phạm nguyên tắc minimal scope, phải xin lại khi thật sự cần |
| Dùng chung App Registration Azure với tổ chức khác (nếu có sẵn) | Chưa đủ thông tin — cần Tech Lead + người quản trị Azure tenant xác nhận trước khi build |

## Hệ quả

- Thêm 1 third-party data processor mới (Microsoft) — **bắt buộc cập nhật
  consent copy/privacy policy** liệt kê Microsoft trước khi bật tính năng cho
  người dùng thật (đúng nguyên tắc "gotcha" trong CLAUDE.md: không âm thầm
  thêm nguồn dữ liệu).
- Thêm 1 giá trị `provider` mới trong bảng `connections`, `messages` —
  không đổi schema, chỉ thêm dữ liệu.
- Cần Azure App Registration thật, một bước thủ công ngoài code, y hệt độ
  phức tạp vận hành Google Cloud Console đã có cho Gmail — không phải chỉ
  code xong là chạy được.
- Rate limit/throttling của Graph API khác Gmail (429 kèm header
  `Retry-After`, tương tự Gmail — connector có thể tái dùng logic backoff
  đã có).

## Acceptance và evidence (khi được duyệt)

1. OAuth Outlook thành công lưu được Connection với `provider_user_id` =
   email, giống Gmail.
2. Sync đọc đúng account đã kết nối, không đọc account Microsoft khác trên
   cùng máy.
3. Extract task/deadline từ email Outlook ra kết quả tương đương chất lượng
   Gmail trên cùng bộ test case (golden dataset mở rộng thêm case Outlook).
4. Revoke/disconnect dừng sync ngay, không còn gọi Graph API cho user đó.
5. Refresh token hết hạn/bị thu hồi → connection chuyển trạng thái lỗi rõ
   ràng, không loop lỗi âm thầm.
6. Không log nội dung email, access token hay refresh token dạng plaintext.

## Việc tiếp theo ngoài ADR

- `src/services/connections/microsoft.py` — OAuth dance (song song
  `google.py`).
- `src/connectors/outlook.py` — `OutlookConnector` implement `BaseConnector`.
- Wire vào `src/connectors/registry.py`, `src/api/connections.py`
  (`_PROVIDERS`), pipeline `fetch_node`/`normalize_node`.
- Frontend: `SourceLibraryPage`, `connectionsApi.ts`, `BrandIcons.tsx`,
  i18n copy cho Outlook.
- Golden dataset mở rộng thêm fixture/expected cho Outlook (theo cấu trúc
  `eval/golden_dataset/fetch_norm_filter/`).
- Cập nhật privacy policy + consent copy trước khi bật cho người dùng thật.

**Toàn bộ mục trên chỉ triển khai sau khi Status chuyển `Approved`.**
