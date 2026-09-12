# Kế hoạch cải thiện test theo đánh giá CERTUS

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Draft |
| Owner | Nguyễn Đức Dũng (PO/QC) |
| Author | Codex, tổng hợp từ báo cáo đánh giá P-004 |
| Reviewers | Technical Lead, Backend Lead, AI/Memory Lead |
| Last updated | 2026-08-09 |
| Source of truth | Không — phương pháp và release threshold nằm tại [Evaluation plan](evaluation-plan.md); execution status nằm tại Jira TAPB |
| Related | [Guardrail](../../../src/guardrail/README.md) · [CI checks](../../../.github/workflows/checks.yml) · [Repository setup](../engineering/repository-setup.md) |

## 1. Mục đích và baseline

Tài liệu này chuyển kết quả CERTUS thành kế hoạch test có thể tách thành Jira
issue. Nó không phải tracker tiến độ và không thay thế evidence của từng lần
chạy.

Baseline từ lượt đánh giá được cung cấp ngày 2026-08-09:

| Chỉ số | Baseline |
| --- | ---: |
| Pytest | 201 passed, 1 skipped |
| Line coverage | 3471/4348 = 79,8% |
| CERTUS grid coverage | 4/177 = 2,3% |
| Ô chưa được canh | 173 |
| Zones | 1 |

Phạm vi grid của baseline gồm bốn trục `tool_level`, `tool_decision`,
`confidence_band` và `hitl_route`. Mọi lần đo tiếp theo phải dùng cùng commit,
cùng include/exclude scope và cùng định nghĩa cell; nếu thay denominator 177 thì
báo cáo phải giải thích thay đổi, không so trực tiếp hai tỷ lệ.

## 2. Nhận định sau khi đối chiếu repo

### Nền tảng có thể mở rộng

- `tests/test_guardrail.py` đã kiểm tra representative case cho năm tool level,
  năm confidence band, evidence gate, external write, destructive action và
  ba ngưỡng HITL chính.
- Test API đã có negative case quan trọng: thiếu token, token rác, access token
  dùng sai chỗ, participant/mentor gọi admin API, cross-user conversation/task/run.
- `tests/test_api/test_runs.py` đã có một case idempotency cho cùng key.
- `tests/test_services/test_llm_failover.py` đã có failover 429/503;
  `tests/test_services/test_telemetry.py` đã kiểm tra allowlist và không log giá
  trị content bị chặn.

### Khoảng trống cần xử lý

- Guardrail test đang gom nhiều nhánh vào một vài test function, nên chạy qua
  code nhưng không tạo đủ evidence cho từng tổ hợp nghiệp vụ của CERTUS.
- Chưa có matrix test cho precedence giữa permission, scope, citation,
  evidence, conflict, coverage, tool impact và confidence.
- HITL mới có approve và timeout tiêu biểu; còn thiếu reject, replay,
  confirmation binding, double confirmation, tamper case và kiểm tra dữ liệu
  nhạy cảm ở cấu trúc lồng nhau.
- Auth chưa có token hết hạn, refresh replay/rotation và các OAuth state case.
- Test connector/API connection còn mỏng. Coverage snapshot chỉ ra các vùng
  đáng ưu tiên gồm `src/api/connections.py`, Gmail/Discord/Telegram connection
  services, `src/services/oauth_state.py`, `src/services/llm.py`, retrieval,
  storage và observability.
- CI hiện chạy `pytest tests/ -v --tb=short` nhưng chưa đo coverage, chưa có
  threshold và chưa xuất artifact CERTUS/coverage.
- `requirements.txt` đã được bổ sung `prometheus-client` và `minio` trong thay
  đổi có sẵn, nhưng chưa có dependency test/coverage được khóa phiên bản.
  README còn hướng dẫn `pip install -e ".[dev]"` trong khi repo chưa có
  `pyproject.toml`. Vì vậy clean setup chưa có một nguồn hướng dẫn duy nhất.
- Test skip hiện tại là live LLM smoke trong `tests/test_agents/test_graph.py`,
  có lý do hợp lệ và bật bằng `RUN_LLM_LIVE=1`. Nó nên được tách khỏi regression
  suite thay vì tiếp tục xuất hiện như một skip không được quản trị.

## 3. Nguyên tắc triển khai

1. Ưu tiên rủi ro trước tỷ lệ dòng: external write, destructive, permission,
   HITL và data leak là release blocker.
2. Mỗi case phải assert cả quyết định, lý do, cờ approval/HITL, side effect và
   audit/log liên quan; không chỉ assert HTTP status hoặc object tồn tại.
3. Default CI hoàn toàn deterministic, không gọi mạng và không cần credential
   thật. Live smoke chạy ở job riêng, manual/nightly và có cost cap.
