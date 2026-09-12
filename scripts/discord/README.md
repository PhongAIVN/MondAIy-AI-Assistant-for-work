# Cào Discord bằng DiscordChatExporter

Dùng khi không add được bot vào server — kênh của ban tổ chức là trường hợp đó.
DCE đọc bằng chính tài khoản của bạn nên thấy đúng những kênh bạn thấy.

Hai bước tách rời: **cào** ra kho raw, rồi **chuẩn hóa** sang shape Discord API.
Tách ra để sửa logic chuẩn hóa xong chạy lại được mà không phải cào lại.

```
export_dce.py   ──>  data/discord/raw/<run_id>/*.json      (DCE nguyên bản + _run.json)
dce_to_raw.py   ──>  data/discord/normalized/<run_id>/*.json  (shape API + _manifest.json)
```

## Cài DCE

Máy này **đã cài rồi**, bản `v2.47.3` (`osx-arm64`) ở `~/tools/dce`:

```bash
export DCE_CMD=~/tools/dce/DiscordChatExporter.Cli
```

Cài lại từ đầu (brew không có formula cho DCE nên phải tải bản dựng sẵn):

```bash
mkdir -p ~/tools/dce && cd ~/tools/dce
curl -L -o dce.zip https://github.com/Tyrrrz/DiscordChatExporter/releases/latest/download/DiscordChatExporter.Cli.osx-arm64.zip
unzip -o dce.zip && rm dce.zip
chmod +x DiscordChatExporter.Cli
find . -type f -exec xattr -d com.apple.quarantine {} \; 2>/dev/null
./DiscordChatExporter.Cli --version
```

Bước `xattr` là để macOS Gatekeeper không giết tiến trình. Bỏ qua nó thì lệnh
chạy im lặng rồi thoát với mã 137 (SIGKILL), không in lỗi gì. Phải gỡ cờ trên
**mọi file** trong thư mục chứ không riêng file thực thi — các `.dylib` đi kèm
cũng bị chặn. `xattr` của macOS này không có cờ `-r` nên phải đi qua `find`.
Nếu vẫn bị chặn thì vào System Settings > Privacy & Security bấm "Open Anyway".

Rồi trỏ script tới nó:

```bash
export DCE_CMD=~/tools/dce/DiscordChatExporter.Cli
```

Muốn khỏi gõ lại mỗi lần thì thêm dòng đó vào `~/.zshrc`.

## Lấy token

DCE cần **user token** của tài khoản bạn, không phải bot token. `DISCORD_BOT_TOKEN`
trong `.env` là của việc khác, đừng dùng nhầm.

1. Mở Discord trên trình duyệt, đăng nhập.
2. `F12` mở DevTools > tab **Network**.
3. Bấm vào một kênh bất kỳ để có request mới.
4. Chọn một request tới `discord.com/api`, xem **Headers > Request Headers**,
   copy giá trị của `authorization`.

```bash
export DISCORD_TOKEN='<token vừa copy>'
```

Vài điều nên biết trước khi làm:

- Token này mở khóa **toàn bộ tài khoản** của bạn. Đừng dán vào chat, đừng commit,
  đừng đưa cho ai. Script cố tình truyền token qua biến môi trường chứ không qua
  tham số dòng lệnh để nó không lọt vào `ps` hay history.
- Token đổi mỗi lần bạn đổi mật khẩu hoặc đăng xuất — hết hạn thì lấy lại.
- Discord không cho phép tự động hóa tài khoản người dùng. Việc này chỉ đọc đúng
  những kênh bạn đã có quyền đọc, và rủi ro là của tài khoản bạn. Cào một lần
  cho gọn, đừng dựng cron chạy liên tục.

## Khai báo kênh cần cào

```bash
cp scripts/discord/channels.example.json scripts/discord/channels.json
```

Sửa `channels.json`, điền channel id thật. Có hai cách lấy id.

**Cách nhanh — để DCE liệt kê hộ.** Cần token trước (mục trên):

```bash
$DCE_CMD guilds                                    # ra id của các server
$DCE_CMD channels -g <guild_id> --include-vc false # ra id mọi kênh text
```

Lệnh thứ hai in ra từng dòng gồm id kèm tên kênh và category — copy thẳng vào
`channels.json`. Nhanh hơn hẳn khi server có vài chục kênh như của ban tổ chức.

