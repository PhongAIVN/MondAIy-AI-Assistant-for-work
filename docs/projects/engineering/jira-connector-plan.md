# Kế hoạch end-to-end — Jira connector

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Draft |
| Owner | Nguyễn Văn Phong (Technical Lead) |
| Author | Nguyễn Văn Phong |
| Reviewers | Thái Hoài An (PM) · Nguyễn Đức Dũng (PO/QC) · Lê Thị Yến Nhi (UI/UX Lead) |
| Last updated | 2026-08-09 |
| Source of truth | Không — kế hoạch thi công, nguồn chuẩn scope vẫn là [ADR-002](adr/adr-002-connector-first-p0-scope.md) · [PRD FR-021](../product/prd.md) |
| Related | [ADR-002](adr/adr-002-connector-first-p0-scope.md) · [ADR-003](adr/adr-003-gmail-va-discord-truoc-trong-hai-tuan-build.md) · [API contract pipeline](api-contract-pipeline.md) · [Discord connector spike](discord-connector-spike.md) |

## Trạng thái implement (2026-08-09)

Code đã viết xong hết CPJ-0 đến CPJ-4 (không chia việc theo người, tự làm
end-to-end). 19 test mới, 194/194 pass toàn repo. **Chưa xong thật sự** vì:

- Chưa đăng ký app trên Atlassian Developer Console — `JIRA_CLIENT_ID`/
  `JIRA_CLIENT_SECRET` vẫn rỗng, OAuth chưa chạy được với site thật.
- Chưa test end-to-end với 1 site Jira sandbox thật (chỉ test bằng dữ liệu
  synthetic).
- Chưa có review của An/Dũng/Nhi — đặc biệt Dũng cần soạn fixture QC thật
  (không lặp lỗi "fixture mồ côi" đã gặp ở Gmail).
- Icon Jira trong FE là SVG placeholder tự vẽ, chưa phải asset thiết kế
  chính thức từ Nhi.

## Bối cảnh

Jira nằm trong 5 nguồn P0 đã duyệt (ADR-002), có yêu cầu rõ (FR-021: đọc
issue, assignee, hạn chót, trạng thái, thời điểm thay đổi trong dự án được
cấp quyền) — nhưng chưa có dòng code nào. Research xác nhận: không connector,
không OAuth service, không env var, không test, không UI, không spike kỹ
thuật nào tồn tại. Sạch hoàn toàn, chỉ có interface chung `BaseConnector`
(`src/connectors/base.py`) để tái dùng.

Plan 2 tuần gốc (ADR-003) chỉ cam kết Gmail rồi Discord — Jira là **giai đoạn
mới sau Checkpoint 3**, cần An biết trước khi xếp lịch, nhưng thiết kế kỹ
thuật do Phong quyết.

**Phát hiện lúc research — chặn dùng chung, không riêng Jira:** 3 chỗ hardcode
"chỉ chấp nhận Gmail" hiện đang chặn luôn cả Discord đã build sẵn OAuth:

1. `src/agents/pipeline/nodes/fetch.py:36` — raise nếu `provider != "google"`.
2. `src/services/filter_classify.py:121` — loại item nếu `deep_link` không
   bắt đầu `"https://mail.google.com/"`.
3. `src/api/runs.py:87` (`_build_brief`) — evidence lọc theo cùng điều kiện,
   Jira evidence sẽ biến mất khỏi brief nếu không gỡ.

Phải gỡ ở CPJ-0 trước khi làm Jira, không phải việc "tiện thể".

## Quyết định đã chốt

- **Auth: OAuth 2.0 3LO** — đồng bộ UX Gmail/Discord (nút Connect, không bắt
  user tự tạo token dán vào).
- **Phạm vi: đợt build riêng sau CP3**, không gộp sprint hiện tại.
- **Không sửa schema pipeline chung** (`filtered_message`/`extracted_item`/
  `resolved_item`) — Jira map vào đúng shape Gmail đang dùng, theo nguyên tắc
  ADR-003 "sửa schema cho vừa 1 nguồn tức là schema chưa đủ tổng quát".
- **Không đọc changelog per-issue ở P0** — `fields.updated` đủ cho "thời điểm
  thay đổi", đọc chi tiết field nào đổi là mở rộng sau.

## Việc cần làm thủ công trước khi code (không phải code, nhưng chặn code)

- Đăng ký app trên [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/)
  — lấy `client_id`/`client_secret`, khai redirect URI
  `{APP_PUBLIC_URL}/api/v1/connections/jira/callback`.
- Xin site Jira Cloud sandbox (Atlassian cấp free trial) để test OAuth thật
  — không test bằng site production của ai.
- Thêm `JIRA_CLIENT_ID`, `JIRA_CLIENT_SECRET` vào `.env.example` (rỗng) và
  `.env` cục bộ (giá trị thật, không commit).

## Lộ trình — 5 ticket, theo đúng khuôn Jira team đang dùng

### CPJ-0 (Phong) — Gỡ chốt chặn dùng chung

**Outcome:** Discord và Jira không còn bị chặn cứng ở tầng pipeline.
**Việc:** `fetch.py` đổi if/raise thành factory theo `connection.provider`;
`filter_classify.py` và `runs.py` đổi hardcode domain Gmail thành whitelist
theo provider.
**Input:** Pipeline hiện tại (chỉ chạy Gmail).
**Điều kiện dừng:** Toàn bộ test cũ vẫn pass; thêm test xác nhận factory chọn
đúng connector theo provider và không đổi hành vi Gmail.
**Ràng buộc:** Không đổi output/behavior của luồng Gmail hiện có.

