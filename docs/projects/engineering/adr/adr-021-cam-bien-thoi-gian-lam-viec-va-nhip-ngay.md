# ADR-021 — Cảm biến thời gian làm việc, và ranh giới của việc học thói quen

| Thuộc tính | Giá trị |
| --- | --- |
| Status | **Proposed — chờ Thái chốt phần QĐ.** Phần chẩn đoán đã đo trên production |
| Owner đề xuất | Tatejo |
| Author | Tatejo, theo yêu cầu của Thái Hoài An (27/08) |
| Last updated | 2026-08-27 |
| Related | [ADR-017 học thích ứng P1](adr-017-adaptive-learning-p1-hermes.md) · [ADR-018 planner xác định](adr-018-planner-xac-dinh-cho-phan-ra-va-uu-tien-viec.md) · `src/services/planner/schedule.py` |

## Bối cảnh

Thái hỏi lịch trong ngày có tự học theo thói quen được không. Tôi đo, báo rằng
9/14 task hoàn thành vào 0h–1h sáng, và nêu đó là tín hiệu về nhịp làm việc.

**Thái bác lại, và đúng:**

> "người dùng làm xong task sẽ không vào ngay để tick mà lúc họ xong hết hoặc
> kết thúc buổi làm mới review lại rồi tick"

Nghĩa là cụm 0h–1h nhiều khả năng là **giờ ngồi tick lại cả buổi**, không phải
giờ làm việc. Tôi có ghi chú giới hạn đó trong báo cáo, nhưng vẫn suýt để một
tín hiệu sai dẫn hướng thiết kế.

Đây không phải lỗi thuật toán. **Đó là lỗi cảm biến** — và không thuật toán nào
sửa được một cảm biến đo nhầm thứ.

## Điều đã đo được trên production

| | |
|---|---|
| task có `actual_minutes` | **0** |
| task có ước lượng lưu sẵn | **0** |
| task có `energy` | **0** / 283 |
| task đã hoàn thành | 17 |
| `started_at` hoặc trạng thái "đang làm" | **không tồn tại** |

Hệ chỉ biết **task tồn tại** và **task xong**. Nó không biết gì về khoảng giữa —
đúng khoảng chứa toàn bộ thông tin về thói quen làm việc.

Hệ quả tức thời cho `schedule.py` vừa lên production: `estimate_minutes` trả
`None` cho mọi task, nên mọi việc đều nhận 30 phút mặc định, và vì 30 < 45 nên
**mọi việc đều bị phân loại `shallow`**. Khung làm việc sâu buổi sáng hiện không
bao giờ được dùng đúng mục đích.

Bộ máy học **đã có sẵn** và đúng thiết kế (`estimate.py`, reference-class
forecasting theo ADR-018). Nó chỉ không có gì để học.

## Điều đã có, không cần dựng lại

`client/extension` đã khai đủ quyền cần thiết: `alarms`, `notifications`,
`tabs`, `scripting`, `offscreen`. Background script đã chạy alarm định kỳ và đã
dựng notification **có nút bấm** (`chrome.notifications.onButtonClicked`).

`src/services/learning.py` (ADR-017) đã có consent, audit log, review candidate,
và quyền xoá theo scope. Docstring ghi rõ Slice 1 dừng ở nền tảng lưu trữ và
điều khiển của user; chưa có worker học.

Nghĩa là **khung pháp lý và nút điều khiển của người dùng đã xong**. Thiếu đúng
hai thứ: một cảm biến đúng, và một worker biết đọc nó.

## Quyết định cần Thái chốt

### QĐ-1 · Cảm biến: hỏi đúng lúc, thay vì suy từ lúc tick

Thái đề xuất: tự ước lượng, rồi popup trên extension hỏi đã xong chưa.

Cụ thể hoá: khi một task được xếp vào lịch, extension đặt alarm ở mốc kết thúc
dự kiến rồi hỏi **"xong chưa / còn bao lâu / chưa bắt đầu"**. Ba câu trả lời đó
cho ra thứ mà `completed_at` không bao giờ cho được:

- `actual_minutes` thật, ghi tại thời điểm gần với sự việc, không phải nhớ lại.
- Mốc **bắt đầu** thật, khi người dùng nói "đang làm".
- Tín hiệu **ước lượng lệch bao nhiêu**, cái mà reference class cần để học.

