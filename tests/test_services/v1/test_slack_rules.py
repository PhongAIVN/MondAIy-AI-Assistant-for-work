import pytest

from src.services.slack_rules import (
    Decision,
    NormalizedMessage,
    RuleConfig,
    ScoreResult,
    decide_from_score,
    evaluate_message,
    extract_deadline_phrase,
    extract_evidence,
    extract_title,
    hard_filter,
    score_message,
)


def _message(**overrides) -> NormalizedMessage:
    base = dict(
        message_id="D0MENTOR01:1755230400.000100",
        channel_id="D0MENTOR01",
        channel_type="im",
        thread_ts=None,
        subtype=None,
        text="nhớ nộp báo cáo tuần trước 5h chiều thứ Sáu nhé",
        author_id="U_MENTOR",
        is_self=False,
        mentions_current_user=True,
    )
    base.update(overrides)
    return NormalizedMessage(**base)


class TestHardFilter:
    def test_system_subtype_is_dropped(self):
        result = hard_filter(_message(subtype="channel_join"))
        assert result.dropped is True
        assert result.reason == "SYSTEM_SUBTYPE"

    def test_message_changed_is_dropped(self):
        result = hard_filter(_message(subtype="message_changed"))
        assert result.dropped is True
        assert result.reason == "MESSAGE_CHANGED_DROPPED"

    def test_empty_text_after_stripping_mentions_is_dropped(self):
        result = hard_filter(_message(text="<@U0PHONG01>"))
        assert result.dropped is True
        assert result.reason == "EMPTY_TEXT"

    def test_normal_message_is_not_dropped(self):
        result = hard_filter(_message())
        assert result.dropped is False

    def test_bot_message_with_real_content_is_not_auto_dropped(self):
        # Bot workflow có nội dung thật (vd Zapier báo tình trạng công việc)
        # KHÔNG tự DROP ở Hard Filter — để Scoring đánh giá (xem docstring
        # bước 3 slack-detail.drawio).
        result = hard_filter(_message(author_id="B0BOT01", text="Vui lòng xác nhận trước thứ Sáu."))
        assert result.dropped is False


class TestScoreMessage:
    def test_matches_worked_example_from_diagram(self):
        message = _message()
        result = score_message(message, RuleConfig())

        assert set(result.reasons) == {
            "MENTIONED_CURRENT_USER",
            "DIRECT_MESSAGE",
            "HAS_ACTION",
            "HAS_DEADLINE_INFERRED",
        }
        # Khớp đúng score=95 trong ví dụ walkthrough slack-detail.drawio.
        assert result.score == 30 + 15 + 25 + 25

    def test_public_channel_gets_no_direct_message_bonus(self):
        message = _message(channel_type="public_channel", mentions_current_user=False)
        result = score_message(message, RuleConfig())
        assert "DIRECT_MESSAGE" not in result.reasons

    def test_group_dm_gets_direct_message_bonus(self):
        message = _message(channel_type="mpim", mentions_current_user=False, text="chào cả nhóm")
        result = score_message(message, RuleConfig())
        assert "DIRECT_MESSAGE" in result.reasons

    def test_no_mention_gets_no_mention_bonus(self):
        message = _message(mentions_current_user=False)
        result = score_message(message, RuleConfig())
        assert "MENTIONED_CURRENT_USER" not in result.reasons

    def test_pinned_message_scores_bonus(self):
        message = _message(is_pinned=True)
        with_pin = score_message(message, RuleConfig())
        without_pin = score_message(_message(is_pinned=False), RuleConfig())
        assert with_pin.score == without_pin.score + RuleConfig().pinned_score
        assert "PINNED" in with_pin.reasons

    def test_newsletter_text_scores_negative(self):
        message = _message(text="Newsletter: unsubscribe from our digest.", mentions_current_user=False)
        result = score_message(message, RuleConfig())
        assert "NEWSLETTER_OR_AUTOMATED" in result.reasons
        assert result.score < 0

    def test_newsletter_and_automated_penalty_not_double_counted(self):
        # Sơ đồ gộp chung "newsletter/automated: -40" thành 1 dòng — khớp cả
        # hai regex cũng chỉ trừ 1 lần, không cộng dồn.
        message = _message(
            text="no-reply: newsletter unsubscribe digest automated notification", mentions_current_user=False
        )
        result = score_message(message, RuleConfig())
        assert result.reasons.count("NEWSLETTER_OR_AUTOMATED") == 1
        assert result.score == RuleConfig().newsletter_or_automated_score

    def test_weights_are_configurable(self):
        message = _message()
        custom = RuleConfig(action_score=1000)
        result = score_message(message, custom)
        assert result.score >= 1000


