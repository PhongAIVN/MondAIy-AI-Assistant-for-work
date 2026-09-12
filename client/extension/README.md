# mondaiy — Extension thông báo

Chrome extension (Manifest V3) hiển thị trạng thái + thao tác nhanh cho task
đang chờ, mở dưới dạng **Side Panel** (giống extension Claude — không đóng khi
đổi tab). Không có UI Brief/Chat riêng. Xây bằng WXT + React + TypeScript.

- Icon extension: badge số task đang chờ (`status=proposed`), bấm icon mở
  **Side Panel** với 2 tab: **Công việc** (liệt kê task, xác nhận/bỏ qua ngay
  tại chỗ — `POST /tasks/{id}/confirm|dismiss`) và **Lấy dữ liệu** (xem mục
  riêng bên dưới).
- Nền định kỳ poll `GET /api/v1/tasks?status=proposed`, bắn OS notification khi có việc.
  Bấm notification → mở tab `WXT_WEB_APP_URL/tasks` (đầy đủ hơn Side Panel: filter, bulk, calendar handoff).
- **Không có form đăng nhập riêng.** Extension tự kiểm tra web app đã đăng nhập
  chưa (content script + probe lúc mở Side Panel) rồi mượn luôn phiên đó — giống
  kiểu extension Claude: mở Side Panel ra thấy ngay nội dung nếu web app đã login,
  không bắt đăng nhập lại lần hai. Options page (chuột phải icon → Tuỳ chọn)
  chỉ hiện trạng thái đã đồng bộ hay chưa + nút mở web app.

## Chạy dev

```bash
pnpm install
cp .env.example .env   # sửa WXT_API_BASE_URL / WXT_WEB_APP_URL nếu khác cổng mặc định
pnpm dev
```

`wxt` in ra đường dẫn `.output/chrome-mv3-dev`. Load thư mục đó vào Chrome (xem bên dưới).
Đổi `.env` xong phải chạy lại `pnpm dev` (hoặc build lại) vì WXT inline giá trị
lúc build, không đọc runtime.

## Build production

```bash
pnpm build   # chỉ dựng .output/chrome-mv3
pnpm zip     # dựng + đóng gói + chạy cổng kiểm artifact
```

`build` và `zip` luôn chạy với mode `production`, đọc endpoint public từ
`.env.production`. Output ở `.output/chrome-mv3/` và file ZIP ở
`.output/mondaiy-extension-*-chrome.zip`.

`zip` gọi thêm `tests/test_build_artifact.sh`, cổng này chặn hai lỗi đã từng
lọt ra bản phát hành: HTML còn thẻ `modulepreload` (gây "cross-world extension
resource mismatch" của Chrome), và bundle production còn trỏ `localhost`. Chạy
tay được: `bash tests/test_build_artifact.sh .output/chrome-mv3 production`.

## Load vào Chrome

1. `chrome://extensions`
2. Bật **Developer mode** (góc trên phải)
3. **Load unpacked** → chọn `.output/chrome-mv3` (hoặc `chrome-mv3-dev` nếu đang `pnpm dev`)
4. Bấm icon extension → Side Panel mở bên cạnh cửa sổ, danh sách task ở tab
   "Công việc". Lần đầu chưa đăng nhập ở web app thì panel hiện nút "Mở
   mondaiy" — đăng nhập xong ở đó, mở lại panel là thấy task ngay (không cần
   đăng nhập thêm lần nào trong extension). Panel không đóng khi đổi tab.

`.output/` chỉ được phép chứa **một** bản build tại một thời điểm. Bản build cũ
để lại trong đó là bẫy thật, không phải rủi ro lý thuyết: đã có lần Chrome đang
load một thư mục cũ hai ngày trong khi mọi người đọc code mới để tìm lỗi, và
triệu chứng — ghi âm báo "Đã gửi 0 đoạn · 1 đoạn lỗi" mà không có dòng lý do —
trông y hệt một bug backend. Trước khi kết luận bất kỳ lỗi extension nào, kiểm
`chrome://extensions` xem đang load đúng thư mục nào, và đối chiếu:

```bash
# bản đang load có chứa bản vá mình vừa đọc trong source không?
grep -rl "mondaiy-recording-request-token" .output/chrome-mv3
```