Cần thêm `Task.started_at` và một trạng thái "đang làm". Hôm nay hệ không có
khái niệm đó.

**Ranh giới tôi đề nghị:** hỏi ít, bỏ qua được, và **không bao giờ hỏi lại quá
một lần cho cùng một task**. Một cảm biến làm phiền sẽ bị tắt, và cảm biến bị
tắt thì đo được số không — tệ hơn cảm biến kém.

### QĐ-2 · Học nhịp ngày, nhưng học từ đâu

Sau khi có QĐ-1, nhịp ngày học từ **mốc bắt đầu/kết thúc đã xác nhận**, không
phải từ `completed_at`.

Nhịp cứng trong `config.py` (08:00 · 12:00 · 13:30 · 18:00 · 19:30 · 22:00) trở
thành **giá trị khởi đầu**, không phải chân lý — và phải nói rõ với người dùng
đây là mặc định chưa cá nhân hoá.

Ngưỡng học cần thận trọng: `estimate.py` đòi ≥5 mẫu tương tự trước khi tin. Nhịp
ngày nên có ngưỡng riêng và cao hơn, vì một tuần bất thường không phải một thói
quen.

### QĐ-3 · Học thói quen KHÔNG có nghĩa là chiều theo thói quen

Thái nói rõ:

> "tuy người dùng có thói quen thức khuya làm task nhưng cần học để hiểu và biết
> điều đúng đắn để nhắc nhở người dùng cải thiện giấc ngủ"

Đây là quyết định sản phẩm quan trọng nhất trong ADR này, và nó đi ngược mặc
định của phần lớn hệ gợi ý: **mô hình hoá hành vi để phục vụ, không phải để
củng cố.**

Cụ thể: nếu học được rằng người dùng thường làm việc tới 1h sáng, hệ **không**
tự dời khung làm việc tới 1h sáng. Nó ghi nhận thực tế đó để xếp lịch cho đúng,
đồng thời **giữ một ngưỡng lành mạnh** và nhắc khi vượt.

Ba ranh giới tôi đề nghị, vì đây là nhắc nhở chạm tới sức khoẻ:

1. **Dựa trên dữ liệu của chính họ, không phải lời khuyên chung chung.**
   "Ba tối liên tiếp bạn làm sau 0h" nói được. "Ngủ đủ 8 tiếng" thì không —
   ta không đo được giấc ngủ của họ.
2. **Nhắc một lần, không lặp.** Nhắc đi nhắc lại về sức khoẻ là dạy đời, và nó
   làm người dùng tắt cả tính năng.
3. **Tắt được, và tắt là tắt hẳn.** Đi qua consent của ADR-017 như mọi dữ liệu
   hành vi khác.

Tôi cố ý KHÔNG tự quyết mục này. Ranh giới giữa "nhắc hữu ích" và "dạy đời" là
phán đoán sản phẩm, và nó thuộc về Thái.

### QĐ-4 · Không dựng hệ thống học thứ hai

Mọi dữ liệu hành vi ở đây đi qua `src/services/learning.py` đã có: consent,
audit, quyền xoá theo scope. Dựng một đường riêng cho dữ liệu thời gian làm việc
là tạo ra một kho dữ liệu cá nhân thứ hai mà nút xoá của người dùng không với tới.

## Thứ tự triển khai đề nghị

1. **Cảm biến trước.** `Task.started_at`, trạng thái "đang làm", và vòng hỏi
   trên extension. Không có bước này thì mọi bước sau là suy đoán.
2. **Thu dữ liệu trong im lặng.** Vài tuần. Không đổi hành vi xếp lịch.
3. **Học ước lượng.** `estimate.py` đã sẵn sàng; nó chỉ cần dữ liệu.
4. **Học nhịp ngày.** Ngưỡng riêng, cao hơn.
5. **Nhắc nghỉ.** Sau cùng, và chỉ sau khi QĐ-3 được chốt.

Đảo thứ tự này — ví dụ học nhịp ngày trước khi có cảm biến đúng — sẽ cho ra một
hệ thống tự tin về một thứ nó đo sai. Đó chính là điều suýt xảy ra hôm nay.

## Hệ quả nếu không làm

`schedule.py` vừa lên production sẽ tiếp tục gán 30 phút cho mọi việc và coi mọi
việc là `shallow`. Lịch vẫn chạy, vẫn trông hợp lý, và vẫn sai — đúng loại hỏng
khó phát hiện nhất.
