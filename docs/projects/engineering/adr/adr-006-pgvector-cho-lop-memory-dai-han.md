# ADR-006 — pgvector cho lớp memory dài hạn, truy hồi lai chấm điểm trong tiến trình

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Proposed |
| Owner | Nguyễn Văn Phong (Technical Lead) |
| Author | Thái Hoài An (PM) |
| Reviewers | Technical Lead, AI/Memory Lead, QA Lead, PO/QC |
| Last updated | 2026-08-11 |
| Related | [Memory lifecycle](../memory-lifecycle.md) · [Architecture](../architecture.md) · [ADR-005](adr-005-capability-aware-llm-routing.md) · [PRD](../../product/prd.md) · [AI usage log](../ai-usage-log.md) |

## Bối cảnh

Lớp memory dài hạn (`user_memories`, `user_memory_evidence`) đã dựng theo
memory-lifecycle §3–§9, nhưng bước 3 của §7 — tìm bằng Postgres FTS và pgvector —
mới chỉ làm nửa đầu. Độ liên quan hiện là tỉ lệ token trùng giữa câu hỏi và chuỗi
`subject predicate object` đã dựng phẳng.

Cách đó hỏng đúng ở chỗ memory cần nhất. Định danh trong mã viết bằng tiếng Anh
theo PRD §10, còn người dùng hỏi bằng tiếng Việt: fact `working_on = mondaiy`
không khớp một token nào với câu "dự án tới đâu rồi". Trong lần dựng đầu, chính
câu hỏi đó làm agent quên sạch dự án mà người dùng vừa kể ở lượt trước. Chỗ vá
tạm hiện tại gồm một bảng nhãn tiếng Việt theo `kind` và một sàn
`BASELINE_RELEVANCE = 0.15` cho mọi fact không khớp chữ nào — cả hai đều là mẹo,
không phải truy hồi.

Sàn đó còn có hại riêng: nó làm mọi fact đều lọt vào tập ứng viên với điểm bằng
nhau, nên thứ tự cuối cùng do recency và reinforcement quyết định chứ không do
câu hỏi. Với người dùng có vài chục fact thì prompt sẽ mang theo phần lớn là
nhiễu.

Hạ tầng cần thiết đã có sẵn và đang chạy: extension `vector` bật lúc khởi động
(`src/main.py`), cột `chunks.embedding` kiểu `Vector(2048)`, và `embed_query`
trong `src/services/retrieval.py` gọi OpenRouter kèm xoay key. Quyết định còn mở
`TODO(OD)` ở `src/models/message.py` — Chroma hay pgvector — chưa được chốt, và
`docs/projects/engineering/memory-lifecycle.md` §7 thì đã ghi thẳng "Postgres FTS
+ pgvector". Hai chỗ này cần một quyết định để hết lệch.

## Lựa chọn đã cân nhắc

| Phương án | Kết luận |
| --- | --- |
| Giữ khớp từ khoá thuần, mở rộng bảng nhãn tiếng Việt | Loại: bảng nhãn phải bảo trì tay theo từng predicate, và vẫn hỏng với mọi cách diễn đạt không nằm trong bảng |
| Chroma làm kho vector riêng cho memory | Loại: thêm một hệ lưu trữ thứ hai, hai đường sao lưu, hai đường xoá khi người dùng đòi xoá dữ liệu, và mất khả năng lọc `user_id` cùng transaction |
| Gọi LLM xếp hạng lại memory mỗi lượt | Loại: thêm một lượt model và một failure point vào đường chat, chi phí theo số fact, kết quả không tái lập được cho eval |
| pgvector trên chính bảng `user_memories`, hợp nhất RRF với khớp từ khoá | Chọn: cùng một transaction, cùng một đường xoá, tái dùng hạ tầng nhúng đang chạy |
| Bỏ hẳn nhánh từ khoá, chỉ dùng vector | Loại: vector trượt tên riêng và mã định danh, mà tên riêng lại là thứ memory hay chứa nhất |

## Quyết định