## Phát hành bản mới cho người dùng

Extension **không lên Chrome Web Store**. Người dùng tải ZIP từ trang
`/extension` của web app (`ExtensionInstallPage.tsx`), file đó được phục vụ tĩnh
từ `client/web-app/public/downloads/mondaiy-extension-chrome.zip`. Nghĩa là ZIP
nằm trong repo và **đi theo lần deploy web app**, không có kênh phát hành riêng.

Hệ quả phải nhớ: sửa code extension mà không làm bước 2-3 dưới đây thì người
dùng vẫn tải về bản cũ, và không có gì trong CI báo cho biết.

```bash
cd client/extension
pnpm zip                                       # 1. build + đóng gói + cổng kiểm

cp .output/mondaiy-extension-0.1.0-chrome.zip \
   ../web-app/public/downloads/mondaiy-extension-chrome.zip   # 2. đẩy sang web app

shasum -a 256 .output/mondaiy-extension-0.1.0-chrome.zip \
   ../web-app/public/downloads/mondaiy-extension-chrome.zip   # 3. hai hash phải trùng
```

Tên file đích cố định (không kèm số phiên bản) vì `EXTENSION_DOWNLOAD_PATH`
trong `ExtensionInstallPage.tsx` trỏ cứng vào đường dẫn đó — đổi tên file là
gãy nút tải, không phải đổi tên vô hại.

Sau đó commit ZIP kèm code rồi deploy web app như bình thường. Nếu số phiên bản
trong `package.json` đổi thì phải sửa cả `downloadMeta` ở hai ngôn ngữ trong
`client/web-app/src/i18n/translations.ts` — chỗ đó đang ghi phiên bản bằng tay,
không tự đọc từ manifest.

Checklist trước khi merge một PR có đụng `client/extension/`:

```
□ pnpm test · pnpm compile
□ pnpm zip chạy sạch (cổng artifact xanh)
□ Đã copy ZIP sang client/web-app/public/downloads/ và hash trùng
□ Đổi version trong package.json thì đã sửa downloadMeta (en + vi)
□ Đã xoá các thư mục build cũ trong .output/
```

### Người dùng cập nhật thế nào

Bản đã cài bằng *Load unpacked* **không tự cập nhật**. Trang `/extension` đã có
sẵn hướng dẫn (`updateDesc` trong translations): tải ZIP mới, thay nội dung
trong đúng thư mục đã giải nén lần đầu, rồi bấm **Reload** ở
`chrome://extensions`. Giữ nguyên đường dẫn thư mục — đổi chỗ là Chrome coi như
extension khác, mất luôn `chrome.storage` nên phải đăng nhập lại từ web app.

Không có cơ chế báo cho người đang dùng biết có bản mới. Bản mới có thay đổi
người dùng buộc phải nhận (sửa lỗi ghi âm, đổi endpoint) thì phải báo qua kênh
ngoài — đây là giới hạn đã biết của cách phân phối ZIP, không phải thiếu sót
tạm thời.

## Biến môi trường (`.env`)

| Biến | Ý nghĩa |
|---|---|
| `WXT_API_BASE_URL` | Base URL backend (FastAPI). Dùng cho `host_permissions` + mọi request — không hardcode. |
| `WXT_WEB_APP_URL` | Base URL web app — extension chỉ mở tab tới đây, không tự render brief/chat/actions. |

## Cấu trúc

```
entrypoints/
  background.ts             service worker: poll task, badge, OS notification, nhận báo session từ content script,
                            điều phối phiên ghi âm (panel ra lệnh → offscreen thực thi), setPanelBehavior mở Side Panel khi bấm icon
  offscreen/main.ts         nơi duy nhất chạm MediaRecorder/getUserMedia — service worker MV3 không có DOM.
                            Cắt chunk, upload kèm offset, xin token từ background (storage.session không đọc được ở đây)
  web-session.content.ts    chạy trong tab web app — đọc localStorage nav_session, báo về background khi đổi
  sidepanel/                Side Panel chính: tab "Công việc" (danh sách task + bảng điều khiển ghi âm) và
                            tab "Lấy dữ liệu" (đọc nội dung tab đang active, lưu vào task) — mở khi bấm icon
  options/                   trạng thái đồng bộ, xin quyền micro một lần, nút mở web app — không có form đăng nhập
components/ui/               Button, Input dùng chung sidepanel + options
lib/
  api.ts                    task (list/confirm/dismiss/from-suggestion/summarize-page-extraction), reminder, meeting note + uploadAudioChunk/finalizeRecording
  pageExtraction.ts         redactSensitive() — che số nhạy cảm trước khi gửi text lên backend tóm tắt, test được bằng vitest
  recording.ts              state machine thuần của phiên ghi âm — không chạm Web API để test được bằng vitest
  auth.ts                   applyWebSession()/getSession()/logout()/refresh, token ở chrome.storage.session (memory-only)
  webSession.ts             đọc nav_session từ localStorage/sessionStorage trang web app
  storage.ts                wrapper chrome.storage (wxt/utils/storage)
types/index.ts               AuthSession, Task, TaskEvidence
```

