# Plan — Evaluation & Observation cho agent P-004 nhằm cải thiện UX

| | |
|---|---|
| Ngày | 2026-08-24 |
| Owner | Tatejo đề xuất · Thái duyệt mục tiêu |
| Nguồn dữ liệu | LangSmith project `p004-production` — 100 root runs đầu tiên (22–24/08) |
| Status | Đề xuất — chờ Thái chốt thứ tự ưu tiên |

## 1. Bằng chứng từ dữ liệu thật (baseline)

| Chỉ số | Giá trị | Ý nghĩa UX |
|---|---|---|
| Latency LangGraph (root) | p50 **10,3s** · p95 **35,6s** · max **75s** | User chờ trung bình 10s/câu — vấn đề số 1 |
| Error rate | 1/100 (OpenAITimeout — memory intent) | Đã fix sáng nay: retry + background |
| Tokens/run | p50 7.135 · p95 33.182 · max 44.362 | Prompt phình — chậm + đắt |
| Feedback | **0 lượt** | Không có ground truth về chất lượng câu trả lời |
| Tên run | `LangGraph`, `RunnableSequence`… chung chung | Không tách được surface (chat/telegram/mobile) |
| Volume | ~33 runs/ngày | Quá ít để eval thống kê → cần golden dataset chủ động |

Kết luận: ưu tiên theo thứ tự **tốc độ → feedback → chất lượng nội dung**, vì
user bỏ đi trước khi kịp đánh giá câu trả lời hay.

## 2. Mục tiêu đo được (đề xuất)

| Mục tiêu | Hiện tại | Target 2 tuần | Target 6 tuần |
|---|---|---|---|
| Chat p95 | 35,6s | ≤ 15s | ≤ 12s |
| Error rate root run | ~1% | < 1% | < 0,5% |
| Lượt có feedback | 0% | ≥ 20% | ≥ 30% |
| Golden regression | outlook (102 case) | +gmail, +chat fact | +judge nightly |

## 3. Trụ OBSERVATION — nhìn thấy mọi thứ

### 3.1 Chuẩn hoá metadata trace (nền tảng, làm đầu tiên)
- Gắn `metadata` bắt buộc ở mọi root run: `surface` (web/telegram/mobile),
  `lane`, `model`, `conversation_id`. TODO.md mục observability đã nợ việc này.
- LangSmith tags thay đổi không cần deploy lại dashboards.

### 3.2 Dashboard Grafana (datasource LangSmith đã có sẵn)
Thêm panel vào `p004-langsmith-traces` hiện hữu:
- p50/p95 latency theo surface, split theo `first_token_time` (TTFB) vs tổng —
  phân biệt "model chậm sinh token" với "pipeline chậm khởi động".
- Error rate theo tên run + nhóm lý do (timeout/rate limit/parse).
- Tokens p95 theo surface — báo động khi vượt ngân sách.
- Số lượt fallback regex của memory intent (từ log Loki, không phải LangSmith).

### 3.3 Alert
- p95 1 giờ > 20s · error rate > 5%/giờ · zero-trace > 30 phút (tracing gãy).

### 3.4 Thu feedback trong sản phẩm
- Nút 👍👎 dưới mỗi câu trả lời web → POST `/feedback` → LangSmith feedback API
  gắn `trace_id`. Đây là nguồn ground truth duy nhất cho eval chất lượng.

## 4. Trụ EVALUATION — đo chất lượng lặp lại được

### 4.1 Golden datasets (mở rộng từ pattern `eval/outlook` đã có)
- **Chat fact**: trích 50–100 cặp (câu hỏi thật từ trace, câu trả lời tốt nhất
  biết được) → dataset "regression hội thoại".
- **Memory intent**: đã có `test_memory_capture_intent` — nâng thành dataset JSON
  giống outlook để cộng case không đụng code.
- Quy ước: **mỗi bug prod sửa xong phải thêm 1 case mới** vào golden tương ứng.

### 4.2 Judge tự động (tuần 2)
- Nightly job chọn ~50 traces gần nhất, LLM-as-judge chấm 1–5:
  grounded (có citation đúng nguồn?), đúng ý, đúng ngôn ngữ UI.
- Kết quả đổ về bảng Grafana; sụt điểm trung bình > 0,5 sao = mở điều tra.

### 4.3 Regression trước deploy
- Gate deploy chạy golden pytest (outlook 102 case + bộ mới) — đã xanh từ hôm nay
  sau khi dứt bom thời gian lịch; giữ bất biến này trong cổng tích hợp.

## 5. Trụ VÒNG LẶP — biến dữ liệu thành cải thiện

1. **Hàng tuần (30 phút)**: review top-5 run chậm nhất + toàn bộ error + phản
   hồi 👎 → tạo task sửa, mỗi task đính golden case.
2. **Mỗi tối ưu latency phải kèm số trước/sau** từ dashboard (không nhận "nghe
   nhanh hơn").
3. Quick-win latency đã lộ từ baseline: p95 tokens 33k cho biết nhiều turn nạp
   context quá lớn → rà soát budget context per-lane (ADR-006) trước khi đổi model.

## 6. Thứ tự thực hiện đề xuất

| # | Việc | Effort | Trả lại gì ngay |
|---|---|---|---|
| 1 | Metadata surface/lane/model ở root runs | ½ ngày | Dashboards tách được kênh |
| 2 | Feedback 👍👎 + API + ghi trace_id | 1 ngày | Ground truth chất lượng |
| 3 | Panel p95/TTFB/tokens/error + alerts | ½ ngày | Nhìn thấy suy thoái sớm |
| 4 | Golden chat-fact dataset từ 100 traces | 1 ngày | Regression an toàn khi tune |
| 5 | Judge nightly | 1–2 ngày | Điểm chất lượng liên tục |
| 6 | Rà context budget cho lane chậm | tuỳ findings | Đường thẳng tới p95 ≤ 12s |

## 7. Điều cần Thái chốt

- [ ] Chấp nhận target p95 ≤ 15s (2 tuần) làm chỉ tiêu chính?
- [ ] Cho phép thêm nút feedback vào UI chat (thay đổi product nhỏ)?
- [ ] Ngân sách: judge nightly dùng model nào (gpt-4o-mini ~vài $/tháng)?
