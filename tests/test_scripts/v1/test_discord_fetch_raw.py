import asyncio
import importlib.util
import json
from pathlib import Path

import httpx

_spec = importlib.util.spec_from_file_location(
    "discord_fetch_raw",
    Path(__file__).resolve().parents[3] / "scripts" / "discord_fetch_raw.py",
)
discord_fetch_raw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(discord_fetch_raw)


def _fake_discord(total: int, rate_limit_once: bool = False):
    """Giả lập kênh có `total` tin, phân trang theo `before` giống Discord thật."""
    ids = [str(1000 + i) for i in range(total)][::-1]
    state = {"limited": not rate_limit_once}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/messages"):
            if not state["limited"]:
                state["limited"] = True
                return httpx.Response(429, headers={"retry-after": "0"}, json={})
            limit = int(request.url.params["limit"])
            before = request.url.params.get("before")
            start = ids.index(before) + 1 if before else 0
            page = ids[start : start + limit]
            return httpx.Response(200, json=[{"id": i, "content": "x"} for i in page])
        return httpx.Response(200, json={"id": "c1", "name": "mau", "guild_id": "g1"})

    return httpx.MockTransport(handler)


def _run(total, max_messages, rate_limit_once=False):
    return asyncio.run(
        discord_fetch_raw.fetch_channel_raw(
            "c1", "token", max_messages, transport=_fake_discord(total, rate_limit_once)
        )
    )


def test_lay_het_nhieu_trang_khong_trung_khong_sot():
    data = _run(total=250, max_messages=1000)
    ids = [m["id"] for m in data["messages"]]
    assert len(ids) == 250
    assert len(set(ids)) == 250
    assert data["channel"]["guild_id"] == "g1"


def test_dung_dung_o_max_messages():
    assert len(_run(total=250, max_messages=120)["messages"]) == 120


def test_kenh_rong():
    assert _run(total=0, max_messages=100)["messages"] == []


def test_gap_429_thi_cho_roi_thu_lai():
    assert len(_run(total=10, max_messages=100, rate_limit_once=True)["messages"]) == 10


def test_chi_bao_thieu_content_voi_tin_that():
    thieu = discord_fetch_raw.thieu_content
    assert thieu({"type": 0, "content": "", "attachments": [], "embeds": []}) is True
    assert thieu({"type": 19, "content": "", "attachments": [], "embeds": []}) is True
    # tin hệ thống "đã tham gia server" vốn không có chữ
    assert thieu({"type": 7, "content": "", "attachments": [], "embeds": []}) is False
    # tin chỉ gửi ảnh cũng không có chữ
    assert thieu({"type": 0, "content": "", "attachments": [{"id": "1"}], "embeds": []}) is False
    assert thieu({"type": 0, "content": "chào", "attachments": [], "embeds": []}) is False


def test_giu_nguyen_payload_khong_chuan_hoa():
    data = _run(total=1, max_messages=100)
    assert json.loads(json.dumps(data["messages"][0])) == {"id": "1000", "content": "x"}
