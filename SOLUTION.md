# SOLUTION.md

**AI Assistant tổng hợp công việc đa nền tảng**

Tài liệu này giải thích *cách giải quyết bài toán*, không chứa code. Đọc từ trên xuống sẽ hiểu được toàn bộ luồng: người dùng bấm gì ở Frontend → Backend làm gì → AI làm gì → kết quả quay lại người dùng ra sao.

---

## Mục lục

1. [Bài toán](#1-bài-toán)
2. [Nguyên tắc thiết kế](#2-nguyên-tắc-thiết-kế)
3. [Bức tranh tổng thể](#3-bức-tranh-tổng-thể)
4. [Frontend làm gì](#4-frontend-làm-gì)
5. [Backend làm gì](#5-backend-làm-gì)
6. [AI làm gì](#6-ai-làm-gì)
7. [Ví dụ chạy xuyên suốt](#7-ví-dụ-chạy-xuyên-suốt)
8. [Ranh giới AI và Code](#8-ranh-giới-ai-và-code)
9. [Giới hạn nền tảng](#9-giới-hạn-nền-tảng)
10. [Đo lường thành công](#10-đo-lường-thành-công)
11. [Phạm vi MVP](#11-phạm-vi-mvp)
12. [Rủi ro](#12-rủi-ro)

---

## 1. Bài toán

Người dùng là người hay quên. Công việc của họ nằm rải rác ở Discord, Gmail, Telegram, Slack. Không ai đọc hết được, và những gì đọc lướt qua thì quên ngay.

Họ mở ứng dụng, chọn các nguồn muốn theo dõi, chọn khoảng thời gian, bấm một nút. Họ mong nhận được câu trả lời cho đúng một câu hỏi:

> **"Ba ngày qua tôi có gì phải làm mà chưa làm?"**

Nhìn từ góc kỹ thuật, đây là bài toán **lọc nhiễu cực đoan**:

```
1.680 tin nhắn / email    →    10 – 15 việc thật sự
```

99% dữ liệu là rác. Cái khó là rác và không-rác **nhìn giống hệt nhau**. "ok anh" và "mai deploy nhé" đều là chuỗi ký tự ngắn, cùng người gửi, cùng một channel, cách nhau một phút.

Đây không phải bài toán "gọi AI cho giỏi". Đây là bài toán **thiết kế phễu lọc**.

---

## 2. Nguyên tắc thiết kế

Bốn nguyên tắc chi phối mọi quyết định trong tài liệu này.

### 2.1. Lọc rẻ trước, AI sau

Mỗi tầng chỉ đẩy xuống dưới thứ mà nó không tự giải quyết được. Việc gì code làm được thì code làm, vì code miễn phí, nhanh, và luôn cho cùng một kết quả.

### 2.2. Nhiều lần đọc ít, thay vì một lần đọc nhiều

Đây là điểm phản trực giác quan trọng nhất:

> **AI đọc 15 tin nhắn thì bắt được gần như 100% việc.**
> **AI đọc 1.000 tin nhắn thì bắt được chưa tới một nửa.**

Model có xu hướng *tóm tắt* thay vì *liệt kê đầy đủ* khi văn bản quá dài, và những gì nằm ở giữa đoạn dài hay bị bỏ qua. Sản phẩm này bán lời hứa "không bỏ sót việc" — mà đó đúng là thứ cách-đọc-một-lần làm tệ nhất.

Chia nhỏ **không phải để tiết kiệm tiền**. Tiết kiệm tiền chỉ là phần thưởng đi kèm. Lý do chính là chất lượng.

### 2.3. AI hiểu ngôn ngữ, Code xử lý dữ liệu

| AI làm                                                  | Code làm                                  |
| -------------------------------------------------------- | ------------------------------------------ |
| Đọc hiểu tiếng Việt lộn xộn, teencode, viết tắt | Tính ngày giờ, múi giờ                |
| Nhận ra câu nào là việc phải làm                  | Tra danh tính người dùng               |
| Viết tiêu đề sạch từ câu nói bừa bãi           | Phát hiện và gộp việc trùng          |
| Viết bản tóm tắt, xếp thứ tự ưu tiên            | Ghi database, đồng bộ lịch, gửi nhắc |

Ranh giới này quyết định hệ thống có đáng tin hay không. Vi phạm nó là nguồn gốc của gần như mọi lỗi không tái hiện được.

### 2.4. Mọi việc phải chỉ ra được nguồn gốc

Mỗi việc hiển thị cho người dùng phải kèm: câu nói gốc, ai nói, lúc nào, và link mở đúng tin nhắn đó trên nền tảng gốc.

Không có phần này, người dùng không bao giờ tin sản phẩm — và một sản phẩm quản lý công việc mà người dùng không tin thì vô dụng.

---

## 3. Bức tranh tổng thể

```
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND                                                   │
│  Cấu hình nguồn → Chọn khoảng thời gian → Bấm Tổng hợp      │
│  Xem tiến trình → Duyệt từng việc → Xác nhận → Lên lịch     │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│  BACKEND — phễu 4 tầng                                      │
│                                                             │
│   1.680 tin thô                                             │
│        │                                                    │
│   ┌────▼────────────────┐                                   │
│   │ T1 · LỌC THÔ        │  Code · 0đ · 0,2s                │
│   │ Bỏ tin không có     │  bỏ 95%                           │
│   │ dấu hiệu công việc  │                                   │
│   └────┬────────────────┘                                   │
│        │ ~90 tin                                            │
│   ┌────▼────────────────┐                                   │
│   │ T2 · HIỂU           │  🔴 AI · 14 lô × 15 tin           │
│   │ Đọc từng lô nhỏ,    │  chạy song song                   │
│   │ điền vào biểu mẫu   │                                   │
│   └────┬────────────────┘                                   │
│        │ ~63 mục việc                                       │
│   ┌────▼────────────────┐                                   │
│   │ T3 · DỌN & GỘP      │  Code · 0đ                        │
│   │ Tính ngày, bỏ trùng,│  gộp xuyên nền tảng               │
│   │ bỏ việc người khác  │                                   │
│   └────┬────────────────┘                                   │
│        │ ~26 việc duy nhất                                  │
│   ┌────▼────────────────┐                                   │
│   │ T4 · VIẾT           │  🔴 AI · 1 lần duy nhất           │
│   │ Tóm tắt + ưu tiên   │  chỉ đọc 26 dòng đã gọn           │
│   └────┬────────────────┘                                   │
│        ▼                                                    │
│   Tóm tắt + Danh sách việc + Cảnh báo trùng lịch            │
└────────────────────────────┬────────────────────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  Google Calendar (sau khi   │
              │  người dùng xác nhận)       │
              └─────────────────────────────┘
```

Chỉ **2 trên 4 tầng** gọi AI. Hai tầng còn lại là code thường, miễn phí, chạy trong tích tắc.

---

## 4. Frontend làm gì

Frontend không chỉ là chỗ hiển thị kết quả. Nó gánh **ba trách nhiệm** ảnh hưởng trực tiếp đến chất lượng và chi phí của cả hệ thống.

### 4.1. Thu hẹp phạm vi — trách nhiệm quan trọng nhất

Người dùng phải chọn **chính xác** nguồn nào được đọc. Không phải "kết nối Discord", mà là "kết nối Discord, và chỉ đọc kênh `#task` và `#dev-team`".

Màn hình cấu hình cho từng nền tảng:

```
Discord · Server "Cty ABC"
   ☑ #task            ~50 tin/ngày
   ☑ #dev-team       ~200 tin/ngày
   ☐ #random         ~310 tin/ngày     ← không tick = không tốn gì
   ☐ #general        ~240 tin/ngày

Gmail
   ☑ Hộp thư chính
   ☐ Quảng cáo
   ☐ Mạng xã hội

Telegram
   ☑ Nhóm "Team ABC"
   ☐ Nhóm "Gia đình"
```

Đây là **bộ lọc rẻ nhất trong toàn hệ thống**. Người dùng biết rõ kênh nào có việc, kênh nào chỉ có meme — thông tin mà không thuật toán nào đoán chính xác bằng. Bỏ tick một kênh 310 tin/ngày là tiết kiệm được đúng 310 tin, ngay lập tức, miễn phí.

Frontend cũng nên hiển thị số tin ước tính bên cạnh mỗi kênh, để người dùng hiểu hệ quả của lựa chọn.

### 4.2. Chọn khoảng thời gian — nhưng đừng bắt người dùng suy nghĩ

Người dùng thường **không biết mình muốn khoảng nào**. Câu hỏi thật trong đầu họ là *"tôi bỏ lỡ gì rồi?"*, không phải *"cho tôi xem từ 29/07 đến 31/07"*.

Vì vậy:

```
Tổng hợp cho tôi:
   ● Từ lần xem cuối   (2 ngày trước)     ← mặc định
   ○ Hôm nay
   ○ 7 ngày qua
   ○ Tùy chọn: [__/__] → [__/__]
```

"Từ lần xem cuối" khớp đúng mô hình tư duy của người hay quên, và tự nhiên tránh xử lý lại dữ liệu cũ. Tùy chọn thủ công vẫn giữ, nhưng là phương án phụ.

Frontend cần chặn khoảng quá rộng (ví dụ tối đa 14 ngày cho gói miễn phí) và nói rõ lý do, thay vì để Backend im lặng cắt bớt.

### 4.3. Hiển thị tiến trình, không hiện vòng xoay

Quá trình xử lý mất khoảng 10–15 giây. Nếu chỉ hiện một vòng xoay, người dùng sẽ nghĩ ứng dụng bị treo và sẽ không quay lại lần thứ ba.

Backend gửi tiến trình theo thời gian thực. Frontend hiện:

```
✓ Đã lấy dữ liệu        1.680 tin từ 3 nguồn        3,2s
✓ Đã lọc                1.680 → 87 tin có dấu hiệu  0,1s
✓ Đã chia               14 nhóm hội thoại
⏳ Đang phân tích        9/14 nhóm...
⏸ Chờ tổng hợp
```

Cách này khiến 12 giây cảm giác ngắn hơn 4 giây nhìn vòng xoay, vì người dùng thấy được hệ thống đang thực sự làm việc và hiểu nó làm gì.

### 4.4. Hộp duyệt việc — nơi quyết định người dùng có tin sản phẩm không

Kết quả **không** tự động vào Google Calendar. Nó vào một hộp chờ duyệt.

Mỗi việc hiển thị đầy đủ:

```
┌─────────────────────────────────────────────────┐
│ 🚀 Deploy production v2.1                       │
│    Hạn: Thứ 3, 04/08 · 17:00                    │
│                                                 │
│    📍 Được nhắc ở 3 nơi · có người hỏi lại      │
│                                                 │
│    💬 Discord #task · Minh · 02/08 09:14        │
│       "deploy prod v2.1 trước thứ 5 nhé Phong"  │
│       [Mở tin nhắn →]                           │
│    💬 Gmail · 02/08 15:40                       │
│       "cần deploy xong trước 04/08 kịp demo KH" │
│       [Mở email →]                              │
│    💬 Telegram · 03/08 08:02                    │
│       "v2.1 deploy chưa a ơi"                   │
│       [Mở →]                                    │
│                                                 │
│    [ ✓ Thêm vào lịch ]  [ ✏️ Sửa ]  [ ✗ Bỏ ]   │
└─────────────────────────────────────────────────┘
```

Bốn điểm cần chú ý trong thiết kế màn hình này:

**a) Bằng chứng luôn hiện.** Không giấu sau nút "xem chi tiết". Người dùng phải thấy ngay vì sao hệ thống nghĩ đây là việc của họ.

**b) Link mở tin nhắn gốc.** Đây là thứ khiến người dùng tin. Họ bấm vào, thấy đúng tin nhắn đó, và từ lần sau họ không cần kiểm tra nữa.

**c) Việc có độ tin cậy thấp phải hiện cảnh báo.**

```
⚠️ "thứ 6 này" chưa rõ là 31/07 hay 07/08 — kiểm tra lại
```

Thà thừa nhận không chắc còn hơn đoán bừa rồi sai.

**d) Mỗi thao tác của người dùng là dữ liệu quý.** Bấm ✓, bấm ✗, sửa tiêu đề, sửa deadline — tất cả được ghi lại. Sau vài nghìn thao tác, đây là bộ dữ liệu để cải thiện bộ lọc và prompt, và là **lợi thế cạnh tranh duy nhất bền vững** của sản phẩm. Không đối thủ nào copy được dữ liệu này.

### 4.5. Tóm tắt trách nhiệm Frontend

| Trách nhiệm                            | Ảnh hưởng                                         |
| ---------------------------------------- | ---------------------------------------------------- |
| Cho chọn kênh cụ thể                 | Giảm 60–80% dữ liệu phải xử lý, miễn phí    |
| Gợi ý khoảng thời gian hợp lý      | Tránh yêu cầu quá rộng gây chậm và tốn kém |
| Hiện tiến trình từng bước          | Giữ người dùng ở lại trong 15 giây chờ đợi |
| Bắt buộc duyệt trước khi lên lịch | Chặn rác vào Google Calendar — rủi ro số 1     |
| Luôn hiện bằng chứng + link gốc     | Xây niềm tin                                       |
| Ghi lại mọi thao tác duyệt           | Tạo dữ liệu cải tiến sản phẩm                 |

---

## 5. Backend làm gì

Backend chịu trách nhiệm cho toàn bộ phễu 4 tầng.

### 5.1. Tầng 0 — Lấy dữ liệu

Nhận yêu cầu từ Frontend (danh sách kênh + khoảng thời gian), gọi song song tới các nền tảng đã kết nối.

Ba việc quan trọng ở tầng này:

**Gọi song song, không tuần tự.** Ba nguồn gọi cùng lúc thì tổng thời gian bằng nguồn chậm nhất, không phải tổng cộng.

**Một nguồn chết không kéo cả hệ thống chết.** Nếu Telegram timeout, vẫn trả kết quả từ Discord và Gmail, kèm cảnh báo rõ ràng: *"Không lấy được dữ liệu Telegram, kết quả có thể thiếu."* Im lặng bỏ qua là hành vi tệ nhất có thể.

**Tôn trọng giới hạn của từng nền tảng.** Mỗi nền tảng có giới hạn số lần gọi khác nhau. Backend phải xếp hàng và chờ đúng nhịp thay vì gọi dồn dập rồi bị chặn.

### 5.2. Tầng 0.5 — Chuẩn hoá

Dữ liệu từ ba nền tảng có ba định dạng hoàn toàn khác nhau. Backend đưa tất cả về **một dạng chung** trước khi xử lý tiếp:

- Ai gửi, có phải chính người dùng không
- Nội dung đã làm sạch
- Có nhắc tên người dùng không
- Thời điểm gửi, đã đổi về múi giờ người dùng
- Link mở tin nhắn gốc

Riêng với email, bước làm sạch tiết kiệm rất nhiều: cắt bỏ phần trích dẫn thư cũ, chữ ký, chân trang, lời từ chối trách nhiệm pháp lý. Một email 3.000 token thường chỉ có khoảng 150 token là nội dung mới thật sự.

**Đây là bước bị coi nhẹ nhất nhưng cho hiệu quả cao nhất trên mỗi giờ công bỏ ra.** Làm sạch tốt giúp chất lượng trích xuất tăng rõ rệt mà không cần đổi model hay sửa prompt.

### 5.3. Tầng 1 — Lọc thô

Chấm điểm từng tin nhắn bằng luật. Không AI, không tốn tiền, chạy trong micro giây.

**Điểm cộng:**

| Dấu hiệu               | Ví dụ                                               |
| ------------------------ | ----------------------------------------------------- |
| Từ chỉ thời gian      | mai, thứ 6, 8h, deadline, trước 15/8, EOD          |
| Động từ công việc   | deploy, họp, gửi, nộp, thanh toán, backup, review |
| Từ mang tính nhờ vả  | nhớ, cần, phải, giúp, nhé, ơi                   |
| Nhắc tên người dùng | @Phong                                                |
| Tin nhắn riêng         | DM 1-1                                                |

**Điểm trừ / loại thẳng:**

| Dấu hiệu                       | Ví dụ                            |
| -------------------------------- | ---------------------------------- |
| Quá ngắn, chỉ là phản ứng  | "ok", "haha", ":v", sticker        |
| Do chính người dùng gửi     | (trừ khi tự ghi chú)            |
| Từ hệ thống, quảng cáo      | no-reply@, newsletter              |
| Từ thể hiện chưa chắc chắn | "chắc mai deploy", "để xem sao" |

**Nguyên tắc chỉnh ngưỡng — rất quan trọng:**

> Đặt ngưỡng **thấp**. Thà giữ nhầm còn hơn bỏ sót.

Lý do bất đối xứng: nếu tầng 1 bỏ nhầm một tin, nó **mất vĩnh viễn**, không tầng nào phía sau cứu được. Còn nếu tầng 1 giữ nhầm, AI ở tầng 2 sẽ loại giúp. Chi phí của hai loại sai lầm này khác nhau một trời một vực.

Kết quả điển hình: từ 1.680 tin còn khoảng 90 tin. Bỏ 95% mà chưa tốn một đồng.

### 5.4. Tầng 2 — Chia lô

Trước khi gọi AI, Backend chia 90 tin còn lại thành các lô nhỏ theo ba ranh giới:

| Ranh giới    | Giá trị                                      | Lý do                                                                       |
| ------------- | ---------------------------------------------- | ---------------------------------------------------------------------------- |
| Không gian   | 1 cuộc hội thoại (1 kênh / 1 thread email) | Tin ở`#dev-team` không giúp hiểu tin ở `#design`                    |
| Thời gian    | Cửa sổ 30 phút                              | Hội thoại chat có nhịp; ngoài 30 phút thì gần như không liên quan |
| Kích thước | Tối đa 15–20 tin                            | Vượt ngưỡng thì chất lượng trích xuất tụt                         |

**Kèm theo ngữ cảnh xung quanh.** Với mỗi tin có dấu hiệu, lấy thêm 3 tin trước và 2 tin sau — kể cả những tin đã bị tầng 1 loại.

Vì sao bắt buộc? Xét tin nhắn này:

> *"à mà nhớ backup db trước khi deploy nhé"*

Không nhắc tên ai, không có giờ, không có ngày. Đọc một mình thì vô nghĩa. Chỉ khi đặt cạnh hai tin phía trên mới hiểu được: Minh đang nói tiếp với Phong, và việc này phải xong trước 8h sáng mai.

**Kết quả:** khoảng 14 lô, mỗi lô ~15 tin.

**Quan trọng:** cuộc hội thoại nào không có tin nào vượt filter thì **không sinh ra lô nào**. Kênh toàn meme mãi mãi tốn 0 đồng.

### 5.5. Tầng 3 — Dọn dẹp sau khi AI trả kết quả

Sau khi AI trả về khoảng 63 mục thô, Backend làm 4 việc, tất cả bằng code:

**a) Tính ngày giờ thật.**

AI chỉ trả về cụm chữ nguyên văn: `"mai lúc 8h"`. Backend dùng thư viện phân tích ngày tháng, kết hợp với thời điểm tin nhắn được gửi và múi giờ người dùng, để ra `01/08/2026 08:00 (+07)`.

Nếu gặp trường hợp mơ hồ — ví dụ "thứ 6 này" khi hôm nay đang là thứ 6 — thì **hạ độ tin cậy và gắn cảnh báo**, thay vì đoán bừa.

> Đây là quy tắc quan trọng nhất của cả hệ thống. Lý do ở mục 8.

**b) Bỏ việc của người khác.**

AI đưa ra gợi ý "việc này của tôi / của người khác / không rõ". Backend đối chiếu với bảng danh tính người dùng trên từng nền tảng. Nếu là việc người khác → bỏ.

Đây là bộ lọc chống spam quan trọng nhất khi người dùng ở trong server đông người. Không có nó, mỗi lời nhờ vả giữa hai đồng nghiệp khác cũng thành một việc trong danh sách.

**c) Bỏ việc đã qua.**

Deadline nằm trước thời điểm tin nhắn được gửi → chắc chắn hiểu sai → bỏ.

**d) Gộp việc trùng — phần tạo giá trị lớn nhất.**

Chi tiết ở mục tiếp theo.

### 5.6. Gộp việc xuyên nền tảng — điểm khác biệt của sản phẩm

Cùng một việc thường xuất hiện ở nhiều nơi:

```
Discord   02/08 09:14   "deploy prod v2.1 trước thứ 5 nhé Phong"
Gmail     02/08 15:40   "...cần deploy xong trước 04/08 để kịp demo KH"
Telegram  03/08 08:02   "v2.1 deploy chưa a ơi"
```

Ba nguồn, ba cách nói, **một việc duy nhất**. Nếu hệ thống trả ra 3 việc riêng, người dùng thấy nó ngu ngốc và gỡ app.

Backend gộp theo **thang 3 bậc**, chỉ leo lên bậc trên khi bậc dưới không quyết được:

| Bậc | Cách nhận biết                                                             | Chi phí | Bắt được                                |
| ---- | ----------------------------------------------------------------------------- | -------- | ------------------------------------------- |
| 1    | Khóa cứng: cùng thread, cùng link, cùng mã hóa đơn, cùng số ticket | 0đ      | Chắc chắn 100%                            |
| 2    | Tiêu đề gần giống nhau về mặt chữ                                     | 0đ      | Đa số trường hợp                       |
| 3    | Gần nhau về**nghĩa** (dùng embedding)                               | ~0đ     | Trường hợp diễn đạt hoàn toàn khác |

> **Đây là chỗ duy nhất trong sản phẩm cần embedding** — không phải để làm RAG, mà để nhận ra hai câu khác chữ nhưng cùng nghĩa. Chỉ cần dùng khả năng vector có sẵn trong PostgreSQL, không cần cài thêm vector database riêng.

Sau khi gộp, Backend suy ra ba thông tin mà **không sản phẩm đơn-nền-tảng nào có được**:

| Thông tin            | Cách suy ra                                     | Ý nghĩa                                                                         |
| --------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------- |
| Mức độ quan trọng | Việc được nhắc ở mấy nguồn khác nhau    | Nhắc ở 3 nơi = gần như chắc chắn là việc gấp nhất                      |
| Đang bị trễ        | Có người hỏi lại ("xong chưa", "sao rồi") | Cần ưu tiên ngay                                                               |
| Deadline thật        | Lấy mốc**sớm nhất** trong nhóm        | Discord nói "trước thứ 5", Gmail nói "trước 04/08" → lấy cái chặt hơn |

Đây chính là lý do người dùng cần sản phẩm này thay vì mở từng app ra xem.

### 5.7. Tầng 4 — Lưu và đồng bộ

Sau khi người dùng bấm ✓ ở Frontend, Backend mới ghi lên Google Calendar.

Ba nguyên tắc bắt buộc:

**a) Chỉ đồng bộ việc đã được duyệt.** Không tự động. Calendar là không gian thiêng của người dùng; tạo nhầm 3 sự kiện là mất người dùng vĩnh viễn.

**b) Ghi có thể lặp lại an toàn.** Backend lưu mã sự kiện Google cho từng việc. Nếu người dùng bấm hai lần, hoặc hệ thống thử lại sau lỗi mạng, chỉ có **một** sự kiện được tạo.

**c) Cập nhật thay vì tạo mới.** Vài ngày sau, nếu có tin nhắn *"dời deploy sang 10h nhé"*, hệ thống nhận ra đây là việc đã có, và **sửa** sự kiện cũ chứ không tạo cái thứ hai. Không có bước này, Calendar của người dùng đầy sự kiện trùng lặp chỉ sau một tuần.

### 5.8. Tóm tắt trách nhiệm Backend

| Tầng | Việc                                         | AI? | Chi phí | Thời gian |
| ----- | --------------------------------------------- | :-: | -------- | ---------- |
| 0     | Lấy dữ liệu song song, chịu lỗi cục bộ |    | thấp    | 3–8s      |
| 0.5   | Chuẩn hoá, làm sạch, đổi múi giờ      |    | 0đ      | 0,2s       |
| 1     | Lọc thô bằng luật                         |    | 0đ      | 0,1s       |
| 2     | Chia lô + kèm ngữ cảnh                    |    | 0đ      | 0,1s       |
| —    | *(gọi AI — mục 6)*                       | 🔴 |          | 4–6s      |
| 3     | Tính ngày, lọc người, gộp trùng        |    | 0đ      | 0,3s       |
| —    | *(gọi AI — mục 6)*                       | 🔴 |          | 2–3s      |
| 4     | Lưu, đồng bộ lịch, nhắc nhở            |    | 0đ      | —         |

---

## 6. AI làm gì

Toàn bộ phần AI của sản phẩm gói gọn trong **hai lần gọi có mục đích rõ ràng**. Không hơn.

### 6.1. Lần gọi thứ nhất — Hiểu và điền biểu mẫu

**Chạy:** 14 lần, song song, mỗi lần đọc ~15 tin nhắn.

**Nhiệm vụ:** đọc một đoạn hội thoại ngắn và điền vào biểu mẫu cố định.

Với mỗi việc tìm được, AI phải điền:

| Trường        | Ví dụ                                            | Ghi chú                                                |
| --------------- | -------------------------------------------------- | ------------------------------------------------------- |
| Loại           | công việc / cuộc họp / hạn chót / thông tin |                                                         |
| Tiêu đề      | "Deploy server"                                    | Đã làm sạch, ngắn gọn                             |
| Chi tiết       | "Xong báo lại cho Minh"                          |                                                         |
| Ai làm         | tôi / người khác / không rõ                  | **Chỉ gợi ý, không kết luận**               |
| Cụm thời gian | **"mai lúc 8h"**                            | ⚠️**Nguyên văn — không phải ngày tháng** |
| Câu gốc       | "mai nhớ deploy server lúc 8h nha"               | Bắt buộc                                              |
| Độ tự tin    | 0,94                                               | AI tự đánh giá                                      |

**Ba quy tắc cứng trong lần gọi này:**

**a) Cấm tính ngày tháng.** AI chỉ trả cụm chữ. Code tính ra ngày giờ.