4. Dùng parameterized test với ID đọc được, ví dụ
   `destructive__high__double-confirm__escalate`; mỗi ID ánh xạ được về cell
   CERTUS.
5. Chỉ sinh tổ hợp hợp lệ. Không tăng grid bằng Cartesian product vô nghĩa;
   danh sách 177 cell phải được review và gắn risk tier trước khi viết test.
6. Fixture phải synthetic/redacted. Không đưa prompt, email body, token hoặc
   provider response chứa dữ liệu thật vào log hay artifact CI.
7. Bug tìm thấy khi viết matrix phải có regression test đỏ trước, sau đó tách
   issue sửa production code. Không nới expected result để làm test xanh.

## 4. Ma trận hành vi tối thiểu

### Tool impact và quyết định

| Tool level / tình huống | Policy bắt buộc | HITL/side-effect invariant |
| --- | --- | --- |
| Safe read | `allow`; `show_warning` khi coverage partial | Không có external write; permission/scope fail phải block |
| Internal computation | `allow`; `show_warning` khi coverage partial | Không có external write; output vẫn qua grounding |
| Draft | `draft_only` | Chỉ preview, không execute dù confidence = 1,0 |
| External write | `require_approval` | Luôn có reviewer approval gắn đúng request/idempotency key; timeout/reject không execute |
| Destructive | `require_double_confirmation` | Hai xác nhận độc lập, timeout mặc định deny/escalate |
| Unknown tool | Fail closed như external write | Không được auto-run; phải escalate |
| High-risk domain | `require_double_confirmation` | Confidence cao không được bypass |

### Confidence boundary

Test ít nhất các giá trị `None`, `0`, ngay dưới/trên `0.50`, `0.70`, `0.85`,
`0.90`, `0.95`, `1.0`, cùng hai giá trị invalid ngoài `[0, 1]`.

Lưu ý: `confidence_band()` dùng các mốc 0.50/0.70/0.85/0.95, còn
`ConfidenceRouter` dùng 0.70/0.90. Test phải thể hiện đây là hai contract khác
nhau, tránh vô tình đồng nhất hai bộ ngưỡng.

### Precedence của safety gate

Các case sau phải giữ nguyên kết quả bất kể confidence cao:

| Điều kiện | Kết quả tối thiểu |
| --- | --- |
| Permission fail hoặc scope fail | `block`, không side effect |
| Citation fail | `block`, không render/execute |
| Evidence missing | `abstain` |
| Evidence conflict | `uncertain`, yêu cầu review |
| Coverage partial | Warning cho read/compute; approval không bị hạ cho write |
| External write | Approval bắt buộc |
| Destructive hoặc high-risk domain | Double confirmation và escalate |

## 5. Kế hoạch theo pha

### Pha 0 — Khóa baseline và tái lập môi trường (P0)

Mục tiêu: một checkout sạch chạy được đúng suite và sinh được evidence mà không
cài tay.

- Lưu metadata của baseline: commit SHA, Python/OS, include/exclude scope,
  lệnh pytest/CERTUS, denominator và report artifacts.
- Export danh sách 177 valid cell, gắn `critical/high/normal` và expected result.
- Chọn một dependency source of truth: `pyproject.toml` với dev extra hoặc
  runtime + dev requirements; không duy trì hai hướng dẫn mâu thuẫn.
- Thêm và khóa dependency test/coverage/CERTUS cần thiết. CI phải tạo môi trường
  sạch chỉ từ file đã commit.
- Chuẩn hóa một lệnh local cho lint + deterministic tests + coverage; cập nhật
  README và `scripts/setup.sh` theo cùng lệnh.
- Đổi live LLM test sang marker `live_external`; default suite deselect rõ ràng.
  Tạo manual/nightly smoke job riêng nếu credential đã được quản trị.

Exit criteria:

- Fresh clone/clean venv chạy deterministic suite thành công, không cài thêm
  package bằng tay.
- Default suite có 0 skip; live test được deselect có chủ đích hoặc chạy ở job
  riêng. Mọi `xfail` phải `strict`, có Jira issue và ngày hết hạn.
- Coverage và CERTUS report được upload thành artifact, có commit SHA.

### Pha 1 — Guardrail và HITL matrix (P0)

Mục tiêu: chặn mọi tổ hợp có thể gây side effect ngoài ý muốn.

Tách test theo contract thay vì tiếp tục dồn vào `tests/test_guardrail.py`:

- `tests/test_guardrail/test_policy_matrix.py`: tool classification, unknown
  tool, policy decision, precedence gate và full boundary confidence.
- `tests/test_guardrail/test_hitl_matrix.py`: route theo confidence/tool impact;
  approve/reject/timeout; auto-send override invalid; provider-prefixed name.
