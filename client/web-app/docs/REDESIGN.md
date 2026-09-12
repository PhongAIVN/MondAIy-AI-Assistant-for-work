# Mondaiy - Design Audit và Kế hoạch Redesign

**Phạm vi:** `client/web-app` (React 19 + Vite + Tailwind v4 + react-router 7 + zustand + lucide-react)
**Trạng thái:** Đề xuất, chưa thực thi. Không có file nào bị sửa khi lập tài liệu này.
**Hướng visual mục tiêu:** Pastel Editorial AI / Quiet Premium / Motion-driven Product Design
**Ngày:** 2026-08-08

> Tài liệu này là bản audit thiết kế và kế hoạch triển khai. Nó không định nghĩa sản phẩm,
> yêu cầu hay quy tắc nghiệp vụ. Những thứ đó nằm ở `docs/projects/` và chỉ có một nguồn
> chuẩn duy nhất.

---

## Ba phát hiện quan trọng nhất

**Token layer đang chết.** `index.css` định nghĩa khoảng 60 CSS variable (`--color-surface`,
`--color-accent`, `--shadow-md`...) nhưng **không có block `@theme`**. Trong Tailwind v4,
thiếu `@theme` nghĩa là không có utility nào (`bg-surface`, `text-accent`) được sinh ra. Cả
hệ token đó gần như không ai dùng được, và hệ quả là **74 giá trị hex thô** rải trong chỉ 14
file sản phẩm. Đây là nguyên nhân gốc của toàn bộ drift màu, không phải là "thiếu kỷ luật".

**Toàn bộ animation hiện tại là class chết.** Code dùng `animate-in fade-in`, `zoom-in-95`,
`slide-in-from-bottom-2` ở 17+ chỗ, nhưng `package.json` không có
`tailwindcss-animate`/`tw-animate-css` và `index.css` không có `@plugin`. Tailwind v4 core
không có các class này. Chúng không render ra gì cả. `Drawer.tsx` cũng khai báo
`transition-transform duration-200` nhưng không hề có `translate-x` nào, nên drawer bật ra
tức thì. Nói cách khác: UI hiện tại **motion bằng 0**, dù code trông như có.

**Có sẵn `hero.png` nhưng không dùng.** Landing page thay vào đó dựng một "product preview"
giả hoàn toàn bằng `<div>` (2 lần: hero và section preview). Đây là AI tell số một trong
danh sách của taste skill.

---

## Design Read

> Đọc brief này là: **redesign visual toàn diện cho một product app đa bề mặt** (marketing +
> auth + workspace dày dữ liệu + admin portal) phục vụ học viên và điều phối viên chương
> trình đào tạo, ngôn ngữ **pastel editorial, quiet premium, motion có chủ đích**, giữ nguyên
> IA, routing, component và business logic.

**Redesign mode:** Overhaul về visual, Preserve tuyệt đối về IA/content. Đây là mode rủi ro
cao nhất nếu làm sai thứ tự, nên kế hoạch bên dưới đi từ token lên bề mặt.

**Dials đề xuất** (hiện tại đang ở khoảng 3 / 1 / 7):

| Bề mặt | VARIANCE | MOTION | DENSITY |
| --- | --- | --- | --- |
| Marketing, auth, onboarding | 7 | 7 | 3 |
| Workspace (briefing, tasks, sources) | 5 | 5 | 5 |
| Data privacy, activity, admin | 4 | 3 | 6 |

Một cảnh báo nghề nghiệp ngay từ đầu: taste skill tự nói nó **không dành cho dashboard và
bảng dữ liệu**, mà Mondaiy có `DataPrivacyPage`, `ActivityPage`, `MemoryInspectorTab` và 10
trang admin. Pastel cộng bo tròn lớn cộng motion nếu áp đồng loạt sẽ **làm hỏng chính lời
hứa cốt lõi của sản phẩm là truy vết được và kiểm chứng được**. Vì vậy đề xuất một hệ token
duy nhất nhưng **hai chế độ biểu đạt**, chi tiết ở phần Design Direction.

---

# PHẦN 1: AUDIT

## 1. Bảng màu

Hệ màu hiện tại là **navy lạnh chuyên nghiệp nhưng đã vỡ kỷ luật**.

Nền tảng ổn: ink `#12305B`, accent `#2563A6`, soft `#DCEBFA`, semantic success `#2F7D5B` /
warning `#A66A16` / danger `#B54747`. Bộ này desaturated tốt, không dính AI-purple gradient,
và **không có gradient nào trên landing page**. Đó là điểm mạnh thật sự, nhiều hơn phần lớn
dự án.

Vấn đề:

- **74 hex thô trong 14 file**, top: `#12305B` (89 lần), `#AEB9CC` (77), `#16233F` (76),
  `#2563A6` (75). Không có nguồn chuẩn.
- **Ít nhất 10 hue accent riêng biệt** đang tồn tại song song, vượt xa "một accent". Ngoài
  bộ semantic hợp lệ còn có: purple lạc `#6656A6` (`DailyBriefingPage.tsx:356`), teal admin
  `#64FFDA`, `amber-600`/`rose-500` chỉ dùng cho admin branding, blue avatar `#3478B8`, và
  4 màu brand icon.
