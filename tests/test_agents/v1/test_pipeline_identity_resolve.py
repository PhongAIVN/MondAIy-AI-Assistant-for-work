from src.agents.pipeline.identity_resolve import resolve_assignee


def test_resolve_assignee_confirms_self_when_hint_empty_and_direct_recipient():
    message = {"to": ["phong@student.mondaiy.vn"]}

    assignee, ambiguous = resolve_assignee("", message, "phong@student.mondaiy.vn")

    assert assignee == "phong@student.mondaiy.vn"
    assert ambiguous is False


def test_resolve_assignee_confirms_self_when_hint_references_group_and_direct_recipient():
    message = {"to": ["phong@student.mondaiy.vn"]}

    assignee, ambiguous = resolve_assignee("các bạn", message, "phong@student.mondaiy.vn")

    assert assignee == "phong@student.mondaiy.vn"
    assert ambiguous is False


def test_resolve_assignee_leaves_blank_when_not_direct_recipient():
    message = {"to": ["other@student.mondaiy.vn"]}

    assignee, ambiguous = resolve_assignee("", message, "phong@student.mondaiy.vn")

    assert assignee is None
    assert ambiguous is True


def test_resolve_assignee_does_not_guess_named_third_party():
    # BR-05/FR-061 áp cho danh tính: có tên cụ thể khác trong hint không có nghĩa là
    # gán được — không có danh bạ để đối chiếu, phải để trống chứ không suy diễn.
    message = {"to": ["phong@student.mondaiy.vn"]}

    assignee, ambiguous = resolve_assignee("Nam", message, "phong@student.mondaiy.vn")

    assert assignee is None
    assert ambiguous is True


def test_resolve_assignee_ambiguous_when_user_email_missing():
    message = {"to": ["phong@student.mondaiy.vn"]}

    assignee, ambiguous = resolve_assignee("", message, None)

    assert assignee is None
    assert ambiguous is True
