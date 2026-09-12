
# 6. Domain Candidates

## 6.1 Identity & Consent Domain

### Trách nhiệm

Domain này quản lý danh tính người dùng, hồ sơ cá nhân, vai trò trong chương trình, quyền truy cập và sự đồng ý cho từng nguồn dữ liệu.

Nó trả lời các câu hỏi:

- Người dùng là ai?
- Người dùng thuộc chương trình, nhóm, vai trò nào?
- Người dùng đã cho phép mondaiy đọc nguồn nào?
- Quyền đó còn hiệu lực không?
- Người dùng đã thu hồi, tạm dừng hay xóa dữ liệu nào?

### Sở hữu dữ liệu

- `users`
- `profiles`
- `profile_versions`
- `consents`
- `source_permissions`
- `user_roles`
- `memberships`
- `access_scopes`

### Được phép làm

- Tạo và cập nhật hồ sơ người dùng.
- Lưu consent theo từng nguồn.
- Thu hồi consent.
- Cung cấp API kiểm tra quyền cho domain khác.
- Ghi lại lịch sử đổi quyền.
- Trả về phạm vi dữ liệu mà user còn được phép dùng.

### Không được làm

- Không tự đồng bộ dữ liệu từ Gmail, Discord, Jira, VLearn hoặc Calendar.
- Không đọc nội dung nguồn.
- Không tạo evidence.
- Không tạo memory chính thức từ dữ liệu nguồn.
- Không sinh câu trả lời AI.
- Không tạo reminder hoặc calendar handoff.

### Boundary

Các domain khác muốn dùng dữ liệu cá nhân hoặc nguồn đã kết nối phải hỏi domain này trước.

```text
Other Domain
  → checkUserAccess(user_id, source_id, scope)
  → Identity & Consent Domain
  → allowed / denied
```

Không domain nào được tự kiểm tra quyền bằng cách đọc trực tiếp bảng consent rồi diễn giải riêng. Logic consent phải tập trung ở domain này.

---

## 6.2 Source Connector Domain

### Trách nhiệm

Domain này quản lý việc kết nối và đồng bộ dữ liệu từ các nguồn P0: Calendar, Jira, Discord, VLearn và Gmail.

Nó trả lời các câu hỏi:

- Nguồn nào đang kết nối?
- Lần đồng bộ gần nhất là khi nào?
- Connector có lỗi không?
- Item nào mới được lấy về?
- Item nào bị gửi lại?
- Connector nào đủ ổn định để bật trong pilot?

### Sở hữu dữ liệu

- `source_connections`
- `ingestion_jobs`
- `capture_events`
- `sync_receipts`
- `connector_runs`
- `connector_errors`
- `external_source_tokens` hoặc token reference nếu có
- `source_status`

### Được phép làm

- Gọi API của Calendar, Jira, Discord, VLearn, Gmail theo quyền đã cấp.
- Nhận webhook hoặc chạy sync định kỳ.
- Chuẩn hóa dữ liệu nguồn ở mức tối thiểu.
- Tính `content_hash` để phát hiện trùng hoặc thay đổi.
- Đẩy item sang Evidence & Versioning Domain.
- Ghi trạng thái đồng bộ: `success`, `failed`, `partial`, `unknown`.
- Tắt/bật connector bằng feature flag.

### Không được làm

- Không tự quyết định một item là task chính thức.
- Không tự tạo memory.
- Không tự tạo briefing.
- Không tự trả lời người dùng.
- Không tự tạo action draft.
- Không tự resolve mâu thuẫn giữa hai nguồn.
- Không bỏ qua consent check.
- Không lưu cookie, mật khẩu hoặc session trình duyệt.

### Boundary

Connector chỉ là cửa vào dữ liệu. Nó không sở hữu “sự thật nghiệp vụ”.

```text
External Source
  → Source Connector Domain
  → raw/normalized source item
  → Evidence & Versioning Domain
```