- **Admin portal dùng bảng màu khác hẳn app** (`#8892B0`, `#1E293B`, `#112240`, teal
  `#64FFDA`). Trông như sản phẩm thứ hai.
- **Trộn xám ấm và xám lạnh**: `#F8FAFC`/`#EAF3FB`/`#64748B` (lạnh, gốc slate) đứng cạnh
  `#52657A`/`#7B8798`/`#5E6B7D`/`#7A8999` (trung tính lệch ấm). Có **bốn** giá trị "text
  secondary" khác nhau đang cùng làm một việc.
- Nhiều token trong `index.css` bị **khai báo hai lần** dưới dạng "legacy compatibility"
  (`--color-text-primary` và `--text-primary`), nhân đôi bề mặt bảo trì.
- `#FFFFFF` thuần làm page background. Không có độ sâu, không có "giấy".

## 2. Typography

Inter (body) + Manrope (heading, qua rule `h1..h6` trong CSS). Cả hai nạp bằng `<link>`
Google Fonts render-blocking, không preload, không self-host.

- **Inter là default bị taste skill khuyến cáo tránh.** Manrope thì ổn và thân thiện với
  pastel, nhưng đang bị dùng lẫn lộn: có chỗ qua tag `h1`, có chỗ qua class `font-heading`,
  có chỗ **hardcode inline** `style={{ fontFamily: "'Manrope', sans-serif", fontWeight: 800 }}`
  (`DailyBriefingPage.tsx:671`, `MondaiyLogo.tsx:29`).
- **Thang chữ sụp đổ về phía nhỏ.** Trong 14 file sản phẩm: `text-xs` **109 lần**,
  `text-[11px]` 29 lần, `text-[10px]` 27 lần, nhưng `text-sm` chỉ 13 và `text-base` chỉ 9.
  Giao diện đọc như một bảng điều khiển bị nén, không phải quiet premium. Đây là vấn đề
  typography nghiêm trọng nhất.
- **Không có hierarchy bằng weight.** Gần như mọi tiêu đề đều là `font-bold` hoặc
  `font-extrabold`. Không có 500/600 để tạo cấp trung gian, nên hệ thống chỉ có "to đậm" và
  "nhỏ mờ".
- Không có `font-mono` ở đâu, không có `tabular-nums`, dù sản phẩm đầy timestamp, số liệu
  audit và ID nguồn.
- Không có `text-wrap: balance`, không giới hạn measure `65ch`.
- Landing H1 chỉ có 2 bậc (`text-3xl sm:text-5xl`), không có bậc `lg:`.

## 3. Spacing

Có nhịp chủ đạo nhưng **không phải một thang**.

`gap-2` (54 lần) áp đảo, rồi `gap-1.5` (23), `gap-1` (19), `gap-3` (18), `gap-2.5` (13). Tức
là phần lớn khoảng cách nằm trong dải 4px đến 12px. Cộng với `text-xs` áp đảo, kết quả là
**mật độ cockpit trên một sản phẩm lẽ ra cần sự bình tĩnh**.

Lỗi cụ thể: `AppShell` cho `<main>` padding `p-3 sm:p-5 lg:p-6`, nhưng `DataPrivacyPage` lại
tự thêm `px-4 sm:px-6 lg:px-8 py-8`. **Padding cộng dồn**, và mỗi trang tự quyết định padding
riêng. Không có page-container chung.

Rải rác giá trị lẻ: `py-0.2`, `px-3.5`, `pb-12`, `gap-8` một lần duy nhất.

## 4. Border radius

**Sáu token trở lên, không có luật.** Trong 14 file sản phẩm: `rounded-lg` 42, `rounded-xl`
41, `rounded-2xl` 21, `rounded` trần 19, `rounded-full` 18, `rounded-md` 4, cộng thêm
`rounded-[12px]`, `rounded-tr-xs`, `rounded-tr-none`, `rounded-tl-none`.

Xung đột rõ nhất: `Card` là `rounded-xl` nhưng panel cấp trang lại `rounded-2xl`; Button đổi
radius theo size (`md` sang `lg` sang `lg` sang `xl`); Badge dùng `rounded-md`/`rounded-lg`
trong khi hero badge trên landing lại `rounded-full`. Không nhất quán về hình khối là một
trong những thứ khiến mắt đọc ra "template".

## 5. Shadow

**Trộn hai hệ.** `Card.tsx` dùng shadow navy-tinted tự viết rất đúng bài:
`shadow-[0_1px_2px_rgba(18,48,91,0.04)]` và hover `shadow-[0_4px_14px_rgba(18,48,91,0.07)]`.
Nhưng mọi nơi khác dùng Tailwind scale đen thuần: `shadow-2xs` (27 lần), `shadow-xs` (5),
`shadow-lg` (4), `shadow-2xl` (4), `shadow-xl` (2), `shadow-sm` (1), cộng `shadow-black/40`.

`--shadow-sm/md/lg` được khai báo trong `:root` nhưng vì không có `@theme` nên **không sinh
ra utility nào**, không ai dùng được.

Kết quả: bóng đổ không có hướng sáng thống nhất, và hầu hết là đen thuần trên nền lạnh, cho
cảm giác bẩn và rẻ.

## 6. Card design

`Card.tsx` chính xác là pattern generic mà skill cảnh báo: **nền trắng cộng border cộng
shadow**, `rounded-xl`, `p-5`.

