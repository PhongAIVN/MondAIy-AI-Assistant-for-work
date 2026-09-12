# Gate 1 — Problem & design baseline

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Ready to submit |
| Owner | Thái Hoài An (PM) |
| Deadline | 2026-08-02 23:59 ICT |
| Nộp lại | 2026-08-04 — viết lại phần văn bản bị đánh giá là do AI sinh, bỏ chỉ số không có cơ sở |
| Git baseline | Tag [`p004-gate-1r2`](https://github.com/AI20K-Build-Phase-Cohort-3/P-004/tree/p004-gate-1r2) |
| Verdict | Lần nộp 2 bị từ chối vì văn bản mẫu do AI sinh; lần 3 đã sửa, chờ đánh giá lại |

Gate 1 chốt bài toán, phạm vi MVP và thiết kế trước khi build.

Ba file `01`–`03` trong thư mục này là **bản đóng băng** tại thời điểm nộp, dùng
để chấm. Bản sống tiếp tục được cập nhật ở `product/` và `design/`; cột Bản sống
bên dưới trỏ tới đó.

## Deliverable

| # | Deliverable | Bản nộp (đóng băng) | Bản sống | Review |
| --- | --- | --- | --- | --- |
| 1 | Brief | [01-brief.md](01-brief.md) | [one-page-brief.md](../../product/one-page-brief.md) | In review |
| 2 | PRD | [02-prd.md](02-prd.md) | [prd.md](../../product/prd.md) | In review |
| 3 | Wireframe / UI flow | [03-wireframe-ui-flow.md](03-wireframe-ui-flow.md) · [Wireframe pack PDF, 22 trang](assets/mondaiy-ui-ux-wireframe-gate-1.pdf) · [Figma Viewer](https://www.figma.com/design/XlUjQ4lV6fY6ov3ZjJYZal/mondaiy-UI-UX?node-id=1-2&t=4RlYkOovbQ1wVNKc-1) | [wireframe-ui-flow.md](../../design/wireframe-ui-flow.md) | In review — còn OI-01, OI-02 |

## Tài liệu hỗ trợ

Không thuộc bộ deliverable bắt buộc, để nguyên ở thư mục sống, xem qua Git tag
nếu cần đúng bản tại thời điểm nộp:

| Nhóm | Tài liệu |
| --- | --- |
| Quyết định | [ADR-001 platform core](../../engineering/adr/adr-001-platform-core-program-navigator-vertical.md) · [ADR-002 connector-first P0](../../engineering/adr/adr-002-connector-first-p0-scope.md) |
| Kỹ thuật | [Architecture](../../engineering/architecture.md) · [Memory lifecycle](../../engineering/memory-lifecycle.md) · [Repository setup](../../engineering/repository-setup.md) |
| Sản phẩm | [User story map](../../product/user-story-map.md) · [Roadmap 6 tuần](../../product/roadmap-6-weeks.md) · [Pilot plan](../../product/pilot-plan.md) |
| Chất lượng | [Evaluation plan](../../qa/evaluation-plan.md) |
| AI | [AI usage log](../../engineering/ai-usage-log.md) |

## Quyết định đã chốt

- mondaiy là product direction; Personal Context Engine là reusable core;
  Program Navigator là first vertical.
- P0 dùng connector chỉ đọc cho Calendar, Jira, Discord, VLearn và Gmail; pilot
  chỉ bật các connector đạt gate.
- P0 không theo dõi màn hình, lịch sử duyệt web, nội dung trang web bất kỳ,
  cookie đăng nhập hoặc nội dung cuộc họp. Extension chỉ hiển thị trạng thái và
  thao tác. Việc có mở lại web capture hay không là
  [OD-07](../../product/prd.md#19-quyết-định-còn-mở), quyết sau pilot bằng ADR mới.
- Postgres là canonical evidence/memory store. Mọi factual item/answer có
  citation; inferred preference không được trình bày như confirmed fact.
- Reminder/calendar action luôn qua preview, edit và confirm. Calendar
  template/`.ics` là P0; OAuth/direct write là P1.
- Chỉ số quan trọng nhất là tỷ lệ hoàn thành công việc trong tuần; thành công
  khi tỷ lệ này tăng so với baseline trước pilot.
- Nguồn chuẩn cho UI flow P0 là [wireframe-ui-flow.md](../../design/wireframe-ui-flow.md).
  [ui-flow.md](../../design/ui-flow.md) bản Chrome side panel đã chuyển sang ghi
  chép lịch sử, không còn là nguồn chuẩn.

## Kiểm tra trước khi nộp

- [x] Ba deliverable Brief, PRD, Wireframe đã có bản đóng băng trong thư mục này.
- [x] Wireframe đóng handoff checklist 14/17; 3 mục còn lại có DRI và hạn.
- [x] 22 màn Figma gộp thành một PDF 22 trang để review một lần mở.
- [x] Relative links hoạt động; không có secret, PII hoặc raw transcript.
- [x] OD-01–07 đã có DRI và là quyết định trước pilot, không chặn Gate 1.
- [x] Commit dùng để nộp đã qua `git diff --check`, lint và production build.
- [ ] Đã xác nhận evaluator có quyền đọc GitHub; repo trả `404` khi mở ẩn danh.

## Open item còn lại

| ID | Vấn đề | DRI | Hạn | Chặn Gate 1? |
| --- | --- | --- | --- | --- |
| OI-01 | Usability test 3–5 user chưa chạy, mới có kế hoạch | Lê Thị Yến Nhi (UI/UX Lead) | 2026-08-13 | Không. Chặn Gate 2 |
| OI-02 | Chưa xác minh link Figma mở được ở chế độ Viewer bằng cửa sổ ẩn danh | Lê Thị Yến Nhi (UI/UX Lead) | 2026-08-05 | Không — PDF 22 trang đã có trong repo. Phải đóng trước buổi review |

Chi tiết tại [mục 24 của wireframe](03-wireframe-ui-flow.md#24-việc-còn-mở-trước-khi-chuyển-approved).

## Evidence ngoài Git

| Hạng mục | Link / trạng thái |
| --- | --- |
| Jira board/sprint | [TAPB backlog](https://vinait004.atlassian.net/jira/software/projects/TAPB/boards/2/backlog?atlOrigin=eyJpIjoiMzY5ODc1NjNiNzkyNGI5OGJlYWE3MGE5NzFhNDhmMTMiLCJwIjoiaiJ9) |
| Git submission path | [`main/docs/projects/gates/gate-1`](https://github.com/AI20K-Build-Phase-Cohort-3/P-004/tree/main/docs/projects/gates/gate-1) |
| Figma | [mondaiy UI-UX](https://www.figma.com/design/XlUjQ4lV6fY6ov3ZjJYZal/mondaiy-UI-UX?node-id=1-2&t=4RlYkOovbQ1wVNKc-1) |
| Mentor approval/feedback | TBD |
| Submission receipt | TBD |

## Lịch sử nộp

| Lần | Tag | Thay đổi |
| --- | --- | --- |
| 1 — 2026-08-02 | [`p004-gate-1`](https://github.com/AI20K-Build-Phase-Cohort-3/P-004/tree/p004-gate-1) | Bản nộp đầu |
| 2 — 2026-08-04 | [`p004-gate-1r1`](https://github.com/AI20K-Build-Phase-Cohort-3/P-004/tree/p004-gate-1r1) | Đóng handoff checklist wireframe, chuẩn hoá header theo Documentation Guide, gộp 22 PDF thành một file, gọn cấu trúc gate còn README + 3 deliverable, đóng mâu thuẫn nguồn chuẩn UI flow |
| 3 — 2026-08-04 | [`p004-gate-1r2`](https://github.com/AI20K-Build-Phase-Cohort-3/P-004/tree/p004-gate-1r2) | Xử lý lý do bị từ chối ở lần 2. Bỏ trích dẫn người dùng không có thật; bỏ 9 ngưỡng chỉ số không có cơ sở, thay bằng cách báo cáo số tuyệt đối; bỏ hai nhóm người dùng chưa phỏng vấn; bỏ các đoạn văn quảng cáo; nói rõ nhóm đã kiểm chứng được gì và chưa kiểm chứng được gì; hợp nhất bản sống của wireframe về đúng bản tiếng Việt |

## Ghi chú kỹ thuật

- Web app lint đạt với một cảnh báo Fast Refresh không chặn build.
- Production build đạt; Vite cảnh báo main chunk khoảng 699 kB, không chặn Gate 1.
- `npm audit` còn advisory mức high của React Router liên quan RSC; prototype
  hiện là Vite SPA và không dùng RSC. Nhóm vẫn phải theo dõi bản vá upstream.