## Tab "Lấy dữ liệu"

Đọc nội dung TRANG ĐANG ACTIVE khi người dùng bấm nút — không tự động, không
đọc nền, không đọc tab khác tab đang xem. Cơ chế:

1. `chrome.tabs.query({active:true, currentWindow:true})` truy vấn lại NGAY
   trước mỗi lần trích xuất (không cache tabId cũ) — đổi tab A→B→C thì luôn
   thao tác đúng tab đang active tại thời điểm bấm.
2. `chrome.scripting.executeScript` inject một hàm tự chứa (không import gì —
   bắt buộc vì `func:` serialize hàm bằng `toString()`, xem
   `extractPageContentInPage` trong `entrypoints/sidepanel/App.tsx`), giới hạn
   20.000 ký tự — hoàn toàn thụ động, model không bấm/cuộn/điều hướng gì trên
   trang (xem quyết định ở mục dưới). Không lấy nguyên `document.body.innerText`
   (dễ lẫn sidebar/nav/danh sách hội thoại cạnh nội dung thật — vd Zalo web):
   ưu tiên landmark `<main>`/`[role=main]`/`<article>` nếu trang tự khai báo;
   không có thì quét `<body>` nhưng loại text trong `nav/aside/header/footer`,
   ARIA landmark (`role=navigation|complementary|banner|...`), phần tử ẩn, và
   class/id có từ khoá điều hướng/sidebar phổ biến — cùng kiểu heuristic
   Readability/Defuddle dùng để lọc boilerplate, viết tay để khỏi thêm
   dependency hay đổi cách inject (xem test ở `pageContentExtraction.test.ts`).
   Heuristic, không tuyệt đối chính xác — trang không đặt tên class rõ ràng và
   không có landmark ngữ nghĩa vẫn có thể lẫn nhiễu.
3. `lib/pageExtraction.ts` che số thẻ/tài khoản dài (13-19 chữ số) trước khi
   text rời khỏi extension. Đến đây UI hiện NGAY danh sách các dòng thô đã lấy
   (chưa gọi backend) — người dùng xem trước, thấy trang đọc được gì, trước
   khi tốn lời gọi LLM ở bước sau.
