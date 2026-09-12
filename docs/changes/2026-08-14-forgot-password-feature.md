# Feature: Quên mật khẩu (forgot/reset password)

## Mục tiêu

Hoàn thiện luồng "quên mật khẩu" — FE đã có sẵn `ForgotPasswordPage` và
`ResetPasswordPage` (kèm route, i18n) nhưng `useAuthStore.forgotPassword` /
`resetPassword` chỉ là stub trả `true` không gọi backend, và backend hoàn
toàn chưa có endpoint tương ứng. Repo cũng chưa có hạ tầng gửi email nào
(không SMTP, không provider) trước thay đổi này.

## Agent/lane và ownership

1 agent, sửa trực tiếp trên `main` checkout, không có lane song song.

## Base/head

- Base: `09024ed` (HEAD lúc bắt đầu).
- Chưa commit — thay đổi đang ở working tree.

## Quyết định phạm vi (đã hỏi user)

User chọn "SMTP thật + fallback dev-log": thêm cấu hình SMTP thật vào
`src/config.py`, gửi qua `smtplib`; nếu `SMTP_HOST` để trống thì chỉ log
link reset ra console (không chặn dev/pilot vì thiếu secret).

## Hành vi thay đổi

### Backend

- `src/config.py` — thêm `password_reset_token_expire_minutes` (mặc định 30
  phút) và block `SMTP_*` (host/port/username/password/use_tls/from_email/
  from_name).
- `src/models/user.py` — thêm `reset_token_hash` (sha256, không lưu
  plaintext) và `reset_token_expires_at` trên bảng `users`.
- `src/db.py` — `_ensure_password_reset_columns()`: migration ALTER TABLE
  idempotent cho DB đã tồn tại (cùng pattern các migration khác trong file,
  vì `create_all` không sửa bảng có sẵn), đăng ký vào `ensure_runtime_schema`.
- `src/services/auth.py` — thêm `generate_reset_token()`
  (`secrets.token_urlsafe(32)`) và `hash_reset_token()` (sha256 — token có
  entropy cao nên không cần bcrypt như password).
- `src/services/email.py` (mới) — `send_password_reset_email()`: dùng
  `smtplib` + STARTTLS khi `SMTP_HOST` có cấu hình, ngược lại log link ra
  console (dev fallback).
- `src/models/schemas.py` — `ForgotPasswordRequest/Response`,
  `ResetPasswordRequest/Response` (CamelModel, khớp convention JSON hiện có).
- `src/api/auth.py` — 2 endpoint mới:
  - `POST /auth/forgot-password` (rate limit 5/phút): luôn trả cùng message
    + 200 bất kể email có tồn tại hay không (chặn user enumeration); chỉ
    thật sự tạo token + gửi mail khi user tồn tại và active. Lỗi gửi mail bị
    log, không lộ ra response.
  - `POST /auth/reset-password` (rate limit 10/phút): tra user theo hash
    token, kiểm tra hết hạn (xử lý naive/aware datetime của SQLite theo đúng
    pattern đã có ở `services/reminders.py`), đổi `password_hash`, xoá token
    (dùng một lần).

### Frontend

- `client/web-app/src/lib/authApi.ts` — thêm `forgotPassword()`,
  `resetPassword(token, newPassword)` gọi 2 endpoint trên.
- `client/web-app/src/stores/useAuthStore.ts` — bỏ stub, gọi `authApi`
  thật; đổi signature `resetPassword` thành `(token, password)`.
- `client/web-app/src/pages/auth/ForgotPasswordPage.tsx` — bọc
  try/catch/finally quanh lời gọi thật, vẫn luôn hiện màn hình "đã gửi" bất
  kể lỗi mạng (giữ đúng UX chống enumeration của trang này).
- `client/web-app/src/pages/auth/ResetPasswordPage.tsx` — đọc `token` từ
  query string (`useSearchParams`), chặn submit nếu thiếu token, bắt lỗi
  400/network từ backend và hiện `t.auth.resetLinkInvalidError`.
- `client/web-app/src/i18n/translations.ts` — thêm key
  `auth.resetLinkInvalidError` (EN + VI).
- `.env.example` — tài liệu hoá biến `SMTP_*` và
  `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`.
- `.claude/launch.json` — thêm config `backend` (uvicorn) để preview_start
  mở được cả 2 server lúc dev (trước đó chỉ có `web-app`).

## File chính

