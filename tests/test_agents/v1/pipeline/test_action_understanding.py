from src.agents.pipeline.action_understanding import infer_action_hint


def test_english_and_vietnamese_direct_requests_are_rule_detected():
    assert infer_action_hint("Please review the contract by Friday.")["action_type"] == "direct_action"
    assert infer_action_hint("Vui lòng kiểm tra hợp đồng trước thứ Sáu.")["action_type"] == "direct_action"


def test_commitment_is_not_a_direct_request():
    assert infer_action_hint("I will send the report tomorrow.")["action_type"] == "commitment"
    assert infer_action_hint("Em sẽ gửi báo cáo vào ngày mai.")["action_type"] == "commitment"


def test_strong_rules_do_not_treat_unrelated_mail_as_a_todo():
    hint = infer_action_hint("The quarterly newsletter is available for your information.")

    assert hint["certainty"] == "uncertain"
    assert hint["matched_terms"] == []


def test_conditional_email_becomes_conditional_work_item_not_unconditional_todo():
    hint = infer_action_hint("Nếu khách chưa phản hồi thứ Sáu thì ping Mai.")

    assert hint["action_type"] == "conditional_action"
    assert hint["requires_user_action"] is True
    assert hint["condition"].startswith("Nếu khách")


def test_prohibition_and_waiting_are_state_items_without_user_action():
    prohibition = infer_action_hint("Đừng gửi proposal mới trước khi Legal approve.")
    waiting = infer_action_hint("Đang chờ Legal approve contract Nova.")

    assert prohibition["action_type"] == "prohibition"
    assert prohibition["requires_user_action"] is False
    assert prohibition["status"] == "blocked"
    assert waiting["action_type"] == "waiting"
    assert waiting["requires_user_action"] is False
    assert waiting["status"] == "waiting"