Mặt tốt: hệ `accentBorder` (`border-l-4` cho urgent/warning/info/success) là một quyết định
thông tin tốt, đáng giữ.

Mặt xấu: `hoverable` tồn tại nhưng `BriefingCard` không truyền, nên card briefing **không có
hover state nào**. Landing page thì lặp lại đúng một vỏ card trắng viền
`p-6 rounded-2xl bg-white border border-[#D0E2F2]` **chín lần** (3 step cộng 6 feature).

## 7. Button

Đây là component **tốt nhất** trong codebase. Có 6 variant, 4 size, `active:scale-[0.98]`,
`transition-all duration-150`, focus ring, disabled state. Nền tảng vững.

Thiếu sót:

- Variant `secondary` **không có `focus:ring-[color]`**, chỉ thừa hưởng `focus:ring-2` không
  màu. Đây là lỗi a11y thật.
- Không variant nào có `active:` background riêng, chỉ dùng chung scale.
- Radius nhảy theo size, phá vỡ shape consistency.
- Không có `link`/tertiary variant, nên mọi CTA phụ đều phải là outline hoặc ghost, tạo
  nhiễu thị giác.
- Không có loading state trong Button (các trang tự chế spinner riêng).

## 8. Navigation

Sidebar `w-56`, collapse xuống `lg:w-16`, `bg-[#F8FAFC]`, `border-r`. Trên mobile trượt bằng
`-translate-x-full` với `transition-all duration-200`. **Đây là animation duy nhất thực sự
hoạt động trong toàn bộ app.**

Active state ổn: `bg-[#DCEBFA] border-l-2 border-[#2563A6] font-semibold`.

Vấn đề:

- **Sidebar chỉ chứa 5 mục** (`/run`, `/sources`, `/data-privacy`, `/activity`,
  `/notifications`) cộng `/admin`. Nhưng app có **15 route người dùng**. `/briefing`,
  `/tasks`, `/calendar`, `/settings`, `/profile`, `/help` **không có đường vào từ nav
  chính**. Đây là lỗi IA, không phải lỗi visual, và không được phép tự sửa IA. Cần PM và
  UI/UX Lead quyết.
- TopBar không có chiều cao cố định (chỉ `py-2`, `text-xs`), nên chiều cao trôi theo nội
  dung.
- Notification bell có **chấm đỏ hardcode**, luôn hiện.
- Admin nav là một hệ điều hướng thứ hai với ngôn ngữ hình ảnh khác hẳn.

## 9. Hero

Hero landing là **centered stack**, không split, `pt-12 md:pt-20`, không dùng `h-screen`
(tốt) nhưng cũng không `min-h-dvh`.

Chấm điểm theo luật hero của skill:

| Tiêu chí | Hiện trạng | Kết quả |
| --- | --- | --- |
| Số text element | 4 (badge, H1, sub, CTA) | Đạt, sát trần |
| Subtext | 22 từ | Vượt trần 20 từ |
| Số CTA | 2 | Đạt |
| Visual | Fake UI dựng bằng div | **Trượt** |
| Thang chữ | Chỉ 2 bậc, dừng ở `text-5xl` | Yếu, thiếu presence |
| Motion | Không có gì | **Trượt** |

Copy thì tốt hơn kỳ vọng: "Turn program updates into clear next actions." rõ ràng, cụ thể,
**không có từ sáo AI nào** (không Elevate/Seamless/Unleash) và không em-dash trong chuỗi
marketing. Đây là tài sản, nên giữ giọng này.

Badge hero "Traceable AI Synthesis for Educational Programs" đang hardcode, không qua i18n.

## 10. Section layout

7 section. Mức lặp lại cao:

- **4 section** dùng đúng một khối mở đầu `text-center max-w-2xl mx-auto mb-12 space-y-3`
  (Problem, How It Works, Features, Preview).
- **2 section** dùng hàng 3 card bằng nhau (`md:grid-cols-3` và `lg:grid-cols-3`), chính là
  layout bị skill cấm.
- **9 card** dùng chung một vỏ trắng giống hệt.
- **2 mock product UI** dựng bằng div.
- Section Trust là **một dải tối `#112240` chen giữa trang sáng**, vi phạm Page Theme Lock.
  Đúng cái mà skill mô tả là "trông như tai nạn copy-paste".

Tính theo luật "8 section phải có tối thiểu 4 layout family", trang này thực chất chỉ có
khoảng 2,5 family.

## 11. Icon system

`lucide-react`, xuất hiện ở **76 file**. Đây chính là lựa chọn icon mặc định của AI mà skill
khuyến cáo tránh, nhưng skill cũng cho phép giữ khi dự án đã phụ thuộc sẵn. Với 76 file thì
thay thư viện là thay đổi rủi ro cao mà lợi ích thị giác thấp.

Vấn đề thật nằm ở chỗ khác:

- **`strokeWidth` không bao giờ được set**, nên tất cả dùng default 2. Ở size nhỏ (`w-3.5`)
  stroke 2 trông nặng và bẩn.
- **Size không có thang**: `w-2`, `w-3.5`, `w-4`, `w-5`, `w-8`, `w-10`. Nút close chỗ thì
  `w-4` chỗ thì `w-5`.