Connector Domain phải gọi Identity & Consent Domain trước khi đồng bộ. Nếu consent bị thu hồi, connector phải dừng sync mới.

---

## 6.3 Evidence & Versioning Domain

### Trách nhiệm

Đây là domain lõi nhất của mondaiy. Nó lưu bằng chứng gốc, phiên bản, provenance, citation và lịch sử thay đổi của item.

Nó trả lời các câu hỏi:

- Thông tin này đến từ nguồn nào?
- Nội dung gốc là gì?
- Được quan sát lúc nào?
- Nguồn cập nhật lúc nào?
- Phiên bản trước là gì?
- Có bị thay thế hay mâu thuẫn không?
- Citation có mở lại được không?

### Sở hữu dữ liệu

- `documents`
- `document_versions`
- `chunks`
- `information_items`
- `information_item_versions`
- `citations`
- `evidence_links`
- `source_item_versions`
- `provenance_records`
- `supersession_links`
- `conflict_links`

### Được phép làm

- Lưu raw evidence.
- Lưu nội dung đã chuẩn hóa.
- Tạo phiên bản mới khi `content_hash` thay đổi.
- Không tạo bản trùng khi cùng một item được gửi lại.
- Đánh dấu item cũ là `superseded` khi có bản mới.
- Liên kết các item mâu thuẫn.
- Cung cấp evidence cho Briefing, Ask, Memory và Action Draft.
- Kiểm tra citation có đúng nguồn không.

### Không được làm

- Không tự sinh câu trả lời cuối cho người dùng.
- Không tự quyết định nguồn nào đúng hơn nếu có mâu thuẫn.
- Không tự biến evidence thành memory chính thức.
- Không tự tạo reminder hoặc calendar event.
- Không xóa evidence im lặng nếu chưa đi qua chính sách retention/delete rõ ràng.
- Không cho domain khác ghi đè phiên bản cũ.

### Boundary

Evidence là nguồn sự thật kỹ thuật, nhưng không phải nơi quyết định hành động.

```text
Connector Domain
  → createEvidence(source_item)

Briefing & Ask Domain
  → searchEvidence(query, user_scope)

Memory Domain
  → linkMemoryToEvidence(memory_id, evidence_id)

Action Draft Domain
  → createDraftFromEvidence(evidence_id)
```

---

## 6.4 Program Context Domain

### Trách nhiệm

Domain này quản lý ngữ cảnh chương trình học: khóa học, cohort, mentor, nhóm, vai trò, milestone, deliverable và mức độ đáng tin của từng nguồn.

Nó trả lời các câu hỏi:

- Người dùng đang thuộc chương trình nào?
- Vai trò của họ là gì?
- Họ thuộc nhóm nào?
- Milestone hiện tại là gì?
- Nguồn nào là official source?
- Nguồn nào chỉ là tham khảo?
- Một item có liên quan tới người dùng này không?

### Sở hữu dữ liệu

- `programs`
- `program_frames`
- `program_frame_versions`
- `teams`
- `roles`
- `memberships`
- `milestones`
- `deliverables`
- `source_authority_rules`

### Được phép làm

- Lưu Program Frame.
- Lưu mapping giữa user, team, role, mentor.
- Xác định mức thẩm quyền của nguồn: official/reference.
- Cung cấp rule lọc thông tin theo vai trò và nhóm.
- Cung cấp context cho Briefing & Ask Domain.

### Không được làm

- Không đọc trực tiếp Gmail/Jira/Discord.
- Không tự tạo evidence.
- Không tự trả lời người dùng.
- Không tự sửa source authority bằng suy luận AI.
- Không tự quyết định một thông tin mâu thuẫn là đúng nếu chưa có rule hoặc người xác nhận.

### Boundary

Program Context chỉ cung cấp khung lọc và mức độ đáng tin, không tạo claim mới.

