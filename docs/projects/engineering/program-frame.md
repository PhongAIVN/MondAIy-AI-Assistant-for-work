# Program Frame — khung chương trình P-004

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Draft — chờ PM và Technical Lead duyệt |
| Owner | Lê Thị Yến Nhi (UI/UX Lead) |
| Reviewers | Thái Hoài An (PM) · Nguyễn Văn Phong (Technical Lead) · Nguyễn Đức Dũng (PO/QC) |
| Last updated | 2026-08-05 |
| Nguồn chuẩn | Có — khai báo chương trình và mức độ đáng tin của nguồn |
| Related | [PRD FR-040](../product/prd.md) · [ADR-002](adr/adr-002-connector-first-p0-scope.md) · [ADR-003](adr/adr-003-gmail-va-discord-truoc-trong-hai-tuan-build.md) · [Pilot plan](../product/pilot-plan.md) · [Evaluation plan](../qa/evaluation-plan.md) · [Gate 2](../gates/gate-2/README.md) |

## 1. Tài liệu này để làm gì

Khung chương trình là bản khai báo cố định về khóa học: học ở đâu, theo múi giờ
nào, ai đóng vai gì, phải nộp cái gì, và nguồn nào đáng tin hơn nguồn nào.

Nó là **ranh giới lọc nội dung trước khi AI tham gia** ([PRD FR-042](../product/prd.md)).
Không có nó thì mọi thứ đọc được từ năm nguồn đều ngang hàng nhau, và không có
cách nào phân xử khi hai nguồn nói khác nhau.

Exit criteria của Gate 2 (TAPB-3) yêu cầu **"Mức A được đối chiếu với Program
Frame"**. Thiếu tài liệu này thì đến 16/08 Gate 2 hụt một điều kiện.

Hai người dùng trực tiếp tài liệu này:

- **Dũng (PO/QC)** — soạn case cho golden set: case nào là Mức A, case nào Mức
  B, case nào cố tình cho hai mức nói ngược nhau.
- **An (AI/Memory)** — viết prompt extraction: prompt phải biết vai trò và sản
  phẩm bàn giao để không rút nhầm việc của người khác thành việc của user.

## 2. Khai báo chương trình

| Thuộc tính | Giá trị |
| --- | --- |
| Tên chương trình | VinUni AI20K Build Phase |
| Mã dự án | P-004 |
| Cohort | Cohort 3 |
| Độ dài | Sáu tuần |
| Quy mô pilot | Một cohort, 5–10 học viên, bảy ngày liên tục ([pilot plan mục 2](../product/pilot-plan.md)) |
| **Múi giờ** | **`Asia/Ho_Chi_Minh` (UTC+07:00)** |

### Quy tắc múi giờ

Đây là quy tắc bắt buộc, không phải mặc định cho tiện:

1. Mọi mốc thời gian lưu trong database ở dạng `TIMESTAMPTZ`. Không lưu giờ
   trần không offset.
2. Web app gửi khoảng thời gian kèm offset thật
   (`2026-08-05T00:00:00+07:00`), vì node `resolve` cần offset để quy đổi cụm
   thời gian tương đối như "thứ sáu tuần sau".
3. Người dùng có thể tự khai múi giờ khác ([FR-001](../product/prd.md)). Khi
   đó `Asia/Ho_Chi_Minh` chỉ còn là giá trị mặc định lúc khởi tạo, mọi phép
   quy đổi phải dùng múi giờ của chính người dùng.
4. Theo [BR-05](../product/prd.md), chỉ chuyển hạn chót thành thời gian chuẩn
   khi có **đủ ngày, giờ và múi giờ**. Thiếu một trong ba thì giữ nguyên câu
   chữ gốc và đánh dấu `ambiguous`, không tự đoán.

## 3. Vai trò

Vai trò quyết định việc nào là việc của ai. Extraction phải dựa vào bảng này
thay vì đoán từ tên trong tin nhắn.