**b) Cấm kết luận ai là người phải làm.** AI chỉ đưa gợi ý và trích nguyên văn tên/mention. Code đối chiếu bảng danh tính.

**c) Bắt buộc trích câu gốc.** Vừa giảm việc AI bịa ra, vừa để Frontend hiển thị bằng chứng.

**Năm việc AI làm được ở đây mà code không bao giờ làm nổi:**

1. **Phân biệt "để mai tôi xem" với "mai bạn deploy nhé"** — cả hai đều có từ chỉ thời gian và động từ công việc, đều lọt qua tầng 1. Nhưng cái đầu là việc của người khác. Phân biệt được cần hiểu đại từ trong ngữ cảnh hội thoại.
2. **Hiểu tin nhắn thiếu chủ ngữ** — "à mà nhớ backup db trước khi deploy nhé" trở nên rõ nghĩa nhờ hai tin phía trên.
3. **Hiểu quan hệ phụ thuộc** — "trước khi deploy" → suy ra deadline nằm trước 8h sáng mai, dù câu gốc không ghi giờ nào.
4. **Chuẩn hoá ngôn ngữ** — "mai nhớ deploy server lúc 8h nha, xong ping mình" → tiêu đề sạch "Deploy server" + chi tiết riêng.
5. **Nhận ra ý định chưa cam kết** — "chắc t bận, để confirm sau" không phải một việc phải làm.

