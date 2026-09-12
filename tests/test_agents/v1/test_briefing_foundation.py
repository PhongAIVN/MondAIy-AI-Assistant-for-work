from datetime import UTC, datetime, timedelta

from src.agents.briefing import intent as intent_module
from src.agents.briefing.evidence import Evidence, fuse_and_rank
from src.agents.briefing.intent import BriefIntent, classify_intent, recognize_intent
from src.agents.briefing.planning import plan_information


def test_small_talk_does_not_activate_retrieval_plan():
    intent = recognize_intent("hello, bạn khỏe không?")
    assert intent == BriefIntent.SMALL_TALK
    assert plan_information(intent, datetime(2026, 8, 11, tzinfo=UTC)) == ()


def test_daily_brief_has_deterministic_multi_source_bounded_plan(monkeypatch):
    _patch_semantic_embeddings(monkeypatch)
    now = datetime(2026, 8, 11, 9, tzinfo=UTC)
    plan = plan_information(recognize_intent("Hôm nay có gì cần chú ý?"), now)
    assert [item.source for item in plan] == ["calendar", "gmail", "jira", "discord", "tasks"]
    assert next(item for item in plan if item.source == "calendar").time_to - now.replace(hour=0, minute=0, second=0, microsecond=0) == timedelta(days=1)


def test_daily_brief_intent_covers_implied_work_summary_requests(monkeypatch):
    _patch_semantic_embeddings(monkeypatch)
    assert recognize_intent("Summarize my work today") == BriefIntent.DAILY_BRIEF
    assert recognize_intent("Hôm nay tôi cần làm gì?") == BriefIntent.DAILY_BRIEF


def _patch_semantic_embeddings(monkeypatch):
    intents = list(intent_module._EXAMPLES)
    anchors = tuple([1.0, 0.0] if intent == BriefIntent.DAILY_BRIEF else [0.0, 1.0] for intent in intents)

    def fake_embed(texts):
        return [[1.0, 0.0] if ("today" in text.lower() or "hôm nay" in text.lower()) else [0.0, 1.0] for text in texts]

    monkeypatch.setattr(intent_module, "_embedding_backend", lambda: fake_embed)
    monkeypatch.setattr(intent_module, "_prototypes", lambda _model: tuple((intent, (anchors[index],)) for index, intent in enumerate(intents)))


def test_semantic_trace_keeps_runner_up_and_threshold(monkeypatch):
    _patch_semantic_embeddings(monkeypatch)
    decision = classify_intent("tóm tắt công việc hôm nay")
    assert decision.intent == BriefIntent.DAILY_BRIEF
    assert decision.score == 1.0
    assert decision.threshold == 0.6
    assert decision.runner_up
    assert decision.trace()["matched_by"] == "embedding"


def test_semantic_classifier_does_not_force_unrelated_text_into_an_intent(monkeypatch):
    monkeypatch.setattr(intent_module, "_embedding_backend", lambda: lambda texts: [[0.0, 0.0] for _ in texts])
    monkeypatch.setattr(intent_module, "_prototypes", lambda _model: tuple((intent, ([1.0, 0.0],)) for intent in intent_module._EXAMPLES))
    decision = classify_intent("một câu không liên quan", threshold=0.6)
    assert decision.intent == BriefIntent.GENERAL_WORK
    assert decision.matched_by == "below_threshold"


def test_evidence_fusion_flags_conflicting_due_dates_and_prioritizes_it():
    now = datetime(2026, 8, 11, 9, tzinfo=UTC)
    clusters = fuse_and_rank([
        Evidence("jira-1", "jira", "Gate one report", 70, now, topic="gate one"),
        Evidence("gmail-1", "gmail", "Gate one report", 65, now + timedelta(days=1), topic="gate one"),
        Evidence("calendar-1", "calendar", "Weekly sync", 90, now + timedelta(days=7), topic="weekly sync"),
    ], now)
    assert clusters[0].topic == "gate one"
    assert clusters[0].conflict is True
    assert clusters[0].priority > clusters[1].priority
