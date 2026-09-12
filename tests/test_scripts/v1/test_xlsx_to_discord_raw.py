import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "xlsx_to_discord_raw",
    Path(__file__).resolve().parents[3] / "scripts" / "xlsx_to_discord_raw.py",
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

CDN = "https://cdn.discordapp.com/attachments/1530052915383894107/1530052915568316467/qr.png?ex=6a6c1552&is=6a6ac3d2&hm=57e7"

ROWS = [
    {"Author": "lamnd.ai", "Date": "46225.882557083336", "Content": "xin chào", "Attachments": "", "Reactions": ""},
    {
        "Author": "tranhoangha94",
        "Date": "46227.433356898146",
        "Content": "gửi QR",
        "Attachments": CDN,
        "Reactions": "⬆️ (4),💯 (1)",
    },
    {"Author": "Trợ lý Kute#3191", "Date": "46227.5", "Content": "Chào bạn nha", "Attachments": "", "Reactions": ""},
]


def test_moi_channel_id_tu_url_attachment():
    data = mod.to_discord_raw(ROWS, "mau")
    assert data["channel"]["id"] == "1530052915383894107"
    assert all(m["channel_id"] == "1530052915383894107" for m in data["messages"])


def test_export_nhieu_kenh_thi_uu_tien_kenh_cua_chinh_tin_do():
    khac = CDN.replace("1530052915383894107", "9990000000000000000")
    rows = ROWS + [dict(ROWS[1], Attachments=khac), dict(ROWS[1], Attachments=khac)]
    data = mod.to_discord_raw(rows, "mau")
    theo_kenh = {m["channel_id"] for m in data["messages"] if m["attachments"]}
    assert theo_kenh == {"1530052915383894107", "9990000000000000000"}
    # kênh hay gặp nhất làm mặc định cho tin không có attachment
    assert data["channel"]["id"] == "9990000000000000000"
    assert len(data["channel_ids_seen"]) == 2


def test_id_tang_dan_theo_thoi_gian_va_khong_trung():
    data = mod.to_discord_raw(ROWS, "mau")
    ids = [int(m["id"]) for m in data["messages"]]
    assert ids == sorted(ids, reverse=True), "API trả tin mới nhất trước"
    assert len(set(ids)) == len(ids)


def test_cung_ten_thi_cung_author_id():
    rows = ROWS + [dict(ROWS[0], Content="lần hai")]
    ids = {m["author"]["username"]: m["author"]["id"] for m in mod.to_discord_raw(rows, "mau")["messages"]}
    assert ids["lamnd.ai"] == mod.fake_author_id("lamnd.ai")
    assert len(ids) == 3


def test_doi_serial_excel_sang_utc_co_timezone():
    tin = mod.to_discord_raw(ROWS[:1], "mau")["messages"][0]
    assert tin["timestamp"] == "2026-07-22T14:10:52.932000+00:00"


def test_tach_reaction_ke_ca_emoji_tuy_chinh():
    reactions = mod.parse_reactions("😆 (2),🤣 (1),adorovibe (2)")
    assert [(r["emoji"]["name"], r["count"]) for r in reactions] == [("😆", 2), ("🤣", 1), ("adorovibe", 2)]


def test_attachment_bo_chu_ky_cdn():
    att = mod.parse_attachments(CDN)[0]
    assert "?" not in att["url"]
    assert att["id"] == "1530052915568316467"
    assert att["filename"] == "qr.png"


def test_nhan_dien_bot_qua_discriminator():
    bots = {m["author"]["username"]: m["author"]["bot"] for m in mod.to_discord_raw(ROWS, "mau")["messages"]}
    assert bots["Trợ lý Kute"] is True
    assert bots["lamnd.ai"] is False


def test_bo_qua_dong_khong_co_tac_gia():
    rows = ROWS + [{"Author": "", "Date": "46227.9", "Content": "rác", "Attachments": "", "Reactions": ""}]
    assert len(mod.to_discord_raw(rows, "mau")["messages"]) == 3