### 6.2. Lần gọi thứ hai — Viết tóm tắt

**Chạy:** 1 lần duy nhất.

**Điểm mấu chốt:** nó **không nhìn thấy một tin nhắn thô nào**. Nó chỉ nhận khoảng 26 dòng đã được cô đặc:

```
[1] Deploy production v2.1 | hạn 04/08 17:00 | nhắc ở 3 nguồn | có người hỏi lại
[2] Họp sprint review | 07/08 14:00 | Discord
[3] Thanh toán hóa đơn INV-882 | hạn 15/08 | Gmail | 12.400.000đ
...
[26] Trang nghỉ phép 05–06/08 | Telegram
```

**Nhiệm vụ:** viết tóm tắt ngắn, chọn 3 việc gấp nhất kèm lý do, cảnh báo trùng lịch nếu có, và **tuyệt đối không thêm việc nào ngoài danh sách trên**.

Ở đây AI làm đúng việc nó giỏi nhất: **viết văn và xếp thứ tự ưu tiên**. Nó không còn phải mò tìm việc trong đống tin nhắn — việc đó đã xong ở lần gọi thứ nhất.

Vì đầu vào chỉ khoảng 3.000 token thay vì 110.000, lần gọi này gần như miễn phí và rất nhanh. Đây cũng là chỗ duy nhất đáng dùng model mạnh nhất, vì chất lượng ở đây là thứ người dùng nhìn thấy trực tiếp, mà chi phí thì không đáng kể.