### Vai trò trong sản phẩm

| Vai trò | Được đọc gì | Nhận việc từ đâu |
| --- | --- | --- |
| Học viên | Nguồn chính họ tự kết nối | Việc gán đích danh, hoặc việc chung cả nhóm |
| Mentor | Không đọc dữ liệu của học viên | Không áp dụng — mentor là người ra yêu cầu, không phải người dùng của bản tóm lược |
| Quản trị chương trình | Không đọc nội dung nguồn cá nhân | Không áp dụng |

Người dùng của P0 chỉ có **học viên**. Mentor và quản trị xuất hiện trong dữ
liệu với tư cách **tác giả của nguồn**, không phải người dùng hệ thống.

### Vai trò trong nhóm P-004

Lấy từ [team directory](../pm/team-directory.md), là nguồn chuẩn:

| Họ tên | Vai trò | Workstream |
| --- | --- | --- |
| Nguyễn Văn Phong | Trưởng nhóm · Technical Lead | Integrator / Platform |
| Lê Thị Yến Nhi | UI/UX Lead | Extension / Product UX |
| Thái Hoài An | PM | Product / Delivery |
| Nguyễn Đức Dũng | PO/QC | Product QA |

## 4. Sản phẩm bàn giao

Đây là danh sách việc mà chương trình bắt buộc phải nộp. Extraction dùng danh
sách này để nhận ra một tin nhắn đang nói về deliverable thật hay chỉ là trò
chuyện.

| Sản phẩm bàn giao | Hạn | Trạng thái |
| --- | --- | --- |
| Gate 1 — Problem & design baseline (Brief, PRD, Wireframe) | 2026-08-02 | Đã nộp lần 3, chờ đánh giá lại |
| Gate 2 — Working MVP & feedback | 2026-08-16 | Đang làm |
| Gate 3 — Release & impact | 2026-09-06 | Chưa bắt đầu |
| Demo Day — 10 deliverables theo checklist BTC | Cuối chương trình | Chưa bắt đầu |

