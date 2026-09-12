"""Regression cho metadata thiếu bằng chứng của câu trả lời hội thoại."""

from src.api.conversations import _message_extras


def test_message_extras_persists_supported_grounding_status() -> None:
    extras = _message_extras({"metadata": {"grounding_status": "abstain"}})

    assert extras == {"groundingStatus": "abstain", "programQuestionHandoffEligible": False}


def test_message_extras_persists_grounded_status() -> None:
    extras = _message_extras({"metadata": {"grounding_status": "grounded"}})

    assert extras == {"groundingStatus": "grounded", "programQuestionHandoffEligible": False}


def test_message_extras_allows_handoff_only_after_program_tool_lacks_evidence() -> None:
    program_extras = _message_extras(
        {"metadata": {"grounding_status": "abstain", "tool_calls": ["program_information_search"]}}
    )
    unrelated_extras = _message_extras(
        {"metadata": {"grounding_status": "abstain", "tool_calls": ["gmail_search"]}}
    )

    assert program_extras == {
        "groundingStatus": "abstain",
        "programQuestionHandoffEligible": True,
    }
    assert unrelated_extras == {
        "groundingStatus": "abstain",
        "programQuestionHandoffEligible": False,
    }


def test_message_extras_ignores_unknown_grounding_status() -> None:
    extras = _message_extras({"metadata": {"grounding_status": "force_admin_access"}})

    assert extras is None


def test_message_extras_persists_structured_conversational_route() -> None:
    route = {
        "action": "READ",
        "source": "google_sheets",
        "resource_ref": "https://docs.google.com/spreadsheets/d/abc_123/edit",
        "status": "error",
        "error_code": "source_unavailable",
    }

    extras = _message_extras({"metadata": {"conversational_route": route}})

    assert extras == {"routing": route}
