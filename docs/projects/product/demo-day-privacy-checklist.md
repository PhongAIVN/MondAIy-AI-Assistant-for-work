# Demo Day privacy checklist

| Thuộc tính | Giá trị |
| --- | --- |
| Scope | Demo Day nội bộ (TAPB Sprint 4 — Stabilize MVP & pilot readiness), KHÔNG phải checklist pilot 7 ngày đầy đủ |
| Liên quan | [Pre-pilot checklist đầy đủ](pilot-plan.md#4-pre-pilot-checklist) · [PRD](prd.md) |
| Cập nhật | 2026-08-15 (v2 — sau khi fix revoke token + xoá tài khoản), dựa trên đọc code thật (`src/api/`, `client/web-app/src/`), không phải tài liệu cũ |

Mục tiêu: xác nhận những gì có thể NÓI trước mặt team/stakeholder ở Demo Day là
đúng với những gì code THẬT SỰ làm — không hứa quá những gì đã implement.

## 1. Những gì hoạt động thật (verify được qua API)

- [x] Disconnect từng nguồn: `POST /connections/{provider}/disconnect` —
      [src/api/connections.py](../../../src/api/connections.py) — revoke token
      thật phía Google/Discord (`oauth2.googleapis.com/revoke`,
      `discord.com/api/oauth2/token/revoke`) TRƯỚC KHI xoá row `Connection`
      local. Jira/Outlook chỉ xoá local — 2 provider này không có API revoke
      app-initiated công khai (xác nhận qua docs chính thức Atlassian/
      Microsoft, không phải thiếu sót ở app), user phải tự vào trang quản lý
      app của provider đó để thu hồi hoàn toàn.
- [x] Xoá vĩnh viễn tài khoản: `DELETE /auth/me` —
      [src/api/auth.py](../../../src/api/auth.py) — yêu cầu đúng password
      hiện tại (nếu tài khoản có đặt password), revoke token mọi connection
      trước, rồi xoá sạch dữ liệu qua
      [src/services/account_deletion.py](../../../src/services/account_deletion.py)
      (~20 bảng không có FK cascade tới `users.id`, xem docstring file đó) +
      xoá chính hàng User. Giữ lại `audit_events` (bằng chứng vận hành, đúng
      thiết kế ở `src/models/telemetry.py`) — không tính là dữ liệu cá nhân,
      không chứa nội dung, chỉ tham chiếu object_id.
- [x] Xoá memory: `DELETE /memory/profile`, `DELETE /memory/long-term`,
      `DELETE /memory/long-term/{key}` — [src/api/memory.py](../../../src/api/memory.py).
- [x] Xoá conversation: `DELETE /conversations/{id}`.
- [x] Xoá meeting note: `DELETE /meeting-notes/{id}`.
- [x] Xoá routine: `DELETE /routines/{id}`.
- [x] Xoá file đã upload: `DELETE /storage/{object_key}`.
- [x] Huỷ đăng ký push: `DELETE /push/subscribe`.
- [x] Scope OAuth Google hiện tại: `openid email profile
      gmail.readonly calendar.readonly calendar.events` —
      [src/config.py:322-324](../../../src/config.py) — CHỈ ĐỌC Gmail/Calendar,
      quyền ghi duy nhất là tạo event Calendar do chính app tạo ra.

## 2. Gap đã xác nhận — PHẢI nói rõ khi demo, không im lặng bỏ qua

- [ ] **"Disconnect" KHÔNG revoke token Jira/Outlook** (chỉ Google/Discord có
      API revoke thật). Nếu demo hỏi "Jira/Outlook cũng thu hồi hoàn toàn
      chứ?" — trả lời đúng: KHÔNG, đây là giới hạn của chính Atlassian/
      Microsoft, không phải app chưa làm. User cần biết để tự vào
      id.atlassian.com/manage-profile hoặc myaccount.microsoft.com revoke tay
      nếu muốn chắc chắn 100%.
- [ ] **Xoá tài khoản (`DELETE /auth/me`) chỉ mới unit test, chưa test qua
      UI** — chưa có nút "Xoá tài khoản" nào trên `client/web-app` gọi tới
      endpoint này (kiểm tra lại trước Demo Day nếu cần demo trực tiếp trên
      UI, không chỉ qua API).
- [ ] **Trang "Data & Privacy" (`/data-privacy`) là mock, KHÔNG kết nối
      backend.** Kiểm tra toàn bộ
      [`useDataPrivacyStore.ts`](../../../client/web-app/src/stores/useDataPrivacyStore.ts)
      (592 dòng) và các component trong
      [`components/privacy/`](../../../client/web-app/src/components/privacy/)
      — KHÔNG có bất kỳ lệnh gọi `fetch`/`axios`/API nào. Toàn bộ Memory
      Inspector, Audit Log, Redaction Editor, Bulk Delete trên trang này là
      dữ liệu tĩnh hard-code trong store, bấm nút không ghi gì xuống DB thật.
      **TUYỆT ĐỐI không demo trang này như tính năng thật** — nếu Demo Day cần
      show privacy control, dùng Sources page (`/sources`, disconnect thật —
      xem [SourceLibraryPage.tsx:501](../../../client/web-app/src/pages/SourceLibraryPage.tsx))
      thay vì `/data-privacy`.

## 3. Trước khi demo

- [ ] Người demo đã đọc mục 2, biết KHÔNG được claim quá những gì code làm.
- [ ] Nếu stakeholder hỏi "xoá tài khoản thế nào" — trả lời đúng thực tế:
      `DELETE /auth/me` xoá thật, xoá sạch, nhưng hiện chỉ gọi được qua API
      (Postman/curl), chưa có nút trên UI web app.
- [ ] Nếu stakeholder hỏi "Jira/Outlook disconnect có revoke thật không" —
      trả lời KHÔNG, nói rõ đây là giới hạn phía Atlassian/Microsoft (xem
      mục 2), không phải thiếu sót có thể sửa nhanh.
- [ ] Demo account dùng `scripts/seed_demo.py` (xem
      [runbook](../engineering/demo-runbook.md)) — không có kết nối OAuth thật
      nào gắn vào account demo, nên không có dữ liệu cá nhân thật nào bị lộ
      nếu demo public/quay recording.

## 4. Không nằm trong scope Demo Day (khác pre-pilot checklist đầy đủ)

Các mục sau thuộc [pre-pilot checklist](pilot-plan.md#4-pre-pilot-checklist)
đầy đủ cho pilot 7 ngày thật (5-10 learner, dữ liệu thật) — KHÔNG bắt buộc cho
Demo Day nội bộ dùng demo account giả:

- Consent copy review theo từng connector thật.
- Golden set/release threshold.
- Source health/queue lag observability cho nhiều user song song.
- Permission/revoke/delete test trên tài khoản thật của learner.

Đừng nhầm 2 checklist — Demo Day pass không có nghĩa pre-pilot pass.
