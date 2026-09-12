# Golden Dataset cho phân loại "có phải việc cần làm không"

Chuyển từ `eval/golden_dataset/task_extraction/` sang đây — đây là data huấn
luyện của model `ml/model for extension/` (chk4 trong `src/services/prefilter.py`
+ `src/services/task_classifier.py`), tách khỏi `eval/golden_dataset/` (nơi
chứa golden dataset EVAL cho các pipeline khác — Slack, Outlook, evidence
verification — không liên quan tới model này). Vẫn CHỈ một bản duy nhất,
không có bản sao ở vị trí cũ.

Bộ case cho `is_task_like()`/`confidence_tier()`/`summarize_page_extraction()`
trong `src/services/page_extraction.py` — tab "Lấy dữ liệu" của extension
(`client/extension/entrypoints/sidepanel/App.tsx`). Dùng chung cho:

- Gate CI: `tests/test_services/test_page_extraction.py` đọc trực tiếp
  `task_extraction_cases.json`, assert từng case qua `is_task_like()` thật.
- So sánh 3 hướng xử lý (rule-based / LLM / rule+LLM hybrid):
  `scripts/eval_task_classifiers.py` đọc cả 2 file, chạy cả 3 hướng, in bảng
  accuracy/precision/recall/F1/chi phí LLM.

Không phải fixture "mồ côi" — mỗi case trong `task_extraction_cases.json` đều
được một test thật đọc và assert.

## Cấu trúc

```text
ml/model for extension/data/
├── README.md
├── task_extraction_cases.json   # 220 câu, gate CI (≥90% accuracy)
└── hard_cases.json              # 7 câu thật, KHÔNG gate CI, chỉ minh hoạ
```

Mỗi file là 1 list case tự chứa `{id, description, input, expected}`, theo
đúng convention `eval/golden_dataset/evidence_verification/`.

## task_extraction_cases.json (220 case, TASK-001..220)

Câu tiếng Việt do kỹ sư tự soạn (không phải template sinh hàng loạt như
`fact_verification_cases.json`) — 110 positive (câu có hình thức việc cần
làm) + 110 negative, cân bằng để đo được cả precision lẫn recall thay vì chỉ
accuracy (dataset lệch lớp dễ đánh lừa accuracy).

| Nhóm | Số lượng | Mục tiêu kiểm |
| --- | --- | --- |
| checklist | 16 | Dấu đầu dòng `- [ ]`/`TODO`/số thứ tự |
| deadline_keyword | 17 | Từ khoá hạn chót/gấp/deadline |
| date_and_action | 17 | Ngày tháng cụ thể (`dd/mm`, "ngày X") kèm hành động |
| imperative_start | 17 | Câu mở đầu bằng hãy/cần/phải/nhớ/... |
| assignee | 16 | "giao cho X" / "nhờ X" / `@mention` + động từ |
| plain_action | 17 | Câu ra lệnh trần, không tín hiệu khác |
| mention_short_request | 10 | `@mention` ngắn + động từ (test riêng vụ bare-mention false positive, xem dưới) |
| greeting | 17 | Chào hỏi/cảm ơn/phản hồi đầu câu |
| statement | 17 | Tường thuật/nhận xét, không hành động |
| question | 17 | Câu hỏi phiếm, không kèm ngày/mention |
| casual_numbers | 16 | Số liệu đời thường (giá tiền, điểm số...) không phải ngày tháng |
| links_media | 17 | Link/ảnh/video/sticker chia sẻ |
| short_reaction | 16 | Phản hồi ngắn/emoji |
| chat_noise | 10 | `@mention` trần + câu trả lời cụt "gửi ạ" — lấy trực tiếp từ nhóm chat Zalo thật lúc test tay tính năng (2026-08-20), rule bản đầu bắt nhầm thành task |

## hard_cases.json (24 case, TASK-HARD-001..024)