1. `user_memories` có thêm cột `embedding` kiểu `Vector`, cùng số chiều và cùng
   model nhúng với `chunks.embedding`. Một model nhúng cho cả hệ thống; đổi model
   là phải nhúng lại cả hai bảng.
2. Truy hồi memory là truy hồi lai theo §7: một nhánh khớp từ khoá, một nhánh
   vector, hợp nhất bằng reciprocal rank fusion với đúng hằng số `RRF_K = 60`
   đang dùng cho chunk.
3. Điểm RRF sau khi chuẩn hoá **là** thừa số `relevance` của công thức §7. Năm
   thừa số còn lại — thẩm quyền, trạng thái, độ mới, độ lặp lại, phạt phản hồi
   tiêu cực — giữ nguyên và vẫn nhân sau. Vector chỉ đổi thứ tự ứng viên, không
   được đụng tới thẩm quyền nguồn hay trạng thái.
4. Nhánh từ khoá chấm điểm trong tiến trình, không dùng Postgres FTS. Đây là
   khác biệt có chủ ý so với chunk: một user có vài chục tới vài trăm memory,
   không phải hàng triệu chunk.
5. Nhúng chạy nền sau khi đã trả lời, cùng chỗ với việc nén tóm tắt hội thoại.
   Không có lời gọi nhúng nào nằm trên đường ghi memory.
6. Nhúng câu hỏi chạy trên đường đọc, nhưng phải chạy ngoài event loop và có
   trần thời gian đọc từ config. Nhúng hỏng hoặc quá hạn thì truy hồi lùi về
   nhánh từ khoá, không được làm hỏng lượt trả lời.
7. Mọi truy vấn vector bắt buộc lọc `user_id` ngay trong câu SQL, không lọc sau
   khi đã lấy kết quả. Truy hồi sai phạm vi ở lớp memory là rò dữ liệu giữa
   người dùng.
8. Nhánh vector chỉ bật khi cả ba điều kiện đủ: dialect là PostgreSQL, cờ
   `memory_semantic_recall_enabled` bật, và câu hỏi nhúng được. Thiếu bất kỳ
   điều nào thì hệ thống chạy nhánh từ khoá như trước.
9. Xoá memory xoá luôn vector của nó, vì vector nằm cùng dòng. Không có bản sao
   phái sinh nào phải dọn riêng.
10. `BASELINE_RELEVANCE` chỉ còn hiệu lực ở chế độ từ khoá thuần. Ở chế độ lai,
    mọi fact đều có thứ hạng từ khoá nên không cần sàn nữa.

## Lý do

**Cùng một kho, cùng một đường xoá.** PRD đòi người dùng gỡ được dữ liệu và đòi
xoá phải có hiệu lực trong truy hồi ngay. Vector nằm trong cùng dòng với fact thì
`DELETE` là xong; vector nằm ở hệ thứ hai thì phải có hợp đồng xoá riêng, phải
xử lý trường hợp xoá một bên thành công một bên hỏng, và mỗi lần lệch là một lần
dữ liệu đã thu hồi vẫn quay lại prompt. Đây là lý do mạnh nhất để không chọn
Chroma, mạnh hơn cả lý do vận hành.

**Lọc quyền phải nằm trong SQL.** Truy hồi vector kiểu KNN trả về k dòng gần
nhất; lọc `user_id` sau khi lấy k dòng nghĩa là k suất đó đã bị memory của người
khác chiếm mất, và chỉ cần một chỗ quên lọc là rò thẳng. Đặt điều kiện trong câu
SQL khiến trường hợp xấu nhất là trả thiếu, không phải trả nhầm người.

**Lai chứ không thuần vector.** Memory chứa nhiều tên riêng, tên dự án và mã
định danh — đúng loại chuỗi mà nhúng ngữ nghĩa xử lý kém nhất, còn khớp từ khoá
lại xử lý tốt nhất. Ngược lại, câu hỏi diễn đạt vòng vo thì vector mới bắt được.
Hai nhánh bù đúng chỗ yếu của nhau, và RRF hợp nhất mà không cần chỉnh trọng số
giữa hai thang điểm khác đơn vị.

