# Architecture Decision Records

Tạo ADR khi quyết định kỹ thuật khó đảo ngược hoặc ảnh hưởng từ hai thành phần
trở lên. Tên file: `adr-NNN-ten-quyet-dinh.md`.

Mỗi ADR cần có trạng thái, bối cảnh, lựa chọn, quyết định, hệ quả, owner, ngày
và các link PRD/Jira/PR liên quan. Không dùng ADR thay cho task kỹ thuật.

## Danh sách

- [ADR-001 — Personal Context Engine với Program Navigator là vertical đầu tiên](adr-001-platform-core-program-navigator-vertical.md)
- [ADR-002 — P0 dùng connector chỉ đọc, không theo dõi màn hình](adr-002-connector-first-p0-scope.md)
- [ADR-003 — Gmail và Discord đi trước trong hai tuần build](adr-003-gmail-va-discord-truoc-trong-hai-tuan-build.md) · `Proposed`
- [ADR-004 — Liên kết danh tính học viên bằng Discord OAuth, không bằng lời tự khai](adr-004-lien-ket-danh-tinh-qua-discord-oauth.md) · `Proposed`
- [ADR-005 — Routing LLM theo loại câu hỏi, capability và provider failover](adr-005-capability-aware-llm-routing.md) · `Proposed`
- [ADR-006 — pgvector cho lớp memory dài hạn, truy hồi lai chấm điểm trong tiến trình](adr-006-pgvector-cho-lop-memory-dai-han.md) · `Proposed`
- [ADR-007 — Lịch tương tác trực tiếp và lớp nhắc việc](adr-007-lich-tuong-tac-truc-tiep-va-lop-nhac-viec.md) · `Approved`
- [ADR-008 — Lịch chương trình nhập từ ICS feed, chỉ mở cho mức A](adr-008-lich-chuong-trinh-tu-ics-feed.md) · `Proposed`
- [ADR-009 — Đồng bộ lịch chương trình sang lịch cá nhân, bắt buộc qua duyệt](adr-009-dong-bo-lich-chuong-trinh-sang-lich-ca-nhan.md) · `Proposed`
- [ADR-010 — Trang quản trị lịch chương trình: sửa tay thắng feed, phát hành có bước duyệt](adr-010-trang-quan-tri-lich-chuong-trinh.md) · `Proposed`
- [ADR-011 — Tự động đồng bộ nền, lặp lại đúng bộ nguồn người dùng đã chọn](adr-011-tu-dong-dong-bo-nen-va-han-muc-nguon.md) · `Proposed`
- [ADR-012 — Telegram P0 cho tóm tắt và nhắc việc](adr-012-telegram-p0-cho-tom-tat-va-nhac-viec.md) · `Approved for P0 pilot`
- [ADR-013 — Outlook làm connector đọc email thứ hai, song song Gmail](adr-013-outlook-connector-doc-email.md) · `Approved`
