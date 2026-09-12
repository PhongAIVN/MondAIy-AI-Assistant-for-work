from src.agents.pipeline.nodes.verify import verify_node


def _extracted_item(*, time_expression="", assignee_hint="", provider="google", text="submit report"):
    return {
        "message": {"id": "m1", "provider": provider, "text": text},
        "title": "Submit report",
        "time_expression": time_expression,
        "assignee_hint": assignee_hint,
        "evidence_quote": text,
    }


def test_verify_node_keeps_time_expression_grounded_in_source_text():
    state = {"extracted": [_extracted_item(time_expression="Friday", text="submit report by Friday")]}

    result = verify_node(state)

    assert result["extracted"][0]["time_expression"] == "Friday"
    assert result["extracted"][0]["fact_verified"] is True
    assert result["verification_stats"]["time_expression_cleared"] == 0


def test_verify_node_clears_time_expression_not_present_in_source_text():
    state = {"extracted": [_extracted_item(time_expression="next Monday", text="submit report by Friday")]}

    result = verify_node(state)

    assert result["extracted"][0]["time_expression"] == ""
    assert result["verification_stats"]["time_expression_cleared"] == 1


def test_verify_node_clears_assignee_hint_not_present_in_source_text():
    state = {"extracted": [_extracted_item(assignee_hint="Minh", text="please submit the report")]}

    result = verify_node(state)

    assert result["extracted"][0]["assignee_hint"] == ""
    assert result["verification_stats"]["assignee_hint_cleared"] == 1


def test_verify_node_keeps_assignee_hint_grounded_case_and_diacritic_insensitive():
    state = {"extracted": [_extracted_item(assignee_hint="minh", text="Minh sẽ phụ trách backend")]}

    result = verify_node(state)

    assert result["extracted"][0]["assignee_hint"] == "minh"
    assert result["verification_stats"]["assignee_hint_cleared"] == 0


def test_verify_node_does_not_drop_item_when_field_ungrounded():
    """Field lệch chỉ bị xóa field đó, không loại cả item — tránh giảm recall."""
    state = {"extracted": [_extracted_item(time_expression="ngày mai", text="submit report")]}

    result = verify_node(state)

    assert len(result["extracted"]) == 1
    assert result["extracted"][0]["time_expression"] == ""


def test_verify_node_skips_jira_items_unchanged():
    item = _extracted_item(time_expression="anything not in text", provider="jira")

    result = verify_node({"extracted": [item]})

    assert result["extracted"][0]["time_expression"] == "anything not in text"
    assert "fact_verified" not in result["extracted"][0]
