from datetime import UTC, datetime

import pytest

from src.services.jira_rules import (
    CurrentUserContext,
    NormalizedIssue,
    RuleConfig,
    compute_due_bucket,
    decide_from_score,
    evaluate_issue,
    extract_evidence,
    hard_filter,
    score_issue,
)

USER = CurrentUserContext(account_id="acc-phong-01", timezone="Asia/Ho_Chi_Minh")


def _issue(**overrides) -> NormalizedIssue:
    base = dict(
        issue_id="10042",
        issue_key="TO04-42",
        project="TO04",
        title="Hoàn thành báo cáo tuần 3",
        description="Đội cần nộp trước thứ Sáu. Xem thêm tại wiki.",
        assignee_account_id="acc-phong-01",
        status="In Progress",
        status_category="In Progress",
        resolution=None,
        priority="High",
        issue_type="Task",
        due_date=datetime(2026, 8, 15, tzinfo=UTC),
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        updated_at=datetime(2026, 8, 10, tzinfo=UTC),
        url="https://vinait004.atlassian.net/browse/TO04-42",
    )
    base.update(overrides)
    return NormalizedIssue(**base)


class TestHardFilter:
    def test_status_done_is_dropped(self):
        result = hard_filter(_issue(status_category="Done"))
        assert result.dropped is True
        assert result.reason == "STATUS_DONE"

    def test_system_generated_without_action_is_dropped(self):
        issue = _issue(
            title="Automated notification",
            description="This is an automated notification. No action needed.",
        )
        result = hard_filter(issue)
        assert result.dropped is True
        assert result.reason == "SYSTEM_GENERATED"

    def test_automated_text_with_action_is_not_dropped(self):
        issue = _issue(
            title="Automated notification",
            description="This is automated but please confirm before Friday.",
        )
        result = hard_filter(issue)
        assert result.dropped is False

    def test_resolution_without_done_status_is_not_dropped_but_flagged(self):
        issue = _issue(status_category="In Progress", resolution="Fixed")
        result = hard_filter(issue)
        assert result.dropped is False
        assert result.resolution_flagged is True

    def test_no_resolution_is_not_flagged(self):
        issue = _issue(resolution=None)
        result = hard_filter(issue)
        assert result.resolution_flagged is False


class TestComputeDueBucket:
    NOW = datetime(2026, 8, 11, tzinfo=UTC)

    def test_no_deadline(self):
        assert compute_due_bucket(None, self.NOW, RuleConfig()) == "NO_DEADLINE"

    def test_overdue(self):
        due = datetime(2026, 8, 10, tzinfo=UTC)
        assert compute_due_bucket(due, self.NOW, RuleConfig()) == "OVERDUE"

    def test_due_today(self):
        due = datetime(2026, 8, 11, tzinfo=UTC)
        assert compute_due_bucket(due, self.NOW, RuleConfig()) == "DUE_TODAY"

    def test_due_tomorrow(self):
        due = datetime(2026, 8, 12, tzinfo=UTC)
        assert compute_due_bucket(due, self.NOW, RuleConfig()) == "DUE_TOMORROW"

    def test_due_soon_within_window(self):
        due = datetime(2026, 8, 14, tzinfo=UTC)
        assert compute_due_bucket(due, self.NOW, RuleConfig()) == "DUE_SOON"

    def test_future_outside_window(self):
        due = datetime(2026, 9, 1, tzinfo=UTC)
        assert compute_due_bucket(due, self.NOW, RuleConfig()) == "FUTURE"


class TestScoreIssue:
    def test_matches_worked_example_from_diagram(self):
        issue = _issue()
        config = RuleConfig()
        result = score_issue(issue, "DUE_SOON", USER, resolution_flagged=False, config=config)

        assert "HAS_ACTION" in result.reasons
        assert "HAS_DEADLINE" in result.reasons
        assert "ASSIGNED_TO_CURRENT_USER" in result.reasons
        assert "HIGH_PRIORITY" in result.reasons
        assert "DUE_SOON" in result.reasons
        assert result.score == 25 + 25 + 15 + 10 + 10

    def test_assigned_to_other_user_gets_no_bonus(self):
        issue = _issue(assignee_account_id="acc-someone-else")
        result = score_issue(issue, "FUTURE", USER, resolution_flagged=False, config=RuleConfig())
        assert "ASSIGNED_TO_CURRENT_USER" not in result.reasons

    def test_unassigned_gets_no_bonus(self):
        issue = _issue(assignee_account_id=None)
        result = score_issue(issue, "FUTURE", USER, resolution_flagged=False, config=RuleConfig())
        assert "ASSIGNED_TO_CURRENT_USER" not in result.reasons

    def test_resolution_flagged_applies_penalty(self):
        issue = _issue()
        config = RuleConfig()
        with_flag = score_issue(issue, "FUTURE", USER, resolution_flagged=True, config=config)
        without_flag = score_issue(issue, "FUTURE", USER, resolution_flagged=False, config=config)
        assert with_flag.score == without_flag.score + config.resolution_not_done_penalty
        assert "HAS_RESOLUTION_NOT_DONE" in with_flag.reasons

    def test_newsletter_text_scores_negative(self):
        issue = _issue(title="Newsletter", description="Unsubscribe from our digest.")
        result = score_issue(issue, "NO_DEADLINE", USER, resolution_flagged=False, config=RuleConfig())
        assert "NEWSLETTER" in result.reasons
        assert result.score < 0

    def test_weights_are_configurable(self):
        issue = _issue()
        custom = RuleConfig(action_score=1000)
        result = score_issue(issue, "FUTURE", USER, resolution_flagged=False, config=custom)
        assert result.score >= 1000


