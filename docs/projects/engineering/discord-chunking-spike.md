# Discord chunking — đo trên dữ liệu thật để chọn đơn vị chunk

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Draft — số liệu đã đo, cách làm chưa chốt |
| Owner | Thái Hoài An (PM) |
| Author | Thái Hoài An (PM) |
| Reviewers | Nguyễn Văn Phong (Technical Lead) |
| Last updated | 2026-08-07 |
| Related | [Architecture §5](architecture.md) · [Memory lifecycle §7](memory-lifecycle.md) · [Discord connector spike](discord-connector-spike.md) |

## Câu hỏi cần trả lời

Bước chunk chưa được đặc tả ở đâu. Trước khi chọn đơn vị chunk phải biết dữ liệu
Discord thật có hình dạng gì — chứ không suy từ trực giác về "một cuộc hội thoại".

Nguồn: run `20260807T014941Z`, 92 file, 10.852 tin, khoảng 2026-07-22 đến 2026-08-07.

## Bốn phát hiện

### 1. Tin cực ngắn, embed từng tin là vô nghĩa

| Kênh | Tin | p50 độ dài content |
| --- | ---: | ---: |
| `💬-chung` | 3.578 | 22 ký tự |
| `Lab-E403` (thread lab khoá 4) | 1.974 | **2 ký tự** |
| `Lec-C401` (thread lý thuyết) | 941 | 47 ký tự |
| `Lec-D302` | 794 | 61 ký tự |

Một nửa số tin trong `chung` ngắn hơn chuỗi `tôi đã ở đây`. Gộp tin thành cụm là
bắt buộc, không phải tối ưu hóa.

### 2. Cây reply có thật, nhưng chỉ phủ thiểu số

DCE giữ đủ trường `reference` — dựng được cây. Trong `chung`, 856 tin có
`reference`, **788 trỏ tới tin còn trong corpus (92%)**; 68 tin còn lại trỏ tới tin
đã xóa.

Nhưng độ phủ thấp, và giảm mạnh ở kênh không phải chat chung:

| Kênh | Số cây | Tin nằm trong cây | Cỡ cây p50 | Sâu nhất |
| --- | ---: | ---: | ---: | ---: |
| `💬-chung` | 432 | 1.220 (**34%**) | 2 | 10 |
| `Lab-E403` | 29 | 76 (**4%**) | 2 | 5 |
| `Lec-C401` | 26 | 70 (**7%**) | 2 | 5 |

Cây phổ biến nhất chỉ gồm **2 tin** — một câu hỏi và một câu trả lời. Đây không
phải "topic", đây là một cặp đối đáp.

**Kết luận: reply tree không đủ làm đơn vị chunk chính.** Dùng nó làm đơn vị duy
nhất thì 66–96% số tin thành mồ côi, không vào chunk nào.

### 3. Phân bố khoảng cách thời gian

Khoảng cách giữa hai tin liên tiếp, tính bằng giây:

| Kênh | p50 | p75 | p90 | p95 | p99 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `💬-chung` | 31 | 124 | 563 | 1.404 | 6.072 |
| `Lab-E403` | **0** | 1 | 5 | 109 | 14.179 |
| `Lec-C401` | 2 | 16 | 106 | 571 | 39.849 |

Số phiên theo từng ngưỡng cắt, kênh `chung`:

| Ngưỡng | Số phiên | Tin mỗi phiên |
| ---: | ---: | ---: |
| 5 phút | 526 | 7 |
| 10 phút | 338 | 11 |
| 15 phút | 247 | 14 |
| **30 phút** | **142** | **25** |
| 60 phút | 68 | 53 |
| 120 phút | 29 | 123 |

Phân bố có hai cụm rõ: rất dày (p50 dưới 1 phút, người ta chat liên tục) rồi nhảy
vọt (p99 vài giờ, qua đêm). Chỗ gãy nằm quanh **30 phút** — đủ rộng để không cắt
giữa một cuộc trao đổi, đủ hẹp để không dính hai buổi khác nhau.

### 4. Cắt thuần theo thời gian sẽ chặt đứt chuỗi reply

Tỉ lệ reply cách tin gốc hơn 30 phút:

| Kênh | Tỉ lệ |
| --- | ---: |
| `💬-chung` | 75/788 (10%) |
| `Lec-C401` | 5/44 (11%) |
| `Lab-E403` | 13/47 (**28%**) |