### 6.3. Vì sao chỉ hai lần gọi?

Bảng dưới so sánh cách làm ngây thơ và cách làm được đề xuất, trên cùng một tập dữ liệu 1.680 tin nhắn:

|                                     | Nhét hết vào 1 lần gọi | Phễu 4 tầng                  |
| ----------------------------------- | --------------------------- | ------------------------------ |
| Token đưa vào AI                 | ~110.000                    | ~40.000 (14 lô nhỏ) + ~3.000 |
| **Tỉ lệ bắt đúng việc** | **~40–60%**          | **~90%**                 |
| Thời gian chờ                     | 40–70 giây                | 10–15 giây                   |
| Chi phí tương đối              | 1×                         | ~0,06×                        |
| Truy vết nguồn gốc               | Không đáng tin, hay bịa | Chính xác từng tin          |
| Một phần lỗi                     | Mất trắng toàn bộ       | Chỉ hỏng 1/14 lô            |
| Khi chọn 30 ngày                  | Vỡ, không xử lý được | Vẫn chạy bình thường      |

Con số đáng chú ý nhất là **tỉ lệ bắt đúng việc**. Nó không đến từ việc đổi sang model đắt hơn, mà đến từ **một quyết định kiến trúc**: chia nhỏ dữ liệu trước khi đưa cho AI.

