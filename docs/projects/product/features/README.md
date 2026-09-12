# Feature specifications

Thư mục này chứa đặc tả riêng cho feature khi một phần của
[PRD](../prd.md) đã lớn đến mức cần tách để design, engineering và QA cùng
review.

## Feature/use-case hiện có

- [AI Planning Workspace](planner-workspace.md) — PL-001, kế hoạch ngày/tuần có ràng buộc cá nhân
- [Web to action](web-to-action.md) — superseded, ngoài P0
- [Meeting to memory](meeting-to-memory.md) — superseded, ngoài P0

## Quy tắc

- PRD vẫn là nguồn chuẩn cho mục tiêu, phạm vi, priority và success metric.
- Tạo đặc tả mới bằng cách copy
  [Feature specification template](../../pm/templates/feature-specification.md);
  không sửa trực tiếp template.
- Mỗi file feature dùng tên `feature-id-ten-ngan.md` và phải link requirement
  ID trong PRD, UI/design, test evidence và Jira Epic/Story liên quan.
- Jira chỉ giữ trạng thái thực thi, assignee và sprint; không copy toàn bộ đặc
  tả vào description.
- Chỉ tạo file khi nội dung cần review độc lập. Feature nhỏ tiếp tục nằm trong
  PRD để tránh phân mảnh.