```text
Briefing & Ask Domain
  → getProgramContext(user_id)
  → Program Context Domain
  → program frame, role, team, source authority
```

Nếu Discord nói deadline A và VLearn nói deadline B, Program Context có thể nói VLearn là nguồn official hơn, nhưng Briefing vẫn phải hiển thị mâu thuẫn, không được ẩn giá trị còn lại.

---

## 6.5 Memory Domain

### Trách nhiệm

Domain này quản lý những gì mondaiy “ghi nhớ” về người dùng hoặc chương trình sau khi đã có evidence hoặc xác nhận của user.

Nó trả lời các câu hỏi:

- Đây là thông tin tự khai báo, đã xác nhận, hay chỉ là suy luận?
- Memory này dựa trên evidence nào?
- Memory còn hiệu lực không?
- Memory có bị thay thế không?
- Người dùng đã sửa, xác nhận, bác bỏ hay xóa chưa?

### Sở hữu dữ liệu

- `memory_candidates`
- `memories`
- `memory_versions`
- `memory_evidence`
- `memory_feedback`
- `memory_status_changes`

### Được phép làm

- Tạo memory candidate từ evidence.
- Liên kết memory với evidence.
- Đánh dấu trạng thái: `proposed`, `confirmed`, `rejected`, `superseded`, `deleted`.
- Lưu version của memory.
- Cho người dùng xác nhận, sửa, bác bỏ hoặc xóa.
- Cung cấp memory đã được phép dùng cho Briefing & Ask.

### Không được làm

- Không tạo memory chính thức nếu không có evidence hoặc user confirmation.
- Không trình bày inferred preference như confirmed fact.
- Không đọc nguồn ngoài connector.
- Không bỏ qua revoke/delete.
- Không tạo action.
- Không tự nâng độ tin cậy thành `confirmed` nếu chưa đủ điều kiện.

### Boundary

Memory không thay thế Evidence. Mọi memory chính thức phải có đường về evidence hoặc user confirmation.

```text
Evidence & Versioning Domain
  → evidence

Memory Domain
  → memory_candidate
  → confirmed memory only after rule/user confirmation
```

---

## 6.6 Briefing & Ask Domain

### Trách nhiệm

Domain này sinh bản tóm lược hằng ngày và trả lời câu hỏi của người dùng bằng dữ liệu đã được phép.

Nó trả lời các câu hỏi:

- Hôm nay có gì cần chú ý?
- Có gì thay đổi từ bản tóm lược trước?
- Việc nào của tôi?
- Có nguồn nào mâu thuẫn không?
- Câu trả lời có evidence không?
- Nếu không đủ evidence thì có nên từ chối trả lời không?

### Sở hữu dữ liệu

- `briefs`
- `brief_items`
- `conversations`
- `messages`
- `answer_records`
- `answer_feedback`
- `source_coverage_snapshots`

### Được phép làm

- Tìm evidence người dùng còn quyền mở.
- Dùng Program Context để lọc theo vai trò, nhóm, milestone.
- Dùng Memory đã hợp lệ để cá nhân hóa nội dung.
- Sinh daily briefing.
- Trả lời câu hỏi có citation.
- Từ chối trả lời khi không đủ bằng chứng.
- Hiển thị trạng thái coverage: `complete`, `partial`, `unknown`.
- Hiển thị mâu thuẫn thay vì tự chọn một bên.

### Không được làm

- Không gọi trực tiếp API Gmail/Jira/Discord/VLearn/Calendar.
- Không dùng dữ liệu đã revoke hoặc đã xóa.
- Không bịa deadline, owner, requirement hoặc status.
- Không ẩn mâu thuẫn.
- Không tạo external action.
- Không lưu raw email/message/question/answer vào product analytics.
- Không tự quyết định hành động thay người dùng.

### Boundary

Briefing & Ask chỉ được đọc qua Evidence, Memory và Program Context. Nó không được đi vòng qua Connector.

