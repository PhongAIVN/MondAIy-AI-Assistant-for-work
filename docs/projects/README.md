# Project Management SSOT — P-004

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Active |
| Owner | Thái Hoài An (PM) |
| Reviewers | Technical Lead, UI/UX Lead, PO/QC |
| Last updated | 2026-08-01 |
| Source of truth | Có — bản đồ tài liệu và vận hành P-004 |

Đây là gateway duy nhất tới tài liệu sống của P-004. Luật tạo, sửa, review và
archive nằm trong [Documentation Guide](DOCUMENTATION-GUIDE.md). Backlog,
sprint, assignee, deadline và bug nằm tại
[Jira TAPB](https://vinait004.atlassian.net/jira/software/projects/TAPB/boards/2/backlog?atlOrigin=eyJpIjoiMzY5ODc1NjNiNzkyNGI5OGJlYWE3MGE5NzFhNDhmMTMiLCJwIjoiaiJ9).

## Document map

```text
projects/
├── README.md                    # Gateway và source map
├── DOCUMENTATION-GUIDE.md       # Cách sử dụng/quản trị tài liệu
├── pm/                          # Team, cadence, templates
├── product/                     # Problem, PRD, story map, feature specs
├── design/                      # UX flow và design artifacts
├── engineering/                 # Repo setup, architecture decisions
├── qa/                          # Test/evaluation method và evidence
├── reports/                     # Weekly, mentor, standup, meeting notes
├── drafts/                      # Proposal đang phản biện, không canonical
└── gates/                       # Manifest + Git snapshot của Gate 1/2/3
```

## Source-of-truth map

| Nội dung | Nguồn chuẩn |
| --- | --- |
| Product problem, MVP, success criteria | [One-page brief](product/one-page-brief.md) |
| Requirement và acceptance cấp sản phẩm/release | [PRD](product/prd.md) |
| Thiết kế và acceptance chi tiết cấp tính năng | [Feature specifications](product/features/README.md) |
| Danh sách user story và traceability | [User story map](product/user-story-map.md) |
| Roadmap sáu tuần và pilot | [Roadmap](product/roadmap-6-weeks.md) · [Pilot plan](product/pilot-plan.md) |
| UX flow và product state | [Wireframe & UI flow](design/wireframe-ui-flow.md) · [Mermaid](design/web-app-ui-flow.mmd) |
| Architecture, memory và delivery rules | [Engineering](engineering/README.md) |
| Test method và evaluation evidence | [QA](qa/README.md) |
| Team và quyền quyết định | [Team directory](pm/team-directory.md) |
| PM cadence và quality bar | [PM Assistant](pm/PM_TEAM_ASSISTANT.md) |
| Weekly, mentor, standup và meeting notes | [Reports](reports/README.md) |
| Hồ sơ nộp Gate 1/2/3 | [Gates](gates/README.md) |
| Backlog, sprint, DRI, deadline và bug | [Jira TAPB](https://vinait004.atlassian.net/jira/software/projects/TAPB/boards/2/backlog?atlOrigin=eyJpIjoiMzY5ODc1NjNiNzkyNGI5OGJlYWE3MGE5NzFhNDhmMTMiLCJwIjoiaiJ9) |
| Handbook kỹ thuật dùng chung của chương trình | [`docs/guide/`](../guide/) |

## Proposals under review

- [Draft proposals](drafts/README.md)
- [Cross-platform task aggregation funnel — Nguyễn Văn Phong](drafts/van-phong-cross-platform-task-funnel-proposal.md)
- [Telegram mobile command center — proposal](drafts/telegram-mobile-command-center-plan.md)

Draft không phải source of truth. Chỉ phần đã được review và promote vào
PRD/ADR/tài liệu canonical mới được dùng làm cơ sở build.

## Ranh giới vận hành

- GitHub lưu product definition, design, technical decision, QA method,
  evidence đã phát hành, report và checkpoint manifest.
- Jira visualize execution: backlog, sprint, assignee, dependency, trạng thái
  và bug. Jira issue link về doc canonical; không trở thành PRD thứ hai.
- Gate dùng Git tag/commit để đóng băng snapshot; không copy PRD thành nhiều
  phiên bản trong `gates/`.
- `docs/guide/` là handbook tham khảo từ chương trình/các team trước; không sửa
  để phản ánh quyết định riêng của P-004.
