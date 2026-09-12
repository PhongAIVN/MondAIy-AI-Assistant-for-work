from src.agents.pipeline.nodes.evidence import evidence_node, select_evidence


def test_select_evidence_keeps_short_text_unchanged():
    text = "Hi team, quick update on the demo."
    assert select_evidence(text) == text


def test_select_evidence_picks_action_and_deadline_sentences_from_long_email():
    filler = "Weather in the office stayed pleasant all week, nothing else worth noting here. " * 6
    text = (
        filler
        + "Please submit the report before Friday. "
        + filler
        + "This is urgent, immediate attention needed. "
        + filler
    )
    assert len(text) >= 400

    selected = select_evidence(text, max_sentences=2)

    assert "Please submit the report before Friday." in selected
    assert "This is urgent, immediate attention needed." in selected
    assert "Weather in the office" not in selected


def test_select_evidence_preserves_original_sentence_order():
    filler = "Nothing important happens here, just filler content padding out the message body. " * 5
    text = (
        "Please review the proposal before Monday. "
        + filler
        + "This is urgent and needs immediate attention. "
        + filler
    )
    assert len(text) >= 400

    selected = select_evidence(text, max_sentences=2)
    review_pos = selected.find("Please review the proposal before Monday.")
    urgent_pos = selected.find("This is urgent and needs immediate attention.")

    assert review_pos != -1
    assert urgent_pos != -1
    assert review_pos < urgent_pos


def test_evidence_node_adds_evidence_text_field_without_dropping_original_text():
    state = {"filtered": [{"id": "m1", "text": "Please reply before Friday."}]}

    result = evidence_node(state)

    item = result["filtered"][0]
    assert item["text"] == "Please reply before Friday."
    assert item["evidence_text"] == "Please reply before Friday."
