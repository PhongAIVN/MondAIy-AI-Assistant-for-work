TASKS.md

Mục tiêu

Cập nhật extension hiện tại với 2 thay đổi chính:

Chuyển cách hiển thị extension sang dạng Side Panel, tương tự extension Claude.
Thêm một tab/chức năng trong extension để thực hiện quá trình lấy dữ liệu từ website đang được mở, sau đó lưu dữ liệu vào công việc.

Lưu ý quan trọng:
Folder Test extension chỉ được sử dụng làm tài liệu/code tham khảo để hiểu và tham khảo flow mô phỏng quá trình lấy dữ liệu bằng extension + DeepSeek Harness.
Không coi Test extension là source code chính cần chỉnh sửa cho task này.

1. Tham khảo implementation hiện có

Folder tham khảo:

C:\Users\THIS PC\Desktop\IT\AI THUC CHIEN\P-004\client\Test extension

Trong folder này có implementation dùng extension và DeepSeek Harness để mô phỏng quá trình lấy dữ liệu từ website và bạn không cần phải lấy Deepseek làm backend hay tool gì cả.

Cần đọc và tìm hiểu implementation trong folder này để:

Hiểu flow lấy dữ liệu.
Hiểu cách extension tương tác với website.
Hiểu cách xác định nội dung cần lấy.
Tham khảo cách xử lý dữ liệu.
Tham khảo cách giao tiếp giữa extension và website.

Sau đó áp dụng ý tưởng/logic cần thiết vào extension hiện tại.

Không copy hoặc thay thế toàn bộ extension hiện tại bằng code trong Test extension nếu không cần thiết.

2. Chuyển extension hiện tại sang Side Panel
   Hiện trạng

Extension hiện tại đang mở trong một tab riêng.

Khi người dùng chuyển sang tab trình duyệt khác thì extension bị đóng hoặc không còn duy trì theo cách mong muốn.

Yêu cầu

Thay đổi cách mở extension:

Extension phải mở dưới dạng Side Panel ở một bên cửa sổ trình duyệt.
Cách hoạt động mong muốn tương tự extension Claude.
Side Panel phải được duy trì khi người dùng chuyển qua lại giữa các tab.
Extension không được phụ thuộc vào một tab riêng để tồn tại.
Extension phải có khả năng nhận biết tab hiện tại đang active.
Ví dụ flow
User đang ở Website A
        ↓
Mở Extension
        ↓
Extension xuất hiện ở Side Panel
        ↓
User chuyển sang Website B
        ↓
Side Panel vẫn còn
        ↓
Extension nhận biết Active Tab = Website B

Acceptance Criteria
 Extension mở dưới dạng Side Panel.
 Side Panel không bị đóng khi chuyển browser tab.
 Side Panel vẫn hoạt động khi chuyển qua lại giữa nhiều tab.
 Extension xác định được tab hiện tại đang active.
 Không ảnh hưởng đến các chức năng hiện tại của extension.
3. Thêm tab "Lấy dữ liệu"

Trong Side Panel của extension, tạo thêm một tab/chức năng dành cho quá trình lấy dữ liệu từ website.

Ví dụ:

┌──────────────────────────────┐
│ Extension                    │
├──────────────┬───────────────┤
│ Công việc    │ Lấy dữ liệu   │
├──────────────┴───────────────┤
│                              │
│      Nội dung chức năng      │
│      lấy dữ liệu             │
│                              │
└──────────────────────────────┘

Tên tab có thể điều chỉnh theo UI hiện tại của extension nếu project đã có convention phù hợp.

4. Lấy dữ liệu chỉ từ Active Tab

Đây là yêu cầu quan trọng.

Khi người dùng sử dụng chức năng "Lấy dữ liệu", extension chỉ được phép làm việc với:

Tab trình duyệt mà người dùng đang mở/đang active tại thời điểm thực hiện thao tác.

Ví dụ:

Tab A = Facebook
Tab B = Website cần lấy dữ liệu
Tab C = Google

User đang ở Tab B
        ↓
Extension lấy dữ liệu
        ↓
Chỉ đọc dữ liệu từ Tab B

Không được lấy dữ liệu từ:

Tab A.
Tab C.
Các tab khác đang mở trong browser.
Một tab cố định được lưu từ trước.

Khi người dùng chuyển tab:

