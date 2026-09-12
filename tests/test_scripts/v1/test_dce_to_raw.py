import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "dce_to_raw",
    Path(__file__).resolve().parents[3] / "scripts" / "discord" / "dce_to_raw.py",
)
dce_to_raw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dce_to_raw)


def _author(name="ducdnghanam", nickname="T004 - Nguyễn Đức Dũng - 01823", bot=False):
    return {
        "id": "1138449718255550484",
        "name": name,
        "discriminator": "0000",
        "nickname": nickname,
        "color": "#1abc9c",
        "isBot": bot,
        "roles": [{"id": "9", "name": "Học viên", "color": "#1abc9c", "position": 3}],
        "avatarUrl": "https://cdn.discordapp.com/avatars/1138449718255550484/83ac5cd2a61.png?size=512",
    }


def _export(messages, channel_kind="GuildTextChat"):
    return {
        "guild": {"id": "1534384336567275551", "name": "AI20K", "iconUrl": None},
        "channel": {
            "id": "1534384337028382793",
            "type": channel_kind,
            "categoryId": "1534384337028382792",
            "category": "CỘNG ĐỒNG",
            "name": "chung",
            "topic": None,
        },
        "dateRange": {"after": None, "before": None},
        "exportedAt": "2026-08-06T10:00:00+07:00",
        "messages": messages,
        "messageCount": len(messages),
    }


def _message(**kwargs):
    base = {
        "id": "1534404521734967316",
        "type": "Default",
        "timestamp": "2026-08-05T10:35:45.839+07:00",
        "timestampEdited": None,
        "callEndedTimestamp": None,
        "isPinned": False,
        "content": "chào mọi người",
        "author": _author(),
        "attachments": [],
        "embeds": [],
        "stickers": [],
        "reactions": [],
        "mentions": [],
        "inlineEmojis": [],
    }
    return {**base, **kwargs}


def test_channel_and_message_kind_map_to_int():
    out = dce_to_raw.to_discord_raw(_export([_message(), _message(id="2", type="GuildMemberJoin")]))
    assert out["channel"]["type"] == 0
    assert {m["type"] for m in out["messages"]} == {0, 7}
    assert out["channel"]["guild_id"] == "1534384336567275551"
    assert out["channel"]["parent_id"] == "1534384337028382792"


def test_thread_parent_id_points_to_parent_channel():
    export = _export([_message()], channel_kind="GuildPublicThread")
    # Với thread, DCE ghi kênh cha vào `categoryId` chứ không phải category.
    export["channel"]["categoryId"] = "1527920232587333724"
    export["channel"]["category"] = "🙋-hỏi-đáp"

    out = dce_to_raw.to_discord_raw(export)

    assert out["channel"]["type"] == 11
    assert out["_dce"]["is_thread"] is True
    assert out["channel"]["parent_id"] == "1527920232587333724"
    assert out["_dce"]["warnings"] == []


def test_unknown_kind_warns_instead_of_raising():
    out = dce_to_raw.to_discord_raw(_export([_message(type="SomethingNew")]))
    assert out["messages"][0]["type"] is None
    assert any("SomethingNew" in w for w in out["_dce"]["warnings"])


def test_timestamps_to_utc_newest_first():
    out = dce_to_raw.to_discord_raw(
        _export(
            [
                _message(id="1", timestamp="2026-08-05T10:00:00+07:00"),
                _message(id="2", timestamp="2026-08-05T11:00:00+07:00"),
            ]
        )
    )
    # DCE ghi cũ trước, API trả mới trước.
    assert [m["id"] for m in out["messages"]] == ["2", "1"]
    assert out["messages"][1]["timestamp"] == "2026-08-05T03:00:00+00:00"
    assert out["channel"]["last_message_id"] == "2"


def test_author_keeps_nickname_and_roles_in_sidecar():
    author = dce_to_raw.to_discord_raw(_export([_message()]))["messages"][0]["author"]
    assert author["username"] == "ducdnghanam"
    assert author["global_name"] == "T004 - Nguyễn Đức Dũng - 01823"
    assert author["avatar"] == "83ac5cd2a61"
    assert author["_dce"]["roles"][0]["name"] == "Học viên"
    assert author["_dce"]["nickname"] == "T004 - Nguyễn Đức Dũng - 01823"


def test_default_avatar_has_no_hash():
    raw = _author()
    raw["avatarUrl"] = "https://cdn.discordapp.com/embed/avatars/3.png"
    assert dce_to_raw.to_author(raw)["avatar"] is None