4. Bấm "Extract công việc" mới gửi text đã redact lên
   `POST /api/v1/tasks/summarize-page-extraction` (`src/api/tasks.py` +
   `src/services/page_extraction.py`). Đường chính: **MỘT lượt gọi LLM trên
   TOÀN đoạn** (`_extract_tasks_via_llm`, structured output, đóng vai chuyên
   viên quản lý dự án, "strict extraction" — ưu tiên precision, neo mốc ngày
   "hôm nay" tường minh) — LLM tự GOM các dòng/tin nhắn RẢI RÁC (không cần
   liền kề) thuộc cùng một việc thành một suggestion, và có đủ ngữ cảnh toàn
   đoạn để nhận ra nhãn nút UI/banner lẫn vào là nhiễu thay vì đoán mù từng
   dòng cô lập. Đây là hướng khuyến nghị cho action-item extraction từ
   chat/meeting (nghiên cứu 2026: structured output + role-based + strict
   extraction prompt), thay cho cách cũ phân loại rule+LLM TỪNG DÒNG riêng lẻ.
   `mock_llm=True` (test) hoặc LLM lỗi/hết quota thì fallback về
   `_summarize_via_line_rules` — rule+LLM hybrid per-line cũ
   (`is_task_like()`/`confidence_tier()` lọc theo mẫu hình thức, LLM chỉ xử lý
   phần mơ hồ), tất định nhưng chỉ gom được dòng LIÊN TIẾP
   (`_group_consecutive_matches`), không gom được task rải rác như đường
   chính. Endpoint này KHÔNG tạo task, chỉ trả gợi ý.

   Trước khi gọi LLM, endpoint đọc `user_profile` (`src/services/profile_memory.py`)
   + `long_term_memories` liên quan (`arecall()` + `to_prompt_payload()` trong
   `src/services/memory_store.py` — cùng hệ thống memory chat agent đang dùng
   ở `src/agents/nodes/core_nodes.py`, tái dùng thẳng, không xây riêng) và
   chèn vào prompt theo đúng format/caveat "đây là dữ liệu, không phải chỉ
   dẫn" đã có. Nhờ vậy LLM điền được bối cảnh mà đoạn text không nói rõ (vd
   tin nhắn chỉ nói "gửi file cho anh" không nêu dự án, nhưng memory ghi user
   đang làm dự án X). LLM chỉ trích **nguyên văn cụm chỉ thời hạn**
   (`deadline_text`, vd "trước 5h chiều mai") — KHÔNG tự tính ngày; server
   dùng `resolve_due_at()` (`src/agents/pipeline/time_resolve.py` — cùng hàm
   Slack/Gmail/Jira/meeting-notes đang dùng) để parse, theo đúng BR-05 (PRD
   §9): chỉ set `due_at` khi text gốc có đủ ngày+giờ+timezone tường minh, mơ
   hồ thì bỏ qua `due_at` (không đoán) nhưng vẫn giữ cụm gốc trong `detail`.
5. Mỗi suggestion hiện thành 1 thẻ riêng (`SuggestionCard`) — người dùng
   xem/sửa title+detail+hạn chót rồi bấm "Lưu" hoặc "Bỏ qua" cho TỪNG cái độc
   lập. "Lưu" tái dùng thẳng `POST /api/v1/tasks/from-suggestion` (endpoint đã
   có sẵn cho thẻ gợi ý ở web app, đã nhận `dueAt` từ trước) — không tạo hệ
   thống lưu trữ task riêng cho tính năng này. "Bỏ qua" chỉ xoá khỏi list phía
   client, suggestion chưa từng tồn tại trên server nên không cần gọi API.

Quyết định dùng hybrid: so sánh thực nghiệm 3 hướng (rule thuần / LLM thuần /
hybrid) trên cùng bộ golden dataset dùng chung
(`ml/model for extension/data/`, chạy bằng
`scripts/eval_task_classifiers.py`) — rule thuần 100% trên 220 câu sạch (cân
bằng 110/110) nhưng chỉ 83.3% trên 24 câu chat thật cân bằng 12/12 (recall
75% — không phân biệt được thì quá khứ/tường thuật với yêu cầu thật, và bỏ lọt
yêu cầu lịch sự dùng động từ ngoài whitelist); LLM thuần đạt 93.2%/100% nhưng
gọi LLM cho MỌI dòng (chậm, tốn); hybrid đạt 94.5%/100% — tốt nhất ở cả hai bộ
vì kế thừa độ chính xác tuyệt đối của rule ở phần rõ ràng, chỉ để LLM xử lý
đúng phần rule không tự tin được — đồng thời rẻ hơn 25-30% lời gọi LLM so với
gọi cho mọi dòng.

**Không dùng model để tự điều khiển trình duyệt** (kiểu bấm/cuộn/điều hướng để
tự đi tìm thông tin) — đã cân nhắc và quyết định KHÔNG làm trong task này: đó
là một hệ thống khác hẳn (action-loop + guardrail chống prompt injection từ nội
dung trang, rủi ro model bị đánh lừa thao tác trên phiên đăng nhập thật của
người dùng), cần task/PRD riêng nếu muốn làm sau này.