class TestExtractTitle:
    def test_prefers_sentence_matching_action_or_deadline(self):
        message = _message(text="Chào buổi sáng. Đội cần nộp trước thứ Sáu. Câu khác.")
        assert extract_title(message) == "Đội cần nộp trước thứ Sáu."

    def test_falls_back_to_first_sentence(self):
        message = _message(text="Không có tín hiệu gì đặc biệt ở đây. Câu thứ hai.")
        assert extract_title(message) == "Không có tín hiệu gì đặc biệt ở đây."

    def test_truncates_long_title(self):
        long_text = "a" * 200
        message = _message(text=long_text)
        title = extract_title(message)
        assert len(title) <= 81  # 80 ký tự + dấu "…"
        assert title.endswith("…")


class TestExtractEvidence:
    def test_returns_sentence_matching_action_or_deadline(self):
        message = _message(text="Không liên quan gì. Đội cần nộp trước thứ Sáu. Câu khác.")
        assert extract_evidence(message) == "Đội cần nộp trước thứ Sáu."

    def test_falls_back_to_full_text_when_no_sentence_matches(self):
        message = _message(text="Không có tín hiệu gì đặc biệt ở đây.")
        assert extract_evidence(message) == "Không có tín hiệu gì đặc biệt ở đây."


class TestExtractDeadlinePhrase:
    def test_returns_sentence_matching_deadline_specifically(self):
        message = _message(text="Vui lòng xác nhận. Hạn chót là thứ Sáu tuần này. Cảm ơn.")
        assert extract_deadline_phrase(message) == "Hạn chót là thứ Sáu tuần này."

    def test_action_only_sentence_does_not_count_as_deadline_phrase(self):
        message = _message(text="Vui lòng xác nhận giúp mình nhé.")
        assert extract_deadline_phrase(message) == ""


class TestDecideFromScore:
    def test_keep_when_at_or_above_threshold(self):
        config = RuleConfig()
        decision = decide_from_score(ScoreResult(score=config.keep_threshold, reasons=("HAS_ACTION",)), config)
        assert decision.decision == "KEEP"
        assert decision.rule_version == config.rule_version

    def test_review_when_between_thresholds(self):
        config = RuleConfig()
        decision = decide_from_score(ScoreResult(score=config.review_threshold, reasons=("HAS_ACTION",)), config)
        assert decision.decision == "REVIEW"

    def test_drop_when_below_review_threshold(self):
        config = RuleConfig()
        decision = decide_from_score(ScoreResult(score=0, reasons=()), config)
        assert decision.decision == "DROP"
        assert decision.reasons == ("NO_ACTION_REQUIRED",)


class TestEvaluateMessageIntegration:
    def test_worked_example_dm_results_in_keep(self):
        message = _message()
        decision, title, evidence = evaluate_message(message)

        assert decision.decision == "KEEP"
        assert decision.score == 95
        assert set(decision.reasons) == {
            "MENTIONED_CURRENT_USER",
            "DIRECT_MESSAGE",
            "HAS_ACTION",
            "HAS_DEADLINE_INFERRED",
        }
        assert title == "nhớ nộp báo cáo tuần trước 5h chiều thứ Sáu nhé"
        assert evidence == "nhớ nộp báo cáo tuần trước 5h chiều thứ Sáu nhé"

    def test_system_subtype_is_dropped_before_scoring_and_has_no_title_or_evidence(self):
        message = _message(subtype="channel_join")
        decision, title, evidence = evaluate_message(message)

        assert decision.decision == "DROP"
        assert decision.reasons == ("SYSTEM_SUBTYPE",)
        assert decision.score == 0
        assert title == ""
        assert evidence == ""

    @pytest.mark.parametrize("mentions", [False, True])
    def test_message_can_still_be_kept_without_mention_via_other_signals(self, mentions):
        message = _message(mentions_current_user=mentions)
        decision, _, _ = evaluate_message(message)
        # HAS_ACTION + HAS_DEADLINE_INFERRED + DIRECT_MESSAGE = 65, vẫn KEEP dù không bị mention
        assert decision.decision == "KEEP"

    def test_low_signal_public_message_is_dropped(self):
        message = _message(
            channel_type="public_channel",
            mentions_current_user=False,
            text="Chào buổi sáng cả nhóm nhé!",
        )
        decision, title, evidence = evaluate_message(message)
        assert decision.decision == "DROP"
        assert title == ""
        assert evidence == ""


class TestDecisionDataclass:
    def test_decision_is_frozen_and_explainable(self):
        decision = Decision(score=50, decision="KEEP", reasons=("HAS_ACTION",), rule_version="slack-rules-v1-draft")
        with pytest.raises(AttributeError):
            decision.score = 100  # type: ignore[misc]