---

## 7. Ví dụ chạy xuyên suốt

Theo dõi 12 tin nhắn Discord trong 40 phút để thấy rõ ai làm gì.

### Đầu vào

| #  | Lúc  | Ai    | Nội dung                                                  |
| -- | ----- | ----- | ---------------------------------------------------------- |
| 1  | 21:40 | Trang | ê hôm nay build lỗi lại rồi 😭                        |
| 2  | 21:41 | Hùng | lỗi gì v                                                 |
| 3  | 21:41 | Trang | npm ci fail trên CI                                       |
| 4  | 21:44 | Minh  | để mai t xem                                             |
| 5  | 21:44 | Hùng | ok                                                         |
| 6  | 21:53 | Minh  | @Phong mai nhớ deploy server lúc 8h nha, xong ping mình |
| 7  | 21:54 | Phong | ok anh                                                     |
| 8  | 21:55 | Minh  | à mà nhớ backup db trước khi deploy nhé              |
| 9  | 21:56 | Trang | hehe                                                       |
| 10 | 22:10 | Minh  | @everyone thứ 6 này 2h chiều họp sprint review nhé    |
| 11 | 22:11 | Hùng | chắc t bận, để confirm sau                             |
| 12 | 22:20 | Trang | *(link gif)*                                             |

### Tầng 1 — Lọc thô *(code, 0đ)*

| #                     | Kết quả          | Lý do                                                           |
| --------------------- | ------------------ | ---------------------------------------------------------------- |
| 1                     | ❌ bỏ             | có "hôm nay" nhưng không có động từ công việc          |
| 2, 3, 5, 7, 9, 11, 12 | ❌ bỏ             | quá ngắn / chỉ là phản ứng / là link                      |
| 4                     | ⚠️**giữ** | có "mai" + "xem" — vùng xám, ngưỡng thấp nên giữ        |
| 6                     | ✅**giữ**   | "mai" + "8h" + "nhớ" + "deploy" + nhắc tên → điểm rất cao |
| 8                     | ⚠️**giữ** | "nhớ" + "backup" — vùng xám                                  |
| 10                    | ✅**giữ**   | "thứ 6" + "2h chiều" + "họp" + @everyone                      |

**12 tin → 4 tin. Bỏ 67%, chưa tốn một đồng.**

### Tầng 2 — Chia lô *(code, 0đ)*

Một lô duy nhất, gồm cả 12 tin (4 tin có dấu hiệu + 8 tin làm ngữ cảnh). Cần đủ ngữ cảnh để tin #8 có nghĩa.

### 🔴 Gọi AI lần 1

AI đọc 12 tin, trả về 3 việc:

| Việc                              | Cụm thời gian             | Ai làm          | Độ tin cậy |
| ---------------------------------- | --------------------------- | ---------------- | ------------- |
| Deploy server                      | "mai lúc 8h"               | tôi (@Phong)    | 0,94          |
| Backup database trước khi deploy | "trước khi deploy mai 8h" | tôi             | 0,78          |
| Họp sprint review                 | "thứ 6 này 2h chiều"     | tôi (@everyone) | 0,89          |