- `BrandIcons.tsx` dùng **PNG** (`discord-icon.png`, `gmail-icon.png`) trộn với SVG lucide.
  PNG không đổi màu theo theme, không sắc nét trên màn hình retina.

## 12. Illustration và visual system

**Gần như không tồn tại.** Không có một illustration nào, không có texture, không có ảnh
thật ở bất kỳ đâu trên bề mặt marketing. `hero.png` nằm trong `assets/` nhưng không file nào
import.

Chỗ lẽ ra là visual thì được thay bằng fake UI dựng từ div, kèm chấm đèn giao thông
rose/amber/emerald giả cửa sổ macOS. Empty state dùng icon `Inbox` lucide `w-10` trong một
vòng tròn xám. Không có ngôn ngữ hình ảnh riêng nào để nhận ra Mondaiy.

## 13. Animation

Như đã nêu ở đầu, **thực tế bằng 0**:

- 17+ chỗ dùng `animate-in`/`fade-in`/`zoom-in-95`/`slide-in-from-bottom-2` là **class
  chết**, không có plugin cung cấp.
- `Drawer` khai báo `transition-transform` nhưng không có translate, và unmount bằng
  `if (!isOpen) return null` nên **không có exit animation** ở bất cứ đâu.
- Không có `hover:scale`, `hover:-translate` ở bất kỳ file nào.
- Không có scroll reveal, không có stagger, không có layout transition.
- Thứ chạy thật: sidebar mobile slide, `animate-spin`, `animate-pulse`, `rotate-180`
  chevron, và `transition-colors` (33 lần).

Điểm cộng: `.reduce-motion` đã có sẵn trong `index.css` và tắt animation toàn cục. Hạ tầng
accessibility đã sẵn sàng cho một motion layer thật.

## 14. Responsive

Breakpoint dùng đúng chuẩn Tailwind, `sm:` 27 lần, `lg:` 16, `md:` 10, `xl:` 2. Sidebar
mobile có backdrop và slide đúng cách.

Rủi ro dưới 768px:

- Tab bar `DataPrivacyPage`: 3 tab kèm icon và label trong `flex gap-1.5`, không có scroll
  ngang hay wrap fallback.
- `DataPrivacyPage` cộng dồn padding với shell, làm hẹp vùng nội dung trên mobile.
- `SignUpPage` để password và confirm trong `grid-cols-2` **cố định**, không stack trên màn
  hẹp.
- Panel "At a glance" của briefing chỉ chuyển ngang ở `xl:`, dải 768px đến 1280px bị bỏ
  trống về mặt bố cục.

## 15. Vì sao UI đang trông generic

Xếp theo mức độ dễ nhận ra, đây là những thứ đang phát tín hiệu "template AI":

1. **Không có chuyển động.** Đây là tín hiệu mạnh nhất. Giao diện đứng yên hoàn toàn, kể cả
   những chỗ có ý nghĩa như briefing được tổng hợp xong.
2. **Fake product UI bằng div** ở hero, kèm chấm đèn giao thông giả macOS. Tell số một trong
   danh sách.
3. **Hàng 3 card bằng nhau**, hai lần, với vỏ card trắng lặp 9 lần.
4. **Card bằng trắng cộng viền cộng bóng**, không có vật liệu, không có texture, không có
   tint.
5. **Inter làm font mặc định**, chữ toàn `text-xs`, hierarchy chỉ dựa vào bold.
6. **Bóng đen thuần** trên nền lạnh, không tint theo hue nền.
7. **Không có ảnh thật nào.** Trang toàn chữ và khối màu phẳng, đọc ra là chưa hoàn thiện
   chứ không phải tối giản.
8. **Dải tối chen giữa trang sáng** ở section Trust.
9. **Lucide stroke 2 ở mọi kích thước**, kèm PNG brand icon lẫn vào.
10. **Logo là chữ đánh máy** với một chữ đổi màu, không có mark.
11. **Em-dash xuất hiện ở 15 file**, riêng `translations.ts` có 8, tức là em-dash đang hiển
    thị cho người dùng thấy.
12. **Empty state chỉ là icon xám trong vòng tròn**, không có thiết kế.

Điều đáng nói: bốn thứ **không** sai, và cần bảo vệ trong redesign. Không có AI-purple
gradient. Copy viết tốt và cụ thể. `accentBorder` trên Card là quyết định thông tin đúng. Hệ
semantic color desaturated hợp lý.

---

# PHẦN 2: ĐỀ XUẤT

## Design direction

**"Verified Calm"**: pastel editorial cho bề mặt thuyết phục, quiet precision cho bề mặt làm
việc, và motion chỉ dùng để diễn tả quá trình sản phẩm biến nhiễu thành kết luận.

Ba nguyên tắc dẫn dắt mọi quyết định bên dưới:

**Giấy, không phải chip.** Nền chuyển từ trắng thuần sang họ pastel có sắc, bề mặt nổi lên
bằng độ sáng và bóng tint chứ không bằng viền. Card mất viền mặc định, giữ lại viền chỉ khi
cần phân tách thật.

**Bằng chứng là vật liệu thẩm mỹ.** Mondaiy bán khả năng truy vết. Vậy nên metadata nguồn,
timestamp, độ tin cậy được nâng lên thành một tầng typography riêng bằng mono với
`tabular-nums`, thay vì bị nén thành `text-[10px]` xám nhạt như hiện nay. Đây là điểm khác
biệt so với Littlebird: Littlebird mềm và thân thiện, Mondaiy mềm nhưng **có thể kiểm chứng
được**.