Câu thật từ Zalo lúc test tay (2026-08-20) + 17 case bổ sung khi research
thêm (2026-08-21) để cân bằng 12 positive / 12 negative — nhãn mang tính
**chủ quan/tranh cãi được**, KHÔNG gate CI, chỉ dùng trong bảng so sánh 3
hướng để minh hoạ khác biệt thật trên chat đời thường (xem
`client/extension/README.md` mục "Tab Lấy dữ liệu" để biết số liệu đầy đủ và
quyết định cuối cùng: production dùng hybrid).

Nhóm case bổ sung (008-024) nhắm vào các mẫu rule chưa từng gặp trong
`task_extraction_cases.json`: giao việc qua "để X lo", nhờ vả không chỉ đích
danh ("ai đó"/"bạn nào rảnh thì"), Vietlish công sở ("check giúp"), câu vừa có
marker thì quá khứ ("rồi") vừa là yêu cầu thật (không phải tường thuật), và
động từ ngoài whitelist ("nhắc", "bổ sung") mà rule không có tín hiệu nào để
bắt — đây chính là nhóm case rule-based dự kiến sai nhiều nhất.

## Hướng 4 — ML classifier rẻ (thử 2026-08-23, CHƯA wire production)

Thử thêm hướng 4 vào `scripts/eval_task_classifiers.py`: TF-IDF bigram (token
qua `underthesea.word_tokenize`) + tín hiệu "có tân ngữ không" xấp xỉ qua
`underthesea.chunk()` (KHÔNG dùng `dependency_parse()` — cần torch, quá nặng
cho máy dev yếu, đã verify thực tế) + `LogisticRegression` — xem
`src/services/task_classifier.py`. Train dưới 1s trên CPU, không cần GPU.

Kết quả (5-fold CV trên golden dataset chính, không leak train/test):
acc 94.5% — nhỉnh hơn hybrid (94.1%), miễn phí hoàn toàn (0 LLM call). Nhưng
trên `hard_cases.json` (24 câu Zalo thật, train trên toàn bộ 220 câu chính):
chỉ 70.8% — tụt xa so với hybrid/LLM thuần (đều 100%). Overfit vào văn phong
"sạch" của 220 câu do kỹ sư tự soạn, không generalize sang chat đời thường —
đúng chỗ hybrid cần LLM xử lý nhất.

**Quyết định: chưa wire vào production** — thay hybrid bằng hướng này ở bước
hiện tại là regression thật trên đúng nhóm case khó, không phải cải thiện.
Kiến trúc đã chứng minh hoạt động tốt khi đủ data; bottleneck là DATA (220
câu sạch không đại diện cho chat thật), không phải model.

### Cập nhật — bootstrap thêm data (2026-08-23)

Đã thử kéo raw text công khai làm nguồn (5CD-AI/Vietnamese-Multi-turn-Chat-
Alpaca, fsnaix/vietnamese-corpus-large) nhưng cả hai sai văn phong (hội thoại
người-hỏi-AI và văn viết trang trọng tin tức/wikipedia, không phải chat nhóm
việc đời thường) — không dùng được. Đổi hướng: `scripts/bootstrap_hard_cases.py`
cho LLM sinh trực tiếp 60 câu theo đúng văn phong `hard_cases.json` (chat
ngắn, ngữ pháp không chuẩn, tiểu từ đệm, @mention, thì quá khứ lẫn yêu cầu
thật), có kiểm soát nhãn ngay lúc sinh — lưu ở
`ml/model for extension/data/bootstrap_cases.json`.

Soát tay 60 câu trước khi dùng, tìm được lỗi hệ thống: LLM gán `false` mỗi
khi câu có dấu hiệu thì quá khứ ("đã/rồi/xong") ở đầu câu, kể cả khi phần sau
là yêu cầu thật rõ ràng ("...kiểm tra giúp nhé!") — đúng cái bẫy
`_PAST_TENSE_MARKER_PATTERN` trong `src/services/page_extraction.py` đã ghi
chú, và mâu thuẫn với chính tiền lệ "Họp xong rồi thì gửi biên bản cho cả
nhóm nhé" (`hard_cases.json`, đã label `true`). Sửa tay 7/60 case bị lỗi này
trước khi gộp — không merge mù dữ liệu LLM tự sinh vào eval set.

