# ADR-018 — Planner xác định cho phân rã, ưu tiên và ước lượng việc

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Accepted — Thái chốt OD-01, OD-02, OD-03 ngày 2026-08-25 |
| Owner đề xuất | Technical Lead + AI Lead |
| Author | Tatejo, theo yêu cầu của Thái Hoài An (25/08) |
| Last updated | 2026-08-25 |
| Related | [ADR-005 capability-aware LLM routing](adr-005-capability-aware-llm-routing.md) · [ADR-007 lịch tương tác và lớp nhắc việc](adr-007-lich-tuong-tac-truc-tiep-va-lop-nhac-viec.md) · [ADR-017 học thích ứng P1](adr-017-adaptive-learning-p1-hermes.md) · [PRD](../../product/prd.md) |
| Thay thế | Đường tắt `is_task_planning_request` ở `src/services/task_planning.py` |

## Bối cảnh

Thái yêu cầu tính năng: AI phân tích và tách việc cho người dùng, hướng dẫn làm
cái nào trước cái nào sau, **trong bao lâu**, và ưu tiên ra sao.

Một phần tính năng này **đã tồn tại** trong repo dưới dạng v0:

- `src/services/task_breakdown.py` (234 dòng) — gọi OpenAI với structured output,
  trả `priority_rank`, `should_break`, `steps`, `context_needed`, `ai_prompt`.
  Prompt đã áp sẵn Eat the Frog, urgency-first và bước 15–60 phút.
- `src/services/task_planning.py` (78 dòng) — regex `_PLANNING_REQUEST` nhận diện
  câu hỏi lập kế hoạch.
- `src/api/tasks.py:282` — endpoint gọi thẳng breakdown.

Ba vấn đề khiến v0 không mở rộng được:

1. **Nó bỏ qua agent.** `src/api/conversations.py:1241` và `src/api/routes.py:108`
   kiểm regex rồi trả thẳng, `agent.ainvoke()` không bao giờ chạy. Lượt này mất
   sanitize untrusted content, mất guardrail tool, mất observation, mất
   grounding, mất trace. Nó cũng không phối được với `calendar_search_events`
   hay `gmail_deadline_sweep` — câu "tuần này làm gì, có lịch nào chặn không"
   chỉ được phục vụ nửa vế.
2. **Không có ước lượng thời lượng.** `Task` không có cột nào cho thời lượng.
   Yêu cầu "trong bao lâu" chưa được đáp ứng ở bất kỳ tầng nào.
3. **Ưu tiên do model tự xếp.** `priority_rank` là số model bịa ra mỗi lượt.
   Hỏi hai lần ra hai thứ tự khác nhau, và không ai trả lời được câu "vì sao
   việc này đứng trước việc kia".

Ngoài ra v0 hardcode một đường OpenAI riêng, lệch luật "LLM/provider config tập
trung ở `src/config.py`" trong `AGENTS.md`.

## Quyết định

### QĐ-1 · Tách quyết định khỏi diễn đạt

Dựng **planner xác định** ở `src/services/planner/`, không gọi LLM:

| Module | Trách nhiệm |
| --- | --- |
| `estimate.py` | Ước lượng thời lượng → `(low_min, high_min)` |
| `score.py` | Điểm ưu tiên giải thích được từ deadline, tầm quan trọng và khối lượng |
| `schedule.py` | Xếp việc vào khối rảnh thật, áp cap số việc trong ngày |

Cùng input cho ra cùng output. Test được bằng golden dataset, không tốn token,
và trả lời được "vì sao" bằng số chứ không bằng cảm tính.

**LLM chỉ giữ hai việc nó thật sự giỏi:**

- Tách một việc lớn thành các bước hành động cụ thể.
- Diễn đạt kế hoạch thành lời — qua `respond_node` như mọi lượt khác.

**LLM không được xếp thứ tự và không được chốt thời lượng.** Nó đề xuất, planner
chốt. Đây là ranh giới cứng của ADR này.

### QĐ-2 · Khung ưu tiên

Chọn framework theo tiêu chí ánh xạ được vào cột đã có trong `Task`, không theo
mức độ nổi tiếng.

