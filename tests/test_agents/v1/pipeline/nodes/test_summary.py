from src.agents.pipeline.nodes.summary import summary_node


def test_summary_node_is_evidence_only_and_never_creates_tasks():
    filtered = [{"id": "m1", "snippet": "deadline Friday"}]

    result = summary_node({"filtered": filtered})

    assert result["summary_items"] == filtered
    assert result["tasks_persisted"] == []
