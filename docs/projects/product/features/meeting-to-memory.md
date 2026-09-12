# Use case — Meeting transcript to personal memory

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Superseded — ngoài P0 theo ADR-002 |
| Owner | Nguyễn Văn Phong (Technical Lead; acting owner) |
| Reviewers | PM, Tech Lead, QA Lead |
| Last updated | 2026-08-02 |
| Related | [PRD](../prd.md) · [Memory lifecycle](../../engineering/memory-lifecycle.md) |

## Actor và preconditions

- User import transcript hoặc meeting được đồng bộ qua Vexa feature flag.
- Meeting nằm trong consent scope.
- Transcript có source artifact; speaker/timestamp nếu provider cung cấp.

## Main flow

1. Artifact được checksum và persist.
2. Transcript segments được upsert theo revision.
3. Khi meeting final, worker extract decision, commitment, action và topic.
4. Mỗi candidate liên kết segment evidence.
5. System so sánh canonical memory/current program facts.
6. Candidate mới được confirm/promote hoặc conflict chuyển `disputed`.
7. Brief hiển thị meeting change/context phù hợp role/goal.
8. User mở timestamp citation hoặc Memory Inspector.
9. User confirm/edit/reject candidate.

## Alternative/failure

- Vexa unavailable → import transcript.
- Transcript draft thay đổi → revision mới, không duplicate.
- Không có speaker/timestamp → citation ở artifact/chunk level và UI nói rõ độ phân giải.
- Discussion chưa phải decision → candidate, không canonical.
- Assignee/deadline mơ hồ → unknown.
- Conflict authority chưa rõ → hiển thị cả versions.

## Acceptance

- Import fallback chạy độc lập với Vexa.
- Segment/version/citation truy được.
- Discussion không bị promotion thành commitment không có evidence.
- Conflict không overwrite history.
- User có thể reject/delete candidate.