| Việc | Framework | Nguồn dữ liệu |
| --- | --- | --- |
| Ưu tiên — mặt người dùng thấy | Eisenhower (khẩn × quan trọng) | khẩn từ `due_at`; quan trọng từ `signal_strength`, `source_count`, liên kết project |
| Ưu tiên — cách máy sắp bên trong | WSJF: chi phí trì hoãn ÷ khối lượng | cho ra điểm số, không phải rank do model bịa |
| Chọn việc trong ngày | MIT + WIP limit kiểu Personal Kanban — hiện 3, kéo tiếp khi xong (OD-01) | v0 mới khuyên "đừng ép", chưa có giới hạn |
| Thứ tự trong ngày | Eat the Frog | đã có trong prompt v0, giữ |
| Thứ tự giữa các bước | Topological sort trên `depends_on` | thay việc để model tự sắp |
| Xếp vào giờ thật | Time-blocking + Deep Work | `calendar_search_events`; khối rảnh dưới 45 phút chỉ nhận việc nhẹ |
| Ước lượng khi có tiền lệ | Reference-class forecasting | `created_at` + `completed_at` + `cluster_key` **đã có sẵn** |
| Ước lượng khi chưa có tiền lệ | PERT ba điểm `(o + 4m + p) / 6` | model đưa ba mốc thay vì một con số |

Loại bỏ có chủ ý: RICE/ICE (dành cho backlog sản phẩm, không cho việc cá nhân),
MoSCoW (dành cho scope một dự án, không cho một ngày), Pomodoro (là đơn vị hiển
thị, không phải mô hình ước lượng).

**Lý do chọn reference-class làm đường chính:** planning fallacy áp cho cả người
lẫn LLM — hỏi model "việc này mất bao lâu" là hỏi sai câu. Câu đúng là "những
việc tương tự của **chính user này** trước đây mất bao lâu". P-004 đã có dữ liệu
đó trong `created_at`/`completed_at`, và đường này **không cần LLM**.

Ước lượng luôn hiển thị dưới dạng **khoảng**, không bao giờ một con số đơn.

### QĐ-3 · Hai tool trong registry, không phải lane riêng

```
plan_my_day(horizon)      → DayPlan có cấu trúc; UI dựng thẻ, theo đúng khuôn suggest_tasks
break_down_task(task_id)  → các bước cho một việc, ghi vào bảng task_step
```

Vì là tool nên chúng đi đúng đường mọi tool khác đi: `is_tool_allowed` →
`sanitize_untrusted_text` → observation → grounding → trace. Model tự phối được
với tool khác trong cùng một vòng.

**Không được thêm luật routing mới vào `src/services/intent_router/tool_planning.py`
cho hai tool này.** Việc "khi nào dùng tool này" thuộc về docstring của chính
tool, theo khuôn `src/agents/tools/calendar_tool.py`.

### QĐ-4 · Xoá đường tắt cũ

Khi QĐ-3 vào `main`:

- Xoá `is_task_planning_request` và nhánh bypass ở `src/api/conversations.py:1241`
  cùng `src/api/routes.py:108`.
- `src/services/task_breakdown.py` giữ lại **chỉ phần tách bước bằng LLM**, bỏ
  `priority_rank` — ưu tiên chuyển hết sang planner.
- Đường OpenAI riêng chuyển về `src/config.py` theo ADR-005.
- Endpoint `src/api/tasks.py:282` giữ URL, đổi ruột sang planner.

### QĐ-5 · Vòng đóng học từ chính người dùng

`reminder_dismiss_count` đã có (ADR-007) để giảm ưu tiên việc user liên tục né.
Bổ sung `actual_minutes` ghi khi user đánh dấu xong. Sau khoảng 20 task hoàn tất,
reference class có dữ liệu thật và ước lượng tự hiệu chỉnh theo từng người.

Đây là điểm khác biệt so với một trợ lý chung: nó có lịch sử của đúng người dùng
này.

#### Giá trị `actual_minutes` lấy từ đâu — bổ sung 2026-08-26

Bản đầu của ADR này nói **ghi** `actual_minutes` nhưng không nói **lấy giá trị từ
đâu**. Đó là lỗ hổng thật: `completed_at − created_at` là **thời gian trôi qua**,
không phải **thời gian làm**. Một việc tạo thứ Hai xong thứ Sáu có elapsed bốn
ngày nhưng có thể chỉ tốn 30 phút. Lấy elapsed làm actual là đo sai đại lượng, và
nó đầu độc mọi ước lượng về sau vì người dùng vẫn tin con số đó.