Quyền dùng là permission `tabs` + `host_permissions: ["<all_urls>"]`. Bản đầu
tiên dùng `activeTab` (không có host_permissions rộng) để tối thiểu quyền, vì
đúng semantics "chỉ tab đang active tại thời điểm thao tác" — nhưng verify
thực tế bị Chrome từ chối ngay khi đổi tab dù đã bấm lại icon toolbar: Side
Panel cố tình sống xuyên suốt lúc đổi tab (khác popup cũ, vốn activeTab luôn
mới vì mỗi lần mở popup là một invoke mới), nên activeTab cấp cho tab lúc mở
panel không tự theo qua tab người dùng chuyển tới sau đó — khớp báo cáo lỗi đã
biết của Chromium về activeTab + Side Panel
(https://groups.google.com/a/chromium.org/g/chromium-extensions/c/DET2SXCFnDg).
Đổi sang `tabs` + `<all_urls>` (cùng cách `client/Test extension` đã dùng) để
ổn định mọi lúc. Ràng buộc "chỉ đọc tab đang active, không đọc tab khác" vẫn
nằm ở CODE (`readActiveTab()` truy vấn lại ngay trước mỗi lần trích xuất),
không phải ở permission — `<all_urls>` chỉ cấp khả năng kỹ thuật, không có
nghĩa extension tự ý đọc tab nào khác.

## Cách mượn phiên đăng nhập từ web app

Web app lưu session ở `localStorage`/`sessionStorage` key `nav_session`
(`{accessToken, refreshToken}` — xem `client/web-app/src/stores/useAuthStore.ts`).
Extension đọc thẳng key đó qua 2 đường, không có API riêng cho việc này:

1. `entrypoints/web-session.content.ts` — content script khớp `WXT_WEB_APP_URL/*`,
   tự báo về background mỗi khi trang load / đổi tab / bấm lại tab (`visibilitychange`) /
   tab khác cùng origin đổi storage (`storage` event).
2. Lúc mở Side Panel, `probeWebAppSession()` chủ động tìm tab web app đang mở và
   `chrome.scripting.executeScript` đọc trực tiếp — không đợi content script
   báo, đảm bảo panel luôn thấy trạng thái mới nhất ngay khi mở ra.

Không tìm thấy tab nào đang mở → giữ nguyên session đã đồng bộ lần trước (không
suy đoán logged-out chỉ vì đóng tab). Tìm thấy tab nhưng localStorage rỗng →
coi là đã đăng xuất, xoá session phía extension theo.

`expiresAt` của session mượn được luôn set về `0` vì không biết hạn thật của
accessToken lấy từ localStorage — lần gọi API đầu tiên sẽ tự refresh lấy hạn
chính xác từ backend (`lib/auth.ts getValidAccessToken`).

## Vì sao không dùng SSE `/runs/{id}/events` để báo brief xong

Service worker MV3 không persistent — bị Chrome tắt sau ~30s không hoạt động,
không giữ được kết nối SSE lâu dài. Backend cũng chưa có endpoint liệt kê
run gần nhất của user (`GET /runs` list) để nền tự dò run_id mà theo dõi.
Vì vậy tín hiệu duy nhất khả thi hiện tại là poll định kỳ task count.

## Icon

`public/icon/{16,48,128}.png` resize từ `client/web-app/public/mondaiy-mascot.png`
(mascot mark dùng chung wordmark/favicon bên web-app — xem `MondaiyMark.tsx`).
Đổi icon thì đổi mascot gốc bên web-app rồi resize lại, không tự vẽ icon riêng
cho extension.

## Quy tắc cứng đã áp dụng (không được phá)

- Token luôn ở `chrome.storage.session` (memory-only), không bao giờ `local`.
- Không hardcode URL backend/web app — mọi thứ qua `WXT_API_BASE_URL` / `WXT_WEB_APP_URL`.
- Không tự thêm phân loại thông báo (urgent/conflict/...) khi backend chưa có API thật cho việc đó.
- Tab "Lấy dữ liệu" chỉ đọc tab đang active TẠI THỜI ĐIỂM người dùng bấm nút —
  không tự động, không polling nền, không đọc tab khác. Ràng buộc này nằm ở
  code (`readActiveTab()` gọi lại ngay trước mỗi lần trích xuất), không phải ở
  permission — `tabs` + `<all_urls>` chỉ là khả năng kỹ thuật đã verify cần
  thiết (xem mục "Tab Lấy dữ liệu" ở trên), không phải giấy phép tự ý mở rộng
  sang đọc tab khác.
