# ADR-019 — Task là một phiếu giao việc, không phải một dòng to-do

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Accepted — Thái chốt hình dạng và hai mục mở ngày 2026-08-26 |
| Owner đề xuất | Technical Lead + AI Lead |
| Author | Tatejo, theo yêu cầu của Thái Hoài An (26/08) |
| Last updated | 2026-08-26 |
| Related | [ADR-018 planner xác định](adr-018-planner-xac-dinh-cho-phan-ra-va-uu-tien-viec.md) · [ADR-007 lớp nhắc việc](adr-007-lich-tuong-tac-truc-tiep-va-lop-nhac-viec.md) · [PRD](../../product/prd.md) |

## Bối cảnh

Thái yêu cầu một task phải mang đủ: tiêu đề, mô tả chi tiết, đầu ra kỳ vọng và
tiêu chí nghiệm thu, bối cảnh/đầu vào, ràng buộc, phần thực thi (các bước, công
cụ, cách làm đề xuất), ưu tiên, hạn chót, người chịu trách nhiệm và các bên liên
quan, và nơi bàn giao khi xong.

Điều bất ngờ khi đo: **phần lớn những trường đó đã được trích ra rồi, rồi bị vứt
đi trước khi lưu.**

`PageExtractionSuggestionItem` (`src/models/schemas.py`) đã có đủ
`expected_output`, `constraint`, `execution_steps`, `execution_tool`,
`execution_method`, `priority`, `assignee`, `stakeholders`, `deliver_to`.
Docstring của chính nó ghi rõ vì sao chúng không sống sót:

> *"lúc lưu thật, client tự gộp lại vào `detail` … vì bảng Task dùng chung nhiều
> pipeline khác không có cột riêng cho các field này"*

Và `TaskFromSuggestionRequest` — schema mà endpoint `POST /tasks/from-suggestion`
thực sự nhận — chỉ có **bốn** trường: `title`, `detail`, `due_at`, `all_day`.

Nên đây không phải việc "thêm tính năng trích xuất". Việc trích xuất đã chạy.
Đây là việc **thôi làm bẹp kết quả của nó**.

## Vấn đề với hiện trạng

- **Mất cấu trúc không hồi lại được.** Bảy nhóm trường bị ép thành một chuỗi
  `detail`. Không parse ngược ra được, nên planner, xếp ưu tiên và bàn giao đều
  không dùng lại được.
- **Chặn ADR-018.** Planner cần biết "xong nghĩa là gì" để xếp thứ tự và ước
  lượng. Tiêu chí nghiệm thu nằm trong một khối text tự do thì không dùng được.
- **Mất dữ liệu ngay lúc này.** Mỗi lần extension lưu một task là một lần bẹp.
  Khác với `actual_minutes` (chỉ mất khi có người tick xong, prod mới có 6 task
  hoàn tất), cái này mất theo mỗi lần tạo task.

## Quyết định

### QĐ-1 · Các trường thành cột thật, không nhét vào một khối JSON

Thêm vào bảng `tasks`, tất cả nullable, không phá dữ liệu cũ:

| Cột | Kiểu | Ý nghĩa |
| --- | --- | --- |
| `expected_output` | `Text NULL` | Sản phẩm bàn giao là cái gì |
| `acceptance_criteria` | `Text NULL` | Căn cứ để nói là đạt |
| `context_input` | `Text NULL` | Bối cảnh, đầu vào cần có trước khi làm |
| `constraints` | `Text NULL` | Những thứ không được làm |
| `execution_tool` | `Text NULL` | Công cụ dự kiến dùng |
| `execution_method` | `Text NULL` | Cách làm đề xuất |
| `stated_priority` | `String(32) NULL` | Mức ưu tiên **do nguồn nói ra** |
| `stakeholders` | `JSON default list` | Danh sách phẳng các bên liên quan |
| `deliver_to` | `Text NULL` | Xong thì bàn giao cho ai / nhóm nào |

Chọn cột thật thay vì một khối JSON vì planner sẽ **truy vấn** `acceptance_criteria`
và `stated_priority`, còn `deliver_to` sẽ là đầu vào của tính năng gửi ở scope sau.
Chôn chúng trong JSON là lặp lại đúng lỗi bẹp-vào-`detail`, chỉ ở một định dạng
gọn hơn.

**Tên `constraints` số nhiều là cố ý:** `CONSTRAINT` là từ khoá dành riêng của
SQL, đặt cột tên `constraint` là phải quote ở mọi nơi dùng.

### QĐ-2 · Các bước thực thi dùng bảng `task_steps` đã có

ADR-018 slice 0 đã tạo `task_steps` (task_id, order_index, title, estimate_min,
done_at). Đó chính là "instruction băm ra thành các bước". **Không** thêm một
cột `execution_steps` JSON song song — một khái niệm một nơi.