- `src/config.py`, `src/models/user.py`, `src/db.py`, `src/services/auth.py`,
  `src/services/email.py` (mới), `src/models/schemas.py`, `src/api/auth.py`
- `client/web-app/src/lib/authApi.ts`,
  `client/web-app/src/stores/useAuthStore.ts`,
  `client/web-app/src/pages/auth/ForgotPasswordPage.tsx`,
  `client/web-app/src/pages/auth/ResetPasswordPage.tsx`,
  `client/web-app/src/i18n/translations.ts`
- `tests/test_api/v1/test_auth.py` — 5 test mới.

## Test đã chạy

```
.venv/Scripts/python.exe -m pytest tests/test_api/v1/test_auth.py -q
# 18 passed (13 cũ + 5 mới: generic message, valid-token single-use,
# unknown-token 400, short-password 422)

cd client/web-app && npx tsc -b
# exit 0, không lỗi type
```

Verify thủ công qua Browser pane, chạy thật với backend
(`.venv/Scripts/python.exe -m uvicorn src.main:app --port 8000`, đã chạy sẵn
từ trước) + frontend (`npm run dev`, port 5173):

- Đăng ký user test `verify-forgot-pw@example.com`.
- `POST /auth/forgot-password` qua curl → 200, message generic.
- Sinh token trực tiếp trong DB (mô phỏng đúng logic endpoint, vì endpoint
  không trả token ra response — đúng thiết kế bảo mật) để test UI
  `/reset-password?token=...`: điền mật khẩu mới → hiện "Password updated
  successfully."
- Xác nhận qua curl: login mật khẩu cũ → 401, mật khẩu mới → 200.
- `/reset-password?token=totally-bogus-token` → submit → hiện đúng
  "This reset link is invalid or has expired. Please request a new one."
- `/forgot-password` qua UI thật (click, không phải curl) → network tab xác
  nhận `POST /auth/forgot-password` 200, hiện màn hình thành công.
- Xoá user test khỏi DB dev sau khi verify xong.

## Phần chưa chạy

- Chưa gửi email thật qua SMTP provider thật (host/port/user/pass) — chỉ
  verify nhánh dev-log (SMTP_HOST rỗng). User chưa cung cấp provider cụ thể;
  khi có thì chỉ cần điền `.env`, không cần đổi code.
- Chưa chạy full test suite (`pytest tests/ -q`) toàn repo, chỉ chạy
  `test_auth.py` liên quan trực tiếp.
- Chưa chạy ruff/ESLint riêng.
- Không có cơ chế thu hồi access/refresh token đang hiệu lực khi reset mật
  khẩu (hệ thống JWT hiện tại là stateless, không lưu token để revoke — hạn
  chế có sẵn từ trước, không phải regression của thay đổi này).

## Risk

Thấp-trung bình. Thêm bảng/cột mới (không đổi cột cũ), 2 endpoint mới
(không đổi endpoint cũ), migration ALTER TABLE idempotent theo đúng pattern
sẵn có. Rủi ro chính là nhánh SMTP thật chưa được test với provider thật.

## Migration/config

- DB: 2 cột mới trên `users` (`reset_token_hash`, `reset_token_expires_at`),
  tự chạy qua `ensure_runtime_schema()` lúc backend khởi động, không cần
  chạy tay.
- Config mới cần set ở production khi muốn gửi mail thật: `SMTP_HOST`,
  `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`,
  `SMTP_FROM_NAME`. Để trống thì vẫn hoạt động (log link ra console thay vì
  gửi mail — không phù hợp cho user thật ở production, chỉ chấp nhận được ở
  dev/pilot).

## Merge/deploy status

Chưa commit, chưa deploy. Cần user xác nhận trước khi commit/push theo
AGENTS.md.

## Rollback

Chưa commit — `git checkout -- <file>` từng file hoặc `git clean` phần
`src/services/email.py` (file mới, chưa track) nếu cần discard toàn bộ.

## Follow-up

- Chọn SMTP provider thật (Gmail App Password, Resend, SendGrid SMTP relay
  ...) và điền `.env` production khi sẵn sàng đi live.
- Cân nhắc thêm cơ chế revoke refresh token khi đổi mật khẩu (hiện tại JWT
  cũ vẫn còn hiệu lực tới khi hết hạn tự nhiên) nếu yêu cầu bảo mật cao hơn.
- Cân nhắc rate-limit thêm theo email (không chỉ theo IP) nếu thấy bị lạm
  dụng để spam mailbox người khác qua `/forgot-password`.