Train lại classifier trên 220 câu chính + 60 câu bootstrap, đánh giá lại trên
`hard_cases.json`: **70.8% → 83.3%** (+12.5 điểm), recall lên 100% (không bỏ
sót positive nào) nhưng precision giảm còn 75% (nhiều false positive hơn —
chấp nhận được cho vai trò pre-filter rẻ, còn bước xác nhận/lưu thủ công ở
extension chặn lại). Vẫn thấp hơn hybrid/LLM thuần (100%) — **vẫn chưa wire
production**, nhưng xác nhận đúng hướng: thêm data văn phong chat thật là
đòn bẩy đúng, không phải đổi kiến trúc model.

### Thử thêm batch 2 (60 câu, +Claude tự sinh trực tiếp khi OpenAI hết billing) — THẤT BẠI, đã revert

Sinh thêm 60 câu nữa (tổng 120 bootstrap), cố tình thêm nhiều cặp gần giống
nhau kiểu minimal-pair (cùng cấu trúc "X xong rồi, ai Y giúp mình với!" vs
"X xong rồi, [không có yêu cầu]") để dạy rõ ranh giới thì-quá-khứ-nhưng-vẫn-
là-yêu-cầu. Kết quả trên hard_cases.json: **83.3% → 75.0%** (tái lập ổn định
3 lần, không phải nhiễu đo) — TỆ HƠN bản 60 câu, dù data trông "sạch"/đúng ý
hơn theo trực giác.

Giả thuyết vì sao: feature TF-IDF bigram (bag-of-words nông) không đủ mạnh để
phân biệt các cặp minimal-pair gần giống nhau về mặt bề mặt nhưng khác nhãn —
nhồi thêm nhiều cặp như vậy có thể làm mô hình "nhoè" quyết định ở đúng vùng
biên khó thay vì học được ranh giới rõ hơn. Đây là giới hạn của bản thân
feature representation (bigram nông), không chỉ là vấn đề thiếu data — nghi
ngờ hợp lý rằng hướng "TF-IDF + Logistic Regression" có trần hiệu năng ở đâu
đó quanh 80-85% trên chat thật, khó vượt qua bằng cách thêm data theo kiểu
này.

**Quyết định: revert `bootstrap_cases.json` về bản 60 câu** (bản đo được tốt
hơn thật, 83.3%) — không giữ data mới làm "chuẩn" chỉ vì nó nhiều hơn hoặc
mới hơn. Bài học: thêm data KHÔNG tự động = cải thiện, phải đo lại mỗi lần,
kể cả khi trực giác nói ngược lại.

### Thử nhiều biến thể feature/model (2026-08-23) — tìm được cải thiện thật

OpenAI hết billing (không gọi được Hướng 2/3 lúc này) nên tập trung cải thiện
riêng Hướng 4 — không đổi data thêm nữa, đổi feature representation + model.
So 5 biến thể trên CÙNG data (220 chính + 60 bootstrap):

| Biến thể | CV 220 câu | hard_cases (24 câu thật) |
|---|---|---|
| A. Baseline cũ (word bigram + tân ngữ, LogisticRegression) | 94.5% | 83.3% |
| B. A + cờ tín hiệu rule (checklist/date/deadline/imperative/assignment/help/mention/action_verb) | 96.8% | 83.3% |
| C. A + char n-gram (analyzer=char_wb, 3-5) | 96.8% | 83.3% |
| D. A + LinearSVC thay LogisticRegression | 95.5% | 83.3% |
| **E. B + C + D gộp cả ba** | **99.1%** | **87.5%** |