Người ta trả lời câu hỏi từ hôm trước. Cắt theo đồng hồ sẽ tách câu trả lời khỏi
câu hỏi — đúng cặp mà retrieval cần nhất.

## Giả định cần sửa: thread không tự nó là đơn vị đủ

Ý ban đầu là "chỉ `chung` mới nặng, hỏi-đáp và chia-sẻ gom theo thread là đủ".
Số liệu bác bỏ:

- `Lab-E403` là **một thread** nhưng có **1.974 tin** — nặng thứ hai toàn bộ dataset.
- `Lec-C401` 941 tin, `Lec-D302` 794 tin, cũng đều là thread.
- Bốn file có từ 500 tin trở lên chiếm **67% tổng số tin**, và ba trong bốn là thread.

Thread nhỏ (bài chia sẻ, 194 tin trở xuống) thì gom nguyên thread là đủ. Thread
lớn thì phải chunk y như `chung`.

Ranh giới đề xuất: **thread dưới ~200 tin gom nguyên khối, trên thì chunk.**

### 5. Lec và Lab neo vào buổi học; `chung` thì không

Phân bố theo giờ địa phương (dữ liệu DCE ghi sẵn offset +07:00):

| Thread | Khung giờ hoạt động | Khớp với |
| --- | --- | --- |
| `Lec-C401`, `Lec-D302` | 09:00–13:00 | khoá 4 lý thuyết buổi sáng |
| `Lab-E403` | 14:00–18:00 | khoá 4 lab buổi chiều |
| `💬-chung` | 08:00–24:00, đỉnh **22h** | không neo vào lịch nào |

Ngày đông nhất của mỗi thread là một khối liền mạch thật sự:

- `Lec-C401` ngày 2026-07-27: **656 tin, 09:18–12:44, không một khoảng lặng nào quá 30 phút**
- `Lab-E403` ngày 2026-08-05: **1.807 tin, 14:01–18:00**, chỉ 3 khoảng lặng

Ngược lại, những ngày thưa bị ngưỡng 30 phút băm vụn vô ích: `Lec-C401` ngày
24/07 có 14 tin rải trong 6.2 giờ với 5 khoảng lặng — thành 6 phiên, mỗi phiên 2
tin. Đó là lý do 11 ngày hoạt động lại ra 29 phiên.

**Với Lec/Lab, đơn vị đúng là buổi, không phải khoảng lặng.** Ngày đông thì hai
cách cho kết quả như nhau; ngày thưa thì cắt theo buổi gom được, cắt theo đồng hồ
thì vụn.

### 6. `chung` đan xen quá nặng để cắt theo thời gian

Đếm số mạch reply riêng biệt cùng tồn tại trong một phiên 30 phút:

| Tin trong phiên | Mạch riêng biệt | Người gửi |
| ---: | ---: | ---: |
| 757 | **645** | 471 |
| 262 | 183 | 64 |
| 260 | 252 | 227 |
| 259 | 162 | 95 |

Trung bình **36.7 mạch hội thoại riêng biệt** trong cùng một phiên. Phiên 757 tin
với 471 người rơi đúng ngày kick-off 23/07 — màn chào hỏi hàng loạt.

Gom theo cửa sổ thời gian ở đây không tạo ra hội thoại, nó trộn hàng trăm mẩu
chuyện rời rạc vào một chunk.

### 7. Nhưng phần lớn `chung` là nhiễu, và lọc được bằng một ngưỡng

| Nhóm | Tin | Khối lượng chữ | p50 độ dài | Tin dài hơn 100 ký tự |
| --- | ---: | ---: | ---: | ---: |
| Nằm trong cây reply | 1.220 | 81.883 (55%) | 49 | 17% |
| Mồ côi | 2.358 | 65.654 (45%) | **11** | 6% |

Tin mồ côi điển hình: `'Em cảm ơn ạ'`, `'Vì kẹt xe ạ'`, `'dc r chị ơi'`,
`'đã mở rồi á'`. Không có giá trị truy hồi.

Tin mồ côi **dài** thì ngược lại, toàn thứ đáng giữ: thông báo của Admin — ODIN và
BTC, câu hỏi của nhóm khác, khảo sát người dùng.

Bỏ tin mồ côi ngắn hơn **60 ký tự**:

- giữ 296/2.358 tin mồ côi (13%)
- nhưng giữ được **57% khối lượng chữ** của nhóm mồ côi
- tổng vào index: **1.516/3.578 tin (42%)**

