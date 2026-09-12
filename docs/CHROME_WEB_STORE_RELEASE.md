# Hướng dẫn Phát hành Extension mondaiy lên Chrome Web Store

Tài liệu này cung cấp quy trình chuẩn hóa, danh mục kiểm tra an toàn (pre-release checklist), giải trình quyền hạn (permission justifications) và báo cáo kiểm toán dữ liệu (data handling audit) phục vụ việc publish và cập nhật extension **mondaiy** trên **Chrome Web Store Developer Dashboard**.

---

## 1. Release Process (Quy trình đóng gói & phát hành)

Quy trình phát hành extension tuân theo chuỗi cổng kiểm soát chất lượng 5 bước:

```text
pnpm run compile       (TypeScript typecheck — 0 lỗi)
       ↓
pnpm test              (Vitest unit & integration test — 100% PASS)
       ↓
pnpm run build         (WXT / Vite production build — inline .env.production)
       ↓
artifact release gate  (verify-build-artifact.mjs — kiểm tra manifest, endpoints, secrets)
       ↓
pnpm run zip           (Đóng gói ZIP production vào .output/)
       ↓
Upload ZIP lên Chrome Web Store Developer Dashboard
```

### Cách đóng gói nhanh trên Windows:
Bạn chỉ cần **double-click** vào file script:
```text
C:\Users\THIS PC\Desktop\IT\AI THUC CHIEN\P-004\scripts\redeploy-extension.bat
```
Script sẽ tự động chạy toàn bộ 5 bước trên, kiểm tra an toàn và in đường dẫn file ZIP sẵn sàng để upload.

---

## 2. Pre-Release Checklist (Danh mục kiểm tra trước khi publish)

Trước khi submit bản build lên Chrome Web Store, hãy đối chiếu các hạng mục sau:

- [x] **Manifest V3**: `manifest_version: 3`, định dạng JSON chuẩn.
- [x] **Version**: Khớp giữa `package.json` và `manifest.json` (hiện tại: `0.1.1`).
- [x] **Permissions**: Đầy đủ 8 permissions + `sidePanel` + `<all_urls>` (không thiếu, không dư thừa).
- [x] **No Localhost**: Production bundle không chứa bất kỳ chuỗi `localhost` hoặc `127.0.0.1` nào.
- [x] **Production Endpoints**: Trỏ chính xác về API `https://p004-api.duckdns.org` và Web App `https://www.c3-app-004.io.vn`.
- [x] **No Secret Leaks**: Không chứa API key (OpenAI/Gemini), AWS secret hay Private Key trong mã nguồn client.
- [x] **No Modulepreload Bug**: Các file HTML không chứa `<link rel="modulepreload">` tránh lỗi cross-world mismatch của Chrome.
- [x] **Icons**: Đầy đủ bộ icon chuẩn trong `.output/chrome-mv3/icon/`:
  - `icon/16.png` (16x16 px)
  - `icon/48.png` (48x48 px)
  - `icon/128.png` (128x128 px)
- [ ] **Store Listing & Assets** (Chuẩn bị thủ công trên Console):
  - Screenshot giao diện (1280x800 hoặc 640x400 px).
  - Promo banner (440x280 px).
  - Mô tả chi tiết (Description) và Privacy Policy URL.

---

## 3. Permission Justifications (Bản giải trình quyền hạn gửi Google Review)

Khi submit lên Chrome Web Store, Google yêu cầu giải trình lý do sử dụng từng permission (Single Purpose Policy). Dưới đây là các đoạn văn mẫu tiếng Anh chuẩn xác, ngắn gọn theo đúng chức năng thực tế của mã nguồn:

### `storage`
> "Used to store user preferences locally (theme, font size, contrast modes, reminder settings) and securely cache authenticated session tokens and unread task counts in the browser."

### `notifications`
> "Used to display native browser notifications to alert users about upcoming task deadlines, urgent reminders, and automated scheduled task bundles."