- `tests/test_guardrail/test_hitl_audit.py`: hash-chain tamper, request binding,
  replay, idempotency, nested sensitive field và redaction.
- `tests/test_guardrail/test_output_grounding.py`: missing/unknown/revoked
  citation, conflict, partial coverage và permission đổi ngay trước execute.

Các test quan trọng nhất:

- External write ở mọi confidence band vẫn yêu cầu approval và route escalate.
- Destructive ở mọi confidence band vẫn double-confirm; thiếu một confirmation
  không execute.
- Unknown hoặc provider-prefixed dangerous tool fail closed.
- Reject/timeout không thể đổi thành approved sau retry hoặc replay request cũ.
- Approval chỉ hợp lệ với đúng request ID, payload/diff và idempotency key đã
  review; payload đổi phải xin lại approval.
- Audit từ chối dữ liệu nhạy cảm ở mọi độ sâu, không chỉ key top-level; error
  message cũng không chứa raw value.

Exit criteria:

- 100% valid CERTUS cell có `external_write`, `destructive`, `block`,
  `require_approval`, `require_double_confirmation` hoặc `escalate` được canh.
- Mỗi giá trị của cả bốn trục xuất hiện trong ít nhất một assertion độc lập.
- Grid coverage tổng đạt tối thiểu 35% (ít nhất 62/177), tức hơn 15 lần baseline.
- Không còn nhánh critical chỉ được chạm dòng mà không assert side effect.

### Pha 2 — Auth, authorization và privacy (P0/P1)

Mục tiêu: token, role hoặc scope sai không đọc/ghi được dữ liệu và không rò bí
mật qua response/telemetry/log.

- Token: access/refresh hết hạn, sai signature/type/issuer/audience, refresh
  replay/rotation, account bị khóa sau khi token được cấp.
- Role: participant/mentor/admin cho từng protected endpoint; role đổi giữa hai
  request; không tự nâng quyền qua request payload.
- Ownership: parameterize hai user trên connections, sources, runs, tasks,
  conversations, storage và admin; response dùng 403/404 đúng contract và không
  tiết lộ object tồn tại.
- OAuth: state hết hạn, state sai user/provider, state replay, callback thiếu
  code, provider revoke và encrypted credential không xuất hiện trong API/log.
- Privacy: nested object, exception, validation error, telemetry attribute,
  Prometheus label và audit details đều không chứa token/content/PII.

Exit criteria:

- Cross-user leak = 0 và unsafe write = 0 trong suite.
- Mỗi protected resource có ít nhất unauthenticated, wrong role và wrong owner.
- Security regression test kiểm cả response body, log capture và side-effect spy.

### Pha 3 — Provider failure, retry và idempotency (P1)

Mục tiêu: lỗi ngoài hệ thống không làm mất dữ liệu, lặp side effect hoặc tạo kết
quả giả là hoàn tất.

- LLM: malformed/empty/partial response, timeout, 429, 5xx, auth error, tất cả
  provider cùng fail, retry budget và tool binding qua failover.
- Gmail/Discord/Telegram: pagination timeout, 429/retry-after, 401/revoke,
  response thiếu field, duplicate event và partial source coverage.
- Run/action: cùng key+cùng payload; cùng key+khác payload; cùng key ở hai user;
  concurrent duplicate; crash sau write trước ACK; retry chỉ tạo một side effect.
- Storage/database/observability: unavailable, permission denied, timeout và
  missing env; startup hoặc request phải fail rõ/fail closed theo contract.
- Golden fixture phải bao gồm các case GML-017/DSC-018 đã mô tả trong
  `eval/golden_dataset/fetch_norm_filter/README.md`.

Exit criteria:

- Retry duplicate = 0 và action-before-confirm = 0.
- Source lỗi tạo `partial`/`unknown`, không bao giờ báo `complete` giả.
- Grid coverage đạt tối thiểu 60% (ít nhất 107/177); mọi cell critical/high còn
  thiếu có owner và Jira issue.

### Pha 4 — CI gate và release evidence (P1)

Mục tiêu: kết quả trên máy phát triển và CI sạch giống nhau, regression quan
trọng chặn merge.

- Chỉ đo production scope đã thống nhất, tối thiểu `src/`; không tính test vào
  numerator để làm đẹp tỷ lệ. Tách coverage của script nếu script là production.
- Bật branch coverage để bắt nhánh allow/deny, không chỉ line coverage.
- Đặt threshold theo hai bước: 85% sau Pha 1, 90% sau Pha 3. Không hạ threshold
  trong PR nếu không có approval của QA + Technical Lead.
- PR chạy deterministic unit/contract và CERTUS critical subset; nightly chạy
  full grid/golden set; release chạy E2E dangerous-action journeys.