**Ba điều AI vừa làm mà code không làm được:**

- **Loại tin #4** — "để mai t xem": "t" nghĩa là Minh, đây là việc của người khác. Tin này đã lọt qua tầng 1 với đầy đủ dấu hiệu, chỉ AI mới loại được.
- **Bắt được tin #8** — không có tên ai, không có giờ, nhưng nhờ đọc tin #6 và #7 phía trên nên hiểu được đây là nói tiếp với Phong.
- **Loại tin #11** — "chắc t bận, để confirm sau" là dự định chưa cam kết, không phải việc phải làm.

Chú ý AI **tự hạ độ tin cậy xuống 0,78** cho việc backup, vì nó không được nhắc tên trực tiếp. Con số này sẽ ảnh hưởng đến cách Frontend hiển thị.

### Tầng 3 — Dọn dẹp *(code, 0đ)*

| Việc              | Cụm thời gian → Ngày giờ thật                                                              |
| ------------------ | ------------------------------------------------------------------------------------------------ |
| Deploy server      | "mai lúc 8h" →**01/08/2026 08:00**                                                       |
| Backup database    | "trước khi deploy mai 8h" →**01/08/2026 07:00** *(trừ 1 giờ đệm)*                 |
| Họp sprint review | "thứ 6 này 2h chiều" →**07/08/2026 14:00** ⚠️ *mơ hồ, hạ tin cậy 0,89 → 0,72* |

Trường hợp thứ ba: hôm nay **đang là** thứ 6 (31/07). "Thứ 6 này" có thể là hôm nay hoặc tuần sau. Hệ thống chọn tuần sau theo luật, nhưng **gắn cảnh báo** để người dùng kiểm tra — không im lặng đoán.

Kiểm tra danh tính: cả 3 việc đều thuộc về người dùng → giữ.
Kiểm tra trùng: không có việc nào giống trong 14 ngày qua → tạo mới cả 3.

### 🔴 Gọi AI lần 2

Nhận 3 dòng đã gọn, viết ra bản tóm tắt và xếp ưu tiên.

### Kết quả cuối

```
📥 3 việc mới từ #dev-team

🔧 Backup database trước khi deploy
   Sáng mai · 07:00
   💬 "à mà nhớ backup db trước khi deploy" — Minh, 21:55 [Mở →]
   ⚠️ Độ tin cậy 78%
   [ ✓ Thêm ]  [ ✏️ Sửa ]  [ ✗ Bỏ ]

🚀 Deploy server
   Sáng mai · 08:00 · Xong báo lại cho Minh
   💬 "mai nhớ deploy server lúc 8h nha" — Minh, 21:53 [Mở →]
   [ ✓ Thêm ]  [ ✏️ Sửa ]  [ ✗ Bỏ ]

📅 Họp sprint review
   Thứ 6, 07/08 · 14:00
   ⚠️ "thứ 6 này" chưa rõ là 31/07 hay 07/08 — kiểm tra lại
   [ ✓ Thêm ]  [ ✏️ Sửa ]  [ ✗ Bỏ ]
```

**Tổng kết ví dụ: 12 tin nhắn → 1 lần gọi AI → 3 việc chính xác.**

### Tình huống tiếp theo — hôm sau kế hoạch thay đổi

**01/08, 06:50** — Minh nhắn: *"à Phong ơi dời deploy sang 10h nhé, sáng t có họp gấp"*

Đây là chỗ 90% sản phẩm tương tự làm sai.

- Tầng 1 giữ tin này lại (có "dời", "10h", tên người dùng)
- AI nhận ra đây là **thay đổi**, không phải việc mới
- Code tính "10h" → 01/08 10:00
- Code tra database, thấy việc "Deploy server" đã tồn tại, cùng tiêu đề nhưng khác giờ
- → **Sửa việc cũ**, không tạo việc mới
- → **Sửa sự kiện Calendar cũ**, không tạo sự kiện thứ hai

Người dùng nhận được:

```
🔔 Lịch thay đổi
   Deploy server:  08:00 → 10:00 hôm nay
   💬 "dời deploy sang 10h nhé" — Minh, 06:50
   [ ✓ OK ]   [ ↩️ Giữ 8h ]
```

Không có bước gộp trùng này, người dùng sẽ có hai sự kiện chồng nhau trên lịch. Đến lần thứ ba như vậy thì họ gỡ ứng dụng.

---

## 8. Ranh giới AI và Code

### 8.1. Bảng phân công

| Việc                                                    |    Ai làm    | Vì sao                                                |
| -------------------------------------------------------- | :------------: | ------------------------------------------------------ |
| Lấy dữ liệu, xác thực, làm mới token              |      Code      | Logic cố định                                       |
| Cắt trích dẫn, chữ ký email                         |      Code      | Có khuôn mẫu rõ ràng                              |
| Lọc thô "có dấu hiệu công việc không"            |      Code      | 95% loại được bằng luật                          |
| **Hiểu "mai deploy nhé b" là việc phải làm** | 🔴**AI** | **Không code nào làm được**                |
| **Viết tiêu đề sạch từ câu nói lộn xộn** | 🔴**AI** | Cần chuẩn hoá ngôn ngữ                            |
| **Đoán ai là người phải làm**               | 🔴**AI** | Cần hiểu ngữ cảnh hội thoại                      |
| **Viết tóm tắt, xếp ưu tiên**                | 🔴**AI** | Sinh ngôn ngữ tự nhiên                             |
| Tính "mai 8h" ra ngày giờ cụ thể                    |      Code      | AI sai thường xuyên và sai âm thầm               |
| Đối chiếu tên với danh tính người dùng          |      Code      | Tra bảng, không cần suy luận                       |
| Quyết định việc này trùng việc cũ không         |      Code      | AI cho kết quả không ổn định                     |
| Ghi database, ghi Google Calendar                        |      Code      | Không được để AI cầm quyền ghi                 |
| Quyết định thứ tự các bước xử lý               |      Code      | Đây là lý do luồng cố định, không dùng agent |
| Nhắc lúc mấy giờ                                     |      Code      | Lịch trình cố định                                |

### 8.2. Vì sao AI tuyệt đối không được tính ngày tháng

Đây là quy tắc bị vi phạm nhiều nhất và gây hậu quả nặng nhất.

**Nếu để AI trả thẳng ngày giờ:**

| Loại lỗi             | Ví dụ                                                                     |
| ---------------------- | --------------------------------------------------------------------------- |
| Sai múi giờ          | Lẫn giữa giờ UTC và giờ Việt Nam → lệch 7 tiếng                    |
| Sai tuần              | "Thứ 6" khi hôm nay là thứ 6 → chọn nhầm hôm nay thay vì tuần sau |
| Sai ngày cuối tháng | "31/09" — ngày không tồn tại                                           |
| Sai năm               | Tháng 1 mà "tháng 12" nghĩa là năm ngoái                             |

