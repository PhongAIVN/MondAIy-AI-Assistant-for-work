# Mentor duty report — 2026-08-04

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Draft — chưa họp, phần khuyến nghị và quyết định điền tại chỗ |
| Owner | Thái Hoài An (PM) |
| Mentor / participants | TBD |
| Date | 2026-08-04 |
| Related | [Jira TAPB](https://vinait004.atlassian.net/jira/software/projects/TAPB/boards/2/backlog) · [Gate 1](../../gates/gate-1/README.md) · [PRD](../../product/prd.md) · [Roadmap](../../product/roadmap-6-weeks.md) |

## Mục tiêu buổi trao đổi

Gỡ bốn chỗ nhóm không tự quyết được: tiêu chí chấm Gate 1, cách trình bày chỉ số
khi cỡ mẫu nhỏ, phạm vi Sprint 2 sau khi roadmap bị lệch một sprint, và chủ sở
hữu lane Memory/AI.

Không dùng buổi này để báo cáo tiến độ. Trạng thái chi tiết xem Jira.

## Trạng thái tính tới đầu buổi

| Hạng mục | Thực tế |
| --- | --- |
| Gate 1 | Bị từ chối ở lần nộp 2, lý do: văn bản mẫu do AI sinh. Đã sửa xong, chờ tag `p004-gate-1r2` |
| Sprint 2 (03/08–09/08) | Ngày 2/7. Bốn task chính, **cả bốn còn To Do**, chưa có task nào In Progress |
| Backend | Chưa có dòng code nào cho domain Sprint 2 — không có `SourceItem`, evidence, extraction hay citation |
| Extension | Đã có contract kiểu dữ liệu, các thành phần hiển thị citation, chế độ dữ liệu giả chạy được |
| Bộ test | `make test` đang hỏng, thiếu `pytest_asyncio` trong môi trường ảo |
| Nghiên cứu người dùng | Chưa phỏng vấn ai. OI-01 usability test 3–5 người, hạn 13/08, chưa chạy |
| Gate 2 | Hạn 16/08, toàn bộ mục Evidence còn TBD |

## Bối cảnh và câu hỏi

| Câu hỏi | Evidence đã cung cấp | Khuyến nghị của mentor |
| --- | --- | --- |
| **1. Tiêu chí "văn bản do AI sinh" cụ thể là gì? Có ghi chú của người chấm chỉ ra chỗ nào bị đánh dấu không?** | Nhóm tự rà và sửa theo phán đoán riêng: bỏ một trích dẫn viết như lời người dùng thật trong khi chưa phỏng vấn ai; bỏ các đoạn văn quảng cáo; bỏ ba chỗ lặp lại cùng một danh sách trong một tài liệu. Diff nằm ở branch `docs/glossary-terminology` | TBD |
| **2. Bỏ ngưỡng phần trăm cho chỉ số hành vi có được chấp nhận không?** | Đã gỡ 9 ngưỡng: 70% hữu ích, 70% đọc bản tin 4 ngày/tuần, 30% xác nhận hành động, 60% giảm thời gian, 95% từ chối đúng. Lý do: pilot 5–10 người, một người đổi ý làm tỷ lệ nhảy 10–20 điểm; và nhóm chưa phỏng vấn ai để chọn con số. Thay bằng báo cáo `x/n người`. Giữ nguyên các ngưỡng chạy được trên bộ dữ liệu kiểm thử: 100% dẫn nguồn, 0 bản trùng, 0 hành động trước xác nhận, 0 rò dữ liệu giữa người dùng | TBD |
| **3. Sprint 2 đang gánh nội dung hai tuần roadmap. Phương án cắt của nhóm có đủ để Gate 2 kịp 16/08 không?** | Sprint 1 đi hết vào discovery và Gate 1, nên 6 tuần roadmap còn 5 tuần build. Phương án nhóm đề xuất: giữ nguyên lát cắt dọc, nhưng chỉ làm 2 endpoint (`/briefings/today`, `/items/{id}`) thay vì 4, đẩy phần Hành động sang Sprint 4 theo đúng thứ tự cắt phạm vi trong roadmap | TBD |
| **4. Lane Memory/AI nên do ai cầm?** | Roadmap chia 4 lane cho 4 người, nhưng bảng phân vai không gán ai vào Memory/AI, nên lane này đang rơi vào tay PM. Tech Lead đứng tên 2 lane mà Sprint 2 không có ticket nào. Đề xuất của nhóm: ghép Memory/AI với Evaluation về PO/QC, PM giữ phần nội dung Khung chương trình vì đó là quyết định sản phẩm | TBD |

### Hai việc nhóm chủ động nêu, không chờ hỏi

- **Chưa phỏng vấn người dùng nào.** Mọi phát biểu về nỗi đau học viên trong PRD
  và brief hiện là giả định của nhóm, đã ghi rõ như vậy trong tài liệu thay vì
  trình bày như dữ liệu. Usability test 3–5 người chạy trước 13/08.
- **Bộ test đang hỏng và backend chưa bắt đầu domain Sprint 2.** Không làm tròn
  con số lên.

## Quyết định của team

| Decision | Rationale | Approver | Canonical doc |
| --- | --- | --- | --- |
| Bỏ 9 ngưỡng chỉ số hành vi, thay bằng báo cáo số tuyệt đối | Cỡ mẫu 5–10 người không đủ để tỷ lệ phần trăm có ý nghĩa; nhóm chưa có cơ sở chọn con số | Proposed — chờ mentor | [PRD mục 4.3](../../product/prd.md#43-hệ-thống-chỉ-số) |
| Ghi rõ trong brief phần nào đã kiểm chứng, phần nào là giả định | Trình bày giả định như dữ liệu là nguyên nhân bị từ chối Gate 1 | Proposed — chờ mentor | [One-page brief](../../product/one-page-brief.md) |
| Sprint 2 chốt contract trước, ba việc còn lại chạy song song | Chia theo tầng tạo chuỗi tuần tự 4 bước; chốt contract trước biến thành 1 bước chung cộng 3 việc song song | Proposed — chờ mentor | [Roadmap](../../product/roadmap-6-weeks.md) |
| Sprint 2 chỉ làm 2 endpoint, phần Hành động lùi sang Sprint 4 | Theo đúng thứ tự cắt phạm vi đã ghi trong roadmap | Proposed — chờ mentor | [Roadmap](../../product/roadmap-6-weeks.md) |
| Ghép lane Memory/AI với Evaluation về PO/QC | Chất lượng extraction được đo bằng golden set; tách hai việc tạo vòng lặp chờ nhau | Proposed — chờ mentor | [Team directory](../../pm/team-directory.md) |

Toàn bộ đang ở trạng thái `Proposed`. Không mục nào được trình bày như đã chốt
cho tới khi có phê duyệt.

## Quyết định còn mở, cần chốt trong tuần

| ID | Vấn đề | Ảnh hưởng nếu chưa chốt |
| --- | --- | --- |
| — | PRD FR-041 ghi 5 trạng thái (mới, đã cập nhật, đã hủy, **đã thay thế**, mâu thuẫn) nhưng TAPB-80 chỉ có 4, thiếu *đã thay thế* | Fixture Sprint 2 hụt một trạng thái PRD bắt buộc; golden subset không có case kiểm nó |
| OD-03 | Gọi mô hình qua OpenRouter hay trực tiếp | Mã hiện đang gọi thẳng OpenAI, khác PRD |
| OD-07 | Extension có được đọc nội dung trang web không | Ngoài phạm vi P0, quyết sau pilot bằng ADR mới |

## Actions đã chuyển sang Jira

| Jira issue | DRI | Due date |
| --- | --- | --- |
| TAPB-80 — Program Frame, extraction và change guardrails | Thái Hoài An | 2026-08-07 |
| TAPB-79 — Evidence/version ingestion và vertical integration | Lê Thị Yến Nhi | 2026-08-08 |
| TAPB-114 — Extension hiển thị item từ API thật | Lê Thị Yến Nhi | 2026-08-08 |
| TAPB-115 — Golden subset, E2E và demo evidence | Nguyễn Đức Dũng | 2026-08-09 |
| TAPB-89 — Weekly report W2 thứ Tư | Thái Hoài An | 2026-08-05 |
| TAPB-100 — Weekly report W2 thứ Bảy | Thái Hoài An | 2026-08-08 |

Việc phát sinh từ buổi này ghi tiếp vào bảng trên, mỗi dòng phải có DRI và hạn.

## Việc cần làm sau buổi

- [ ] Chuyển mỗi khuyến nghị của mentor thành một trong hai: decision record cập
      nhật PRD/ADR, hoặc issue Jira có DRI và hạn. Không để lơ lửng trong biên bản.
- [ ] Đổi trạng thái các quyết định từ `Proposed` sang đã duyệt, hoặc ghi lý do
      bác bỏ.
- [ ] Nếu mentor xác nhận cách trình bày chỉ số, tạo tag `p004-gate-1r2` và nộp
      lại Gate 1.
