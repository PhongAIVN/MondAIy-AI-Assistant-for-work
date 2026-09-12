# ADR-020 — Tầng định tuyến của agent chat

| Thuộc tính | Giá trị |
| --- | --- |
| Status | **Proposed — chờ Thái chốt.** Phần chẩn đoán và ba bản vá đã Accepted và đã lên production |
| Owner đề xuất | Tatejo |
| Author | Tatejo, đêm 26→27/08 theo yêu cầu của Thái Hoài An |
| Last updated | 2026-08-27 |
| Related | [ADR-018 planner xác định](adr-018-planner-xac-dinh-cho-phan-ra-va-uu-tien-viec.md) · `tests/eval/routing_gold.py` |

## Bối cảnh

Thái báo một lỗi cụ thể: hỏi *"trước khi họp mentor duty cần làm gì"* thì Mondaiy
trả lời về báo cáo Jira, không nhắc cuộc họp. Anh đặt câu hỏi kiến trúc kèm theo:
*"sao không dùng LLM để routing"*.

Điều tra đêm đó lật đổ hai chẩn đoán, trong đó có chẩn đoán đầu tiên của chính
Tatejo. Ghi lại đầy đủ vì cách sai cũng đáng học như kết luận.

## Điều đã đo được

### Hệ đang có **ba** tầng định tuyến, không phải một

1. **Embedding** — `src/agents/briefing/intent.py`. Nhúng câu hỏi, so cosine với
   câu mẫu, ngưỡng 0,6.
2. **Regex** — `src/services/intent_router/tool_planning.py`, 23 `re.compile`
   trên text đã bỏ dấu, cộng các luật vá.
3. **LLM tool-calling** — `core_nodes.py:568`, `bind_tools`. Đây là tầng đang
   thật sự chọn tool trong mọi lượt chat.

### Tầng embedding chưa từng chạy trên production

Gọi thẳng trong container: OpenRouter trả `HTTP 402 — "Insufficient credits.
This account never purchased credits."` Lỗi bị `except Exception` nuốt, chỉ ghi
`type(exc).__name__` ở mức warning, rồi rơi về `GENERAL_WORK`.

Tác dụng thật của tầng này trên production là **đúng một biến boolean**
(`core_nodes.py:915`) quyết định có nối `_DAILY_BRIEF_PROMPT` hay không. Vì nó
chưa từng chạy, đoạn prompt đó **chưa từng được áp dụng**.

`plan_information()` — hàm map intent sang kế hoạch truy hồi, phần nhìn có vẻ giá
trị nhất — **không có caller production**, chỉ test gọi.

Blast radius rộng hơn: `embed_queries` dùng chung với `retrieval.py:126`, nên RAG
tìm kiếm ngữ nghĩa cũng chết theo.

### Nguyên nhân lỗi Thái báo **không phải** router chết

Chẩn đoán đầu của Tatejo là "router chết nên gợi ý sai". Sai. Router chết chỉ ảnh
hưởng biến `daily_brief`.

Một lane đối chứng độc lập (Codex, mô tả trung tính, không thấy giả thuyết của
Tatejo) chỉ sang hướng ngân sách/tổng hợp. Đo lại thì thủ phạm bắn trước là trần
`agent_max_observations_in_context = 8`:

```
13 observation vào  →  8 giữ lại, TOÀN BỘ là gmail_read_email
calendar_search_events  ✗ bị loại   ← nguồn DUY NHẤT biết "Mentor Duty 29/08 20:00"
jira_search_issues      ✗ bị loại
```

Câu trả lời nhắc Jira là lấy từ **email digest của Jira**, không phải từ tool
Jira. Dữ liệu có, tool chạy đúng, guardrail không chặn — **bằng chứng bị vứt ở
bước cuối**.

### Router xác định chỉ đúng 67%

Bộ đo mới (`tests/eval/`) cho baseline **14/21**. Bảy khoảng trống, trong đó hai
cặp cho thấy rõ tính giòn:

| Đạt | Trượt | Khác nhau ở |
|---|---|---|
| "mai có lịch gì" | "tuần này có họp gì không" | regex bắt `lịch`, không bắt `họp` |
| "trước khi họp mentor duty cần làm gì" | "chuẩn bị gì cho buổi họp với mentor" | chỉ khác cách nói |

Ngoài ra `"AI thực chiến là gì"` và `"LangGraph là gì"` **không route đi đâu cả**.
Tatejo từng khẳng định với Thái là `_prefer_web_search` đã lo câu đầu — đo lại thì
sai, và linh cảm ban đầu của Thái về khoảng trống này mới đúng.

### Ràng buộc cứng

- Thái **chưa nạp được credit OpenRouter**. Đây là ràng buộc, không phải sở thích.
- LLM chat **đã chạy bằng key OpenAI trực tiếp**: `LLM_PROVIDER=openai`,
  `MODEL_NAME=gpt-4o-mini`, `LLM_ROUTING_ENABLED=false`. Đó là lý do chat sống
  trong khi embedding chết.
