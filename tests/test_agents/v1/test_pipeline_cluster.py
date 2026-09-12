from datetime import UTC, datetime

from src.agents.pipeline.nodes.cluster import cluster_node


def _resolved_item(
    message_id: str,
    title: str,
    due_at=None,
    ambiguous: bool = False,
    assignee: str | None = None,
    assignee_ambiguous: bool = True,
) -> dict:
    return {
        "message": {"id": message_id},
        "title": title,
        "due_at": due_at,
        "ambiguous": ambiguous,
        "assignee": assignee,
        "assignee_ambiguous": assignee_ambiguous,
        "evidence_quote": f"quote for {message_id}",
    }


def test_cluster_groups_similar_titles_on_same_day():
    due = datetime(2026, 8, 14, 9, 0, tzinfo=UTC)
    state = {
        "user_id": "1",
        "resolved": [
            _resolved_item("m1", "Nộp báo cáo tuần trước thứ Sáu", due_at=due),
            _resolved_item("m2", "Nộp báo cáo tuần trước thứ sáu", due_at=due),
        ],
    }

    result = cluster_node(state)

    assert len(result["clusters"]) == 1
    assert result["clusters"][0]["source_count"] == 2


def test_cluster_keeps_dissimilar_titles_separate():
    state = {
        "user_id": "1",
        "resolved": [
            _resolved_item("m1", "Nộp báo cáo tuần"),
            _resolved_item("m2", "Chuẩn bị demo sản phẩm"),
        ],
    }

    result = cluster_node(state)

    assert len(result["clusters"]) == 2


def test_cluster_key_is_stable_for_same_user_title_and_due_date():
    due = datetime(2026, 8, 14, 9, 0, tzinfo=UTC)
    state = {"user_id": "42", "resolved": [_resolved_item("m1", "Nộp báo cáo", due_at=due)]}

    first = cluster_node(state)["clusters"][0]["cluster_key"]
    second = cluster_node(state)["clusters"][0]["cluster_key"]

    assert first == second


def test_cluster_carries_assignee_when_one_source_confirms_it():
    # 1 nguồn xác nhận assignee là đủ cho cả cụm, kể cả khi nguồn kia mơ hồ —
    # cùng tinh thần "nhiều nguồn xác nhận, không cần TẤT CẢ" của signal_strength.
    due = datetime(2026, 8, 14, 9, 0, tzinfo=UTC)
    state = {
        "user_id": "1",
        "resolved": [
            _resolved_item(
                "m1", "Nộp báo cáo tuần 3", due_at=due, assignee="phong@student.mondaiy.vn", assignee_ambiguous=False
            ),
            _resolved_item("m2", "Nộp báo cáo tuần 3", due_at=due, assignee=None, assignee_ambiguous=True),
        ],
    }

    cluster = cluster_node(state)["clusters"][0]

    assert cluster["assignee"] == "phong@student.mondaiy.vn"
    assert cluster["assignee_ambiguous"] is False


def test_cluster_keeps_same_title_but_conflicting_due_dates_separate():
    # Ràng buộc TAPB-129: 2 nguồn nói khác nhau (deadline lệch >24h dù tiêu đề
    # giống nhau) không được gộp đè lên nhau — phải giữ cả hai cluster riêng.
    due_a = datetime(2026, 8, 14, 9, 0, tzinfo=UTC)
    due_b = datetime(2026, 8, 20, 9, 0, tzinfo=UTC)
    state = {
        "user_id": "1",
        "resolved": [
            _resolved_item("m1", "Nộp báo cáo tuần 3", due_at=due_a),
            _resolved_item("m2", "Nộp báo cáo tuần 3", due_at=due_b),
        ],
    }

    clusters = cluster_node(state)["clusters"]

    assert len(clusters) == 2
    due_dates = {c["due_at"] for c in clusters}
    assert due_dates == {due_a, due_b}
    message_ids = {item["message"]["id"] for c in clusters for item in c["items"]}
    assert message_ids == {"m1", "m2"}


def test_cluster_assignee_ambiguous_when_no_source_confirms_it():
    state = {
        "user_id": "1",
        "resolved": [_resolved_item("m1", "Đăng ký slot demo", assignee=None, assignee_ambiguous=True)],
    }

    cluster = cluster_node(state)["clusters"][0]

    assert cluster["assignee"] is None
    assert cluster["assignee_ambiguous"] is True