Điểm nguy hiểm nhất: **những lỗi này xảy ra âm thầm**. Kết quả trả về nhìn hoàn toàn hợp lệ. Bạn không có cách nào phát hiện ngoài việc người dùng đến báo là họ trễ họp.

**Khi tách ra — AI trả cụm chữ, code tính ngày:**

- Mọi lỗi ngày tháng đều trở thành bug trong code
- Bug trong code thì **viết được test tự động**
- Sửa một lần là đúng vĩnh viễn cho mọi người dùng
- Chạy được 100 trường hợp kiểm thử trong 0,2 giây, miễn phí

Đây là quyết định đơn lẻ có tỉ lệ lợi ích trên công sức cao nhất trong toàn bộ thiết kế.

### 8.3. Phép thử kiểm tra thiết kế

Có một cách rất đơn giản để biết bạn có đang giao đúng việc cho AI không:

> **Thay AI bằng một người ngồi đọc 15 tin nhắn và điền biểu mẫu. Hệ thống có chạy được không?**

**Nếu có** → thiết kế đúng. AI đang làm đúng loại việc của nó. Mọi thứ khác do code quyết định, nên bạn test được, debug được, biết trước chi phí.

**Nếu không** → có chỗ nào đó đang giao cho AI việc nó không nên làm. Ví dụ: *"AI sẽ tự tra database rồi tự quyết định gộp việc nào"* hoặc *"AI sẽ quyết định có ghi lên Calendar không"*. Những chỗ này sẽ biểu hiện thành lỗi không tái hiện được, chi phí không kiểm soát nổi, và không thể viết kiểm thử.

Trong thiết kế này, phép thử pass hoàn toàn.

---

## 9. Giới hạn nền tảng

Đây là phần quyết định phạm vi sản phẩm nhiều hơn cả phần AI. Cần biết trước để không hứa những gì không làm được.

| Nền tảng         | Lấy được gì                                                             | Không lấy được                                                                         | Mức ưu tiên                                                                     |
| ------------------ | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| **Telegram** | Tin trong nhóm có bot, tin người dùng chủ động chuyển tiếp cho bot | ❌ Lịch sử trước khi thêm bot❌ Tin nhắn riêng giữa người dùng và người khác | 🥇 Làm đầu tiên — rẻ và nhanh nhất, lại kiêm luôn kênh gửi nhắc nhở |
| **Gmail**    | Toàn bộ hộp thư, có lịch sử                                           | Cần đánh giá bảo mật định kỳ khi vượt quy mô nhất định                       | 🥈 Nguồn giá trị cao nhất                                                      |
| **Discord**  | Tin trong kênh mà bot được thêm vào, có lịch sử                    | ❌ Tin nhắn riêng của người dùng                                                      | 🥉 Chỉ dùng cho server công việc                                               |
| **Slack**    | Tin thời gian thực qua cơ chế sự kiện                                  | ❌ Lịch sử — giới hạn rất chặt, gần như không lấy được                        | Hoãn sang giai đoạn sau                                                         |

### Hai hệ quả quan trọng

**a) Với Telegram, phải nói rõ với người dùng ngay từ màn hình kết nối:** *"Chỉ tổng hợp được từ lúc bạn thêm bot vào nhóm."* Nếu họ chọn khoảng thời gian trước đó, Frontend phải hiện cảnh báo, không im lặng trả về kết quả rỗng.

**b) Có một cách kết nối luôn hoạt động trên mọi nền tảng và thường bị đánh giá thấp:** để **người dùng chủ động đẩy tin nhắn vào**.

- Telegram: chuyển tiếp tin nhắn cho bot
- Discord: chuột phải vào tin nhắn → "Thêm vào việc cần làm"
- Slack: menu tin nhắn → "Thêm vào việc cần làm"
- Gmail: chuyển tiếp email tới địa chỉ riêng của hệ thống
- Bất kỳ trang web nào: tiện ích trình duyệt, bôi đen văn bản → tạo việc

Cách này có ba ưu điểm lớn: **độ chính xác gần 100%** (người dùng đã lọc giùm), **không vướng bất kỳ giới hạn nào**, và **công sức xây dựng rất thấp**. Nên làm ngay từ MVP, song song với việc tự động đọc.

---

## 10. Đo lường thành công

Chỉ một con số quan trọng hơn tất cả:

> **Trong 10 việc hệ thống đề xuất, người dùng bấm ✓ cho bao nhiêu cái?**

Nếu dưới 7, mọi kiến trúc trong tài liệu này đều vô nghĩa — vấn đề nằm ở bộ lọc và cách ra lệnh cho AI, không nằm ở hạ tầng.

### Bốn chỉ số cần theo dõi

| Chỉ số                         | Ý nghĩa                                                         | Mục tiêu |
| -------------------------------- | ----------------------------------------------------------------- | ---------- |
| **Độ chính xác**       | Trong các việc đề xuất, bao nhiêu % là đúng              | ≥ 85%     |
| **Độ bao phủ**          | Trong các việc thật sự có, bắt được bao nhiêu %         | ≥ 85%     |
| **Độ đúng ngày giờ** | Trong các việc bắt đúng, ngày giờ chính xác bao nhiêu % | ≥ 95%     |
| **Thời gian phản hồi**  | Từ lúc bấm nút đến khi có kết quả                        | ≤ 15s     |

### Vì sao độ chính xác quan trọng hơn độ bao phủ

Hai loại sai lầm có hậu quả rất khác nhau:

- **Bỏ sót một việc** → người dùng chưa mất gì; họ vốn đã quen tự nhớ
- **Tạo thừa 5 việc rác** → người dùng mất niềm tin và gỡ ứng dụng

Vì vậy khi phải đánh đổi, luôn ưu tiên độ chính xác.

### Cách đo trước khi có người dùng

Chuẩn bị khoảng 200 tin nhắn thật (chép từ Discord/Gmail của chính bạn), tự tay gán nhãn xem tin nào là việc, deadline là bao giờ. Đây là bộ dữ liệu chuẩn.

Mỗi lần thay đổi bộ lọc hoặc cách ra lệnh cho AI, chạy lại và so sánh. Đây là cách duy nhất biết được thay đổi vừa rồi là tốt hơn hay tệ đi — thay vì đoán mò.

---

## 11. Phạm vi MVP

### Có trong MVP