def test_reply_becomes_message_reference():
    out = dce_to_raw.to_discord_raw(
        _export(
            [
                _message(
                    type="Reply",
                    reference={
                        "type": 0,
                        "messageId": "111",
                        "channelId": "222",
                        "guildId": "333",
                    },
                )
            ]
        )
    )
    message = out["messages"][0]
    assert message["type"] == 19
    assert message["message_reference"] == {
        "message_id": "111",
        "channel_id": "222",
        "guild_id": "333",
    }
    # DCE không lồng nội dung tin được trả lời, phải join lại theo id.
    assert message["referenced_message"] is None


def test_mention_roles_and_everyone_derived_from_content():
    out = dce_to_raw.to_discord_raw(_export([_message(content="<@&555> <@&666> nhắc @everyone nộp bài <@777>")]))
    message = out["messages"][0]
    assert message["mention_roles"] == ["555", "666"]
    assert message["mention_everyone"] is True


def test_plain_content_fabricates_no_mentions():
    message = dce_to_raw.to_discord_raw(_export([_message(content="chào")]))["messages"][0]
    assert message["mention_roles"] == []
    assert message["mention_everyone"] is False


def test_reaction_keeps_users_in_sidecar():
    out = dce_to_raw.to_discord_raw(
        _export(
            [
                _message(
                    reactions=[
                        {
                            "emoji": {
                                "id": "888",
                                "name": "kekw",
                                "code": ":kekw:",
                                "isAnimated": True,
                                "imageUrl": "https://x/y.gif",
                            },
                            "count": 2,
                            "users": [_author(name="a"), _author(name="b")],
                        }
                    ]
                )
            ]
        )
    )
    reaction = out["messages"][0]["reactions"][0]
    assert reaction["count"] == 2
    assert reaction["emoji"] == {"id": "888", "name": "kekw", "animated": True}
    assert len(reaction["_dce"]["users"]) == 2


def test_embed_footer_name_to_text_and_color_to_int():
    out = dce_to_raw.to_discord_raw(
        _export(
            [
                _message(
                    embeds=[
                        {
                            "title": "Deadline",
                            "description": "nộp trước 23h",
                            "url": None,
                            "timestamp": None,
                            "color": "#ff0000",
                            "author": None,
                            "thumbnail": None,
                            "image": {"url": "https://x/i.png", "width": 10, "height": 20},
                            "video": None,
                            "footer": {"name": "ban tổ chức", "url": None, "iconUrl": None},
                            "images": [{"url": "https://x/i.png"}],
                            "fields": [{"name": "Hạn", "value": "06/08", "isInline": True}],
                            "inlineEmojis": [],
                        }
                    ]
                )
            ]
        )
    )
    embed = out["messages"][0]["embeds"][0]
    assert embed["color"] == 0xFF0000
    assert embed["footer"] == {"text": "ban tổ chức", "icon_url": None}
    assert embed["image"] == {"url": "https://x/i.png", "width": 10, "height": 20}
    assert embed["fields"][0] == {"name": "Hạn", "value": "06/08", "inline": True}
    assert embed["_dce"]["images"] == [{"url": "https://x/i.png"}]


def test_attachment_uses_api_keys_and_proxy_url():
    out = dce_to_raw.to_discord_raw(
        _export(
            [
                _message(
                    attachments=[
                        {
                            "id": "999",
                            "url": "https://cdn.discordapp.com/attachments/1/2/bai.pdf",
                            "fileName": "bai.pdf",
                            "fileSizeBytes": 1234,
                        }
                    ]
                )
            ]
        )
    )
    attachment = out["messages"][0]["attachments"][0]
    assert attachment["filename"] == "bai.pdf"
    assert attachment["size"] == 1234
    assert attachment["proxy_url"] == "https://media.discordapp.net/attachments/1/2/bai.pdf"


def test_stripping_sidecar_leaves_exact_api_keys():
    message = dce_to_raw.to_discord_raw(_export([_message()]))["messages"][0]
    con_lai = set(message) - {"_dce"}
    assert con_lai == {
        "id",
        "type",
        "channel_id",
        "guild_id",
        "author",
        "content",
        "timestamp",
        "edited_timestamp",
        "attachments",
        "embeds",
        "reactions",
        "sticker_items",
        "mentions",
        "mention_roles",
        "mention_everyone",
        "pinned",
        "tts",
        "flags",
        "components",
        "message_reference",
        "referenced_message",
    }


def test_convert_file_emits_manifest_row(tmp_path):
    src = tmp_path / "chung_123.json"
    src.write_text(json.dumps(_export([_message()])), encoding="utf-8")
    dst = tmp_path / "ra" / "chung_123.json"

    row = dce_to_raw.convert_file(src, dst)

    assert dst.exists()
    assert row["message_count"] == 1
    assert row["channel_id"] == "1534384337028382793"
    assert row["channel_name"] == "chung"
    assert len(row["source_sha256"]) == 64
    assert len(row["output_sha256"]) == 64
