# ADR-017 — Học thích ứng P1: tư duy Hermes-agent, bề mặt cho người không kỹ thuật

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Accepted — Thái chốt ba mục mở ngày 2026-08-22 (OD-02, OD-SLA, OD-COHORT theo đề xuất mặc định) |
| Owner đề xuất | PM + Technical Lead + Memory/AI Lead |
| Author | Tatejo, theo yêu cầu của Thái Hoài An (22/08) |
| Last updated | 2026-08-22 |
| Related | [Execution plan P1](../../../plans/active/memory-adaptation-p1.md) · [Adaptive learning plan](../adaptive-agent-learning-plan.md) · [Memory lifecycle](../memory-lifecycle.md) · [ADR-006](adr-006-pgvector-cho-lop-memory-dai-han.md) · [PRD](../../product/prd.md) |
| Research reference | NousResearch/hermes-agent — bản clone local `AI thực chiến/za. Tham khảo/hermes-agent/` |

## Bối cảnh

Plan P1 đã được duyệt hướng ngày 21/08 và điều kiện tiên quyết P0 ("make
adaptation user-controlled") đã vào `main` @ `dd6f781`. Ngày 22/08 Thái yêu cầu
kéo hermes-agent về tham khảo thiết kế và áp tư duy đó vào mondaiy với yêu cầu
bổ sung: **mọi tính năng phải dùng được bởi người không kỹ thuật** — không
terminal, không file cấu hình, không đọc diff.

Hermes-agent là agent tự cải thiện đang chạy thật: skill tự tạo và tự vá khi
dùng, memory do agent curated kèm nudge định kỳ, tìm kiếm xuyên phiên, mô hình
hoá người dùng, tự động hoá bằng ngôn ngữ tự nhiên. Điểm mạnh là vòng học kín;
điểm yếu là toàn bộ bề mặt xem xét lại (review surface) dành cho người kỹ thuật:
file Markdown, diff, lệnh CLI.

## Nguyên lý mượn từ Hermes

Bảy cơ chế cốt lõi của Hermes và cách mondaiy tiếp nhận. Tham chiếu file tính
theo gốc repo clone.

| Cơ chế Hermes | Tham chiếu | Áp vào mondaiy |
| --- | --- | --- |
| Nudge counter → fork nền sau khi trả lời xong, không bao giờ tranh quyền với lượt chat (`agent/turn_finalizer.py`, `agent/background_review.py`) | Fork học chạy post-delivery trên worker; trigger là bộ đếm lượt, không nằm trên critical path | Worker review theo lease/cursor; fork chỉ có tool đọc ghi candidate, không có tool hệ thống |
| Frozen snapshot memory trong system prompt giữ prefix cache ổn định (`tools/memory_tool.py` → `format_for_system_prompt`) | Context assembly chót một bản chụp style/skill đầu mỗi lượt; giữa stream không thêm hay thay | Bản chụp kèm version refs ghi vào `assistant_context_refs` để feedback truy được về đúng phiên bản đã dùng |
| Progressive disclosure kỹ năng: metadata mỏng vào danh sách, thân đầy đủ nạp theo nhu cầu (`tools/skills_tool.py`) | Skill card hiển thị tên + mô tả + tóm tắt evidence trước; nội dung đầy đủ, diff và provenance mở khi user bấm vào | Mỗi lượt chỉ inject top skill relevant trong token budget |
| Thứ tự ưu tiên cập nhật skill: vá skill đang dùng → vá skill tổng → thêm support file → tạo mới cấp lớp; cấm đặt tên theo artifact của một phiên; mặc định "nothing to learn" (`agent/background_review.py` `_SKILL_REVIEW_PROMPT`) | Compiler skill mondaiy theo cùng thứ tự; một workflow one-off không thành skill; không tối ưu số skill tạo ra | Tránh skill tràn lan và skill mang tên riêng một phiên chat |
| Staged pending writes: mọi ghi từ nền stage vào hàng đợi duyệt, daemon không tự prompt được (`tools/write_approval.py`) | Chính là `learning_candidates`: candidate chưa accept không ảnh hưởng response; thẻ duyệt là chỗ user quyết | Khớp sẵn invariant "candidate không điều khiển hành vi" của plan |
| Ledger audit append-only + snapshot nội dung băm cho rollback một thao tác (`tools/skill_ledger.py`) | `learning_audit_events` append-only (id/version/reason code) + bảng versioned; rollback về last-known-good một chạm | Không log raw transcript hay compiled prompt |
| Curator vòng đời: 30 ngày không dùng → stale, 90 ngày → archived, không bao giờ tự xoá, pin miễn trừ (`agent/curator.py`) | Pending quá hạn 30 ngày expire; accepted không reinforce 30 ngày → rời retrieval mặc định; 90 ngày → archived còn xem lại; chỉ reset/delete tường minh của user mới xoá | Chống nagging và rác học tích tụ mà vẫn giữ audit |

## Dịch sang bề mặt cho người không kỹ thuật

Khoảng cách lớn nhất của Hermes với sản phẩm consumer là review surface và nội
dung skill.mondaiy dịch như sau:

1. **Duyệt bằng thẻ chat-native, không diff file.** Candidate hiện dưới dạng
   thẻ "Mondaiy nhận thấy…, từ N lần trong M tuần" với bốn hành động:
   `Chấp nhận` · `Sửa` · `Không đúng` · `Đừng gợi ý lại`. Người dùng không bao
   giờ phải đọc JSON hay diff.
2. **Skill là playbook nghiệp vụ, không công thức terminal.** Nội dung skill
   mondaiy là declarative workflow theo task class (cách format weekly review,
   thứ tự chuẩn bị briefing), không phải script shell.
3. **Cấu hình bằng toggle và form, không lệnh.** Consent từng năng lực nằm ở
   trang privacy "Mondaiy đã học gì"; pause/reset từng lớp đều là nút UI.
4. **Blueprint catalog cho tự động hoá.** Routine/tự động hoá tạo bằng form có
   sẵn các slot kiểu hoá (giờ, ngày tuần, tần suất) hoặc agent hỏi thiếu slot
   nào trong chat — người dùng không cần hiểu khái niệm cron. Tư duy này lấy từ
   `cron/blueprint_catalog.py` của Hermes: một engine, nhiều bề mặt nhập liệu.
5. **Recall xuyên phiên tái dụng hạ tầng có sẵn.** Hermes dùng FTS5/trigram
   SQLite vì nó chạy standalone; mondaiy đã có truy hồi lai keyword + pgvector
   theo ADR-006 — dùng lại, không dựng index thứ hai.

## Quyết định

1. Consent bốn công tắc riêng — `chat_learning`, `adaptive_style`,
   `learned_skills`, `routine_learning` — mặc định tắt, lưu kèm
   `policy_version`; onboarding không được âm thầm bật chat learning.
2. Trigger học = bộ đếm kiểu Hermes (đề xuất: review memory sau mỗi 10 lượt
   chat, review skill sau mỗi 10 lần gọi công cụ) GỘP với trần tối đa 1 lần
   chạy/24h/user/mỗi capability và luôn chạy sau khi response đã giao. Nút
   "Xem mondaiy học được gì" (on-demand) luôn khả dụng và không tốn bộ đếm.
3. Frozen snapshot đầu lượt: tập style dimension đã confirmed + top skill
   relevant chốt lúc bắt đầu lượt; ghi version refs vào `assistant_context_refs`
   trong cùng transaction với message assistant, cả đường thường và streaming.
4. Learned skill thuần declarative (trigger/input/steps/output/verification);
   cấm code/shell/generated script; `allowed_tools` là giao với allowlist hệ
   thống, skill không tự mở quyền.
5. Thứ tự cập nhật skill theo preference order của Hermes (mục bảng trên);
   "nothing to learn" là kết quả mặc định và phải đo đếm được.
6. Candidate inbox cap ≤3 đề xuất mới/user/tuần, ≤5 pending cùng lúc; rejection
   latch cùng stable key 30 ngày.
7. Audit append-only chỉ ghi id/version/reason code; rollback last-known-good
   một thao tác; log không chứa raw transcript.
8. Vòng đời curator: pending hết 30 ngày → expired; accepted không reinforce
   30 ngày → stale khỏi retrieval mặc định; 90 ngày → archived (ẩn, còn tra
   cứu); chỉ reset/delete tường minh của user mới xoá dữ liệu.
9. Non-tech surface là tiêu chí nghiệm thu, không phải trang trí: mọi năng lực
   học phải có toggle, thẻ duyệt, preview Trước/Sau và reset tương ứng trên
   UI/web/mobile. Một năng lực không có bề mặt UI thì chưa coi là xong slice.
10. Recall xuyên phiên và mô hình hoá người dùng: tái dụng ADR-006; KHÔNG đưa
    Honcho hay provider nhớ ngoài vào critical path P1 (đúng plan). Style
    profile nội bộ là mô hình người dùng của P1; Honcho chỉ cân nhắc A/B test
    sau pilot.
11. Precedence giữ nguyên plan: safety + permission policy > core persona >
    instruction tường minh lượt hiện tại > style profile đã accepted > active
    learned skill > inferred candidate (chỉ dùng để hỏi xác nhận).
12. Deletion propagation: xoá conversation hoặc revoke consent vô hiệu hoá
    evidence phụ thuộc trong cùng transaction trước khi nguồn biến mất;
    reference đứt dây không được coi là accessible; candidate/skill phụ thuộc
    chuyển stale chờ re-evaluate.

## Threat model rút gọn

| Rủi ro | Kiểm soát |
| --- | --- |
| Prompt injection trong lịch sử chat | History là dữ liệu có delimiter, structured output, static scan trước khi persist candidate và trước khi activate |
| Agent tự củng cố hallucination thành belief | Chỉ message của user và outcome quan sát được là evidence; assistant text chỉ dựng lại ngữ cảnh đánh giá |
| Rò dữ liệu chéo user | Mọi query lọc `user_id` ngay trong SQL; test denial chéo user bắt buộc cho mọi endpoint |
| Secret/PII vào skill, log, analytics | Redaction trước signal store; scanner chặn secret/raw id; log chỉ id/version/reason |
| Candidate ảnh hưởng response trước khi được chấp nhận | Context assembly chỉ đọc trạng thái accepted; regression test chứng minh candidate không đổi behavior |
| Xoá/revoke đua với việc học | Invalidation cùng transaction; drill xoá giữa extraction và activation |
| Skill xung đột nhau | Conflict đưa về review, không tự merge bằng LLM |

## OD còn mở — đã chốt 22/08/2026

| Mã | Quyết định | Giá trị đã chốt |
| --- | --- | --- |
| OD-02 (mở rộng) | Thời hạn lưu chat history dùng cho học | Học chỉ trên conversation còn nằm trong thời hạn lưu nguồn; không giữ bản sao riêng |
| OD-SLA | Hard-delete SLA sau reset/xoá | Loại khỏi retrieval ngay; hard-delete trong 30 ngày |
| OD-COHORT | Nhóm pilot và ngưỡng eval cuối | Opt-in nội bộ nhỏ; ngưỡng pre-register ở mục trên |

Thái chấp nhận cả ba đề xuất mặc định ngày 2026-08-22 (trao đổi trực tiếp).
Slice 1 được phép bắt đầu.

## Ngưỡng đánh giá pre-register

Chốt số cuối trước khi chạy model trên golden set (nguồn đầy đủ: execution plan
P1, mục Pre-Registered Evaluation Matrix):

| Chiều | Ngưỡng |
| --- | --- |
| Evidence coverage của accepted artifact | 100% |
| Rò chéo user / unsafe activation / raw secret-PII | 0 |
| Candidate sinh từ one-off hoặc assistant-only | 0 trên negative set |
| Style candidate precision | ≥90% |
| Style adherence sau accept (an toàn/citation/permission delta = 0) | ≥90% |
| Skill precision | ≥85% |
| Security/counterexample evaluation trước activation | 100% pass |
| Duplicate khi retry | 0 |
| Volume candidate | ≤3 mới/user/tuần; ≤5 pending |
| Evidence đã revoke còn được dùng | 0 |

## Lý do chọn tiếp cận này

Hermes đã chứng minh vòng học kín chạy ổn định ở quy mô cá nhân với chi phí thấp
(fork nền, snapshot đóng băng, store nhỏ có kiểu). Kế hoạch P1 của mondaiy đã
hình dung đúng pattern đó nhưng thiếu chi tiết cơ chế trigger và vòng đời bảo
trì — hai chỗ Hermes đã xử lý kỹ (nudge counter, curator). Tiếp nhận nguyên lý
kèm dịch bề mặt giúp mondaiy có đủ tính năng tự tiến hoá mà người thường vẫn
kiểm soát được, đúng BR-13 và ranh giới an toàn hiện có.