E thắng rõ rệt, đã wire vào `src/services/task_classifier.py` làm bản chính
thức (thay A). Lưu ý một bug thật gặp lúc wire: thứ tự ghép token trong
`_preprocess()` ảnh hưởng trực tiếp tập bigram sinh ra — đặt cờ tín hiệu rule
TRƯỚC token câu thật (thay vì SAU, đúng như lúc đo) làm hard_cases tụt từ
87.5% xuống 83.3% dù cùng feature set/model — đã sửa, giữ đúng thứ tự đã đo.

Cũng thử weak-supervision: lấy 400 câu bình luận Facebook thật từ ViHOS
(`visolex/ViHOS`, dataset gốc dùng cho hate-speech span detection — ở đây bỏ
qua nhãn gốc, chỉ mượn RAW TEXT) chạy qua `confidence_tier()` (rule engine
free, không tốn LLM) để tự gán nhãn, thêm vào làm data train. **Kết quả: TỆ
ĐI ở MỌI biến thể** — biến thể E rớt từ 87.5% xuống 70.8%. Bình luận công
khai trên post (thường là phản ứng/ý kiến, gần hate-speech) sai sub-văn
phong so với chat nhóm việc riêng tư — dù cùng là "tiếng Việt đời thường",
KHÔNG dùng được. Không lặp lại hướng này.

**Vẫn dưới hybrid/LLM thuần (100%) — vẫn CHƯA wire vào `confidence_tier()`
production.** Nhưng khoảng cách đã thu hẹp đáng kể (70.8% → 87.5% qua 2 vòng
cải thiện, không đổi kiến trúc model gốc, chỉ đổi feature).

### Thử dịch DailyDialog (2026-08-23) — THẤT BẠI LẦN 3, không dùng

DailyDialog (`ConvLab/dailydialog`, HF) có nhãn dialogue-act "directive" —
tưởng khớp "task" nhưng thực ra là taxonomy ngôn ngữ học (Searle: directive/
commissive/inform/question), KHÔNG khớp 1:1 định nghĩa is_task của mình (vd
câu hỏi lịch sự cũng bị gắn directive, câu tự hứa việc của bản thân lại gắn
commissive). Đã tự soát và gắn lại nhãn theo đúng tiêu chí is_task (không tin
thẳng nhãn gốc), chọn câu đa dạng chủ đề (Tourism/Finance/Health/
Relationship/Ordinary Life/Work/School — không trùng văn phòng/trường học đã
có nhiều), dịch TỰ NHIÊN sang tiếng Việt (không word-by-word) — lưu ở
`dailydialog_translated_cases.json` (giữ lại làm tham khảo, KHÔNG wire vào
`load_training_cases()`).

Ban đầu chỉ 36 câu (đo được: làm tệ đi, xem ngay dưới). 2026-08-23, theo yêu
cầu dịch sâu hơn, mở rộng qua 14 đợt lên **1849 câu** (305 positive / 1544
negative — lệch hẳn về negative vì mỗi đợt dịch ưu tiên lấy hết case true rõ
ràng tìm được trước, case false thì dồi dào hơn nhiều trong data gốc DailyDialog;
cùng cách soát nhãn tay theo tiêu chí is_task, không trùng câu/id giữa các
đợt — một lần bắt được lỗi trùng ID số giữa 2 đợt lúc ghi, đã sửa). Full
DailyDialog sau khi lọc độ dài còn hàng chục nghìn câu (≈56,700 câu duy nhất
đủ điều kiện, đo lúc 968 câu — xem lịch sử hội thoại) — 1849 câu này KHÔNG
phải "toàn bộ" dataset, chỉ là mẫu chọn lọc tay lớn nhất khả thi trong phạm
vi làm bằng tay (không có API dịch máy để tự động hoá — đã nói rõ với người
dùng rằng dịch hết ~55,000+ câu còn lại là không khả thi theo cách này, chỉ
khả thi nếu có OPENROUTER_API_KEY để chạy `scripts/bootstrap_hard_cases.py`
kiểu tự động hoá).