| Tính năng                                                          | Lý do                                        |
| -------------------------------------------------------------------- | --------------------------------------------- |
| Kết nối**Telegram** + **Gmail**                        | Nhanh nhất và giá trị cao nhất           |
| Người dùng chủ động đẩy tin (chuyển tiếp, menu ngữ cảnh) | Chính xác gần 100%, công sức thấp nhất |
| Chọn nguồn cụ thể + chọn khoảng thời gian                     | Chính là bài toán gốc                    |
| Toàn bộ phễu 4 tầng                                              | Phần lõi                                    |
| Hộp duyệt việc, có bằng chứng và link gốc                    | Xây niềm tin                                |
| Đồng bộ Google Calendar một chiều, sau khi duyệt               | Giá trị rõ ràng, ít rủi ro              |
| Gộp việc trùng xuyên nền tảng                                  | Điểm khác biệt của sản phẩm            |
| Bộ dữ liệu chuẩn + quy trình đo                                | Nền tảng cho mọi cải tiến                |

### Cắt khỏi MVP

| Cắt                        | Lý do                                                         |
| --------------------------- | -------------------------------------------------------------- |
| Slack                       | Giới hạn lịch sử quá chặt, tốn công cho giá trị nhỏ |
| Discord tự động đọc    | Làm menu ngữ cảnh trước, tự động sau                   |
| Chạy nền tự động       | Mô hình bấm-nút đủ tốt cho MVP và dễ demo hơn        |
| Đồng bộ lịch hai chiều | Xử lý xung đột tốn ít nhất 2 tuần                      |
| Tiện ích trình duyệt    | Chưa cần để chứng minh giá trị cốt lõi                |
| Trợ lý trò chuyện       | Giai đoạn sau                                                |
| Kế hoạch tuần            | Cần dữ liệu tích luỹ mới có ý nghĩa                   |

### Thứ tự làm

**Bước 1 — Tầng 1 và tầng 3, không cần AI.**
Viết hàm chấm điểm lọc tin. Viết hàm chuyển "mai 8h" thành ngày giờ. Viết hàm gộp việc trùng. Chuẩn bị 200 tin thật làm dữ liệu thử.

*Bước này chiếm khoảng 60% khối lượng công việc và không cần AI, không cần LangGraph.*

**Bước 2 — Thêm tầng 2 và tầng 4.**
Gọi model, ép trả đúng biểu mẫu. Chạy tuần tự trước, chưa cần song song. Lúc này đã có sản phẩm chạy được đầu-cuối.

**Bước 3 — Đo.**
Chạy trên 200 tin đã gán nhãn. Xem độ chính xác, độ bao phủ, độ đúng ngày giờ. Điều chỉnh cho tới khi độ chính xác vượt 85%.

**Bước 4 — Chuyển sang chạy song song và làm giao diện.**
Lúc này mới cần đến việc chia lô chạy đồng thời và hiển thị tiến trình.

Thứ tự này khiến phần khó nhất về công cụ nằm ở cuối, khi bạn đã hiểu rõ bài toán, thay vì là rào cản ngay từ đầu.

---

## 12. Rủi ro

| Rủi ro                                                                  | Mức | Cách giảm                                                                                                          |
| ------------------------------------------------------------------------ | :--: | -------------------------------------------------------------------------------------------------------------------- |
| **Tạo việc sai → rác Google Calendar**                         |  🔴  | Bắt buộc duyệt thủ công. Luôn hiện bằng chứng. Nút hoàn tác một chạm. Đo độ chính xác hàng tuần |
| **Sai ngày giờ**                                                 |  🔴  | AI tuyệt đối không tính ngày. Bộ kiểm thử 100 cách nói thời gian tiếng Việt chạy tự động           |
| **Nhầm việc của người khác thành việc của mình**         |  🔴  | AI chỉ gợi ý, code đối chiếu danh tính. Không rõ thì hạ tin cậy, hiện cảnh báo                        |
| **Không gộp được việc trùng**                               |  🟠  | Thang 3 bậc. Ưu tiên khoá cứng trước khi dùng ngữ nghĩa                                                    |
| **Giới hạn nền tảng làm thiếu dữ liệu**                    |  🟠  | Nói rõ khả năng từng nền tảng ngay ở màn hình kết nối                                                    |
| **Rò rỉ dữ liệu riêng tư**                                   |  🔴  | Mã hoá token, không ghi log nội dung, có chính sách xoá dữ liệu, cho người dùng xoá bất cứ lúc nào |
| **Chi phí vượt kiểm soát**                                    |  🟠  | Tầng 1 là tuyến phòng thủ chính. Đặt hạn mức theo người dùng theo ngày                                 |
| **Người dùng bị đưa cho một AI mà họ không hiểu**       |  🟠  | Luôn hiện bằng chứng và link gốc. Không có hộp đen                                                         |
| **Làm nhiều nền tảng cùng lúc, không nền tảng nào tốt** |  🔴  | Rủi ro sản phẩm lớn nhất. Làm**một** nguồn thật xuất sắc trước                                    |

---

## Tóm tắt một trang

**Bài toán:** 1.680 tin nhắn → 10 việc. 99% là nhiễu.

**Giải pháp:** phễu 4 tầng, mỗi tầng dùng công cụ rẻ nhất còn làm được việc.

| Tầng | Ai làm | Việc                                     | Còn lại          |
| ----- | ------- | ----------------------------------------- | ------------------ |
| 1     | Code    | Lọc thô bằng luật                     | 1.680 → 90        |
| 2     | 🔴 AI   | Đọc từng lô 15 tin, điền biểu mẫu | 90 → 63 mục      |
| 3     | Code    | Tính ngày, lọc người, gộp trùng    | 63 → 26 việc     |
| 4     | 🔴 AI   | Viết tóm tắt, xếp ưu tiên           | 26 → 1 bản brief |

**Frontend:** thu hẹp phạm vi (chọn kênh), gợi ý khoảng thời gian, hiện tiến trình, bắt buộc duyệt trước khi lên lịch, luôn hiện bằng chứng.

**Backend:** lấy dữ liệu song song và chịu lỗi cục bộ, làm sạch, lọc, chia lô, tính ngày, gộp trùng, đồng bộ lịch an toàn khi lặp lại.

**AI:** đúng hai lần gọi. Một lần để *hiểu ngôn ngữ*, một lần để *viết văn*. Không tính toán, không quyết định, không ghi dữ liệu.

**Ba câu cần nhớ:**

1. Chia nhỏ dữ liệu trước khi đưa cho AI — không phải để tiết kiệm, mà vì **chất lượng cao hơn hẳn**.
2. AI hiểu ngôn ngữ, code xử lý dữ liệu. Vi phạm ranh giới này là nguồn gốc của gần như mọi lỗi khó chữa.
3. Mọi việc phải chỉ được ra nguồn gốc. Không có bằng chứng thì không có niềm tin, không có niềm tin thì không có sản phẩm.
