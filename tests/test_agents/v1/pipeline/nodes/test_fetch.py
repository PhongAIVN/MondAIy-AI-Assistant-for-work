import pytest

from src.agents.pipeline.nodes import fetch
from src.models.connection import Connection


@pytest.mark.asyncio
async def test_fetch_reads_only_declared_source_and_persists_raw_audit(pipeline_state, monkeypatch):
    class FakeConnector:
        def __init__(self, connection, db):
            self.connection = connection

        async def fetch_range(self, source, time_from, time_to, on_item=None):
            assert source.id == "INBOX"
            return [{"id": "m1", "snippet": "deadline"}]

    # Không hardcode id — DB dùng chung session-scope với các test khác,
    # id cụ thể có thể đã bị test chạy trước chiếm mất (UNIQUE constraint).
    connection = Connection(user_id="u-test", provider="google")
    pipeline_state["db"].add(connection)
    pipeline_state["db"].commit()
    pipeline_state["db"].refresh(connection)
    pipeline_state["sources"] = [{"connection_id": connection.id, "source_id": "INBOX"}]
    monkeypatch.setattr(fetch, "resolve_connector", lambda provider, source_id: (FakeConnector, source_id))

    result = await fetch.fetch_node(pipeline_state)

    assert result["raw_messages"][0]["raw_items"][0]["id"] == "m1"
    assert pipeline_state["db"].query(fetch.PipelineRawMessage).count() == 1