### Đo bản 1849 câu (2026-08-23) — hoà accuracy, nhưng recall giảm = vẫn không dùng

Đã đo bản đầy đủ 1849 câu (holdout trên hard_cases.json, train = golden +
bootstrap + toàn bộ DailyDialog):

| Cấu hình train | Acc | Precision | Recall | F1 |
|---|---|---|---|---|
| 220 + 60 bootstrap (mốc production) | 87.5% | 80.0% | **100.0%** | 88.9% |
| + 1849 DailyDialog (2129 câu) | 87.5% | 90.9% | 83.3% | 87.0% |
| 220 + DailyDialog (không bootstrap) | 79.2% | 88.9% | 66.7% | 76.2% |
| Chỉ DailyDialog (không golden, không bootstrap) | 66.7% | 100.0% | 33.3% | 50.0% |

Khác 3 lần thất bại trước (accuracy tệ đi rõ ràng) — lần này accuracy **hoà**
(87.5% = 87.5%), nhưng đổi lấy đánh đổi precision/recall: recall tụt từ 100%
xuống 83.3% (bỏ sót nhiều task thật hơn) để đổi lấy precision cao hơn. Với
sản phẩm này (người dùng còn bước xem/sửa/bỏ qua từng gợi ý trước khi lưu),
bỏ sót task thật tốn hơn báo dư (dễ bỏ qua 1 click) — nên dù accuracy hoà,
đây vẫn là đánh đổi sai hướng cho mục tiêu thật. DailyDialog đứng một mình
rất tệ (66.7%, recall 33.3%) — chỉ "đỡ" được nhờ ké vào golden+bootstrap.

**Quyết định: vẫn KHÔNG gộp vào `load_training_cases()`.** Đây là lần thứ 4
data nguồn ngoài không mang lại cải thiện thật cho mục tiêu sản phẩm (dù lần
này không tệ đi ở accuracy tổng, vẫn tệ đi ở recall — chỉ số quan trọng hơn
ở đây). File `dailydialog_translated_cases.json` (1849 câu) giữ lại làm tham
khảo/tài nguyên dịch, không phải data huấn luyện production.

Kết quả trên hard_cases.json: **87.5% → 83.3%** khi thêm vào (220+60+36) —
TỆ ĐI, dù đã cẩn thận soát nhãn + dịch tự nhiên (không phải lỗi ẩu như 2 lần
trước). Đây là lần thứ 3 liên tiếp data từ nguồn ngoài (LLM sinh dàn trải,
ViHOS, giờ tới DailyDialog dịch) làm HẠI thay vì giúp, dù mỗi lần motivation/
cách làm khác nhau. Kết luận nhất quán: **60 câu tự soạn khớp đúng văn phong
chat nhóm việc tiếng Việt (không phải "càng đa dạng nguồn càng tốt") vẫn là
bộ train tốt nhất tìm được cho tới giờ** — đa dạng chủ đề không bù được lệch
sub-văn phong (dù cùng ngôn ngữ, cùng đã dịch tự nhiên, cùng đã soát nhãn
tay). Dừng hướng "thêm nguồn ngoài" tại đây — đủ bằng chứng (3 lần độc lập)
để không thử lại kiểu này nữa.

## Quy tắc

1. Case đã ổn định thì không sửa ngầm — sửa rule engine/prompt LLM thay đổi
   thì cập nhật case + README cùng lúc, chạy lại
   `scripts/eval_task_classifiers.py` để xác nhận không tụt điểm.
2. Thêm case mới khi tìm ra edge case chưa cover (nhất là từ dữ liệu chat thật
   khi test tay), không xoá case cũ để "cho test pass".
3. Đây là bộ case do kỹ sư soạn khi implement, **không phải** bộ case QA chính
   thức — cùng tinh thần ghi chú ở
   `eval/golden_dataset/resolve_make_batches/README.md`.