```text
User question
  → Briefing & Ask Domain
  → check access
  → search evidence
  → get program context
  → get allowed memory
  → answer with citation or abstain
```

---

## 6.7 Action Draft Domain

### Trách nhiệm

Domain này biến thông tin có nguồn thành bản nháp hành động an toàn: nhắc việc trong app, `.ics`, hoặc calendar handoff.

Nó trả lời các câu hỏi:

- Có đủ thông tin để tạo bản nháp chưa?
- Thiếu ngày, giờ, timezone hoặc owner không?
- User đã xem trước chưa?
- User đã sửa chưa?
- User đã xác nhận chưa?
- Hành động đã được handoff hay mới là draft?

### Sở hữu dữ liệu

- `action_drafts`
- `reminders`
- `calendar_handoffs`
- `action_state_transitions`
- `draft_idempotency_keys`

### Được phép làm

- Tạo action draft từ evidence.
- Để trống field còn mơ hồ.
- Cho user xem trước và sửa.
- Chuyển trạng thái: `drafted`, `previewed`, `confirmed`, `handoff_opened`, `completed`, `cancelled`.
- Tạo reminder trong app sau khi user xác nhận.
- Tạo `.ics` hoặc mở calendar handoff sau khi user xác nhận.
- Chống tạo draft trùng khi request lặp lại.

### Không được làm

- Không tự gửi tin nhắn.
- Không tự tạo Google Calendar event trực tiếp trong P0.
- Không tự update hoặc delete external calendar event.
- Không tự điền thời gian mơ hồ như fact.
- Không tạo handoff trước khi user xác nhận.
- Không sửa/hủy action đã xác nhận chỉ vì nguồn thay đổi.

### Boundary

AI chỉ được yêu cầu tạo bản nháp, không được gọi công cụ ghi ra ngoài.

```text
Briefing / Answer
  → createActionDraft(evidence_id)
  → Action Draft Domain
  → drafted
  → previewed by user
  → edited by user
  → confirmed by user
  → reminder / .ics / calendar handoff
```

---

## 6.8 Data & Privacy Control Domain

### Trách nhiệm

Domain này cung cấp giao diện và API để người dùng kiểm soát dữ liệu: xem nguồn đang kết nối, tạm dừng capture, disconnect, revoke consent, xóa dữ liệu, xem dữ liệu đã lưu.

Nó trả lời các câu hỏi:

- mondaiy đang đọc nguồn nào?
- Nguồn nào active/paused/error?
- Có bao nhiêu record đã capture?
- Người dùng muốn tạm dừng hay xóa?
- Sau khi xóa/thu hồi, dữ liệu có bị dùng lại không?

### Sở hữu dữ liệu

Domain này có thể không sở hữu toàn bộ dữ liệu nguồn, nhưng sở hữu workflow điều khiển:

- `privacy_requests`
- `deletion_requests`
- `revoke_requests`
- `data_review_sessions`
- `privacy_action_logs`

Nó phối hợp với:

- Identity & Consent để revoke quyền.
- Source Connector để dừng sync.
- Evidence để ẩn/xóa theo policy.
- Memory để xóa hoặc vô hiệu memory.
- Briefing & Ask để không dùng dữ liệu đã revoke/delete.

### Được phép làm

- Hiển thị trạng thái nguồn.
- Tạm dừng toàn bộ capture.
- Disconnect từng nguồn.
- Yêu cầu xóa dữ liệu đã capture.
- Ghi log thao tác quyền riêng tư.
- Kiểm tra sau xóa rằng dữ liệu không xuất hiện trong search mới.

### Không được làm

- Không tự đọc raw private content vào analytics.
- Không cho admin xem chi tiết nội dung riêng tư của user.
- Không xóa âm thầm không audit.
- Không để domain khác tiếp tục retrieval từ dữ liệu đã revoke/delete.

### Boundary

Domain này là control plane cho quyền riêng tư, không phải nơi xử lý AI.