**Cách thủ công — khi chưa có token.** Discord > Settings > Advanced > bật
**Developer Mode**, rồi chuột phải vào kênh > **Copy Channel ID**.

Mẹo: `--channel` của DCE **nhận cả category id**, và sẽ cào mọi kênh trong
category đó. Muốn lấy trọn một mảng (ví dụ cả nhóm "CỘNG ĐỒNG") thì chuột phải
vào **tên category** thay vì vào từng kênh. Đổi lại là kênh mới thêm về sau cũng
tự lọt vào — tiện hay không thì tùy bạn muốn phạm vi cố định hay co giãn.

`channels.json` đã bị `.gitignore` chặn vì nó lộ cấu trúc server ban tổ chức.
Sau này muốn thêm kênh nhỏ khác thì chỉ thêm một dòng vào đây, không sửa script.

## Chạy

```bash
python scripts/discord/export_dce.py -c scripts/discord/channels.json --dry-run   # xem lệnh trước
python scripts/discord/export_dce.py -c scripts/discord/channels.json             # cào thật
python scripts/discord/dce_to_raw.py data/discord/raw/<run_id>                    # chuẩn hóa
```

Lần sau chỉ lấy tin mới:

```bash
python scripts/discord/export_dce.py -c scripts/discord/channels.json --incremental
```

`--incremental` đọc `last_message_id` của từng kênh, **gộp qua mọi run đã chuẩn
hóa** rồi truyền `--after` cho DCE. Gộp chứ không lấy mỗi run cuối, vì run tăng
dần chỉ chứa tin mới: kênh nào không ai nhắn trong lần cào trước sẽ có
`last_message_id` là `null` ở manifest đó, nhìn mỗi run cuối là mất con trỏ và
lần sau cào lại kênh đó từ đầu.

Muốn giới hạn tay thì dùng `--after` / `--before`, nhận cả ngày (`2026-08-01`)
lẫn message id. `--after` truyền tay đè lên con trỏ tự động.

## Cào tiếp rồi nạp thẳng vào kho, một lệnh

Bốn bước trên (cào, chuẩn hóa, chunk, nạp DB) gõ tay mỗi lần thì dễ quên một
bước và dễ nhầm `run_id`. `sync.py` gọi lại đúng bốn script đó theo thứ tự:

```bash
export DISCORD_TOKEN='<user token>'
export DCE_CMD=~/tools/dce/DiscordChatExporter.Cli

python scripts/discord/sync.py --dry-run    # xem sẽ chạy lệnh gì
python scripts/discord/sync.py              # cào tiếp phần mới rồi nạp
python scripts/discord/sync.py --embed      # nạp xong nhúng vector luôn
```

Mặc định là tăng dần và đọc `scripts/discord/channels.json`. Vài cờ đáng nhớ:

| Cờ | Dùng khi |
| --- | --- |
| `--full` | Cào lại toàn bộ lịch sử thay vì phần mới |
| `--embed` | Nhúng vector sau khi nạp; bỏ qua thì FTS vẫn chạy |
| `--skip-export --run-id <id>` | Chạy lại phần xử lý trên một run đã cào xong |
| `--dry-run` | Chỉ in các lệnh, không chạy |

Không kênh nào có tin mới thì DCE không ghi file nào, sync in "Không có tin mới"
rồi thoát với mã 0 — đó là trạng thái bình thường, không phải lỗi. Hỏng ở bước
nào thì sync dừng ngay tại đó và in mã thoát; chạy lại đúng script đó với
`run_id` in ở dòng đầu, không phải cào lại từ đầu.

Sync không dựng cron sẵn. Discord không cho phép tự động hóa tài khoản người
dùng, nên chạy tay theo nhịp của chương trình chứ đừng để chạy liên tục.

Kênh mới thêm vào server không tự lọt vào trừ khi `channels.json` khai bằng
**category id** — DCE cào mọi kênh trong category đó, kể cả kênh thêm sau.

Mặc định **không** tải file đính kèm, chỉ giữ URL. Thêm `--media` nếu cần, nhưng
liệu dung lượng trước.

## Kho dữ liệu

