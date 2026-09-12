from datetime import UTC, datetime

from src.agents.pipeline.nodes.cluster import cluster_node


def test_cluster_deduplicates_same_task_from_two_messages():
    base = {
        "title": "Submit report",
        "due_at": None,
        "ambiguous": False,
        "assignee": None,
        "evidence_quote": "submit report",
    }
    result = cluster_node(
        {
            "user_id": "u-test",
            "resolved": [
                {**base, "message": {"id": "m1"}},
                {**base, "message": {"id": "m2"}},
            ],
        }
    )

    assert len(result["clusters"]) == 1
    assert result["clusters"][0]["source_count"] == 2


def test_cluster_key_is_stable_across_runs_when_llm_title_wording_drifts():
    # Bug thật: cluster_key trước đây hash theo title LLM sinh ra — resync
    # cùng 1 mail (title bị paraphrase khác chút mỗi lần chạy) tạo cluster_key
    # khác nhau -> task trùng. Cùng thread_id (Gmail threadId ổn định) phải
    # luôn map về đúng 1 cluster_key bất kể title đổi chữ.
    item_run1 = {
        "title": "Nộp báo cáo tuần",
        "due_at": None,
        "ambiguous": False,
        "assignee": None,
        "evidence_quote": "submit report",
        "message": {"id": "m1", "provider": "google", "thread_id": "t-abc", "sent_at": datetime(2026, 8, 8, tzinfo=UTC)},
    }
    item_run2 = {
        **item_run1,
        "title": "Cần hoàn thành và nộp báo cáo tuần này",
    }

    key_run1 = cluster_node({"user_id": "u-test", "resolved": [item_run1]})["clusters"][0]["cluster_key"]
    key_run2 = cluster_node({"user_id": "u-test", "resolved": [item_run2]})["clusters"][0]["cluster_key"]

    assert key_run1 == key_run2


def test_cluster_key_differs_between_users_for_same_thread():
    item = {
        "title": "Nộp báo cáo",
        "due_at": None,
        "ambiguous": False,
        "assignee": None,
        "evidence_quote": "submit report",
        "message": {"id": "m1", "provider": "google", "thread_id": "t-abc"},
    }

    key_a = cluster_node({"user_id": "user-a", "resolved": [item]})["clusters"][0]["cluster_key"]
    key_b = cluster_node({"user_id": "user-b", "resolved": [item]})["clusters"][0]["cluster_key"]

    assert key_a != key_b


def test_cluster_groups_same_thread_even_when_titles_do_not_fuzzy_match():
    original = {
        "title": "Hoàn thành form đăng ký",
        "due_at": None,
        "ambiguous": False,
        "assignee": None,
        "evidence_quote": "please register",
        "message": {"id": "m1", "provider": "google", "thread_id": "t-xyz", "sent_at": datetime(2026, 8, 1, tzinfo=UTC)},
    }
    reply = {
        "title": "Sếp nhắc lại deadline khác hẳn nội dung ban đầu",
        "due_at": None,
        "ambiguous": False,
        "assignee": None,
        "evidence_quote": "reminder",
        "message": {"id": "m2", "provider": "google", "thread_id": "t-xyz", "sent_at": datetime(2026, 8, 5, tzinfo=UTC)},
    }

    result = cluster_node({"user_id": "u-test", "resolved": [original, reply]})

    assert len(result["clusters"]) == 1
    # Tiêu đề hiển thị lấy theo tin mới nhất trong cụm — task phản ánh đúng
    # nội dung gần nhất thay vì kẹt ở câu chữ của tin khởi tạo cụm.
    assert result["clusters"][0]["title"] == reply["title"]


def test_cluster_never_merges_two_different_threads_by_similar_title():
    """Tiêu đề lưới an toàn dùng chung tiền tố dài nên 2 mail chẳng liên quan
    vẫn đạt ratio > 0.72 và bị gộp — bug thật: task mang tiêu đề "Biên lai
    thanh toán" nhưng nội dung là review bài báo."""
    prefix = "Cần xem lại — có hạn và yêu cầu hành động: "
    state = {
        "user_id": "u1",
        "resolved": [
            {
                "title": prefix + "Biên lai thanh toán",
                "due_at": None,
                "detail": "Biên lai chuyển tiền.",
                "message": {"id": "m1", "provider": "google", "thread_id": "t-bank"},
            },
            {
                "title": prefix + "Mã OTP của bạn",
                "due_at": None,
                "detail": "Mã OTP có hiệu lực 5 phút.",
                "message": {"id": "m2", "provider": "google", "thread_id": "t-otp"},
            },
        ],
    }

    clusters = cluster_node(state)["clusters"]

    assert len(clusters) == 2
    assert {c["cluster_key"] for c in clusters}.__len__() == 2


def test_cluster_still_merges_same_thread_across_titles():
    state = {
        "user_id": "u1",
        "resolved": [
            {
                "title": "Nộp báo cáo",
                "due_at": None,
                "detail": "a",
                "message": {"id": "m1", "provider": "google", "thread_id": "t-1"},
            },
            {
                "title": "Hoàn toàn khác hẳn không giống chút nào",
                "due_at": None,
                "detail": "b",
                "message": {"id": "m2", "provider": "google", "thread_id": "t-1"},
            },
        ],
    }

    clusters = cluster_node(state)["clusters"]

    assert len(clusters) == 1
    assert clusters[0]["source_count"] == 2