class TestExtractEvidence:
    def test_returns_sentence_matching_action_or_deadline(self):
        issue = _issue(description="Không liên quan gì. Đội cần nộp trước thứ Sáu. Câu khác.")
        assert extract_evidence(issue) == "Đội cần nộp trước thứ Sáu."

    def test_falls_back_to_title_when_no_sentence_matches(self):
        issue = _issue(title="Chỉ để tham khảo", description="Không có tín hiệu gì đặc biệt ở đây.")
        assert extract_evidence(issue) == "Chỉ để tham khảo"


class TestDecideFromScore:
    def test_keep_when_at_or_above_threshold(self):
        from src.services.jira_rules import ScoreResult

        config = RuleConfig()
        decision = decide_from_score(ScoreResult(score=config.keep_threshold, reasons=("HAS_ACTION",)), config)
        assert decision.decision == "KEEP"
        assert decision.rule_version == config.rule_version

    def test_review_when_between_thresholds(self):
        from src.services.jira_rules import ScoreResult

        config = RuleConfig()
        decision = decide_from_score(ScoreResult(score=config.review_threshold, reasons=("HAS_ACTION",)), config)
        assert decision.decision == "REVIEW"

    def test_drop_when_below_review_threshold(self):
        from src.services.jira_rules import ScoreResult

        config = RuleConfig()
        decision = decide_from_score(ScoreResult(score=0, reasons=()), config)
        assert decision.decision == "DROP"
        assert decision.reasons == ("NO_ACTION_REQUIRED",)


class TestEvaluateIssueIntegration:
    def test_worked_example_to04_42_results_in_keep(self):
        issue = _issue()
        decision, evidence = evaluate_issue(issue, USER, now=datetime(2026, 8, 11, tzinfo=UTC))

        assert decision.decision == "KEEP"
        assert decision.score == 85
        assert set(decision.reasons) == {
            "HAS_ACTION",
            "HAS_DEADLINE",
            "ASSIGNED_TO_CURRENT_USER",
            "HIGH_PRIORITY",
            "DUE_SOON",
        }
        assert evidence == "Đội cần nộp trước thứ Sáu."

    def test_done_issue_is_dropped_before_scoring_and_has_no_evidence(self):
        issue = _issue(status_category="Done")
        decision, evidence = evaluate_issue(issue, USER, now=datetime(2026, 8, 11, tzinfo=UTC))

        assert decision.decision == "DROP"
        assert decision.reasons == ("STATUS_DONE",)
        assert decision.score == 0
        assert evidence == ""

    @pytest.mark.parametrize("account_id", ["acc-someone-else", None])
    def test_issue_not_assigned_to_current_user_is_dropped_before_scoring(self, account_id):
        """Hợp đồng ĐÃ ĐẢO so với bản đầu (2026-08-21, quyết định của chủ sở
        hữu sản phẩm).

        Trước đây issue của người khác vẫn KEEP được nhờ điểm số
        (HAS_ACTION + HAS_DEADLINE + HIGH_PRIORITY + DUE_SOON = 70). Nay hộp
        việc chỉ chứa việc của chính người dùng — tương đương luật
        `not_addressed` đã áp cho mail: việc giao cho người khác không phải
        việc của tôi, dù hạn có gấp tới đâu.

        Issue chưa ai nhận (`None`) cũng bị loại. Muốn giữ lại nhóm đó thì nới
        đúng nhánh `assignee_account_id is None` trong `hard_filter`.
        """
        issue = _issue(assignee_account_id=account_id)
        decision, evidence = evaluate_issue(issue, USER, now=datetime(2026, 8, 11, tzinfo=UTC))

        assert decision.decision == "DROP"
        assert decision.reasons == ("NOT_ASSIGNED_TO_ME",)
        assert evidence == ""

    def test_issue_of_someone_else_survives_when_it_mentions_me(self):
        """Người khác làm nhưng cần mình trả lời — Jira nhúng mention dạng
        `[~accountid:xxx]`, đối chiếu thẳng accountId chứ không dò tên hiển
        thị (tên trùng nhau là chuyện thường)."""
        issue = _issue(
            assignee_account_id="acc-someone-else",
            description=f"Nhờ [~accountid:{USER.account_id}] xác nhận trước thứ Sáu.",
        )
        decision, _ = evaluate_issue(issue, USER, now=datetime(2026, 8, 11, tzinfo=UTC))

        assert decision.decision != "DROP"

    def test_the_rule_is_skipped_when_no_current_user_is_known(self):
        """`hard_filter` còn được gọi trực tiếp ở vài đường không có ngữ cảnh
        người dùng — thiếu `user` thì luật này phải im lặng bỏ qua, không loại
        sạch mọi issue."""
        issue = _issue(assignee_account_id="acc-someone-else")

        assert not hard_filter(issue).dropped
