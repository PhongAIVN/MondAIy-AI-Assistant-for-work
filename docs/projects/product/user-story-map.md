# User story map — mondaiy

| Thuộc tính | Giá trị |
| --- | --- |
| Status | In review |
| Owner | Nguyễn Đức Dũng (PO/QC) |
| Reviewers | PM, UI/UX Lead, Technical Lead |
| Last updated | 2026-08-02 |
| Source of truth | Có — user outcome, priority và PRD traceability |
| Related | [PRD](prd.md) · [UI flow](../design/wireframe-ui-flow.md) · [Jira TAPB](https://vinait004.atlassian.net/jira/software/projects/TAPB/boards/2/backlog?atlOrigin=eyJpIjoiMzY5ODc1NjNiNzkyNGI5OGJlYWE3MGE5NzFhNDhmMTMiLCJwIjoiaiJ9) |

## Story map

| ID | Activity | Actor | User story | Priority | PRD trace |
| --- | --- | --- | --- | --- | --- |
| US-001 | Onboard | User | Tôi muốn khai báo vai trò, mục tiêu, múi giờ và cấp quyền theo nguồn để kiểm soát dữ liệu mondaiy được đọc. | P0 | [J1](prd.md#j1-bắt-đầu-sử-dụng-và-cấp-quyền), FR-001–004 |
| US-002 | Connect sources | User | Tôi muốn kết nối Calendar, Jira, Discord, VLearn hoặc Gmail ở chế độ chỉ đọc và thấy trạng thái đồng bộ. | P0 | [J2](prd.md#j2-đồng-bộ-nguồn), FR-010–015 |
| US-003 | Detect change | User | Tôi muốn item mới hoặc thay đổi được lưu theo phiên bản và chỉ rõ mâu thuẫn giữa các nguồn. | P0 | [J3](prd.md#j3-từ-thay-đổi-nguồn-đến-thông-tin-ghi-nhớ), FR-020–024 |
| US-004 | Remember safely | User | Tôi muốn xem, confirm, sửa hoặc reject memory candidate để inference không bị trình bày như sự thật. | P0 | [`8.4`](prd.md#84-memory-lifecycle), FR-030–035 |
| US-005 | Set program | Admin | Tôi muốn seed Program Frame, role, deliverable và source authority để first vertical có ranh giới rõ. | P0 | [`8.5`](prd.md#85-program-vertical-và-brief), FR-040–042 |
| US-006 | Brief | User | Tôi muốn xem việc cần xử lý, thay đổi, context liên quan và coverage để biết điều gì quan trọng. | P0 | [J4](prd.md#j4-daily-brief), FR-043–045 |
| US-007 | Ask | User | Tôi muốn hỏi trên context đã cho phép và nhận factual answer có citation hoặc abstain. | P0 | [J5](prd.md#j5-grounded-ask), FR-050–055 |
| US-008 | Inspect memory | User | Tôi muốn biết vì sao hệ thống nhớ một fact và có thể edit/delete nó. | P0 | [J6](prd.md#j6-memory-inspector), FR-034–035 |
| US-009 | Act | User | Tôi muốn preview, edit và confirm reminder/Calendar draft có nguồn để hành động an toàn. | P0 | [J7](prd.md#j7-action-draft), FR-060–066 |
| US-010 | Assure quality | Operator/QC | Tôi muốn audit và evaluation có version nhưng không lộ raw context để release có thể kiểm chứng. | P0 | [`8.8`](prd.md#88-audit-evaluation-và-operations), FR-070–073 |

## Value slices

| Slice | Stories | Exit outcome |
| --- | --- | --- |
| Gate 1 baseline | US-001–010 ở mức PRD/design/architecture | Scope, trust model và traceability được review |
| Source sync → evidence | US-001–003 | Dữ liệu được đồng bộ có consent, provenance và không mất/duplicate |
| Evidence → memory → Brief/Ask | US-004–008 | Fact/candidate phân biệt rõ; Brief/Ask có citation và coverage |
| Ask → confirmed Act | US-009–010 | Killer journey chạy được, action trước confirm = 0, evidence tái lập |

## Quy tắc đồng bộ với Jira

- ID `US-NNN` ổn định và được ghi trong Jira Story tương ứng.
- File này giữ user outcome, priority và PRD trace; Jira giữ assignee, sprint,
  estimate, dependency và status.
- Acceptance criteria chi tiết nằm trong [PRD](prd.md) hoặc
  [feature specification](features/README.md); Jira link tới nguồn đó.
- Thay đổi priority/scope phải cập nhật file này và PRD trong cùng change set,
  sau đó cập nhật Jira.
