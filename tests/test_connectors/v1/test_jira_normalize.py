from src.connectors.base import Source
from src.connectors.jira import JiraConnector


class _FakeConnection:
    def __init__(self, provider_user_id: str, account_label: str = "https://mycompany.atlassian.net") -> None:
        self.provider_user_id = provider_user_id
        self.account_label = account_label


def _connector(provider_user_id: str, account_label: str = "https://mycompany.atlassian.net") -> JiraConnector:
    return JiraConnector(_FakeConnection(provider_user_id, account_label), db=None)


def _adf_paragraph(text: str) -> dict:
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def _synthetic_issue(
    *,
    assignee_account_id: str | None,
    duedate: str | None,
    description: dict | None,
    status_category_key: str = "indeterminate",
    resolution: str | None = None,
    priority: str | None = "High",
) -> dict:
    return {
        "key": "PROJ-42",
        "fields": {
            "summary": "Sửa lỗi đăng nhập",
            "description": description,
            "reporter": {"accountId": "acc-reporter-1", "displayName": "Reporter Name"},
            "assignee": {"accountId": assignee_account_id, "displayName": "Assignee Name"}
            if assignee_account_id
            else None,
            "status": {"name": "In Progress", "statusCategory": {"key": status_category_key}},
            "duedate": duedate,
            "updated": "2026-08-09T10:15:30.123+0700",
            "created": "2026-08-01T09:00:00.000+0700",
            "resolution": {"name": resolution} if resolution else None,
            "priority": {"name": priority} if priority else None,
            "issuetype": {"name": "Task"},
        },
    }


def test_normalize_extracts_text_from_adf_description():
    connector = _connector("acc-me")
    raw = _synthetic_issue(
        assignee_account_id=None,
        duedate=None,
        description=_adf_paragraph("Vui lòng fix bug đăng nhập trước thứ Sáu."),
    )
    source = Source(id="PROJ", name="Project")

    result = connector.normalize(raw, source)

    assert result["text"].startswith("Vui lòng fix bug đăng nhập trước thứ Sáu.")
    assert result["subject"] == "Sửa lỗi đăng nhập"
    assert result["provider"] == "jira"
    assert result["id"] == "PROJ-42"


def test_normalize_is_self_true_when_assignee_matches_connection():
    connector = _connector("acc-me")
    raw = _synthetic_issue(assignee_account_id="acc-me", duedate=None, description=None)
    source = Source(id="PROJ", name="Project")

    result = connector.normalize(raw, source)

    assert result["is_self"] is True


def test_normalize_is_self_false_when_assignee_differs():
    connector = _connector("acc-me")
    raw = _synthetic_issue(assignee_account_id="acc-other", duedate=None, description=None)
    source = Source(id="PROJ", name="Project")

    result = connector.normalize(raw, source)

    assert result["is_self"] is False


def test_normalize_is_self_false_when_unassigned():
    connector = _connector("acc-me")
    raw = _synthetic_issue(assignee_account_id=None, duedate=None, description=None)
    source = Source(id="PROJ", name="Project")

    result = connector.normalize(raw, source)

    assert result["is_self"] is False


def test_normalize_appends_duedate_as_explicit_sentence_for_resolve_due_at():
    # resolve_due_at() cần đủ ngày/giờ/timezone tường minh trong câu chữ.
    connector = _connector("acc-me")
    raw = _synthetic_issue(assignee_account_id=None, duedate="2026-08-14", description=None)
    source = Source(id="PROJ", name="Project")

    result = connector.normalize(raw, source)

    assert "Hạn chót: 2026-08-14 00:00 (Asia/Ho_Chi_Minh)" in result["text"]


def test_normalize_status_becomes_label_ids():
    connector = _connector("acc-me")
    raw = _synthetic_issue(assignee_account_id=None, duedate=None, description=None)
    source = Source(id="PROJ", name="Project")

    result = connector.normalize(raw, source)

    assert result["label_ids"] == ["In Progress"]


def test_deep_link_uses_connection_site_url():
    connector = _connector("acc-me", account_label="https://mycompany.atlassian.net")
    raw = {"key": "PROJ-42"}

    assert connector.deep_link(raw) == "https://mycompany.atlassian.net/browse/PROJ-42"


def test_normalize_handles_missing_description_gracefully():
    connector = _connector("acc-me")
    raw = _synthetic_issue(assignee_account_id=None, duedate=None, description=None)
    source = Source(id="PROJ", name="Project")

    result = connector.normalize(raw, source)

    assert result["text"] == ""


def test_normalize_exposes_structured_fields_for_rule_engine():
    connector = _connector("acc-me")
    raw = _synthetic_issue(
        assignee_account_id="acc-me",
        duedate="2026-08-15",
        description=None,
        status_category_key="indeterminate",
        resolution=None,
        priority="High",
    )
    source = Source(id="PROJ", name="Project")

    result = connector.normalize(raw, source)

    assert result["jira_assignee_account_id"] == "acc-me"
    assert result["jira_status"] == "In Progress"
    assert result["jira_status_category"] == "In Progress"
    assert result["jira_resolution"] is None
    assert result["jira_priority"] == "High"
    assert result["jira_issue_type"] == "Task"
    assert result["jira_due_date"].date().isoformat() == "2026-08-15"
    assert result["jira_created_at"] is not None


def test_normalize_maps_done_status_category_key():
    connector = _connector("acc-me")
    raw = _synthetic_issue(assignee_account_id=None, duedate=None, description=None, status_category_key="done")
    source = Source(id="PROJ", name="Project")

    result = connector.normalize(raw, source)

    assert result["jira_status_category"] == "Done"


def test_normalize_resolution_name_when_present():
    connector = _connector("acc-me")
    raw = _synthetic_issue(assignee_account_id=None, duedate=None, description=None, resolution="Fixed")
    source = Source(id="PROJ", name="Project")

    result = connector.normalize(raw, source)

    assert result["jira_resolution"] == "Fixed"


def test_normalize_unassigned_issue_has_no_account_id():
    connector = _connector("acc-me")
    raw = _synthetic_issue(assignee_account_id=None, duedate=None, description=None)
    source = Source(id="PROJ", name="Project")

    result = connector.normalize(raw, source)

    assert result["jira_assignee_account_id"] is None
