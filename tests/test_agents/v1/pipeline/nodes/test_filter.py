from sqlalchemy import select

from src.agents.pipeline.nodes.filter import filter_node
from src.models.message import Message
from tests.test_agents.v1.pipeline.conftest import gmail_item


def test_filter_keeps_actionable_mail_and_rejects_noise(pipeline_state):
    pipeline_state["normalized"] = [
        gmail_item("action", "Please submit the report by Friday"),
        gmail_item("noise", "Newsletter: ten tips for your inbox"),
    ]

    result = filter_node(pipeline_state)

    assert {item["id"] for item in result["filtered"]} == {"action"}
    assert any(item["id"] == "noise" for item in result["filter_rejected"])


def test_filter_indexes_useful_gmail_for_offline_brief_reads(pipeline_state):
    pipeline_state["normalized"] = [gmail_item("cached", "Please review Parkwave by Friday")]

    filter_node(pipeline_state)

    row = pipeline_state["db"].execute(select(Message).where(Message.external_id == "cached")).scalar_one()
    assert row.external_id == "cached"
    assert row.provider == "google"