Tab B → Tab C
        ↓
Active Tab = Tab C
        ↓
Lần lấy dữ liệu tiếp theo
        ↓
Chỉ lấy dữ liệu từ Tab C

5. Tham khảo flow từ Test extension

Implementation trong:

C:\Users\THIS PC\Desktop\IT\AI THUC CHIEN\P-004\client\Test extension

được dùng để tham khảo cách mô phỏng quá trình:

Website
   ↓
Extension
   ↓
Lấy dữ liệu
   ↓
Xử lý dữ liệu
   ↓
Đưa dữ liệu vào workflow

Cần xác định trong implementation tham khảo:

Cách lấy content từ trang.
Cách xác định DOM/content cần lấy.
Cách giao tiếp giữa extension và content script/background.
Cách xử lý dữ liệu sau khi lấy.
Các vấn đề kỹ thuật đã được giải quyết trong implementation tham khảo.

Sau đó áp dụng những phần phù hợp vào extension hiện tại.

Không cần giữ nguyên kiến trúc của Test extension nếu kiến trúc của extension hiện tại khác.

6. Lưu dữ liệu vào công việc để đồng bộ với web-app

Sau khi lấy dữ liệu từ Active Tab, kết quả cần được đưa vào công việc hiện tại.

Flow mong muốn:

User mở Website
        ↓
Mở Extension Side Panel
        ↓
Extension xác định Active Tab
        ↓
Mở tab "Lấy dữ liệu"
        ↓
Thực hiện lấy dữ liệu
        ↓
Xử lý dữ liệu
        ↓
Lưu vào Công việc hiện tại

Cần ưu tiên sử dụng cơ chế Task/Work/Job hiện có trong extension hiện tại nếu project đã có.

Không tự tạo một hệ thống task mới nếu không cần thiết.

7. Kiểm tra extension hiện tại trước khi code

Trước khi implementation cần xác định:

Extension hiện tại đang được mở bằng cơ chế nào.
Manifest/version Chrome Extension đang sử dụng.
Kiến trúc hiện tại của extension.
Background/service worker hiện tại.
Content script hiện tại.
Cách extension giao tiếp với active tab.
Cách dữ liệu/công việc hiện tại đang được quản lý.
Có API/state/storage nào có thể tái sử dụng.
Những phần nào trong Test extension có thể tham khảo.
Nguyên tắc

Extension hiện tại là source code chính.

Test extension chỉ là:

Reference / Prototype / Example

8. Không tự ý mở rộng phạm vi

Trong quá trình thực hiện:

Không thay đổi architecture lớn nếu chưa cần thiết.
Không rewrite toàn bộ extension.
Không thay thế extension hiện tại bằng Test extension.
Không thay đổi backend/API không liên quan.
Không đọc dữ liệu từ các tab không active.
Không tạo hệ thống task/work mới nếu project hiện tại đã có.
Không tự ý thêm các tính năng ngoài phạm vi task.

Nếu phát hiện architecture hiện tại không đáp ứng được yêu cầu, cần phân tích nguyên nhân và đưa ra phương án trước khi thực hiện thay đổi lớn.

9. Definition of Done

Task hoàn thành khi:

 Extension hiện tại hoạt động dưới dạng Side Panel.
 Side Panel vẫn tồn tại khi chuyển sang tab khác.
 Extension nhận biết đúng Active Tab.
 Có thêm tab/chức năng "Lấy dữ liệu".
 Chức năng lấy dữ liệu chỉ làm việc với Active Tab.
 Có thể chuyển A → B → C và extension luôn xác định đúng tab hiện tại.
 Logic lấy dữ liệu được xây dựng dựa trên việc tham khảo Test extension.
 Không coi Test extension là source code chính để sửa.
 Dữ liệu lấy được được lưu vào công việc hiện tại.
 Không làm hỏng các chức năng hiện có.
 Đã kiểm tra các flow chính.
 Không còn lỗi runtime/console liên quan đến các thay đổi mới.
10. Nếu có điểm chưa rõ

Nếu trong quá trình đọc extension hiện tại và implementation tham khảo mà có điểm không thể xác định chính xác, không tự suy đoán.

Hãy hỏi lại để xác nhận trước khi thực hiện các thay đổi có ảnh hưởng lớn đến architecture hoặc behavior của extension.