**Chốt (Thái, 2026-08-26): hỏi người dùng đúng một câu khi họ đánh dấu xong.**

- Khi bấm hoàn tất, hiện nhanh "Mất khoảng bao lâu?" kèm vài lựa chọn sẵn
  (15 phút / 30 phút / 1 giờ / 2 giờ / hơn) và **cho bỏ qua**.
- Bỏ qua thì `actual_minutes` để `NULL`. **Không suy từ elapsed, không đoán.**
  Cột nullable chính là để mang nghĩa "không biết", và "không biết" là một câu
  trả lời hợp lệ mà reference class xử lý được — còn một con số sai thì không.
- Lựa chọn sẵn thay vì ô nhập tự do: người dùng đang ở nhịp đánh dấu xong, một
  ô trống làm họ bỏ qua; vài nút bấm thì họ trả lời.

Đã cân nhắc và loại: suy từ elapsed (đo sai đại lượng), và bấm giờ start/stop
(chính xác nhất nhưng ma sát cao nhất — với một trợ lý người dùng chỉ ghé vài
phút mỗi ngày thì gần như không ai dùng).

## Thay đổi schema

Migration bằng `apply_migration`, không `execute_sql`.

**Bảng `tasks` — thêm cột, đều nullable, không phá dữ liệu cũ:**

| Cột | Kiểu | Ý nghĩa |
| --- | --- | --- |
| `estimate_low_min` | `Integer NULL` | Cận dưới ước lượng, phút |
| `estimate_high_min` | `Integer NULL` | Cận trên ước lượng, phút |
| `actual_minutes` | `Integer NULL` | Thời lượng thật, ghi khi hoàn tất |
| `depends_on_task_id` | `Integer NULL` | Phụ thuộc, FK về `tasks.id` |
| `energy` | `String(16) NULL` | `deep` \| `shallow` |

**Bảng mới `task_steps`:**

| Cột | Kiểu |
| --- | --- |
| `id` | PK |
| `task_id` | FK `tasks.id`, index |
| `order_index` | `Integer` |
| `title` | `String(500)` |
| `estimate_min` | `Integer NULL` |
| `done_at` | `DateTime(timezone=True) NULL` |

Sau migration chạy `get_advisors` soát security/performance.

## Cái đã cân nhắc và loại

**Multi-agent cho planner** — estimator, prioritizer, scheduler thành ba agent
riêng. Loại: đây là bài toán tính toán xác định, chia ra chỉ thêm độ trễ, thêm
phi xác định và mất khả năng giải thích. Multi-agent hợp khi cần nhiều góc nhìn
độc lập; xếp lịch không thuộc loại đó.

**Để LLM tự chọn khung ưu tiên mỗi lượt** — loại vì mất tính lặp lại, đúng lỗi
v0 đang mắc.

**Thêm cổng preflight thứ bảy** — loại. Hệ đã có sáu cổng trong `think_node` cộng
một cổng regex ngoài agent; thêm nữa là bồi tiếp nợ, không trả nợ.

## Hệ quả

**Tích cực**

- Thứ tự và thời lượng lặp lại được, giải thích được bằng số.
- Phần đắt nhất (xếp lịch) không tốn token và test được không cần LLM.
- Trả nợ: xoá một đường tắt bỏ qua toàn bộ tầng an toàn của agent.
- Ước lượng cải thiện dần theo dữ liệu thật của từng người.

**Tiêu cực và rủi ro**

- Reference class cần thời gian tích luỹ; giai đoạn đầu chỉ có PERT, sai số cao.
  Giảm thiểu: luôn hiển thị khoảng, và nói rõ khi ước lượng chưa có tiền lệ.
- Planner xác định kém linh hoạt hơn LLM với tình huống lạ. Chấp nhận: đổi lấy
  tính lặp lại và khả năng giải thích.
- `depends_on_task_id` cho phép chu trình; planner phải phát hiện và báo, không
  được treo.

## Lộ trình