**Hai chế độ, một hệ token.** Cùng một bộ biến CSS, nhưng marketing/auth/onboarding chạy ở
biên độ biểu đạt cao (pastel wash, motion 7, mật độ thấp), còn workspace/privacy/admin chạy ở
biên độ nén (pastel chỉ làm tint trạng thái, motion 3 đến 5, mật độ vừa). Điều này ngăn việc
pastel hóa một bảng audit và làm hỏng niềm tin.

Điều **không** lấy từ Littlebird: bo tròn cực lớn kiểu mọi thứ đều là viên thuốc,
illustration 3D bóng bẩy, và tông giọng vui nhộn. Mondaiy phục vụ deadline và quyền riêng tư.

## Font

Bỏ Inter và Manrope. Chuyển sang một họ duy nhất cộng một mono, self-host bằng `@font-face`
với `font-display: swap` thay cho `<link>` Google Fonts đang chặn render.

| Vai trò | Font | Lý do |
| --- | --- | --- |
| Display và UI | **Geist** | Trung tính nhưng có tính cách ở weight cao, dải weight rộng (300 đến 800) đủ dựng hierarchy bằng weight, chữ số đẹp |
| Bằng chứng và số liệu | **Geist Mono** | Cùng họ nên không lệch nhịp, dùng cho timestamp, source ID, độ tin cậy, số liệu audit |

Nếu team muốn một giọng editorial rõ hơn ở marketing, phương án thay thế là **Satoshi** cho
display giữ Geist cho UI. **Không đề xuất serif**: hướng "editorial" ở đây đạt được bằng bố
cục bất đối xứng, measure có kiểm soát và khoảng trắng, chứ không bằng chân chữ. Serif ở đây
sẽ là phản xạ mặc định chứ không phải quyết định.

## Pastel color palette

Suy ra trực tiếp từ màu hiện có, giữ nguyên navy làm mực và làm màu hành động để không hy
sinh contrast.

### Ink (từ `#12305B`)

| Token | Hex | Dùng cho |
| --- | --- | --- |
| `ink-900` | `#0F1F38` | Heading |
| `ink-700` | `#243A5C` | Body chính |
| `ink-500` | `#5A6A85` | Body phụ |
| `ink-400` | `#8B98AB` | Metadata, disabled |

Bốn giá trị này thay thế toàn bộ `#52657A`, `#5E6B7D`, `#64748B`, `#7A8999`, `#7B8798`,
`#94A3B8` đang lẫn lộn.

### Paper (thay `#FFFFFF` thuần)

| Token | Hex | Dùng cho |
| --- | --- | --- |
| `paper` | `#F5F7FC` | Nền trang |
| `surface` | `#FFFFFF` | Card, panel nổi |
| `surface-sunken` | `#EBEFF8` | Input, well, vùng lõm |

### Pastel wash

Chỉ dùng làm nền section trên marketing, cùng dải sáng nên không phá Theme Lock.

| Token | Hex |
| --- | --- |
| `wash-porcelain` | `#EDF2FB` |
| `wash-sage` | `#E7F0EA` |
| `wash-apricot` | `#FBEEE3` |
| `wash-mist` | `#EFF0F4` |

Apricot là tint biểu đạt của thương hiệu, dùng tiết chế. Apricot đặt cạnh navy là cặp ít gặp,
ấm mà vẫn nghiêm túc, và tránh được cả AI-purple lẫn cliché beige-brass.

### Action và semantic (giữ hue cũ, chuẩn hóa tint)

| Vai trò | Solid | Tint pastel |
| --- | --- | --- |
| Action | `#2563A6` | `#E1EBFA` |
| Success | `#2A6B4F` | `#DFF0E6` |
| Warning | `#8A5712` | `#FBEBD2` |
| Danger | `#A03D3D` | `#F9DEDE` |

**Phải khai tử:** purple `#6656A6`, teal admin `#64FFDA`, `amber-600`/`rose-500` dùng cho
branding admin, và toàn bộ bảng màu riêng của admin portal. Admin dùng chung hệ, chỉ khác ở
mật độ.

Dark mode giữ nguyên cấu trúc hiện có (`#0B132B`/`#111C35`) nhưng ánh xạ lại theo đúng bốn
nhóm token trên, thay vì duy trì hai bộ biến legacy song song.

## Typography hierarchy

Thang này kéo đáy lên: `text-xs` **không còn là mặc định của body**, chỉ dùng cho metadata.

| Bậc | Size / line-height | Weight | Tracking | Dùng cho |
| --- | --- | --- | --- | --- |
| Display | `clamp(2.5rem, 5vw, 4rem)` / 1.05 | 700 | `-0.03em` | Hero marketing |
| H1 | 32px / 1.15 | 650 | `-0.02em` | Tiêu đề trang |
| H2 | 24px / 1.2 | 600 | `-0.015em` | Tiêu đề section |
| H3 | 18px / 1.3 | 600 | `-0.01em` | Tiêu đề card |
| Body L | 16px / 1.6 | 400 | 0 | Nội dung đọc, tối đa `65ch` |
| Body | 14px / 1.55 | 400 | 0 | **Mặc định UI mới** |
| Label | 13px / 1.4 | 500 | 0 | Nhãn form, nav |
| Evidence | 12px / 1.4 mono | 450 | `0.01em` | Timestamp, source ID, số liệu, `tabular-nums` |

