# ADR-002 — P0 dùng connector chỉ đọc, không theo dõi màn hình

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Approved |
| Owner | Thái Hoài An (PM) + Nguyễn Văn Phong (Technical Lead) |
| Author | Thái Hoài An (PM) |
| Reviewers | UI/UX Lead, PO/QC |
| Last updated | 2026-08-11 |
| Related | [One-page brief](../../product/one-page-brief.md) · [PRD](../../product/prd.md) · [Architecture](../architecture.md) · [ADR-001](adr-001-platform-core-program-navigator-vertical.md) |

## Bối cảnh

Phạm vi cũ gồm thu thập DOM trên web và nhập transcript cuộc họp. Hai năng lực
này mở rộng ranh giới riêng tư, tăng khối lượng kỹ thuật và không cần thiết để
kiểm chứng năm trường hợp sử dụng của mondaiy trong sáu tuần.

## Quyết định

1. P0 chỉ tự động đọc dữ liệu người dùng chủ động kết nối từ Calendar, Jira,
   Discord, VLearn và Gmail; pilot có thể giới hạn còn các connector đạt gate.
2. P0 không theo dõi màn hình, lịch sử duyệt web, nội dung trang web tùy ý,
   cookie đăng nhập hoặc nội dung cuộc họp.
3. Extension, nếu được giữ, chỉ là bề mặt thao tác và hiển thị trạng thái; không
   tự thu thập nội dung trang đang mở.
4. Mỗi source item giữ mã nguồn, deep link, thời điểm cập nhật, phiên bản và
   quyền truy cập. Connector lỗi phải hiển thị trạng thái chưa đầy đủ.
5. Lệnh tạo tường minh chỉ dựng proposal. Hành động ghi chỉ được thực thi sau
   khi người dùng xem preview và bấm Chấp nhận; trường bắt buộc còn thiếu phải
   thành draft clarification, không được tự đoán.
6. Ngoại lệ ghi gồm tạo Calendar event từ task đã Confirm + Sync và tool hội
   thoại giới hạn để tạo mới event/task/todo. Tool hội thoại kiểm tra lại user
   scope, intent hiện tại hoặc draft ngay trước đó; Calendar dùng event ID xác
   định để retry cùng lượt không tạo trùng. Sửa/xóa vẫn ngoài phạm vi.

Quyết định này thay thế phần P0 về browser capture, transcript import và Vexa
trong ADR-001. Hướng sản phẩm hai lớp của ADR-001 vẫn giữ nguyên.

## Hệ quả

- Giảm rủi ro riêng tư và bỏ đường găng Chrome MV3/Vexa khỏi sáu tuần.
- Có thể tập trung vào giá trị tổng hợp việc, phát hiện thay đổi, hỏi có nguồn
  và tỷ lệ hoàn thành công việc trong tuần.
- Chất lượng P0 phụ thuộc vào API, OAuth và quyền đọc của từng nguồn.
- Generic web capture và meeting transcript chỉ được xem lại sau pilot bằng ADR
  mới, không tự động trở lại backlog P0.
