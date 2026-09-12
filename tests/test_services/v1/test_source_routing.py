import pytest

from src.services.source_routing import analyze_source_mentions


def test_project_activity_without_source_gets_explainable_source_affinity():
    decision = analyze_source_mentions("Trong dự án Parkwave tôi đã làm được những gì?")

    assert decision.entities == ("parkwave",)
    assert decision.mode == "entity_discovery"
    assert decision.confidence == 0.72
    assert decision.needs_confirmation is True
    assert set(decision.candidate_sources) == {
        "tasks", "jira", "gmail", "calendar", "discord", "google_sheets", "google_docs"
    }


def test_explicit_jira_narrows_source_affinity():
    decision = analyze_source_mentions("Parkwave ở Jira ấy")

    assert decision.entities == ("parkwave",)
    assert decision.candidate_sources == ("jira",)
    assert decision.mode == "explicit"
    assert decision.confidence == 0.97
    assert decision.needs_confirmation is False


def test_explicit_google_sheet_url_narrows_source_affinity():
    decision = analyze_source_mentions("Đọc https://docs.google.com/spreadsheets/d/abc_123/edit")

    assert decision.explicit_sources == ("google_sheets",)
    assert decision.candidate_sources == ("google_sheets",)
    assert decision.mode == "explicit"
    assert decision.action == "continue"


def test_generic_work_vocabulary_is_not_an_explicit_source():
    decision = analyze_source_mentions("ở quản lý công việc")

    assert decision.explicit_sources == ()
    assert decision.candidate_sources == ("tasks",)
    assert decision.mode == "semantic"


@pytest.mark.parametrize(
    "provider_query,domain_query,source",
    [
        ("đọc Jira", "bug này cần xử lý", "jira"),
        ("đọc Gmail", "email này nói về deadline", "gmail"),
        ("xem Calendar", "meeting sáng nay", "calendar"),
        ("tìm trên Discord", "tin nhắn này", "discord"),
        ("mở Mondaiy Tasks", "công việc đang làm", "tasks"),
    ],
)
def test_provider_names_and_domain_vocabulary_have_different_strength(
    provider_query, domain_query, source
):
    provider = analyze_source_mentions(provider_query)
    domain = analyze_source_mentions(domain_query)

    assert provider.explicit_sources == (source,)
    assert provider.mode == "explicit"
    assert domain.explicit_sources == ()
    assert domain.candidate_sources == (source,)
    assert domain.mode == "semantic"


def test_explicit_google_doc_url_narrows_source_affinity():
    decision = analyze_source_mentions("Tóm tắt https://docs.google.com/document/d/abc_123/edit")

    assert decision.explicit_sources == ("google_docs",)
    assert decision.candidate_sources == ("google_docs",)
    assert decision.mode == "explicit"
    assert decision.action == "continue"


def test_explicit_all_sources_is_high_confidence():
    decision = analyze_source_mentions("Parkwave, lấy từ tất cả nguồn")

    assert decision.entities == ("parkwave",)
    assert decision.explicit_sources == ("all",)
    assert decision.candidate_sources == (
        "tasks", "jira", "gmail", "calendar", "discord", "google_sheets", "google_docs"
    )
    assert decision.confidence_band == "high"
    assert decision.action == "continue"
    assert decision.needs_confirmation is False


def test_unrelated_query_is_not_blocked_by_source_uncertainty():
    decision = analyze_source_mentions("1+1=")

    assert decision.confidence_band == "low"
    assert decision.action == "not_applicable"
    assert decision.needs_confirmation is False