Ba luật đi kèm: hierarchy tạo bằng **weight và màu trước, size sau**; heading dùng
`text-wrap: balance`; đoạn văn dùng `text-wrap: pretty` và giới hạn `65ch`. Bỏ toàn bộ
`text-[10px]` và `text-[11px]`.

## Border và radius system

Bốn bậc, có luật viết ra và áp dụng ở mọi nơi.

| Token | Giá trị | Áp cho |
| --- | --- | --- |
| `r-sm` | 8px | Input, chip, badge, checkbox |
| `r-md` | 12px | Button (**mọi size**), nav item, icon button |
| `r-lg` | 18px | Card, panel, section block |
| `r-xl` | 26px | Modal, drawer, khối marketing lớn |
| `r-full` | pill | Chỉ avatar và toggle |

Button thôi đổi radius theo size. `rounded` trần, `rounded-[12px]`, `rounded-tr-xs` bị loại
bỏ.

Về border: mặc định card **không viền**, dùng bóng và tint để phân tách. Viền chỉ còn ba lý
do tồn tại: input, `accentBorder` trạng thái (giữ nguyên, đây là quyết định tốt), và bảng dữ
liệu ở admin. Hairline chuyển sang `rgba(15,31,56,0.08)` thay vì hex đặc `#DDE3EA`.

## Shadow system

Bốn bậc, tất cả tint navy, hai lớp (ambient cộng key) để có hướng sáng thống nhất từ trên
xuống.

```css
--shadow-1: 0 1px 2px rgba(15,31,56,0.04);
--shadow-2: 0 2px 4px rgba(15,31,56,0.04), 0 6px 16px rgba(15,31,56,0.06);
--shadow-3: 0 4px 8px rgba(15,31,56,0.05), 0 14px 32px rgba(15,31,56,0.08);
--shadow-4: 0 8px 16px rgba(15,31,56,0.06), 0 28px 64px rgba(15,31,56,0.12);
```

Bậc 1 cho card nghỉ, bậc 2 cho card hover và dropdown, bậc 3 cho drawer và popover, bậc 4 cho
modal. Dark mode dùng bóng bậc thấp hơn cộng inner border `rgba(255,255,255,0.06)`, vì trong
tối bóng gần như vô hình còn viền trong mới tạo được cạnh.

Bỏ toàn bộ `shadow-2xs`/`xs`/`lg`/`xl`/`2xl` của Tailwind và `shadow-black/40`.

## Motion language

Đây là hạng mục có đòn bẩy lớn nhất, vì xuất phát điểm là 0. Cài `motion` (`motion/react`),
cô lập trong client leaf component.

### Token easing và duration

| Token | Giá trị | Dùng cho |
| --- | --- | --- |
| `ease-out-quint` | `cubic-bezier(0.16, 1, 0.3, 1)` | Vào, mở, reveal |
| `ease-in-out-soft` | `cubic-bezier(0.4, 0, 0.2, 1)` | Đổi trạng thái |
| `spring-panel` | `stiffness 260, damping 30` | Drawer, modal, sheet |
| `d-fast` | 140ms | Hover, màu, focus |
| `d-base` | 240ms | Vào, thoát, chuyển tab |
| `d-slow` | 420ms | Reveal marketing, stagger |

### Bốn khoảnh khắc chuyển động

Mỗi cái phải giải thích được bằng một câu.

1. **Synthesis reveal.** Briefing card vào theo stagger 60ms, dịch lên 16px cộng fade. Diễn
   tả việc hệ thống vừa tổng hợp xong và đang trình bày theo thứ tự ưu tiên. Đây là khoảnh
   khắc chữ ký của sản phẩm.
2. **Evidence expand.** Mở source reference dùng height transition cộng fade nội dung, không
   phải bật tức thì. Diễn tả hành động lần ngược về bằng chứng.
3. **Panel physics.** Drawer và modal trượt bằng spring, **có exit animation** (hiện đang
   unmount thẳng). Sửa luôn cái `transition-transform` treo lơ lửng trong `Drawer.tsx`.
4. **Tactile feedback.** Giữ `active:scale-[0.98]` đã có, thêm hover nâng nhẹ 1px cho card có
   thể bấm, và transition cho focus ring.

**Bắt buộc:** chỉ animate `transform` và `opacity`; mọi motion phải tôn trọng
`prefers-reduced-motion` **và** class `.reduce-motion` sẵn có; cấm
`window.addEventListener('scroll')`, dùng `useScroll` hoặc IntersectionObserver. Marketing
chạy ở cường độ 7, workspace 5, privacy và admin 3.

Việc đầu tiên trong hạng mục này là **xóa 17+ class `animate-in` chết** để không ai tưởng
nhầm là đang có motion.

## Icon style

Giữ `lucide-react`. Với 76 file phụ thuộc, đổi thư viện là rủi ro cao mà lợi ích thị giác
thấp, và skill cho phép giữ khi dự án đã có sẵn. Thay vào đó chuẩn hóa và bổ sung.

