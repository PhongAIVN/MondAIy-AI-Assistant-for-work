# Memory auto-record, conflict proposal và graph

## Intent

Cho phép memory suy ra được ghi nhận và sử dụng ngay; người dùng sửa/xoá khi
sai. Khi có nhiều giá trị mâu thuẫn, giữ version và propose để người dùng xử lý.
Thêm graph trực quan theo pattern Graphiti/Zep và Obsidian.

## Acceptance criteria

- Inferred memory không còn chờ nút confirm mới được recall.
- Conflict không tự âm thầm chọn một giá trị; các version liên quan được giữ để
  hiển thị proposal.
- Có graph API/UI với node, edge, provenance và local graph.
- Có regression tests cho auto-record, conflict, versioning, access control và
  graph filtering.

## Scope / ownership

- Lead Codex: backend schema/service/API và frontend graph.
- Antigravity: test matrix/review độc lập; gate đã được người dùng waive cho
  lượt này vì runtime không có tool Antigravity khả dụng.

## Research

- Graphiti/Zep: episodes, entities, facts, provenance và temporal validity.
- Obsidian: global/local graph, directed links, filtering và node navigation.

## Status

In progress. Backend auto-record, conflict proposal state, graph provenance API
và graph SVG UI đã có ở local; chưa commit/deploy.

## Local validation

- Backend targeted regression: `64 passed`.
- Backend Ruff + `git diff --check`: passed.
- `npx vitest run tests/MemoryGraphView.test.tsx`: `1 passed`.
- Frontend `npm run build`: passed.
- Full frontend `npm test`: `118 passed, 1 failed`; failure là existing
  `tests/extensionDownloadArtifact.test.ts` thiếu `popup.html` trong published
  extension artifact, không liên quan memory graph.
- Antigravity was invoked in plan mode after explicit user authorization, but
  the direct call returned no usable output. A subsequent Herdr-managed
  Antigravity review returned findings: wrong-version selection, missing graph
  mocks, duplicate accessible names and hardcoded graph labels. The version
  selection, mocks, accessible labels and vi/en graph copy were fixed locally.
