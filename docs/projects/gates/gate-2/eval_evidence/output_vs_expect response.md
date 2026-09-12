# LangSmith — 10 Traces Gần Nhất

**Project:** `p004-production`  
**Nguồn:** `eval/langsmith_export/recent_10_traces.json`  
**Số trace:** 10  

## Bảng tổng hợp

| # | Trace ID | Câu hỏi / input chính | Expected output  | Output thật | Đánh giá |
|---:|---|---|---|---|---|
| 1 | `01a00474-8acd-7e11-b30a-79d99454c617` | “Nhắc tôi tối T7 báo cáo với mentor về dự án lúc 20h” | Tạo task draft **“Báo cáo với mentor về dự án”**, đặt hạn vào **thứ Bảy lúc 20:00**. Vì chưa có thời gian kết thúc nên **chưa ghi Calendar event** và hỏi thêm thời gian kết thúc. Phản hồi cuối phải xác nhận draft đã được tạo. | Hệ thống đã tạo draft “Báo cáo với mentor về dự án”, due lúc 20h T7 và yêu cầu bổ sung thời gian kết thúc; nhưng field `response` lại ghi “Mình chưa tạo vì lượt hiện tại không có yêu cầu ghi rõ ràng”. | **Fail / inconsistent** — `analysis` đúng hướng nhưng `response` mâu thuẫn. |
| 2 | `01a00474-41b9-7503-ba09-b8df0bb70161` | “Tạo công việc quan trọng cho tôi vào lịch” | Hỏi thêm **tiêu đề công việc** và **thời gian/hạn chót cụ thể** trước khi tạo task hoặc Calendar event; không tự suy đoán thông tin còn thiếu. | “Mình cần thêm thông tin về công việc bạn muốn tạo. Bạn có thể cho mình biết cụ thể công việc đó là gì và thời gian bạn muốn đặt vào lịch không?” | **Pass** |
| 3 | `01a00473-daa7-7e52-90ef-08509f5367c5` | Yêu cầu tóm tắt các email/Jira evidence trong 3–5 câu. | Tóm tắt trong **3–5 câu**, chỉ sử dụng evidence được cung cấp, không suy đoán; nêu các ticket, CI/deployment, pull request và yêu cầu phản hồi nếu có trong evidence. | Tóm tắt 4 câu về JIRA TAPB-159/TAPB-84, CI/deployment, pull request, GitHub và yêu cầu phản hồi. | **Pass theo prompt contract** |
| 4 | `01a00472-d065-78c1-bd86-7dcfe0d6f312` | Pipeline `summary`, Gmail INBOX, 01–15/08/2026. | Chạy pipeline `summary` cho Gmail INBOX trong khoảng **01–15/08/2026**, trả về thống kê số item được filter, số item bị reject và số task đã persist. Nếu không có task hợp lệ, ghi rõ **0 tasks persisted**. | Pipeline hoàn tất với **34 filtered**, **46 rejected**, **0 tasks persisted**. | **Pass theo observed behavior** |
| 5 | `01a0038a-3aa8-7281-9a27-87af7dabb289` | Pipeline `task_extraction`, 10 Gmail sources. | Chạy `task_extraction` trên 10 Gmail sources. Nếu Google connection thiếu refresh token, trả về lỗi xác thực rõ ràng, đánh dấu pipeline bị chặn, không tạo batches/clusters/tasks và không báo thành công giả. | Fetch thất bại ở các source do Google connection không có refresh token; không tạo được batches/clusters. | **Pass theo expected error handling** |
| 6 | `01a0038a-340d-7870-89d7-584df3c1501d` | Pipeline `task_extraction`, Gmail INBOX. | Chạy `task_extraction` trên Gmail INBOX, lọc email hợp lệ, trích xuất và resolve task, sau đó persist các task đủ điều kiện; trả về thống kê pipeline và số task đã lưu. | **1 filtered**, **0 rejected**, **1 task persisted**. | **Pass theo observed behavior** |
| 7 | `01a0038a-31c8-7190-99fd-01694a9d585d` | Pipeline `task_extraction`, connection `999999`. | Khi connection ID `999999` không tồn tại, trả về lỗi cho biết không tìm thấy connection của user. Pipeline phải dừng an toàn, không tạo filtered items, extracted tasks hoặc persisted tasks. | Fetch lỗi: không tìm thấy connection `999999` của user; filtered/extracted/resolved đều rỗng. | **Pass — expected error path** |
| 8 | `01a0038a-30ca-7dc1-90ee-35da1dcc73d4` | Pipeline `task_extraction`, Gmail INBOX. | Nếu Google connection thiếu refresh token, báo pipeline bị chặn bởi lỗi xác thực; không tạo task hoặc dữ liệu đầu ra giả. | Fetch lỗi do Google connection không có refresh token; không có filtered item/task. | **Pass theo expected error handling** |
| 9 | `01a0038a-2b13-7181-a4fc-4c7e35e536f5` | Pipeline `task_extraction`, Gmail INBOX. | Phát hiện thiếu refresh token, trả về lỗi xác thực có nguyên nhân, không có filtered item và không persist task nào. | Fetch lỗi do Google connection không có refresh token; không có filtered item/task. | **Pass theo expected error handling** |
| 10 | `01a0038a-2a0c-7890-9cfb-c6be3a39298b` | Pipeline `task_extraction`, Gmail INBOX. | Báo lỗi Google connection thiếu refresh token, dừng pipeline an toàn và xác nhận không tạo task. | Fetch lỗi do Google connection không có refresh token; không có filtered item/task. | **Pass theo expected error handling** |

## Kết luận

- Có **3 trace tương tác/LLM** có thể lập expected output tương đối rõ từ query hoặc system prompt.
- Trace #2 và #3 đáp ứng expected inferred/prompt contract.
- Trace #1 có dấu hiệu **mâu thuẫn giữa `analysis` và `response`**: pipeline đã tạo draft nhưng câu trả lời cuối lại nói chưa tạo. Đây là lỗi cần ưu tiên sửa.
- Có **6 trace pipeline** không có user question và không có golden expected output trong LangSmith; expected output được bổ sung ở đây dưới dạng pipeline contract dựa trên input và kết quả thực tế.
- Trace #5, #8, #9, #10 bị chặn bởi thiếu Google refresh token; trace #7 kiểm tra đường lỗi connection không tồn tại.

## Expected output contract cho pipeline

Các pipeline nên trả về cấu trúc trạng thái tương đương:

```json
{
  "status": "completed | blocked | failed",
  "filtered_count": 0,
  "rejected_count": 0,
  "extracted_count": 0,
  "persisted_count": 0,
  "error": null
}
```

Khi có lỗi, trường `error` nên chứa loại lỗi, thông báo nguyên nhân và cho biết lỗi có thể khắc phục hay không. Khi pipeline bị block bởi lỗi kết nối, các count liên quan phải là `0` và phản hồi không được mô tả pipeline là thành công.

## Khuyến nghị cải tiến

1. Đồng bộ `response` cuối với tool result và trạng thái thực tế trong `analysis`.
2. Phân biệt rõ ba trạng thái: `completed`, `blocked` và `failed`.
3. Chuẩn hóa các count của pipeline: `filtered`, `rejected`, `extracted`, `resolved`, `persisted`.
4. Với task có thời gian bắt đầu nhưng thiếu thời gian kết thúc, tạo draft trước, không ghi Calendar event và hỏi bổ sung thời gian kết thúc.
5. Với lỗi refresh token hoặc connection không tồn tại, trả về lỗi có nguyên nhân cụ thể và không tạo dữ liệu giả.