- **`strokeWidth: 1.5` toàn cục**, đặt một lần qua wrapper `<Icon>` thay vì rải trên từng
  call site. Riêng icon từ 24px trở lên dùng 1.25.
- **Thang size 4 bậc**: 14 (inline trong text), 16 (mặc định UI), 20 (nav, nút), 24 (header,
  empty state). Bỏ `w-3.5`, `w-8`, `w-10` tùy hứng. Nút close thống nhất 16.
- **Thay 2 PNG brand icon bằng SVG** để đổi màu theo theme và sắc nét trên retina.
- **Đặt làm khoảng 10 glyph riêng** cho các khái niệm cốt lõi mà lucide không diễn tả đúng:
  source verified, source conflict, memory, redaction, capture paused, provenance trail. Đây
  là những chỗ mà icon generic đang làm loãng thông điệp sản phẩm.

## Logo direction

Hiện tại logo là chữ đánh máy: "mond" cộng "ai" đổi màu cộng "y", Manrope 800, cộng một chấm
tròn 8px tùy chọn. Không có mark, đặt inline style, và trò đổi màu chữ "ai" ở giữa từ là một
thủ pháp đã quá quen.

Ba hướng, khuyến nghị hướng B:

**A. Wordmark tinh chỉnh.** Giữ nguyên cấu trúc chữ, bỏ trò đổi màu "ai", vẽ lại chữ ở Geist
weight 600 với tracking âm, xử lý riêng chữ "y". An toàn nhất, ít khác biệt nhất.

**B. Mark bằng chứng (khuyến nghị).** Một glyph hình học rút gọn từ ý niệm "nhiều nguồn hội
tụ thành một kết luận truy vết được": ba nét ngắn lệch nhau chụm vào một điểm neo. Hoạt động
ở 16px trên favicon, hoạt động ở 400px trên marketing, và animate được ở màn chờ đúng lúc hệ
thống đang tổng hợp. Ghép với wordmark Geist chữ thường.

**C. Monogram trong khung.** Chữ "m" trong squircle. Dễ làm, dễ nhận, nhưng chung chung và
không kể được câu chuyện truy vết.

Dù chọn hướng nào cũng cần: bản SVG thật (không phải div), biến thể on-light và on-dark,
favicon (hiện **đang thiếu hoàn toàn**), và OG image. Theo quy ước dự án, đổi logo là material
change nên cần UI/UX Lead duyệt trước khi làm.

## Component cần redesign

Xếp theo tỉ lệ tác động trên rủi ro.

### Tầng nền, chạm là ảnh hưởng toàn bộ

| Mục | Việc |
| --- | --- |
| `index.css` | Thêm block `@theme`, gộp bộ biến legacy trùng lặp, khai báo font, easing, radius, shadow |
| Font loading | Self-host Geist và Geist Mono, bỏ `<link>` chặn render |
| `Icon` wrapper | Component mới bọc lucide, chuẩn hóa stroke và size |
| Page container | Một component container thay cho việc mỗi trang tự đặt padding |

### Primitive, 12 file, tác động lan rộng

`Button` (bổ sung focus ring cho secondary, thêm tertiary và loading, khóa radius), `Card`
(bỏ viền mặc định, giữ `accentBorder`, thêm hover), `Badge` (thống nhất `r-sm`, bỏ variant
purple), `Dialog` và `Drawer` (thêm exit animation, focus trap, khóa scroll body, sửa
transition treo), `LoadingState` (đổi spinner sang skeleton theo hình dáng nội dung),
`EmptyState` (thiết kế lại, có illustration), `Toast`, `CommandPalette`, `MondaiyLogo`,
`BrandIcons`.

### Marketing, viết lại nhiều nhất về visual

Hero (thay fake div UI bằng ảnh thật hoặc ảnh generate, tăng thang chữ, cắt subtext xuống 20
từ, thêm entry motion), section Trust (bỏ dải tối, chuyển sang pastel wash), Features và How
It Works (phá hai hàng 3 card đều nhau, thay bằng bento có nhịp), CTA cuối, `MarketingLayout`
header và footer.

### Workspace, chạm nhẹ và cẩn thận

`Sidebar` và `TopBar` (chiều cao cố định, chuẩn hóa nav, xóa chấm đỏ hardcode),
`BriefingCard` (tầng evidence bằng mono, hover state, stagger), `BriefingSection`,
`ChatMessage`, `NavigatorDrawer`, `SourceReference` (nâng thành khoảnh khắc chữ ký của sản
phẩm).

### Privacy và admin, chỉ chuẩn hóa token

10 trang admin và các component privacy: chỉ ánh xạ lại màu, chữ, radius, bóng theo token
mới. **Không** pastel hóa, **không** thêm motion, **không** đổi mật độ. Đây là bề mặt của sự
tin cậy.

---

# PHẦN 3: KẾ HOẠCH REDESIGN THEO STAGE

Nguyên tắc xuyên suốt: mỗi stage tự nó ship được, không stage nào chạm vào routing, business
logic, hay xóa component. Stage 0 và 1 là bắt buộc trước mọi thứ, vì không có chúng thì mọi
thay đổi visual đều tiếp tục là hex thô.

## Stage 0. Sửa nền móng

Không thay đổi thị giác nào đáng kể. Đây là stage dọn đường.

