from src.services.profile_memory import extract_profile_mutation


def test_extracts_only_explicit_profile_facts():
    mutation = extract_profile_mutation("Tôi tên là An và tôi thích câu trả lời ngắn gọn. Tôi là một học viên.")

    assert mutation.updates == {
        "display_name": "An",
        "response_style": "ngắn gọn",
        "role": "học viên",
    }


def test_work_claim_does_not_become_profile_memory():
    mutation = extract_profile_mutation("Deadline dự án là thứ Sáu, Jira đang có ba issue và mentor yêu cầu nộp sớm.")

    assert mutation.updates == {}
    assert mutation.deleted_keys == frozenset()
    assert mutation.cleared_all is False


def test_explicit_forget_name_wins_over_name_in_same_message():
    mutation = extract_profile_mutation("Đừng nhớ tên tôi nữa, dù trước đó tôi tên là An.")

    assert mutation.updates == {}
    assert mutation.deleted_keys == frozenset({"display_name", "preferred_name"})


def test_explicit_clear_profile_clears_everything():
    mutation = extract_profile_mutation("Hãy xóa bộ nhớ profile của tôi.")

    assert mutation.cleared_all is True