```text
User privacy action
  → Data & Privacy Control Domain
  → update consent / pause connector / delete evidence / invalidate memory
  → audit event
```

---

## 6.9 Audit & Evaluation Domain

### Trách nhiệm

Domain này lưu audit trail, test result, metric vận hành và dữ liệu đánh giá đã loại nội dung nhạy cảm.

Nó trả lời các câu hỏi:

- Ai đã làm gì, lúc nào?
- Connector nào lỗi?
- Citation validator pass/fail?
- Có rò dữ liệu chéo user không?
- Action có bypass confirm không?
- Pilot có cải thiện completion rate không?
- Có case nào cần đưa vào golden dataset không?

### Sở hữu dữ liệu

- `audit_events`
- `feedback`
- `evaluation_runs`
- `test_cases`
- `golden_dataset_cases`
- `metric_events`
- `incident_records`
- `quality_reports`

### Được phép làm

- Lưu metadata vận hành.
- Lưu kết quả test.
- Lưu feedback dạng đã loại nội dung nhạy cảm.
- Ghi audit event cho sync, memory, answer, action, consent.
- Xuất báo cáo validation.
- Theo dõi success/failure criteria.

### Không được làm

- Không lưu raw email.
- Không lưu raw message.
- Không lưu câu hỏi/câu trả lời gốc vào product analytics.
- Không dùng audit log làm nguồn trả lời người dùng.
- Không cho admin đọc nội dung riêng tư chi tiết.
- Không dùng metric để suy luận profile cá nhân ngoài mục đích sản phẩm.

### Boundary

Audit nhận event từ các domain khác, nhưng không điều khiển business flow chính.

```text
Any Domain
  → emitAuditEvent(metadata_only)
  → Audit & Evaluation Domain
```

---

# 7. Cross-domain Boundary Rules

## Rule 1 — Consent đi trước mọi retrieval hoặc sync

Không domain nào được sync, search, generate answer hoặc tạo draft từ dữ liệu nguồn nếu Identity & Consent Domain báo quyền không còn hiệu lực.

```text
Before:
- sync source
- search evidence
- generate briefing
- answer question
- create action draft

Must call:
checkUserAccess(...)
```

Giới hạn:

- Consent theo từng source.
- Revoke phải có hiệu lực với retrieval mới.
- Delete phải loại dữ liệu khỏi search mới.
- Không được cache quyền quá lâu làm sai trạng thái hiện tại.

## Rule 2 — Connector không được tạo sự thật nghiệp vụ

Connector chỉ đưa dữ liệu vào hệ thống. Nó không được quyết định:

- deadline nào là đúng;
- owner nào là chính thức;
- task nào là của user;
- nguồn nào thắng khi mâu thuẫn;
- có nên nhắc user hay không.

Connector chỉ gửi item sang Evidence & Versioning Domain.

## Rule 3 — Evidence là nguồn bắt buộc cho factual claim

Mọi claim kiểu factual phải có citation:

- deadline;
- owner;
- requirement;
- status;
- source update;
- conflict;
- task;
- event time;
- mentor instruction.

Giới hạn:

- Không có evidence thì answer phải abstain.
- Evidence người dùng không còn quyền mở thì không được dùng.
- Citation phải chứng minh đúng claim, không chỉ trỏ về cùng document.

## Rule 4 — Memory không được vượt evidence

Memory giúp cá nhân hóa và ghi nhớ, nhưng không được mạnh hơn evidence.

Giới hạn:

- Official memory phải có evidence hoặc user confirmation.
- Inferred memory phải được gắn nhãn là suy luận.
- Inferred preference không được trình bày như confirmed fact.
- Memory bị xóa hoặc hết hiệu lực không được dùng trong briefing/answer mới.

## Rule 5 — Program Context lọc thông tin, không tự bịa thông tin

Program Context được dùng để lọc theo:

- chương trình;
- cohort;
- team;
- role;
- mentor;
- milestone;
- source authority.

Giới hạn:

- Không được tự tạo deadline nếu không có evidence.
- Không được tự tạo owner nếu không có evidence.
- Không được tự sửa source authority bằng AI.
- Nếu nguồn official và nguồn reference mâu thuẫn, vẫn phải hiển thị conflict.

## Rule 6 — Briefing & Ask không được gọi trực tiếp connector

Briefing & Ask chỉ đọc dữ liệu qua:

- Evidence & Versioning;
- Memory;
- Program Context;
- Identity & Consent.

Giới hạn:

- Không gọi Gmail API trực tiếp.
- Không gọi Discord API trực tiếp.
- Không gọi Jira/VLearn/Calendar trực tiếp.
- Không bỏ qua evidence store để lấy dữ liệu “cho nhanh”.
- Không dùng dữ liệu partial như complete.

## Rule 7 — AI chỉ được diễn giải trong phạm vi evidence

AI được phép:

- tóm tắt;
- xếp hạng mức liên quan;
- diễn đạt lại;
- gợi ý bước tiếp theo;
- tạo draft.

AI không được phép:

- tạo fact mới;
- chọn nguồn thắng trong conflict rồi giấu nguồn còn lại;
- tự nâng confidence;
- tự tạo deadline/owner;
- tự hành động ra ngoài.

## Rule 8 — Action Draft luôn tách khỏi external action

Action Draft Domain chỉ tạo bản nháp trước.

Giới hạn:

- Không reminder nào được scheduled trước khi user confirm.
- Không `.ics` hoặc calendar handoff nào được mở trước khi user confirm.
- Không gửi message.
- Không update/delete external calendar event.
- Field mơ hồ phải để trống.
- Request lặp lại không được tạo draft trùng.

## Rule 9 — Audit chỉ lưu metadata đã an toàn

Audit được dùng để debug, đánh giá và compliance, nhưng không được trở thành kho nội dung riêng tư.

Được lưu:

- source type;
- status;
- latency;
- duplicate true/false;
- error class;
- count;
- actor type;
- state transition;
- citation count;
- abstained true/false.

Không được lưu:

- raw email body;
- raw Discord message;
- raw Gmail thread;
- raw user question;
- raw answer;
- private file content;
- token;
- cookie;
- password.

## Rule 10 — Data ownership phải rõ ràng

Mỗi bảng chỉ có một domain owner chính.

| Table | Owner Domain | Domain khác được làm gì |
|---|---|---|
| `consents` | Identity & Consent | Chỉ đọc qua API check quyền |
| `source_connections` | Source Connector | UI đọc trạng thái, không tự sửa token |
| `information_items` | Evidence & Versioning | Briefing search qua service |
| `memories` | Memory | Briefing đọc memory hợp lệ |
| `briefs` | Briefing & Ask | Audit đọc metadata |
| `action_drafts` | Action Draft | Briefing tạo request, không tự sửa state |
| `audit_events` | Audit & Evaluation | Domain khác chỉ emit event |

## Rule 11 — Cross-user isolation áp dụng ở mọi lớp

Không chỉ database mới kiểm tra quyền. Phải kiểm tra ở:

- database/RLS;
- API;
- search/retrieval;
- display/UI;
- source-open link;
- action draft;
- audit export.

Giới hạn:

- User B không được thấy evidence, memory, conversation, answer hoặc action draft của User A.
- Admin không mặc định được xem nội dung riêng tư chi tiết.
- Operator chỉ xem trạng thái tổng hợp và log đã loại nội dung nhạy cảm.

## Rule 12 — Mở rộng scope phải có ADR mới

Các thay đổi sau không được “lén” đưa vào domain hiện tại:

- đọc trang web bất kỳ;
- theo dõi màn hình;
- đọc lịch sử duyệt web;
- đọc file local;
- desktop app/background agent;
- Messenger/Zalo/Facebook/Slack;
- write integration;
- AI tự hành động không cần confirm;
- admin xem nội dung riêng tư chi tiết;
- đổi PostgreSQL khỏi vai trò canonical evidence store.

Những thay đổi này phải có ADR riêng vì làm thay đổi ranh giới quyền riêng tư và niềm tin sản phẩm.

---

# 8. Domain Interaction Map

```text
User
  → UI / Web App
  → Identity & Consent
  → Source Connector
  → Evidence & Versioning
  → Program Context
  → Memory
  → Briefing & Ask
  → Action Draft
  → Audit & Evaluation
```

Luồng chính của P0:

```text
1. User cấp quyền nguồn
2. Identity & Consent lưu consent
3. Source Connector sync dữ liệu read-only
4. Evidence & Versioning lưu evidence và version
5. Program Context lọc theo khóa học, nhóm, vai trò
6. Memory tạo candidate hoặc dùng memory đã xác nhận
7. Briefing & Ask sinh brief hoặc answer có citation
8. Action Draft tạo bản nháp nếu user muốn hành động
9. Audit & Evaluation ghi metadata an toàn để kiểm tra chất lượng
```

---

# 9. Decision Options

## Option A — Chia ít domain: Connector, AI, Action, User

Ưu điểm:

- Dễ hiểu lúc đầu.
- Ít service/module hơn.
- Build nhanh trong prototype nhỏ.

Nhược điểm:

- Consent dễ bị trộn với user profile.
- Evidence dễ bị trộn với AI answer.
- Memory dễ bị coi như fact.
- Audit dễ lưu nhầm raw content.
- Khó test boundary an toàn.

## Option B — Chia theo technical layer: Frontend, Backend, Database, AI

Ưu điểm:

- Phù hợp cách tổ chức code truyền thống.
- Dễ phân chia theo kỹ năng kỹ thuật.

Nhược điểm:

- Không thể hiện rõ ownership nghiệp vụ.
- Logic consent, evidence, memory, action có thể rải khắp backend.
- Không giúp đội biết bug thuộc domain nào.
- Không phù hợp với mục tiêu test-driven ADR.

## Option C — Chia theo product domain và boundary an toàn

Các domain:

1. Identity & Consent
2. Source Connector
3. Evidence & Versioning
4. Program Context
5. Memory
6. Briefing & Ask
7. Action Draft
8. Data & Privacy Control
9. Audit & Evaluation

Ưu điểm:

- Rõ owner dữ liệu.
- Rõ boundary privacy/safety.
- Dễ viết test theo domain contract.
- Phù hợp vertical slice P0.
- Giảm rủi ro AI bịa hoặc tự hành động.
- Dễ mở rộng connector sau này mà không phá logic answer/action.

Nhược điểm:

- Cần kỷ luật kiến trúc.
- Có thể nhiều module hơn so với prototype nhỏ.
- Cần thống nhất contract giữa domain trước khi code.

## Decision

Chọn **Option C — Chia theo product domain và boundary an toàn**.

Lý do:

- mondaiy là sản phẩm dựa trên niềm tin, evidence và consent, không chỉ là chatbot.
- P0 cần chứng minh được dữ liệu vào từ nguồn nào, dùng vào câu trả lời nào và hành động nào.
- Việc tách Evidence, Memory, Briefing và Action Draft giúp giảm rủi ro lớn nhất: AI nói hoặc làm điều không có nguồn.
- Việc tách Identity & Consent và Data & Privacy Control giúp bảo vệ quyền người dùng ở mọi bước.

---

# 10. Hypothesis

If mondaiy is split into clear product domains around consent, connectors, evidence, program context, memory, briefing, action drafts, privacy control, and audit,

then the team can build vertical slices faster without mixing privacy, ingestion, AI reasoning, and user actions,

because each domain has explicit data ownership, boundary rules, and testable contracts.
