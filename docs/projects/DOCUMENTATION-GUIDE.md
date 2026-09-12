# Documentation Guide — P-004

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Approved |
| Owner | Thái Hoài An (PM) |
| Reviewers | Technical Lead, UI/UX Lead, PO/QC |
| Last updated | 2026-08-01 |
| Source of truth | Không — source map nằm tại [Project SSOT](README.md) |
| Related | [Project SSOT](README.md) · [PM Assistant](pm/PM_TEAM_ASSISTANT.md) |

## Mục đích

File này hướng dẫn cách tạo, sửa, review, phát hành và archive tài liệu P-004.
Nó không định nghĩa lại nguồn chuẩn; mọi source-of-truth và quyền quyết định
được xác định tại [Project SSOT](README.md).

## Tạo tài liệu mới

1. Xác định nội dung thuộc product, design, engineering, QA, PM, report hay Gate.
2. Kiểm tra đã có tài liệu canonical cùng mục đích chưa.
3. Tạo file tại đúng domain; không tạo tracker task/bug Markdown song song Jira.
4. Thêm header chuẩn, owner, reviewer và related links.
5. Thêm file vào document map trong SSOT hoặc index của domain.
6. Yêu cầu review phù hợp trước khi đổi trạng thái sang `Approved`.

## Quy tắc bắt buộc

1. **Một tài liệu, một mục đích.** Không trộn research thô, quyết định cuối và
   task list trong cùng file.
2. **Một loại dữ liệu, một nguồn chuẩn.** Link được phép; copy requirement,
   status hoặc decision sang nguồn khác là không được phép.
3. **Material change phải cập nhật đồng bộ.** Đổi scope, requirement, metric,
   privacy, data source, timeline hoặc architecture phải cập nhật source links,
   Jira impact và evidence trong cùng change set.
4. **Không dùng `final`.** Dùng `Status`, `Last updated` và `Superseded by`.
5. **Không xóa history có ý nghĩa.** Tài liệu đã review được archive/supersede
   kèm link thay thế.
6. **Không commit secret, token, PII hoặc transcript thô.** Fixture phải
   synthetic hoặc redacted.
7. **Dùng relative link và kiểm tra sau rename/move.** Gate đã nộp không được
   đổi tên nếu chưa cập nhật toàn bộ link phụ thuộc.

## Header chuẩn

```md
# Tên tài liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Draft / In review / Approved / Superseded / Archived |
| Owner | @DRI |
| Author | @người khởi tạo nội dung |
| Reviewers | @reviewers |
| Last updated | YYYY-MM-DD |
| Source of truth | Có / Không — link nếu Không |
| Related | PRD, ADR, Jira, design hoặc evidence |
```

Author ghi nhận người khởi tạo nội dung; Owner là DRI chịu trách nhiệm duy trì
tài liệu và có thể là người khác. `Approved` chỉ dùng sau khi DRI có quyền đã
review.

## Đặt tên và vị trí

- Living document dùng `kebab-case.md`; file entry point dùng `README.md`.
- ADR dùng `adr-NNN-quyet-dinh-ngan.md`.
- Weekly report dùng `YYYY-Www-weekly-report.md`; daily standup dùng một file
  `YYYY-Www-standup.md` cho cả tuần.
- Mentor report và meeting note dùng `YYYY-MM-DD-loai-report.md`.
- Không dùng hậu tố `new`, `latest`, `final` hoặc `final-final`.
- Template nằm trong `pm/templates/`; report thực tế không ghi đè template.
- Proposal chưa được chấp nhận nằm trong `drafts/`, phải ghi author, status,
  conflict với source of truth và điều kiện promote.
- Gate chứa bản đóng băng của **deliverable bắt buộc** (Brief, PRD, Wireframe/UI
  flow), đánh số `01-`, `02-`, `03-`. Tài liệu hỗ trợ chỉ được link, không copy.
  Manifest tại `gates/gate-N/README.md` phải ghi Git tag của lần nộp. Chi tiết
  tại [Gates](gates/README.md).

## Change control

| Loại | Ví dụ | Review tối thiểu |
| --- | --- | --- |
| Editorial | Chính tả, link, diễn đạt không đổi nghĩa | Self-review |
| Minor | Làm rõ flow/AC không đổi scope | Owner + một reviewer |
| Material | Đổi MVP/P0, metric, source, privacy, timeline hoặc architecture | Decision record + PM + relevant DRI |
| Emergency | Privacy incident, data loss hoặc Gate blocker | Mitigate/rollback ngay; review trong 24 giờ |

Material change chỉ hoàn tất khi:

- Rationale và alternatives đã ghi.
- Affected docs, Jira issue, design và evidence đã link.
- Acceptance, test/evaluation impact đã rõ.
- Owner, deadline và rollback/mitigation đã được giao.
- Reviewer có quyền đã phê duyệt.

## Product và AI guardrails

- No source, no publish: claim, requirement và evaluation result phải truy vết
  được về evidence.
- Không gộp nguồn Mức A và Mức B; thay đổi source/confidence/deadline parsing là
  material change.
- PRD phải có happy path, empty state, source unavailable, conflict và consent.
- Dataset/golden set không chứa raw sensitive data; phải có schema, rubric và
  cách tái lập.
- External action luôn qua preview, edit và human confirmation.

## Sử dụng feature specification template

1. Chỉ tách file khi một feature trong PRD đủ lớn để design, engineering và QA
   cần review độc lập; feature nhỏ tiếp tục nằm trong PRD.
2. Copy [Feature specification template](pm/templates/feature-specification.md)
   thành `product/features/feature-id-ten-ngan.md`; không sửa template gốc.
3. Link requirement trong PRD, User Story, Jira Epic/Story, UI/UX, contract và
   test evidence liên quan. Không định nghĩa lại scope, priority hoặc metric.
4. Dùng file feature làm nguồn chuẩn cho thiết kế và acceptance criteria; Jira
   giữ assignee, sprint, deadline và trạng thái thực thi.
5. Trước khi chuyển sang `Approved`, phải có review tối thiểu của PM, Technical
   Lead, UI/UX Lead và PO/QC cho phần thuộc trách nhiệm của họ.

## Sử dụng report template

1. Copy template phù hợp sang đúng thư mục con của `reports/`.
2. Đổi metadata, ngày và owner; không sửa template gốc.
3. Link Jira filter, PR, demo và evaluation evidence thay vì copy task list.
4. Chuyển action sang Jira và decision material sang doc canonical trong 24 giờ.
5. Report chính thức được index bởi [Reports](reports/README.md); chỉ thêm trực
   tiếp vào SSOT nếu report đó trở thành nguồn chuẩn cấp dự án.

Report template hiện có:

- [Báo cáo tuần](pm/templates/weekly-status-report.md)
- [Mentor duty report](pm/templates/mentor-duty-report.md)
- [Daily standup theo tuần](pm/templates/daily-standup-week.md)
- [Meeting notes](pm/templates/meeting-note.md)
- [Báo cáo demo và feedback](pm/templates/demo-feedback-report.md)
- [Báo cáo tổng kết và tác động](pm/templates/final-impact-report.md)

## Lưu checkpoint và transcript

- Gate 1/2/3 dùng manifest tại [Gates](gates/README.md) và Git tag tương ứng.
  Living docs tiếp tục được sửa tại `product/`, `design/`, `engineering/` và
  `qa/`.
- Git lưu meeting note gồm agenda, decision, rationale và Jira actions. Raw
  recording/transcript mặc định ở external restricted storage với consent và
  retention; chỉ commit bản redacted khi thật sự cần làm evidence.
- Report không sao chép task status. Sau meeting/standup, owner, blocker,
  deadline và status chính thức phải được cập nhật trên Jira.

## Nhịp quản trị tài liệu

| Thời điểm | Việc bắt buộc |
| --- | --- |
| Trước planning | PM cập nhật scope/decision; owner link evidence/dependency |
| Trước feature build | PRD/AC, UI/data contract và test approach ở `In review` hoặc `Approved` |
| Sau meeting | Decision/action cập nhật nguồn chuẩn trong 24 giờ |
| Hằng tuần | Kiểm tra doc stale, broken link, owner trống và decision thiếu DRI |
| Trước Gate/release | Kiểm tra index, approvals, evidence, privacy và archive |

## Review checklist

- [ ] Doc có owner, status, reviewer, ngày cập nhật và index link.
- [ ] Không trùng hoặc mâu thuẫn với source of truth.
- [ ] Claim, user insight, metric hoặc AI result có evidence và ngày đo.
- [ ] Requirement có actor, priority, AC, error state và analytics khi áp dụng.
- [ ] Không có secret, PII hoặc raw transcript.
- [ ] Relative links hoạt động.
- [ ] Material change có decision record, reviewer và impact đã cập nhật.

## Xử lý tranh chấp

1. Dừng phần build nếu mâu thuẫn ảnh hưởng scope, privacy, dữ liệu hoặc metric.
2. Owner ghi decision cần chốt, evidence, alternatives và khuyến nghị.
3. PM gọi đúng DRI phê duyệt và cập nhật source of truth trong 24 giờ.
4. Chỉ tiếp tục build sau khi Jira/PRD liên quan đã link quyết định.