- Upload JUnit, coverage XML/HTML, CERTUS grid report và danh sách skip/deselect.
- So sánh baseline theo commit; report phải nêu cell mới được canh và cell bị
  mất, không chỉ tỷ lệ tổng.

Release blocker:

- Có test đỏ, unexpected skip/xfail, cross-user leak, unsafe action, duplicate
  external write, false-complete coverage hoặc critical CERTUS cell chưa canh.
- Line coverage đạt số nhưng critical grid chưa đạt vẫn không được xem là
  production-ready.

## 6. Jira issue seeds theo thứ tự ưu tiên

Tạo issue trong Jira; bảng này chỉ là breakdown đề xuất, không lưu trạng thái
thực thi trong Markdown.

| Thứ tự | Issue seed | Priority | Acceptance chính |
| ---: | --- | --- | --- |
| 1 | `[QA] Freeze CERTUS baseline và export 177-cell risk map` | P0 | Có SHA, scope, commands, valid-cell manifest và risk tier |
| 2 | `[DevEx] Clean environment + dependency lock + one-command test` | P0 | CI sạch không cài tay; README/setup thống nhất |
| 3 | `[Safety] Tool policy decision matrix` | P0 | Toàn bộ critical tool/decision cell được assert |
| 4 | `[Safety] HITL route, reviewer decision và timeout matrix` | P0 | Reject/timeout/double-confirm không execute |
| 5 | `[Safety] Approval binding, replay và idempotency` | P0 | Approval cũ/payload đổi/retry không tạo write |
| 6 | `[Security] Auth token expiry, refresh replay và role matrix` | P0 | Token/role sai fail closed |
| 7 | `[Security] Cross-user resource isolation matrix` | P0 | Connections/sources/runs/tasks/conversations/storage không leak |
| 8 | `[Privacy] Recursive redaction across audit/log/telemetry/errors` | P0 | Không raw secret/PII ở output hoặc artifact |
| 9 | `[Resilience] LLM malformed, timeout và all-provider failure` | P1 | Bounded retry, safe error/abstain, không mất tool binding |
| 10 | `[Resilience] Connector timeout/revoke/pagination/duplicate` | P1 | Partial coverage đúng, retry không duplicate |
| 11 | `[CI] Coverage/CERTUS gates and artifacts` | P1 | Threshold staged, critical subset chặn PR |
| 12 | `[E2E] Dangerous-action killer journeys` | P1 | Preview/edit/approve/reject/timeout/source-change đều có evidence |

## 7. Definition of Done cho từng test issue

- Risk/requirement và expected invariant được link, không chỉ ghi tên function.
- Có ít nhất happy path, negative/error path và boundary tương ứng.
- Test assert output **và** absence/presence của side effect, audit, log khi áp
  dụng.
- Case có stable parameter ID và ánh xạ về CERTUS cell/risk tier.
- Không gọi mạng thật trong default suite; fixture synthetic hoặc redacted.
- Chạy xanh khi chạy riêng, chạy theo module và chạy full deterministic suite.
- Nếu phát hiện bug production: có regression test, Jira bug và evidence
  before/after; không sửa expected để che bug.
- PR cập nhật manifest/evidence và không làm mất cell đã được canh.

## 8. Mốc đo đề xuất

| Checkpoint | Line coverage | Grid coverage | Điều kiện quan trọng hơn tỷ lệ |
| --- | ---: | ---: | --- |
| Baseline | 79,8% | 2,3% (4/177) | 201 passed, 1 skipped |
| Sau Pha 0 | Không giảm | Không giảm | Clean setup; default suite không unexpected skip |
| Sau Pha 1 | ≥85% production scope | ≥35% (≥62/177) | 100% critical guardrail/HITL cell |
| Sau Pha 3 | ≥90% production scope | ≥60% (≥107/177) | 0 unsafe action/leak/duplicate write |
| Trước release | Không giảm | Tăng hoặc giữ; mọi gap có risk acceptance | Full E2E + golden + CERTUS evidence, blocker = 0 |

Các mốc raw grid là floor để tránh đứng yên ở 2,3%, không phải lý do để viết
test vô nghĩa. Nếu 177 cell gồm tổ hợp không reachable hoặc không hợp lệ, QA
phải adjudicate và version denominator trước khi loại; không tự đánh dấu N/A để
làm tăng tỷ lệ.

## 9. Thứ tự bắt đầu khuyến nghị

Trong sprint đầu chỉ nhận issue 1–5 và 8. Đây là lát cắt nhỏ nhất tạo giá trị an
toàn ngay: khóa cách đo, dựng được môi trường sạch, rồi phủ external
write/destructive/HITL và data leak. Auth/provider/E2E tiếp tục sau khi matrix
và CI artifact đã ổn định để mọi test mới đều đóng góp evidence có thể so sánh.
