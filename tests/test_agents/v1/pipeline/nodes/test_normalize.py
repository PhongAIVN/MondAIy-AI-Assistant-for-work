from src.agents.pipeline.nodes.normalize import normalize_node
from tests.test_agents.v1.pipeline.conftest import gmail_item


def test_normalize_converts_connector_items_and_records_message_id(pipeline_state):
    class Connector:
        def normalize(self, raw, source):
            return gmail_item(raw["id"], raw["text"])

    pipeline_state["raw_messages"] = [
        {
            "connection_id": 1,
            "connector": Connector(),
            "source": type("S", (), {"id": "INBOX"})(),
            "raw_items": [{"id": "m1", "text": "Please submit the report by Friday"}],
        }
    ]

    result = normalize_node(pipeline_state)

    assert len(result["normalized"]) == 1
    assert result["normalized"][0]["_pipeline_normalized_message_id"] is not None
