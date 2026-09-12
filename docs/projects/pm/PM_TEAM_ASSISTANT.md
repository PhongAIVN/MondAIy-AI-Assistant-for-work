# Trợ lý PM — AI Program Navigator

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Approved |
| Owner | PM |
| Last updated | 2026-08-01 |
| Source of truth | Không — dùng [Project Management SSOT](../README.md) làm điểm vào |

Trợ lý PM biến thông tin rời rạc thành outcome, owner, deadline, evidence và
decision được lưu vết. Nó không tự thay thế quyết định của PM/Tech Lead, đóng
issue chưa hoàn tất hoặc ghi dữ liệu nhạy cảm vào tài liệu.

## Nhịp vận hành

- Mỗi ngày: assignee cập nhật Jira trước standup; blocker phải có owner.
- Thứ Ba: owner cập nhật trước 16:00; PM gửi weekly report trước 18:00.
- Thứ Tư: mentor meeting có agenda, evidence, decision và action cập nhật trong
  24 giờ.
- Cuối sprint: demo từ evidence thật, review gate và tạo action cho sprint sau.

## Cách dùng trợ lý PM

- Tổng hợp Sprint, việc trễ, blocker và issue thiếu owner từ Jira.
- Chuyển feedback/meeting thành proposed Jira issue, PRD/ADR change hoặc report.
- Rà Gate/Demo Day theo outcome, evidence và quality bar.
- Chuẩn bị báo cáo bằng các template trong `pm/templates/`.

Xem [Project Management SSOT](../README.md) để biết nơi cập nhật
canonical cho backlog, requirement, decision, bug và báo cáo.
