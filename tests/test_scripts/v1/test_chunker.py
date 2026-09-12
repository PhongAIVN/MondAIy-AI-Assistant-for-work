import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "chunker",
    Path(__file__).resolve().parents[3] / "scripts" / "discord" / "chunker.py",
)
chunker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chunker)


def _msg(mid, content, ts, reply=None, kind=0, bot=False, name="T004 - Người A"):
    return {
        "id": mid,
        "type": kind,
        "content": content,
        "timestamp": ts,
        "edited_timestamp": None,
        "attachments": [],
        "message_reference": {"message_id": reply} if reply else None,
        "author": {
            "id": "u1",
            "username": "nguoia",
            "global_name": name,
            "bot": bot,
            "_dce": {"roles": [{"name": "Learner"}]},
        },
    }


def _channel(msgs, kind=0, name="chung"):
    return {
        "channel": {
            "id": "111",
            "name": name,
            "type": kind,
            "guild_id": "999",
            "parent_id": "222",
        },
        "fetched_at": "2026-08-07T00:00:00+00:00",
        "messages": msgs,
    }


def test_drops_bot_and_system_messages():
    msgs = [
        _msg("1", "tin thật của người", "2026-08-01T10:00:00+00:00"),
        _msg("2", "tin của bot", "2026-08-01T10:01:00+00:00", bot=True),
        _msg("3", "ai đó vào server", "2026-08-01T10:02:00+00:00", kind=7),
        _msg("4", "", "2026-08-01T10:03:00+00:00"),
    ]
    chunks, stats = chunker.chunk_channel(_channel(msgs))
    assert stats["messages_total"] == 4
    assert stats["messages_kept"] == 1
    assert sum(c["message_count"] for c in chunks) == 1


def test_thread_grouped_one_session_per_day():
    msgs = [
        _msg(str(i), f"nội dung {i}", f"2026-08-0{d}T0{h}:00:00+00:00")
        for i, (d, h) in enumerate([(1, 2), (1, 3), (2, 2), (2, 3)], start=1)
    ]
    msgs += [_msg(str(100 + i), f"thêm {i}", "2026-08-01T05:00:00+00:00") for i in range(200)]
    chunks, stats = chunker.chunk_channel(_channel(msgs, kind=11, name="Lab-E403"))
    assert stats["mode"] == "session"
    # Giờ địa phương lệch +7 nên mốc 02:00 UTC vẫn rơi vào cùng ngày dương lịch.
    assert len({c["group_key"] for c in chunks}) >= 2


def test_small_channel_grouped_whole():
    msgs = [_msg(str(i), f"tin {i}", "2026-08-01T10:00:00+00:00") for i in range(10)]
    chunks, stats = chunker.chunk_channel(_channel(msgs))
    assert stats["mode"] == "whole"
    assert all(c["group_key"] == "whole_channel" for c in chunks)


def test_thread_mode_keeps_reply_chain_drops_short_orphans():
    dai = "x" * 80
    msgs = [_msg("1", "câu hỏi gốc", "2026-08-01T10:00:00+00:00")]
    msgs.append(_msg("2", "trả lời", "2026-08-01T10:01:00+00:00", reply="1"))
    msgs.append(_msg("3", "ok", "2026-08-01T11:00:00+00:00"))
    msgs.append(_msg("4", dai, "2026-08-01T12:00:00+00:00"))
    msgs += [
        _msg(str(10 + i), f"lấp chỗ {i} " + dai, f"2026-08-02T{i // 60:02d}:{i % 60:02d}:00+00:00") for i in range(200)
    ]

    chunks, stats = chunker.chunk_channel(_channel(msgs))
    assert stats["mode"] == "thread"
    ids = {i for c in chunks for i in c["message_ids"]}
    # Mạch reply phải còn nguyên cả cặp.
    assert {"1", "2"} <= ids
    # Tin lẻ đủ dài đứng riêng, tin lẻ "ok" bị loại khỏi index.
    assert "4" in ids
    assert "3" not in ids
    assert stats["orphans_dropped"] >= 1


def test_packing_respects_char_budget():
    dai = "y" * 500
    msgs = [_msg(str(i), dai, f"2026-08-01T10:{i:02d}:00+00:00") for i in range(10)]
    chunks, _ = chunker.chunk_channel(_channel(msgs))
    assert len(chunks) > 1
    for c in chunks:
        assert c["char_count"] <= chunker.CHAR_BUDGET


def test_render_keeps_speaker_and_deep_link():
    msgs = [_msg("1", "xin chào", "2026-08-01T10:00:00+00:00", name="Lab Coach - A")]
    chunks, _ = chunker.chunk_channel(_channel(msgs))
    c = chunks[0]
    assert "Lab Coach - A: xin chào" in c["text"]
    assert c["deep_link"].endswith("/999/111/1")
    assert c["authors"][0]["roles"] == ["Learner"]