Chi tiết từng gate ở [gates/README.md](../gates/README.md). Deliverable Demo Day
ở [README gốc của template](../../../README.md#-10-deliverables-cho-demo-day).

## 5. Mức độ đáng tin của nguồn

### Phạm vi

Đúng **năm nguồn** trong [ADR-002](adr/adr-002-connector-first-p0-scope.md),
được [ADR-003](adr/adr-003-gmail-va-discord-truoc-trong-hai-tuan-build.md) xác
nhận lại là không đổi. Không nguồn nào khác được xếp mức ở đây.

### Bảng xếp mức

| Nguồn | Mức | Vì sao |
| --- | --- | --- |
| **Discord** | **A** | Kênh công bố chính thức của cohort. Ban tổ chức và mentor thông báo hạn nộp, đổi lịch và yêu cầu ở đây trước tiên |
| **Jira** | **A** | Backlog chính thức. Mỗi issue có người chịu trách nhiệm và trạng thái do người thật đặt, không phải suy ra từ câu chữ |
| **VLearn** | **A** | Hệ thống học tập của trường. Thông báo ở đây là công bố chính thức của chương trình |
| **Google Calendar** | **B** | Lịch **cá nhân** của người dùng, không phải lịch chương trình. Người dùng tự thêm sự kiện theo cách hiểu của họ, nên nó phản ánh kế hoạch riêng chứ không phải công bố chính thức |
| **Gmail** | **B** | Hộp thư cá nhân, lẫn quảng cáo và thư tự động. [ADR-003](adr/adr-003-gmail-va-discord-truoc-trong-hai-tuan-build.md) gọi đây là "nguồn khó nhất về mặt lọc" |

Mỗi nguồn có đúng một mức. Không có nguồn nào vừa A vừa B.

`Calendar` trong [ADR-002](adr/adr-002-connector-first-p0-scope.md) được cụ thể
hóa thành **Google Calendar** ở đây. Đây là thu hẹp phạm vi, không phải thêm
nguồn mới, nên không cần ADR mới.

Mức của Gmail là **tạm thời**. PM chốt ngày 2026-08-05 giữ Gmail ở Mức B cho
tới khi có thêm dữ liệu từ pilot. Nếu hóa ra thông báo chính thức của chương
trình cũng đi qua email thì xem lại, và ghi vào lịch sử sửa đổi ở cuối tài liệu
theo ràng buộc số 4 ở mục 8.

### Vì sao chia như vậy

Ranh giới không nằm ở định dạng dữ liệu, mà ở chỗ **ai có thẩm quyền đặt thông
tin vào đó**. Mức A là nơi người điều hành chương trình công bố. Mức B là nơi
chính người dùng ghi lại cách họ hiểu.

Hai hệ quả dễ hiểu sai nên nói rõ:

- **Discord là Mức A dù là chat.** Trong cohort này, thông báo chính thức đi qua
  Discord trước khi lên bất kỳ đâu khác. Xếp nó xuống Mức B thì hạn chót thật
  sẽ bị trình bày như tin đồn.
- **Google Calendar là Mức B dù thời gian có cấu trúc sẵn.** Dữ liệu sạch không
  đồng nghĩa với đáng tin. Một sự kiện người dùng tự đặt sai ngày vẫn là sai
  ngày, và không được phép ghi đè hạn chót công bố trên Discord hay Jira.

## 6. Khi Mức A và Mức B nói khác nhau

Theo [BR-06](../product/prd.md): *"Mức độ đáng tin của nguồn ảnh hưởng đến lựa
chọn, nhưng thông tin mâu thuẫn vẫn phải được hiển thị."*

Quy tắc xử lý, theo đúng thứ tự:

1. **Lưu cả hai.** Giữ cả hai phiên bản kèm nguồn, tác giả và thời điểm. Không
   xóa, không ghi đè bản cũ.
2. **Mức A thắng về thẩm quyền.** Giá trị của Mức A là giá trị được dùng khi
   hệ thống phải chọn một để hiển thị làm chính.
3. **Vẫn phải hiển thị bản Mức B.** Không được lặng lẽ bỏ bản Mức B đi. Người
   dùng phải nhìn thấy là có hai nguồn nói khác nhau.
4. **Không tự chọn khi cả hai cùng mức.** Hai nguồn cùng Mức A mâu thuẫn thì
   đánh dấu `disputed` và để người dùng quyết. Không lấy bản mới hơn làm chuẩn,
   vì mới hơn không đồng nghĩa với đúng hơn.
5. **Không suy ra ngược.** Mức B mâu thuẫn với Mức A không làm Mức A trở thành
   đáng ngờ. Nó chỉ tạo ra một mục cần người dùng xem lại.

Ví dụ cụ thể để Dũng soạn case:

> Discord `#announcements` ghi hạn nộp wireframe là 07/08 17:00. Trong Google
> Calendar của người dùng, sự kiện "Nộp wireframe" đang đặt ở 10/08.
>
> Đúng: hiện hạn 07/08 17:00 làm chính, kèm cảnh báo "một nguồn khác nói khác",
> mở ra thấy được thông báo Discord nguyên văn kèm link tin gốc, và thấy luôn
> sự kiện 10/08 trong lịch cá nhân.
>
> Sai: hiện hạn 10/08 vì lịch cá nhân "cụ thể hơn". Sai: chỉ hiện 07/08 và giấu
> sự kiện lịch đi — người dùng sẽ không biết mình cần sửa lại lịch của chính
> mình.

## 7. Không có nguồn thì không được publish

Exit criteria thứ hai của TAPB-3: *"Mỗi briefing item có source link; item
thiếu source không publish."*

Điều kiện để một mục được lên bản tóm lược:

1. Có ít nhất một bằng chứng (`task_evidence`) gắn với nó.
2. Bằng chứng đó có `evidence_quote` **khác rỗng** — trích nguyên văn, không
   phải câu do mô hình viết lại.
3. Bằng chứng đó có `deep_link` mở được, hoặc nêu rõ vì sao không có link.
4. Người dùng vẫn còn quyền đọc nguồn đó ở thời điểm hiển thị ([BR-10](../product/prd.md)).

Thiếu bất kỳ điều nào thì mục đó không lên bản tóm lược, kể cả khi tiêu đề trông
hợp lý.

**Trạng thái hiện tại: chưa có chỗ nào trong mã kiểm điều này.** `_build_brief`
ở `src/api/runs.py` sắp việc theo `signal_strength` rồi lấy ba mục đầu, không
kiểm bằng chứng. `persist.py` dùng `item.get("evidence_quote", "")` nên trích
dẫn rỗng vẫn ghi được vào database. Đây là việc phải đóng trước Gate 2.

## 8. Ràng buộc

1. **Chỉ năm nguồn ADR-002.** Thêm nguồn mới là thay đổi về quyền riêng tư,
   phải có ADR mới, không phải sửa bảng ở mục 5.

   Cụ thể với Telegram: web app đã ẩn nó khỏi màn chọn nguồn, Thư viện nguồn và
   số đếm ở sidebar. Công tắc nằm ở `ENABLED_PROVIDERS` trong
   `client/web-app/src/types/pipeline.ts` — thêm `'telegram'` vào đó là mở lại,
   nhưng **chỉ được làm sau khi có ADR mới**. Mã backend
   (`src/api/connections.py`, `src/services/connections/telegram.py`) giữ
   nguyên, không xóa, để lần mở lại không phải viết lại từ đầu.
2. **Một nguồn một mức.** Không có nguồn nào vừa A vừa B tùy ngữ cảnh.
3. **Không gộp hai mức.** Theo [Documentation Guide](../DOCUMENTATION-GUIDE.md),
   không được trộn dữ liệu Mức A và Mức B thành một mục duy nhất rồi mất dấu vết
   mỗi phần đến từ đâu.
4. **Đổi mức phải ghi lại.** Chuyển một nguồn từ B lên A là thay đổi cách hệ
   thống phân xử mâu thuẫn. Ghi vào lịch sử sửa đổi ở cuối tài liệu này, kèm lý
   do và người duyệt.

## 9. Việc còn mở

| ID | Vấn đề | DRI | Chặn Gate 2? |
| --- | --- | --- | --- |
| PF-01 | ~~`src/api/connections.py` đang chạy provider `telegram`, ngoài năm nguồn ADR-002~~ **Đã xử 2026-08-05:** web app ẩn Telegram khỏi mọi màn hình qua `ENABLED_PROVIDERS`. Mã backend giữ nguyên để mở lại được | Lê Thị Yến Nhi (đã xong phần web app) · Nguyễn Văn Phong (quyết định có gỡ hẳn backend không) | Không còn |
| PF-02 | Chưa có chỗ nào kiểm "thiếu bằng chứng thì không publish" (mục 7) | Nguyễn Văn Phong | Có — là exit criteria của TAPB-3 |
| PF-03 | Program Frame chưa có bảng nào trong database, cũng chưa có endpoint. Hiện chỉ là tài liệu | Nguyễn Văn Phong | Không cho Gate 2 nếu đối chiếu bằng tay và ghi lại được |
| PF-04 | Discord là nguồn Mức A duy nhất có thể chạy trước 16/08. [ADR-003](adr/adr-003-gmail-va-discord-truoc-trong-hai-tuan-build.md) quyết định 1 ghi rõ Jira và VLearn "chưa đụng tới" trong hai tuần build. Discord đã đọc được raw message (TAPB-122) nhưng chưa cắm vào pipeline chung (TAPB-130): `GET /integrations/{id}/sources` vẫn trả 400 cho Discord | Thái Hoài An (An) — TAPB-130 | Có — không có nguồn Mức A chạy thật thì không đối chiếu được |
| PF-06 | [ADR-003](adr/adr-003-gmail-va-discord-truoc-trong-hai-tuan-build.md) quyết định 3: nếu 15/08 chưa thông hai nguồn thì **cắt Discord**, giữ Gmail. Với bảng mức này, cắt Discord là cắt luôn nguồn Mức A cuối cùng | Nguyễn Văn Phong (owner ADR-003) | Có |
| PF-07 | [ADR-003](adr/adr-003-gmail-va-discord-truoc-trong-hai-tuan-build.md) phần Lý do ghi "Discord của cohort thưa tin, có tuần không có gì để rút trích". Nguồn Mức A mà thưa tin thì golden set thiếu case Mức A thật | Nguyễn Đức Dũng | Không, nhưng ảnh hưởng chất lượng đánh giá |
| PF-05 | `docs/architecture/dataflow_detail.mmd:71` ghi quy tắc mâu thuẫn là "BR-05", nhưng BR-05 trong PRD là quy tắc chuyển hạn chót. Quy tắc mâu thuẫn là **BR-06**. Sửa lại trong sơ đồ | Lê Thị Yến Nhi | Không |

### PF-04 và PF-06 là cùng một đường găng

Ghép ba dòng đã có sẵn trong tài liệu của nhóm:

1. **ADR-003 quyết định 1** — hai tuần build chỉ làm Gmail và Discord; Jira và
   VLearn "chưa đụng tới".
2. **Program Frame mục 5** — trong hai nguồn đó, chỉ Discord là Mức A.
3. **TAPB-3 exit criteria** — "Mức A được đối chiếu với Program Frame".

Ba dòng đó cộng lại thành một kết luận: **TAPB-130 (cắm Discord vào pipeline
chung) là điều kiện cần của Gate 2**, không phải việc tốt-thì-có. Hiện nó chưa
xong — `GET /integrations/{id}/sources` vẫn trả 400 cho Discord nên người dùng
chưa chọn được nguồn Discord để chạy.

Và **ADR-003 quyết định 3 đang mâu thuẫn với chính exit criteria đó**: nếu
15/08 chưa thông hai nguồn thì cắt Discord, giữ Gmail. Cắt Discord tức là chỉ
còn Gmail — Mức B. Không còn nguồn Mức A nào để đối chiếu, Gate 2 hụt một điều
kiện dù pipeline chạy đẹp.

Quyết định 3 viết ra khi chưa có Program Frame nên chưa biết Discord sẽ là Mức
A. Không phải người viết sai, chỉ là thiếu dữ kiện. ADR-003 vẫn đang ở trạng
thái `Proposed`, sửa lúc này rẻ.

### Đã chốt 2026-08-05

**Discord vẫn là nguồn chính thức và không bị cắt.** Nó cần API để chạy thật,
nhưng việc chưa có API không được phép chặn phần còn lại.

Trong lúc chờ TAPB-130, giao diện đi trước bằng dữ liệu mẫu:

1. Backend trả 400 khi liệt kê nguồn con của Discord. Web app **vẫn hiện một
   nguồn mẫu chọn được**, kèm dòng nói rõ đây là dữ liệu mẫu. Không có nó thì
   cả trang đứng ở bước chọn nguồn và không demo được gì.
2. Chọn nguồn mẫu thì **cả lần chạy đi theo đường dữ liệu mẫu** và băng vàng
   bật lên. Không gửi id giả lên backend, vì làm vậy chỉ tạo ra một run chắc
   chắn lỗi.
3. Mức A và Mức B **hiện thành nhãn trên giao diện** — ở màn chọn nguồn và ở
   từng dòng bằng chứng trong hộp duyệt việc. Bảng mức ở mục 5 là nguồn chuẩn,
   web app đọc lại qua `SOURCE_LEVEL` trong `client/web-app/src/types/pipeline.ts`.

Khi TAPB-130 xong, nguồn mẫu biến mất và băng vàng tự tắt. Đó là cách kiểm tra
bằng mắt xem Gate 2 đã có nguồn Mức A thật hay chưa.

**Quyết định 3 của ADR-003 vẫn cần sửa.** Câu "nếu trễ thì cắt Discord, giữ
Gmail" viết khi chưa có Program Frame nên chưa biết Discord sẽ là Mức A. Cắt
Discord bây giờ là cắt luôn nguồn Mức A cuối cùng, tức là tự bỏ một exit
criteria của Gate 2. ADR-003 còn ở trạng thái `Proposed` nên sửa lúc này rẻ.

Đề xuất: đổi thành *nếu trễ thì cắt Gmail, giữ Discord*. Lý do ADR-003 chọn
Gmail trước là "Gmail là nguồn khó nhất về mặt lọc" — mục tiêu đó đã đạt khi
bước filter chạy được với Gmail. Giữ Gmail tới phút chót không thêm giá trị cho
Gate 2, trong khi mất Discord là mất một điều kiện. Cần Technical Lead duyệt.

## 10. Cách dùng tài liệu này

**Dũng — soạn golden set:** mục 5 cho biết case nào gắn nhãn A hay B; mục 6 cho
biết kết quả đúng khi hai mức mâu thuẫn; mục 7 cho biết case nào phải bị chặn
không được publish. Bộ tối thiểu theo [evaluation plan mục 3](../qa/evaluation-plan.md)
cần ít nhất một case cho mỗi dòng ở mục 6.

**An — viết prompt extraction:** mục 3 cho biết vai trò để không rút nhầm việc
của người khác; mục 4 cho biết tên deliverable thật để nhận ra tin nhắn nào nói
về việc thật; mục 2 cho biết múi giờ để prompt **không tự quy đổi ngày giờ** mà
chỉ trích nguyên văn cụm thời gian, để node `resolve` xử lý.

## Lịch sử sửa đổi

| Ngày | Thay đổi | Người |
| --- | --- | --- |
| 2026-08-05 | Bản đầu. Khai báo chương trình, múi giờ, vai trò, sản phẩm bàn giao; xếp mức năm nguồn ADR-002; quy tắc mâu thuẫn A/B; quy tắc chặn publish khi thiếu bằng chứng | Lê Thị Yến Nhi |
| 2026-08-05 | Đổi mức theo chốt của PM: Discord lên Mức A vì là kênh công bố chính thức của cohort; Calendar xuống Mức B và cụ thể hóa thành Google Calendar vì là lịch cá nhân. Cập nhật ví dụ mâu thuẫn và PF-04 theo mức mới | Lê Thị Yến Nhi |
| 2026-08-05 | Đối chiếu với ADR-003: thêm PF-06 (quyết định cắt Discord mâu thuẫn với exit criteria Gate 2) và PF-07 (Discord thưa tin nên thiếu case Mức A cho golden set) | Lê Thị Yến Nhi |
| 2026-08-05 | Chốt giữ Discord là nguồn chính thức; web app đi trước bằng nguồn mẫu và nhãn Mức A/B trong lúc chờ TAPB-130. Đề nghị sửa quyết định 3 của ADR-003 | Lê Thị Yến Nhi |
| 2026-08-05 | Ẩn Telegram khỏi web app qua `ENABLED_PROVIDERS`; giữ nguyên mã backend để mở lại được khi có ADR mới. Đóng PF-01 | Lê Thị Yến Nhi |
| 2026-08-05 | PM xác nhận giữ Gmail ở Mức B, đánh dấu là mức tạm thời, xem lại sau khi có dữ liệu pilot | Lê Thị Yến Nhi |