```
data/discord/
├── raw/<run_id>/           DCE nguyên bản, không sửa gì — đây là bản gốc để đối chiếu
│   ├── <tên kênh>_<id>.json
│   └── _run.json           chạy lệnh gì, bản DCE nào, kênh nào lỗi
└── normalized/<run_id>/    shape Discord API
    ├── <tên kênh>_<id>.json
    └── _manifest.json      số tin, mốc đầu/cuối, last_message_id, sha256, cảnh báo
```

`run_id` là giờ UTC lúc chạy. Mỗi lần cào là một run mới, không đè lên run cũ,
nên luôn quay lại được bản trước và so được hai lần cào. `data/` bị `.gitignore`
chặn toàn bộ — đây là chat thật của người thật, không commit.

`_manifest.json` có sha256 của cả file nguồn lẫn file đích, đủ để biết bản chuẩn
hóa nào sinh ra từ bản raw nào.

## Định dạng đầu ra

Giống `scripts/discord_fetch_raw.py` (bản kéo bằng bot) để pipeline phía sau
không cần biết dữ liệu tới từ đâu: tin xếp mới nhất trước, thời gian quy về UTC,
`type` là số chứ không phải chữ.

Những gì DCE có mà Discord API không có chỗ chứa nằm dưới khóa `_dce`. **Bỏ mọi
khóa `_dce` đi là còn đúng payload API.** Đáng chú ý nhất là `author._dce.roles`
— role của người gửi ngay tại thời điểm cào, biết ai là mentor ai là học viên mà
không phải đoán qua tên hiển thị. Bot API không trả cái này.

### Bốn chỗ không lấy được nguyên bản

Đều ghi trong `_dce.derived` của mỗi file:

| Trường | Cách xử lý |
| --- | --- |
| `mention_roles` | Suy từ `<@&id>` trong nội dung, DCE không tách riêng |
| `mention_everyone` | Suy từ chuỗi `@everyone` / `@here` trong nội dung |
| `referenced_message` | Luôn `None`; join theo `message_reference.message_id` |
| `author.avatar` | Moi từ URL CDN; ai để avatar mặc định thì `None` |

### `global_name` không hẳn là global name

DCE gộp **nickname riêng trong server** và **display name toàn cục** vào chung
một trường `nickname`. Tên kiểu `T004 - Nguyễn Đức Dũng - 01823` nhiều khả năng
là nickname bắt buộc của server chứ không phải global name thật của tài khoản.

Script đặt nó vào `global_name` để pipeline chạy y như với dữ liệu bot, và giữ
bản gốc ở `author._dce.nickname`. Nếu sau này cần phân biệt hai thứ đó, dữ liệu
vẫn còn — nhưng đừng khẳng định `global_name` từ DCE là global name thật.

### `--markdown false` là bắt buộc

Mặc định DCE viết lại `<@123>` thành `@username` ngay trong JSON, làm content
khác hẳn bot trả về và mất token để suy ra `mention_roles`. `export_dce.py` luôn
truyền `--markdown false`. Cào tay bằng DCE thì nhớ tự thêm.

### Thread

DCE mặc định **bỏ qua thread** (`--include-threads None`), nên `export_dce.py`
luôn truyền `all`. Cào tay thì nhớ tự thêm. Mỗi thread ra một file riêng với
`channel.type` là 11 (public) hoặc 12 (private).

`parent_id` lấy từ `categoryId` của DCE. Tên trường dễ gây hiểu lầm: DCE đặt tên
đó từ thời chưa có thread, nhưng thứ nó ghi là `Channel.Parent` — category với
kênh thường, **kênh cha** với thread. Trùng đúng ngữ nghĩa `parent_id` của
Discord API nên map thẳng, không cần xử lý riêng cho thread.

Tên file đặt theo `%C_%c` (tên kênh + channel id). Với thread, `%c` là id của
chính thread chứ không phải của forum cha, nên nhiều thread trong cùng một forum
không ghi đè lên nhau.

## Liên quan

- `scripts/discord_fetch_raw.py` — kéo bằng bot token, dùng cho server tự tạo.
- `scripts/xlsx_to_discord_raw.py` — bản cũ đọc xlsx của DCE. **Đã bị thay thế.**
  xlsx chỉ có 6 cột nên phải bịa message id, bịa author id và đoán múi giờ. Bản
  JSON không phải đoán chỗ nào. Chỉ giữ lại để đọc được đống dữ liệu đã cào
  trước đó trong `data/discord/Crawl_*.json`.