### QĐ-3 · `stated_priority` khác với ưu tiên do planner tính

Hai thứ dễ nhầm, và nhầm là hỏng:

- `stated_priority` — **nguồn nói gì**. Email ghi "gấp", Jira đặt P1. Là dữ kiện
  quan sát được, không phải phán quyết.
- Điểm ưu tiên của planner — **hệ quyết gì**, theo ADR-018 QĐ-2 (Eisenhower ở mặt
  người dùng, WSJF bên trong), tính từ `due_at`, `signal_strength`, `source_count`,
  liên kết project, và **có** `stated_priority` làm một tín hiệu đầu vào.

Không ghi đè cái này lên cái kia. Người gửi mail nói "gấp" không tự động biến nó
thành việc quan trọng nhất trong ngày của người nhận.

### QĐ-4 · RACI phẳng, không bốn vai

Chỉ `assignee` (đã có) cộng `stakeholders` là một danh sách phẳng. Thái chốt
26/08: bốn vai R/A/C/I tách biệt đúng chuẩn hơn nhưng nặng cho người dùng cá
nhân, và không ai điền đủ.

### QĐ-5 · `deliver_to` chỉ ghi lại, chưa gửi

Ở scope này Mondaiy **chỉ lưu text** người dùng hoặc bộ trích xuất ghi vào. Việc
thật sự gửi khi task hoàn tất (Discord, Telegram, email) là **scope sau**.

Lý do tách: gửi ra ngoài là biên rủi ro riêng — cần chọn kênh, chống gửi trùng,
chống gửi nhầm nhóm, và một đường để người dùng duyệt trước. Nhét nó vào cùng
lượt đổi schema là gộp hai loại rủi ro khác nhau.

### QĐ-6 · Mở đường ở API, không chỉ ở bảng

Thêm cột mà không sửa `TaskFromSuggestionRequest` thì dữ liệu vẫn bị vứt ở tầng
API. Phải làm cả ba:

1. `TaskFromSuggestionRequest` nhận đủ các trường mới (đều optional).
2. `POST /tasks/from-suggestion` ghi chúng xuống thay vì bỏ.
3. Client thôi gộp vào `detail`; `detail` trở lại đúng nghĩa "mô tả chi tiết".

Bước 3 là chỗ dễ quên nhất và cũng là chỗ quyết định ADR này có hiệu lực hay không.

## Cái đã cân nhắc và loại

**Một cột JSON `brief` chứa tất cả** — loại theo QĐ-1: planner cần truy vấn.

**Bốn vai RACI đầy đủ** — loại theo QĐ-4.

**Bảng `task_briefs` riêng, quan hệ 1-1 với `tasks`** — loại: quan hệ 1-1 chỉ để
gom cột là thêm một `JOIN` vào mọi truy vấn mà không đổi được gì về ngữ nghĩa.

**Gửi luôn khi hoàn tất** — loại theo QĐ-5, tách scope.

## Hệ quả

**Tích cực**

- Bộ trích xuất đang chạy sẵn bỗng có giá trị: kết quả của nó tồn tại được.
- Gỡ chặn cho planner ADR-018 slice 1 — có `acceptance_criteria` và
  `stated_priority` thật để xếp hạng.
- `detail` trở lại đúng nghĩa, thôi làm nơi chứa tạp.

**Tiêu cực và rủi ro**

- `tasks` rộng thêm 9 cột. Chấp nhận: đều nullable, và một phiếu giao việc vốn
  có nhiều mặt.
- Task cũ có các trường này nằm lẫn trong `detail` sẽ **không** được tách ngược.
  Không cố parse text tự do — đoán sai còn tệ hơn để trống. Task cũ giữ nguyên
  `detail`, các cột mới để `NULL`.
- Nhiều ô trống hơn trên giao diện. UI phải ẩn ô rỗng thay vì phơi một biểu mẫu
  chín dòng trống.

## Nghiệm thu

- Migration Alembic theo khuôn ADR-018: chỉ thêm cột nullable, `downgrade` đảo
  ngược được, test round-trip.
- Test chứng minh `POST /tasks/from-suggestion` **giữ** đủ các trường mới —
  gửi lên rồi đọc ra phải bằng nhau, không rơi trường nào.
- Test chứng minh task cũ (các cột mới `NULL`) vẫn đọc và hiển thị bình thường.
- Test chứng minh `stated_priority` **không** ghi đè điểm ưu tiên của planner.

## Việc kéo theo, không thuộc ADR này

- Bộ trích xuất điền các cột mới ở những đường khác ngoài extension (Gmail,
  Discord, Jira) — mỗi nguồn một lượt.
- Tính năng gửi khi hoàn tất (QĐ-5).
- `actual_minutes` — ADR-018 QĐ-5, vẫn chưa có logic ghi.