Thêm block `@theme` vào `index.css` để token thực sự sinh ra utility. Gộp bộ biến legacy
trùng lặp. Self-host Geist và Geist Mono. Xóa 17+ class `animate-in` chết. Cài `motion`. Thêm
favicon và meta tag.

Rủi ro thấp, mở khóa toàn bộ phần còn lại.

**Nghiệm thu:** build sạch, `oxlint` sạch, giao diện trông gần như y hệt trước.

## Stage 1. Token và typography

Ánh xạ 74 hex thô về token ngữ nghĩa. Áp thang typography mới, kéo body từ `text-xs` lên
14px. Khóa hệ radius 4 bậc. Thay toàn bộ shadow bằng 4 bậc tint navy.

Đây là stage tạo ra **cú nhảy thị giác lớn nhất trên mỗi đơn vị rủi ro**. Cần review kỹ vì
chạm nhiều file.

**Nghiệm thu:** không còn hex thô ngoài file token; contrast đạt WCAG AA; kiểm tra cả light
và dark; kiểm tra `.high-contrast` và `.large-text` không vỡ.

## Stage 2. Primitive layer

Redesign 12 component trong `components/ui/` cộng `Icon` wrapper và page container. Sửa focus
ring của `secondary`. Thêm exit animation, focus trap và scroll lock cho Dialog và Drawer.
Đổi loading sang skeleton.

Vì mọi trang đều dùng primitive, stage này nâng toàn app cùng lúc mà không phải sửa từng
trang.

**Nghiệm thu:** đi hết 15 route người dùng và 10 route admin, không có regression; kiểm tra
bàn phím và focus.

## Stage 3. Motion layer

Xây 4 khoảnh khắc chuyển động đã định nghĩa. Đặt easing và duration token. Nối
`prefers-reduced-motion` với `.reduce-motion` sẵn có.

**Nghiệm thu:** mỗi animation giải thích được bằng một câu; bật reduced motion thì mọi thứ về
tĩnh; không có jank trên mobile; không có `window.addEventListener('scroll')`.

## Stage 4. Marketing và auth

Đây là stage biểu đạt cao nhất, và cũng là stage cần asset thật.

Dựng lại hero với ảnh thật thay fake div UI. Phá hai hàng 3 card đều nhau. Bỏ dải tối ở
Trust, chuyển sang pastel wash. Áp nhịp section theo 4 wash. Thêm scroll reveal. Redesign auth
và onboarding.

**Cần chuẩn bị trước:** ảnh hero và 3 đến 4 ảnh section. Không có ảnh thật thì stage này
không nên bắt đầu, vì sẽ lại rơi về div và khối màu phẳng.

**Nghiệm thu:** chạy toàn bộ Pre-Flight Check của taste skill; hero vừa viewport; đếm eyebrow
không vượt trần; tối thiểu 4 layout family.

## Stage 5. Workspace

Áp ngôn ngữ mới vào briefing, tasks, calendar, sources. Nâng `SourceReference` thành khoảnh
khắc chữ ký. Bổ sung tầng evidence bằng mono. Sửa `Sidebar` và `TopBar`.

**Nghiệm thu:** mật độ thông tin không giảm; luồng người dùng không đổi; test trên mobile.

## Stage 6. Privacy, admin, và hoàn thiện

Ánh xạ token cho 10 trang admin và các component privacy, giữ nguyên mật độ. Thống nhất bảng
màu admin về hệ chung. Bổ sung empty, loading, error state còn thiếu. Sửa 4 điểm gãy
responsive dưới 768px. Xóa em-dash khỏi `translations.ts` và 14 file còn lại. Thay 2 PNG bằng
SVG.

**Nghiệm thu:** bảng audit vẫn đọc được và đáng tin; đủ 3 trạng thái ở mọi bề mặt bất đồng
bộ.

---

# Quyết định cần chốt trước khi viết code

Theo quy ước dự án, mấy điểm này không thuộc quyền tự quyết của người thực thi:

**Logo là material change.** Hướng B cần UI/UX Lead duyệt. Nếu chưa duyệt, làm hướng A ở
Stage 2 và để mark lại sau.

**Sidebar chỉ có 5 trong 15 route.** `/briefing`, `/tasks`, `/calendar`, `/settings`,
`/profile`, `/help` không có đường vào từ nav. Đây là lỗi IA có thật, nhưng sửa nav là chạm
vào IA, mà ràng buộc hiện tại là giữ nguyên. Cần PM và UI/UX Lead xác nhận đây là lỗi hay là
chủ ý.

**Asset ảnh cho Stage 4.** Cần biết team tự cung cấp hay để generate.

---

## Phụ lục: Ràng buộc bảo tồn

Những thứ **không được thay đổi** trong toàn bộ quá trình redesign:

- Routing và slug URL (`App.tsx`, 15 route người dùng cộng 10 route admin cộng 4 route auth)
- Business logic và store (`stores/`, `lib/`)
- Tên component hiện có (chỉ sửa nội dung, không xóa)
- Nhãn nav chính và cấu trúc IA
- Tên và thứ tự field trong form
- Giọng văn copy hiện tại (đang tốt, chỉ sửa lỗi em-dash và độ dài hero subtext)
- Hệ `accentBorder` của `Card` (quyết định thông tin đúng, giữ nguyên ngữ nghĩa)
- Class `.reduce-motion`, `.high-contrast`, `.large-text` trong `index.css`
