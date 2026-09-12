# Documentation Map — P-004

Bắt đầu ở bề mặt authoritative nhỏ nhất. Thứ tự dưới đây là thứ tự đọc.

## Nguồn sự thật của P-004 (ưu tiên cao nhất)

- [`projects/README.md`](projects/README.md): **entrypoint sản phẩm** — PRD, phạm vi, acceptance.
- [`ADR/`](ADR): quyết định kiến trúc/sản phẩm mà việc sau phải kế thừa.
- [`../AGENTS.md`](../AGENTS.md): hợp đồng vận hành cho mọi coding agent, gồm cổng tích hợp
  bắt buộc trước push/deploy.
- [`changes/`](changes): bản ghi WHAT_CHANGED của từng lane.
- [`guide/`](guide), [`mcp/`](mcp), [`diagram/`](diagram): vận hành, tích hợp, sơ đồ.
- Code, test, CI và tín hiệu runtime: sự thật chạy được.

## Bổ sung từ repository-harness

- [`WORKFLOW.md`](WORKFLOW.md): chọn hình dạng công việc, cổng authority, chuẩn nghiệm thu.
- [`patterns/encoding-invariants.md`](patterns/encoding-invariants.md): biến luật đã được chấp
  nhận thành check cơ giới của chính repo.
- [`templates/`](templates): mẫu plan, decision, runbook — tuỳ chọn.
- [`plans/active/`](plans/active): **một** file kế hoạch cho việc cần trí nhớ bền; xong thì chuyển
  sang [`plans/completed/`](plans/completed).

## Luật ưu tiên khi hai bên nói khác nhau

Nguồn của P-004 thắng. `WORKFLOW.md` mô tả *cách làm việc*; nó không ghi đè PRD, ADR, hay cổng
tích hợp trong `AGENTS.md`. Quyết định mới ghi vào `ADR/`, không ghi vào `decisions/`.