- Nhánh sau `llm_routing_enabled` (`llm.py:371`) chỉ dựng candidate cho
  `openrouter`/`groq` — **OpenAI không nằm trong đó**. Bật cờ hiện không giúp gì.
- 2.370 chunk trong pgvector đều **2048 chiều** (nemotron). Đổi model nhúng là
  phải nhúng lại toàn bộ và đổi kiểu cột. `text-embedding-3-small` là 1536 chiều.

## Đã làm và đã lên production

| PR | Nội dung |
|---|---|
| #71 | Bật `strict` cho `bind_tools`. Đo trước: 26/26 tool đã hợp lệ, không phải sửa schema nào |
| #73 | Gói bằng chứng xếp theo **vòng** — mọi tool có mặt trước khi tool nào được suất thứ hai |
| #75 | Lỗi embedding log mức ERROR kèm nguyên văn và traceback. Hành vi hạ cấp giữ nguyên |
| #77 | Suite tự đủ trên clean checkout; sửa 7 test đỏ lâu ngày, trong đó 6 do dựng LLM quá sớm |
| #78 | Bộ đo định tuyến, baseline 67% |

Bốn PR đầu đã deploy và nghiệm thu trong container đang chạy.

## Quyết định cần Thái chốt

### QĐ-1 · Tầng định tuyến đi tiếp thế nào

**Phương án A — gộp intent vào chính lượt gọi LLM đang có** (Tatejo đề xuất).
Một field enum trong structured output của lượt `bind_tools` sẵn có. Gần như
không thêm chi phí hay độ trễ, cắt hẳn phụ thuộc OpenRouter cho định tuyến. Bỏ
tầng embedding, giữ regex chỉ ở chỗ cần tính tái lập (yêu cầu hành động rõ ràng).

**Phương án B — kiến trúc planner có kiểu** (lane Codex đề xuất độc lập):
`typed planner → capability registry xác định → read tool song song → gói bằng
chứng theo truy vấn → grounding mức claim`. Lane lập luận rằng đổi model đơn
thuần không sửa được lỗi, và điểm yếu thật nằm ở khâu chọn bằng chứng — điều
PR#73 vừa xác nhận một phần.

Hai bên **không mâu thuẫn**: A là bước nhỏ nằm gọn trong B. Khuyến nghị của
Tatejo là làm A trước, đo bằng `tests/eval/`, rồi quyết B khi có số.

### QĐ-2 · RAG khi không có credit OpenRouter

Nhúng lại 2.370 chunk bằng `text-embedding-3-small` tốn khoảng vài cent, nhưng
phải đổi cột `2048 → 1536`. Lane đề xuất ngược lại: **giữ nguyên vector cũ**, và
khi embedding lỗi thì RAG rơi về FTS/unaccent/trigram thay vì hỏng cả đường.

Đề xuất Tatejo: theo lane — rẻ hơn, đảo ngược được, và giữ đường quay lại nếu
Thái nạp credit sau. Nếu làm, đi **expand-then-contract**, không xoá cột cũ.

### QĐ-3 · Cổng grounding có nên kiểm độ liên quan không

`ground_candidate` (`output.py`) kiểm *"có bịa không"*, **không** kiểm *"có đúng
câu hỏi không"* — và docstring nói rõ đó là cố ý. Lane chỉ ra hệ quả: câu trả lời
chỉ nói về Jira vẫn qua cổng là `grounded`.

Thêm kiểm relevance là **đổi định nghĩa của một guardrail**. Tatejo cố ý không tự
quyết. Cần Thái chốt trước khi ai đó động vào.

### QĐ-4 · Bó Jira trong luồng agenda

`_ensure_agenda_coverage` gọi Jira với `{"query": ""}` hardcode, trả tối đa 30
issue kèm evidence — 6.200 ký tự, đủ chiếm nửa ngân sách.

Truyền `context.query` vào **không sửa được gì**: `_jira_search_terms` chỉ trích
`ISSUE-KEY` và `dự án X`, câu thường không cho term nào. Bó theo cửa sổ deadline
thì loại luôn task chưa có hạn. Đây là phán đoán sản phẩm, cần Thái.

## Hệ quả nếu không quyết

Router giữ nguyên 67%, và khoảng trống lớn nhất là các câu diễn đạt khác đi —
đúng cách người dùng thật hỏi. Bộ đo sẽ giữ con số đó khỏi tụt, nhưng không tự
nâng nó lên.

## Bài học ghi lại

Ba lần trong một phiên, kết luận sai đến từ **đo sai đơn vị**, không phải từ
thiếu dữ liệu:

- `grep -c` theo file, không theo class → "32 cột thiếu" thành blocker giả.
- Tag image, không phải phiên bản code → "prod trễ 14 ngày".
- `--collect-only`, không phải một lần chạy → "suite ổn" trong khi 298 test đỏ.
- `is_tool_allowed(phase="read")`, không phải predicate `action_node` thật dùng →
  suýt báo động giả "5 tool bị chặn trên production".

Cái cuối đáng nhớ nhất: nó nằm trong **chính công cụ đo** vừa viết ra để bắt loại
lỗi này. Công cụ đo cũng phải nghiệm thu như hệ thống.
