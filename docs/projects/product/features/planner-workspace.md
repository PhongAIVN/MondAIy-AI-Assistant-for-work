# PL-001 — AI Planning Workspace

## Vấn đề và quyết định sản phẩm

Task list trả lời được “còn việc gì”, nhưng không trả lời được “làm việc nào,
vào lúc nào, hôm nay có còn đủ sức/chỗ hay không”. PL-001 biến task đã có
thành một **bản nháp kế hoạch ngày hoặc tuần**. Nó không phải một calendar tự
động: người dùng nắm quyền đặt ràng buộc và quyết định mọi hành động ra ngoài.

## Workday Contract

Người dùng tạo một hợp đồng thời gian cá nhân gồm: giờ bắt đầu/kết thúc ngày,
nghỉ trưa, và block bảo vệ (mặc định Happy Time 16:00–17:00). Scheduler không
được đặt task đè lên các block này. Nếu không còn chỗ, task được nêu là at-risk,
không bị giấu hoặc bị hứa sai.

## Cách “AI” làm việc

1. Lớp AI hiện hữu đọc title, mô tả, expected output, criteria, context,
   constraints, stakeholder và deliver-to để gợi ý bước chuẩn bị/thực hiện.
2. Lớp quyết định lịch là thuật toán xác định: WSJF/deadline, estimate lịch sử
   hoặc estimate trên task, energy deep/shallow, rồi mới tìm slot rảnh.
3. Mỗi block trả về lý do xếp; task chưa xếp có lý do at-risk. Vì vậy kết quả
   kiểm tra lại được, không phụ thuộc việc LLM “bịa” giờ.

## Trải nghiệm

- **Hôm nay:** time block, thời lượng, loại deep/shallow và “vì sao ở giờ này”.
- **Tuần này:** chạy cùng logic cho bảy ngày để lộ tải vượt quá năng lực.
- **Giao tiếp:** task có stakeholder/deliver-to được AI breakdown thành bước
  chuẩn bị/gửi/follow-up; phiên bản đầu hiển thị trong kế hoạch, không tự gửi.
- **Reality check:** panel at-risk nêu task chưa có chỗ thay vì ép lịch tối.
- **Chat-first:** người dùng có thể nói “lên kế hoạch tuần này” hoặc “đặt
  Happy Time 16:00--17:00”; agent gọi tool planner để tạo/cập nhật ngay bản
  nháp nội bộ. Mọi kết quả vẫn sửa được tại `/planner`.

## Ranh giới an toàn

`POST /planner/generate` chỉ sinh proposal; không tạo/sửa/xóa Google Calendar,
không gửi tin nhắn, không thay đổi deadline/task. Bất kỳ calendar handoff nào
vẫn phải đi qua luồng xác nhận hiện hữu.

## Success metrics cho pilot

- Plan acceptance: số người tạo plan và giữ ít nhất một block / số người mở planner.
- Protected-time integrity: block bị xếp chồng lên nghỉ trưa/Happy Time = 0.
- Capacity honesty: task chưa vừa lịch phải xuất hiện trong at-risk = 100% trên test fixture.
- Weekly on-time completion: dùng công thức chuẩn trong PRD; so trước/sau pilot,
  không tự gán một ngưỡng khi chưa có baseline.
