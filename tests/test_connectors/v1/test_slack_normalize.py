from src.connectors.base import Source
from src.connectors.slack import SlackConnector


class _FakeConnection:
    def __init__(
        self,
        provider_user_id: str,
        account_label: str | None = "mondaiy",
        external_site_id: str | None = "T0MONDAIY",
    ) -> None:
        self.provider_user_id = provider_user_id
        self.account_label = account_label
        self.external_site_id = external_site_id


def _connector(
    provider_user_id: str, account_label: str | None = "mondaiy", external_site_id: str | None = "T0MONDAIY"
) -> SlackConnector:
    return SlackConnector(_FakeConnection(provider_user_id, account_label, external_site_id), db=None)


def _synthetic_message(
    *,
    ts: str = "1755230400.000100",
    channel: str = "D0MENTOR01",
    channel_type: str = "im",
    user: str | None = "U_MENTOR",
    text: str = "<@U0PHONG01> nhớ nộp báo cáo trước thứ Sáu",
    parsed_text: str | None = None,
    thread_ts: str | None = None,
    subtype: str | None = None,
    reactions: list[dict] | None = None,
) -> dict:
    return {
        "type": "message",
        "subtype": subtype,
        "ts": ts,
        "channel": channel,
        "_channel_type": channel_type,
        "user": user,
        "text": text,
        "_parsed_text": parsed_text if parsed_text is not None else text,
        "_author_name": "Mentor Name" if user else "",
        "thread_ts": thread_ts,
        "reactions": reactions or [],
    }


def test_normalize_produces_shared_contract_fields():
    connector = _connector("U0PHONG01")
    raw = _synthetic_message(parsed_text="@Phong nhớ nộp báo cáo trước thứ Sáu")
    source = Source(id="D0MENTOR01", name="DM · Mentor Name")

    result = connector.normalize(raw, source)

    assert result["provider"] == "slack"
    assert result["id"] == "D0MENTOR01:1755230400.000100"
    assert result["text"] == "@Phong nhớ nộp báo cáo trước thứ Sáu"
    assert result["author_id"] == "U_MENTOR"
    assert result["author_name"] == "Mentor Name"
    assert result["is_dm"] is True
    assert result["capture_mode"] == "slack_api"


def test_normalize_thread_id_falls_back_to_ts_when_no_thread():
    connector = _connector("U0PHONG01")
    raw = _synthetic_message(ts="123.456", thread_ts=None)
    source = Source(id="D0MENTOR01", name="DM")

    result = connector.normalize(raw, source)

    assert result["thread_id"] == "123.456"
    assert result["has_thread_change"] is False


def test_normalize_thread_id_uses_thread_ts_for_replies():
    connector = _connector("U0PHONG01")
    raw = _synthetic_message(ts="123.789", thread_ts="123.456")
    source = Source(id="D0MENTOR01", name="DM")

    result = connector.normalize(raw, source)

    assert result["thread_id"] == "123.456"
    assert result["has_thread_change"] is True


def test_normalize_mentions_current_user_true_when_raw_text_has_mention():
    connector = _connector("U0PHONG01")
    raw = _synthetic_message(text="<@U0PHONG01> vui lòng xác nhận")
    source = Source(id="D0MENTOR01", name="DM")

    result = connector.normalize(raw, source)

    assert result["slack_mentions_current_user"] is True


def test_normalize_mentions_current_user_false_when_different_user_mentioned():
    connector = _connector("U0PHONG01")
    raw = _synthetic_message(text="<@U_OTHER> vui lòng xác nhận")
    source = Source(id="D0MENTOR01", name="DM")

    result = connector.normalize(raw, source)

    assert result["slack_mentions_current_user"] is False


def test_normalize_is_self_true_when_author_matches_connection():
    connector = _connector("U0PHONG01")
    raw = _synthetic_message(user="U0PHONG01")
    source = Source(id="C0GENERAL", name="#general")

    result = connector.normalize(raw, source)

    assert result["is_self"] is True


def test_normalize_is_self_false_when_author_differs():
    connector = _connector("U0PHONG01")
    raw = _synthetic_message(user="U_OTHER")
    source = Source(id="C0GENERAL", name="#general")

    result = connector.normalize(raw, source)

    assert result["is_self"] is False


def test_normalize_exposes_structured_fields_for_rule_engine():
    connector = _connector("U0PHONG01")
    raw = _synthetic_message(
        channel="C0GENERAL", channel_type="public_channel", subtype="bot_message", reactions=[{"name": "question"}]
    )
    source = Source(id="C0GENERAL", name="#general")

    result = connector.normalize(raw, source)

    assert result["slack_channel_id"] == "C0GENERAL"
    assert result["slack_channel_type"] == "public_channel"
    assert result["slack_message_ts"] == "1755230400.000100"
    assert result["slack_subtype"] == "bot_message"
    assert result["slack_reactions"] == ("question",)


def test_normalize_dm_and_group_dm_are_is_dm_true():
    connector = _connector("U0PHONG01")
    source = Source(id="C0GROUP", name="Group DM")
    for channel_type in ("im", "mpim"):
        result = connector.normalize(_synthetic_message(channel_type=channel_type), source)
        assert result["is_dm"] is True


def test_normalize_public_and_private_channel_are_is_dm_false():
    connector = _connector("U0PHONG01")
    source = Source(id="C0GENERAL", name="#general")
    for channel_type in ("public_channel", "private_channel"):
        result = connector.normalize(_synthetic_message(channel_type=channel_type), source)
        assert result["is_dm"] is False


def test_deep_link_uses_team_domain_when_available():
    connector = _connector("U0PHONG01", account_label="mondaiy")
    raw = _synthetic_message(channel="C0GENERAL", ts="1755230400.000100")

    assert connector.deep_link(raw) == "https://mondaiy.slack.com/archives/C0GENERAL/p1755230400000100"


def test_deep_link_falls_back_to_app_slack_com_when_domain_missing():
    connector = _connector("U0PHONG01", account_label=None, external_site_id="T0MONDAIY")
    raw = _synthetic_message(channel="C0GENERAL", ts="1755230400.000100")

    assert connector.deep_link(raw) == "https://app.slack.com/client/T0MONDAIY/C0GENERAL/p1755230400000100"


def test_deep_link_appends_thread_ts_for_replies():
    connector = _connector("U0PHONG01", account_label="mondaiy")
    raw = _synthetic_message(channel="C0GENERAL", ts="123.789", thread_ts="123.456")

    assert connector.deep_link(raw) == "https://mondaiy.slack.com/archives/C0GENERAL/p123789?thread_ts=123.456"
