# Checkpoint gates

`gates/` lưu hồ sơ nộp bài theo checkpoint.

## Mô hình snapshot

Mỗi `gate-N/` gồm đúng hai thứ:

1. `README.md` — manifest: deadline, owner, deliverable, quyết định đã chốt,
   checklist, open item, verdict, evidence ngoài Git và Git tag.
2. Bản đóng băng của **deliverable bắt buộc**, đánh số theo thứ tự đọc:
   `01-brief.md`, `02-prd.md`, `03-wireframe-ui-flow.md`, kèm `assets/` nếu có.

Quy tắc:

- Chỉ đóng băng deliverable bắt buộc. Tài liệu hỗ trợ (ADR, architecture,
  roadmap, QA plan) để nguyên ở thư mục sống và chỉ link tới; cần đúng bản tại
  thời điểm nộp thì xem qua Git tag.
- Bản đóng băng phải có banner ghi rõ nó là snapshot và link về bản sống. Sau
  khi nộp thì không sửa; muốn sửa thì nộp lại và ghi vào bảng Lịch sử nộp.
- Không lồng thư mục `evidence/submission/...`. Một tầng, tên file nói rõ nội
  dung.
- Relative link trong bản đóng băng phải được tính lại theo vị trí mới để không
  chết link.

Tag đề xuất: `p004-gate-1`, `p004-gate-2`, `p004-gate-3`; nộp lại thì thêm hậu
tố `r1`, `r2`. Chỉ tạo tag sau khi checklist đã được review. Không dời tag cũ:
mỗi lần nộp là một bản ghi riêng. Manifest phải ghi tag thật, không để evaluator
dựa vào nhánh đang thay đổi.

| Gate | Checkpoint | Manifest |
| --- | --- | --- |
| Gate 1 — Problem & design baseline | 2026-08-02 | [gate-1](gate-1/README.md) |
| Gate 2 — Working MVP & feedback | 2026-08-16 | [gate-2](gate-2/README.md) |
| Gate 3 — Release & impact | 2026-09-06 | [gate-3](gate-3/README.md) |