| Slice | Nội dung | Lý do thứ tự |
| --- | --- | --- |
| 0 | Migration + bắt `actual_minutes` khi user tick xong | Reference class cần thời gian tích luỹ — bật thu dữ liệu sớm nhất, kể cả khi chưa dùng tới |
| 1 | `src/services/planner/` + golden test, chưa nối UI | Không LLM nên test rẻ; chốt thuật toán trước khi tốn token |
| 2 | Hai tool vào registry; xoá bypass theo QĐ-4 | Feature mới trả nợ cũ |
| 3 | Thẻ kế hoạch và timeblock trên UI | Sau khi contract đã ổn định |

## Nghiệm thu

- Golden test cho `score.py` và `schedule.py`: cùng input cho cùng thứ tự, chạy
  100 lần không đổi.
- Test cho `estimate.py` ở cả hai đường: có tiền lệ và không có tiền lệ.
- Test phát hiện chu trình `depends_on_task_id`.
- Test chứng minh câu hỏi lập kế hoạch **đi qua** `agent.ainvoke()` chứ không
  bypass, và có `groundingStatus` thật thay vì gán cứng.
- Migration chạy được cả `upgrade` lẫn `downgrade` trên bản sao dữ liệu thật.

## Mục đã chốt — Thái quyết ngày 2026-08-25

### OD-01 · Kế hoạch hiện 3 việc, phần còn lại theo cơ chế kéo

Kế hoạch **hiển thị đúng 3 việc**. Việc thứ tư trở đi không biến mất mà nằm sau
một trong hai lối, dùng cả hai:

- **"Xem thêm"** — người dùng chủ động mở phần còn lại khi muốn nhìn toàn cảnh.
- **Phân tích tiếp khi làm xong** — đánh dấu xong một việc thì planner chạy lại
  và đưa việc kế tiếp vào chỗ trống.

Đây là hệ **kéo (pull)**, không phải danh sách đẩy: 3 là giới hạn công việc đang
mở, không phải hạn ngạch mỗi ngày. Khác biệt quan trọng khi cài đặt — `schedule.py`
không cắt danh sách còn 3 rồi vứt phần dư, nó xếp hạng toàn bộ và chỉ *hiển thị*
3 mục đầu, phần còn lại giữ nguyên thứ hạng để lần chạy sau dùng lại.

Hệ quả: planner phải chạy lại được **theo sự kiện hoàn tất một việc**, không chỉ
theo lịch mỗi sáng. `plan_my_day` phải rẻ và xác định — thêm một lý do nữa để nó
không gọi LLM.

### OD-02 · "Quan trọng" ưu tiên tự động, hỏi khi cần, học dần theo hành vi

Ba nguồn, xếp theo thứ tự ưu tiên:

1. **Tự động (mặc định)** — suy từ `due_at` cộng `signal_strength`, `source_count`
   và liên kết project. Đây là đường chính; đa số việc không bao giờ cần hỏi.
2. **Hỏi người dùng** — chỉ khi tín hiệu tự động mâu thuẫn hoặc quá yếu để xếp
   hạng. Hỏi phải là ngoại lệ, không phải bước bắt buộc trong luồng.
3. **Học từ hành vi** — `reminder_dismiss_count` đã có sẵn (ADR-007); bổ sung tín
   hiệu từ thứ tự người dùng thực sự làm so với thứ tự planner đề xuất.

Ràng buộc: **không bắt người dùng tự gắn mức quan trọng cho từng việc.** Đó là
thêm việc cho họ, và thực tế ai cũng gắn mức cao nhất.

### OD-03 · Ngưỡng deep/shallow

Ước lượng **cận trên trên 45 phút** thì xếp `deep`, dưới thì `shallow`. Khớp với
ngưỡng khối rảnh tối thiểu khi xếp vào Calendar.

## Quyết định liên quan, ngoài phạm vi ADR này

- **Trần vòng tool `_MAX_TOOL_ITERATIONS` giữ nguyên** (Thái chốt 2026-08-25).
  Không chuyển kiểm lên trước lời gọi model: nêu đích danh nguồn nào chưa kịp đọc
  đáng giá hơn một lượt model tiết kiệm được. Chi tiết trong
  `Guidebook-Agent-Deploy/changes/2026-08-25/p004-agent-flow-cleanup.md`.