**Không dựng FTS cho memory.** Chunk cần index GIN vì quét tuyến tính hàng triệu
dòng là không chấp nhận được. Memory của một người thì không: quét vài trăm dòng
đã lọc sẵn theo `user_id` rẻ hơn chi phí bảo trì thêm một cột sinh, một hàm
`immutable` và một index. Chỗ nào không cần Postgres thì không buộc phải có
Postgres — sqlite dev và test vẫn chạy đủ đường từ khoá.

**Nhúng nền cho ghi, đồng bộ cho đọc.** Ghi memory nằm trong transaction của lượt
trả lời; thêm một lời gọi HTTP vào đó nghĩa là provider nhúng chậm thì người dùng
chờ, provider nhúng chết thì lượt chat rollback. Đọc thì khác: không nhúng câu
hỏi thì không có nhánh vector, nên chấp nhận một lời gọi có trần thời gian và có
đường lùi.

## Hệ quả

### Chấp nhận

- Memory mới không được truy hồi bằng vector cho tới khi việc nhúng nền chạy
  xong. Trong khoảng đó nhánh từ khoá vẫn tìm được, chỉ kém hơn.
- Mỗi lượt hỏi tốn thêm một lời gọi nhúng, đo bằng telemetry và tắt được bằng cờ.
- Đổi model nhúng là phải nhúng lại cả `chunks` lẫn `user_memories`, vì pgvector
  khoá số chiều theo cột.
- Thứ tự kết quả không còn suy ra được chỉ từ văn bản; eval phải cố định model
  nhúng để tái lập.
- Dev và test trên sqlite chạy nhánh từ khoá, nên có một đường mã chỉ được kiểm
  chứng đầy đủ trên Postgres. QA phải có ít nhất một bài chạy trên Postgres.

### Phải làm

- Thêm cột `embedding` và job nhúng nền cho memory chưa có vector.
- Thêm cờ `memory_semantic_recall_enabled` và env template tương ứng.
- Test cách ly người dùng cho nhánh vector, không chỉ cho nhánh từ khoá.
- Test đường lùi: nhúng hỏng thì vẫn trả kết quả từ khoá, không ném lỗi.
- Ghi model nhúng và version bộ trích xuất vào ai-usage-log khi đổi.
- Đóng `TODO(OD)` ở `src/models/message.py` bằng chính ADR này.

### Không đổi

- Thẩm quyền nguồn và trạng thái vẫn do §5, §6 quyết. Vector không thăng cấp
  được `candidate` thành `confirmed`.
- Bất biến §11 giữ nguyên: memory không có bằng chứng thì không tồn tại.
- Phạm vi user vẫn lấy từ phiên đã xác thực, không bao giờ từ model.
- Sửa chữa tường minh của người dùng vẫn thắng mọi thứ suy ra được.

## Rollback

Tắt `memory_semantic_recall_enabled`. Truy hồi quay về nhánh từ khoá cùng sàn
`BASELINE_RELEVANCE`, không cần đổi schema và không mất dữ liệu — cột `embedding`
để nguyên, chỉ thôi được đọc. Rollback không được đụng tới trạng thái hay thẩm
quyền của bất kỳ memory nào, vì hai thứ đó chưa bao giờ phụ thuộc vector.

## Điều kiện chuyển sang `Accepted`

- [ ] Technical Lead duyệt việc lớp memory dùng chung model nhúng với chunk.
- [ ] QA có test cách ly người dùng chạy thật trên PostgreSQL, không chỉ sqlite.
- [ ] QA có test đường lùi khi provider nhúng trả lỗi hoặc quá hạn.
- [ ] Đo được p95 của bước nhúng câu hỏi trên staging và chốt trần thời gian.
- [ ] `TODO(OD)` ở `src/models/message.py` được cập nhật trỏ về ADR này.
- [ ] PM xác nhận hợp đồng xoá dữ liệu không phát sinh bước dọn nào ngoài
      `user_memories`.