Tức là bỏ 58% số tin mà chỉ mất khoảng một phần tư khối lượng chữ, phần bị mất là
phần không mang thông tin.

## Cách làm đề xuất: hai chế độ cho hai loại kênh

| | Thread Lec/Lab | `💬-chung` |
| --- | --- | --- |
| Cấu trúc | Buổi học, neo vào lịch | Liên tục, không neo |
| Đan xen hội thoại | Thấp | 36.7 mạch mỗi phiên |
| Tin nằm trong cây reply | 4–7% | 34% |
| **Đơn vị chunk** | **Buổi (theo ngày)** rồi đóng gói theo ngân sách | **Mạch reply**, cộng tin mồ côi đã lọc |

Với Lec/Lab, giữ nguyên bước đóng gói theo ngân sách bên trong mỗi buổi — ngày
05/08 của `Lab-E403` có 1.807 tin, một buổi vẫn quá lớn cho một chunk.

Với `chung`, thứ tự là **lọc trước, chunk sau**: bỏ tin mồ côi ngắn, rồi lấy mạch
reply làm đơn vị, tin mồ côi dài đứng riêng thành chunk của chính nó.

## Cách làm cũ (giữ lại làm đối chiếu): phiên theo thời gian, hợp nhất theo reply, đóng gói theo ngân sách

Ba bước, mỗi bước sửa đúng một khuyết điểm ở trên:

1. **Cắt phiên** khi khoảng lặng vượt 30 phút.
2. **Hợp nhất** hai phiên nếu có một cạnh reply nối chúng (union-find). Sửa được
   phát hiện 4.
3. **Đóng gói** trong mỗi nhóm theo ngân sách ~1.200 ký tự, không bao giờ gộp qua
   ranh giới nhóm. Sửa được phát hiện 1 và chuyện `Lab-E403` toàn tin 2 ký tự.

Đóng gói theo **ngân sách ký tự** chứ không theo số tin — vì cùng 25 tin có thể là
550 ký tự ở `chung` mà chỉ 50 ký tự ở `Lab-E403`.

### Kết quả đo với ngưỡng 30 phút, ngân sách 1.200 ký tự

| Kênh | Tin | Phiên (chỉ thời gian) | Sau khi nối reply | Chunk cuối | Tin/chunk p50 | Ký tự/chunk p50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `💬-chung` | 3.578 | 142 | 101 | 263 | 13 | 688 |
| `Lab-E403` | 1.974 | 48 | 37 | 76 | 17 | **151** |
| `Lec-C401` | 941 | 29 | 26 | 147 | 3 | 889 |
| `Lec-D302` | 794 | 26 | 23 | 150 | 2 | 922 |

Bước nối reply giảm số nhóm 12–29%, tức nó **thực sự vá được** những chỗ mà cắt
thuần thời gian đã chặt nhầm.

`Lab-E403` vẫn lệch: 76 chunk mà p50 chỉ 151 ký tự. Nguyên nhân là thread này gần
như không có nội dung chữ — 1.974 tin với p50 hai ký tự, phần lớn là điểm danh và
thả icon. Đây là vấn đề **lọc**, không phải vấn đề chunk. Xem việc còn mở.

## Việc còn mở

| Mã | Nội dung | DRI |
| --- | --- | --- |
| CH-01 | Ngưỡng 30 phút mới đo trên 4 kênh, chưa đo trên `hoi-dap`, `chia-se`, `bai-hoc`, `g10-*` vì lúc đo chưa cào xong | An |
| CH-02 | Ngưỡng 60 ký tự để lọc tin mồ côi mới đo trên `chung`, chưa kiểm trên kênh khác. Tin bị loại khỏi index **vẫn phải giữ trong evidence** để không mất bằng chứng | An + Phong |
| CH-06 | Ranh giới buổi hiện lấy theo ngày lịch. Có ngày chat kéo tới 23:00, tức lẫn cả buổi học lẫn tán gẫu tối. Cân nhắc cắt theo cửa sổ buổi thay vì cả ngày | An |
| CH-03 | Ngân sách 1.200 ký tự chọn theo cảm tính, chưa đối chiếu với cửa sổ của model embedding sẽ dùng | Phong |
| CH-04 | Chưa quyết chunk có mang theo N tin lân cận làm ngữ cảnh hay không | An |
| CH-05 | Thread lớn dùng ngưỡng 200 tin để phân loại — con số này chưa kiểm chứng | An |
