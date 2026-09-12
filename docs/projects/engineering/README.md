# Engineering

Tài liệu sống về cách hệ thống được xây dựng và vận hành.

| Tài liệu | Mục đích |
| --- | --- |
| [System architecture](architecture.md) | Target architecture và trust boundaries |
| [Program Frame](program-frame.md) | Khai báo khóa học, múi giờ, vai trò, sản phẩm bàn giao và mức A/B của từng nguồn |
| [API contract pipeline](api-contract-pipeline.md) | Hợp đồng dữ liệu giữa web app và đường ống 9 node, SSE, Calendar handoff |
| [Review `src/database.sql`](database-schema-review.md) | Chỗ sai, thiếu và conflict trong schema tại `cc1cd28` |
| [Capture/sync protocol](capture-sync-protocol.md) | Lịch sử phương án browser capture — superseded bởi ADR-002 |
| [Memory lifecycle](memory-lifecycle.md) | Candidate, canonical memory, conflict và deletion |
| [Zep memory provider proposal](zep-memory-provider-proposal.md) | Đề xuất dùng Zep cho episodic/semantic memory với PostgreSQL làm authoritative store |
| [Adaptive agent learning plan](adaptive-agent-learning-plan.md) | Kế hoạch P1 học routine, workflow skill và phong cách giao tiếp có evidence, evaluation, consent và rollback |
| [Discord connector spike](discord-connector-spike.md) | Quyền cần để đọc raw message, trường lấy được, giới hạn của dataset xlsx |
| [Jira connector plan](jira-connector-plan.md) | Kế hoạch end-to-end OAuth 3LO + `JiraConnector`, đã implement |
| [LLM routing](llm-routing.md) | Target architecture cho small talk, work/tool lane, free-first model selection và provider failover |
| [Production capacity & remediation](production-capacity-remediation-report.md) | Snapshot production, giới hạn pilot, rủi ro và roadmap tăng capacity |
| [Repository setup](repository-setup.md) | Ranh giới repo, branch/PR, CI và bảo mật |
| [ADR](adr/README.md) | Quyết định kỹ thuật có ảnh hưởng dài hạn |

Backlog, bug, assignee và trạng thái triển khai nằm tại
[Jira TAPB](https://vinait004.atlassian.net/jira/software/projects/TAPB/boards/2/backlog?atlOrigin=eyJpIjoiMzY5ODc1NjNiNzkyNGI5OGJlYWE3MGE5NzFhNDhmMTMiLCJwIjoiaiJ9).