### CPJ-1 (Phong) — OAuth 2.0 3LO + schema

**Outcome:** Người dùng bấm Connect Jira, chọn site, token lưu mã hoá.
**Việc:** Viết `src/services/connections/jira.py` (mirror `google.py`);
resolve `cloudId` qua `GET /oauth/token/accessible-resources`; thêm cột
`Connection.external_site_id`; thêm `"jira"` vào `_PROVIDERS`/`ConnectionProvider`;
route callback trong `connections.py`.
**Input:** CPJ-0 xong; app Atlassian đã đăng ký (bước thủ công ở trên).
**Điều kiện dừng:** OAuth thật chạy được với 1 site sandbox; `GET /connections`
trả về `jira` connected kèm `accountLabel` là tên site.
**Ràng buộc:** Chỉ scope đọc (`read:jira-work read:me offline_access`), không
xin scope ghi. Token mã hoá bằng `crypto.py` sẵn có, không lưu plaintext.

### CPJ-2 (Phong) — `JiraConnector`: list_sources / fetch_range / normalize

**Outcome:** `filtered_message` thật cho Jira, có provenance.
**Việc:** `src/connectors/jira.py` implement `BaseConnector`; viết
`_extract_adf_text()` đệ quy cho Atlassian Document Format; nối
`fields.duedate` thành câu tường minh trong `text` để `resolve_due_at()` bắt
được không cần sửa gì; cap tổng số issue liệt kê + retry 429 **ngay từ đầu**
(rút kinh nghiệm 4 fix phải vá sau ở Gmail).
**Input:** CPJ-1 xong.
**Điều kiện dừng:** `test_jira_normalize.py` pass; fetch được ít nhất 1
project Jira thật (sandbox) đi hết `fetch_range` → `normalize`.
**Ràng buộc:** Không đọc changelog per-issue; không ghi ngược Jira (đúng
ADR-002, chỉ đọc).

### CPJ-3 (Dũng) — Test crawl/normalize/filter cho Jira

**Outcome:** Test pass; biên bản duyệt checkpoint Jira.
**Việc:** Soạn fixture thật cho Jira (không lặp lỗi "mồ côi" — 18 fixture
Gmail hiện có chưa từng được test nào chạy qua, phải tránh lặp lại); review
case biên: issue không có assignee, không có duedate, ADF rỗng, mô tả có
bảng/hình.
**Input:** CPJ-2 chạy được.
**Điều kiện dừng:** 1 batch issue Jira thật đi hết crawl → normalize → filter,
xem lại được provenance (deep_link mở đúng issue trên Jira).
**Ràng buộc:** Fixture phải synthetic hoặc redact, không chứa dữ liệu Jira
thật của tổ chức nào.

### CPJ-4 (Nhi) — FE thêm provider Jira

**Outcome:** UI chọn nguồn Jira dùng dữ liệu thật, không mock.
**Việc:** `types/pipeline.ts` thêm `'jira'` vào `ConnectionProvider`/
`PROVIDER_LABEL`/`ENABLED_PROVIDERS`; thêm icon Jira; nối màn Thư viện nguồn
với `GET /connections` đã có `jira`.
**Input:** CPJ-1/CPJ-2 xong, API `/integrations/{id}/sources` trả project Jira.
**Điều kiện dừng:** Chọn được project Jira trong `/run`, chạy 1 run thật ra
task.
**Ràng buộc:** Theo đúng convention `api-contract-pipeline.md` — cập nhật tài
liệu đó song song nếu response shape đổi (xem mục dưới).

## Tài liệu cần cập nhật song song (Documentation Guide — material change)

- [`api-contract-pipeline.md`](api-contract-pipeline.md) — thêm mục Jira vào
  bảng `provider`, mô tả `sources` trả về là project key/name.
- `docs/projects/engineering/README.md` — thêm link tài liệu này vào index.
- Nếu thêm ADR riêng cho quyết định OAuth 3LO (không bắt buộc, PRD/ADR-002 đã
  đủ cho phạm vi nguồn — chỉ cần nếu Dũng/An muốn có quyết định ghi riêng).

## Rủi ro / mở còn lại — chưa tự chốt

- **ADF parsing**: viết tay hàm nhỏ (đề xuất, nhất quán style Gmail, không
  thêm dependency) hay dùng thư viện Atlassian chính thức? Cần Phong xác nhận
  trước khi code CPJ-2.
- **Nhiều Jira site cho 1 user** (multi-cloud) — pilot bỏ qua, backlog sau.
- **Tên cột** `external_site_id` (generic, đề xuất) hay `jira_site_url`
  (đặt tên riêng)?

## Ước lượng thô (không phải story point chính thức — An/Dũng tự xếp trên Jira)

CPJ-0 và CPJ-1 nặng nhất (OAuth mới hoàn toàn + schema). CPJ-2 lặp lại đúng
pattern đã làm với Gmail nên nhanh hơn. CPJ-3/CPJ-4 phụ thuộc CPJ-1/2 xong
trước, không chạy song song được với backend.

## Verification — chạy sau khi implement từng ticket, chưa chạy bây giờ

1. `pytest tests/test_connectors/test_jira_normalize.py -v`
2. `pytest tests/test_agents/ tests/test_api/ -q` — xác nhận factory ở
   `fetch.py` không phá luồng Gmail.
3. OAuth thật với site Jira sandbox — xác nhận `cloudId` resolve đúng.
4. `pytest -q` toàn repo trước khi coi 1 ticket là xong.