### `alarms`
> "Used to schedule periodic background checks at user-configured intervals to query pending task reminders and sync notification states without consuming excess system resources."

### `scripting`
> "Required to extract text and tasks from the user's active browser tab only when the user explicitly clicks the 'Extract data' button, and to synchronize login session status from the official companion web application."

### `tabs`
> "Used to obtain the URL and title of the active tab during user-initiated task extraction to attach source backlinks to created tasks, and to open or focus the mondaiy web application when interacting with notifications."

### `tabCapture`
> "Required to capture audio streams from the active tab strictly when the user manually initiates a meeting recording session from the extension interface."

### `offscreen`
> "Required under Manifest V3 architecture to create an offscreen document that hosts the MediaRecorder API for audio recording, as MV3 background service workers do not support DOM or MediaRecorder APIs."

### `sidePanel`
> "Serves as the primary extension interface, allowing users to view, manage, and extract tasks seamlessly alongside their active browsing workflow."

### Host Permissions: `<all_urls>`
> "Allows the extension's user-initiated content extraction script to operate across various websites (e.g., chat applications, webmail, docs) where work tasks originate, and enables authentication synchronization from the companion web app origin."

---

## 4. Data Handling & Privacy Audit (Kiểm toán thu thập dữ liệu)

Báo cáo kiểm toán luồng dữ liệu dựa trên mã nguồn thực tế:

| Hạng mục | Dữ liệu thực tế | Chi tiết & Mục đích |
| :--- | :--- | :--- |
| **Dữ liệu đọc tại trình duyệt** | Tiêu đề & URL tab active | Đính kèm link nguồn gốc vào phiếu giao việc (`readActiveTab`). |
| | Nội dung chữ trên trang | Chỉ đọc khi người dùng bấm "Lấy dữ liệu" hoặc bôi đen văn bản; tự động che số thẻ/tài khoản và token JWT (`redactSensitive`). |
| | Session Token đăng nhập | Đọc từ `localStorage` của web app `https://www.c3-app-004.io.vn` để xác thực người dùng. |
| | Tab Audio Stream | Chỉ capture âm thanh khi người dùng chủ động bấm bắt đầu ghi âm cuộc họp. |
| **Dữ liệu gửi lên server** | Văn bản trích xuất | Gửi lên `https://p004-api.duckdns.org/api/v1/tasks/summarize-page-extraction` để AI bóc tách công việc. |
| | Thông tin phiếu giao việc | Gửi lên `POST /api/v1/tasks/from-suggestion` khi người dùng bấm "Lưu". |
| | Audio Chunks | Gửi lên API xử lý âm thanh khi sử dụng tính năng ghi âm. |
| **Lưu trữ cục bộ (`chrome.storage.local`)** | Cài đặt & Trạng thái | Lưu cấu hình giao diện (theme, palette, textSize, highContrast, autoOpenReminderPopup) và bộ đếm task chờ duyệt. |
| **Bảo mật & AI** | Không chia sẻ bên thứ ba | Không sử dụng SDK theo dõi, không gửi dữ liệu cho bên thứ ba; dữ liệu gửi lên backend AI được gán theo User ID của người dùng. |

---

## 5. File ZIP Release & Hướng dẫn Upload

* **Đường dẫn file ZIP release**:
  ```text
  C:\Users\THIS PC\Desktop\IT\AI THUC CHIEN\P-004\client\extension\.output\mondaiy-extension-0.1.1-chrome.zip
  ```
* **Các bước upload lên Chrome Web Store**:
  1. Truy cập [Chrome Web Store Developer Console](https://chrome.google.com/webstore/devconsole).
  2. Bấm **New Item** (hoặc chọn item **mondaiy** nếu đã tạo).
  3. Upload file `mondaiy-extension-0.1.1-chrome.zip`.
  4. Điền các mục giải trình quyền hạn từ Mục 3 ở trên vào tab **Privacy practices**.
  5. Bấm **Submit for review**.
