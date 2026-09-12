"""Gộp việc trùng theo MÃ ISSUE — xuyên nguồn và xuyên ngày.

Jira nhắc hạn mỗi ngày một thư, mỗi thư một threadId riêng, nội dung y hệt chỉ
khác ngày. Bám theo thread thì mỗi ngày đẻ thêm một task cho cùng một việc. Và
khi cả Jira lẫn thư nhắc cùng có mặt, bản Jira mới là bản đầy đủ — thư chỉ liệt
kê tên việc.
"""

from datetime import UTC, datetime, timedelta

from src.agents.pipeline.nodes.cluster import cluster_node

BASE = datetime(2026, 8, 22, 1, 0, tzinfo=UTC)
KEYS = ["TAPB-81", "TAPB-114", "TAPB-127", "TAPB-131"]


def _digest_mail(day_offset: int) -> dict:
    """Thư tổng hợp Jira gửi hằng ngày, liệt kê 4 việc còn treo."""
    day = BASE - timedelta(days=day_offset)
    subject = f"[Jira][T004] 4 công việc cần cập nhật • {day:%d/%m/%Y}"
    return {
        "title": f"Cần xem lại — có hạn và yêu cầu hành động: {subject}",
        "due_at": None,
        "message": {
            "id": f"mail-{day_offset}",
            "provider": "google",
            "thread_id": f"thread-{day_offset}",
            "author_id": "jira@vinait004.atlassian.net",
            "subject": subject,
            "text": " ".join(KEYS),
            "sent_at": day,
        },
    }


def _jira_issue(key: str, title: str | None = None) -> dict:
    return {
        "title": title or f"[Sprint] {key} việc thật",
        "due_at": None,
        "message": {
            "id": key,
            "provider": "jira",
            "thread_id": key,
            "author_id": "acc-hoaian",
            "sent_at": BASE - timedelta(days=5),
        },
    }


def _cluster(resolved: list[dict]) -> list[dict]:
    return cluster_node({"user_id": "1", "resolved": resolved})["clusters"]


def test_daily_reminder_mails_collapse_into_one_task():
    """7 thư nhắc = 7 threadId khác nhau, nhưng chỉ là một việc."""
    clusters = _cluster([_digest_mail(i) for i in range(7)])

    assert len(clusters) == 1
    assert clusters[0]["source_count"] == 7


def test_a_digest_mail_is_dropped_when_jira_already_has_every_issue():
    """Thư tổng hợp nhắc 4 việc mà cả 4 đều đã có issue Jira thật: bỏ hẳn.

    Gộp nó vào một trong bốn issue là sai (nó nói về cả bốn); để nguyên thì
    người dùng có thêm một task "4 công việc cần cập nhật" chồng lên 4 task thật.
    """
    resolved = [_digest_mail(i) for i in range(7)] + [_jira_issue(key) for key in KEYS]

    clusters = _cluster(resolved)

    assert len(clusters) == 4
    for cluster in clusters:
        providers = {(item["message"] or {}).get("provider") for item in cluster["items"]}
        assert providers == {"jira"}


def test_a_digest_mail_survives_when_jira_is_not_connected():
    """Không có issue Jira nào thì thư nhắc là nguồn tin duy nhất — bỏ nó đi là
    mất trắng việc."""
    resolved = [_digest_mail(0), _jira_issue("TAPB-999")]

    clusters = _cluster(resolved)

    assert len(clusters) == 2


def test_a_mail_about_one_issue_merges_with_that_issue():
    """Định danh xuyên nguồn: thư nói về TAPB-178 và issue TAPB-178 là một việc."""
    mail = _digest_mail(0)
    mail["title"] = "[JIRA] (TAPB-178) lỗi đăng nhập trên web mobile"
    mail["message"]["subject"] = mail["title"]
    mail["message"]["text"] = "TAPB-178 cần sửa gấp"

    clusters = _cluster([mail, _jira_issue("TAPB-178")])

    assert len(clusters) == 1
    providers = {(item["message"] or {}).get("provider") for item in clusters[0]["items"]}
    assert providers == {"google", "jira"}


def test_the_jira_wording_wins_over_the_mail_reminder():
    """Issue mang mô tả đầy đủ; thư nhắc chỉ có tên việc."""
    mail = _digest_mail(0)
    mail["title"] = "Nhắc: TAPB-178 sắp tới hạn"
    mail["message"]["subject"] = mail["title"]
    mail["message"]["text"] = "TAPB-178"

    clusters = _cluster([mail, _jira_issue("TAPB-178", title="Sửa lỗi đăng nhập trên web mobile")])

    assert clusters[0]["title"] == "Sửa lỗi đăng nhập trên web mobile"


def test_issue_keys_beat_similar_titles():
    """Bảng thật có cụm "[Cadence] Weekly report W3/W4/W5/W6" chỉ khác một ký
    tự. Luật gộp thư-nhắc-lặp-lại từng kéo chúng vào chung một task."""
    resolved = [
        _jira_issue("TAPB-90", title="[Cadence] Weekly report W3 (T4 12:00)"),
        _jira_issue("TAPB-91", title="[Cadence] Weekly report W4 (T4 12:00)"),
        _jira_issue("TAPB-92", title="[Cadence] Weekly report W5 (T4 12:00)"),
    ]

    clusters = _cluster(resolved)

    assert len(clusters) == 3


def test_the_cluster_key_survives_a_new_reminder_the_next_day():
    """cluster_key phải ổn định xuyên ngày, nếu không resync sẽ tạo task mới."""
    today = _cluster([_digest_mail(0)])[0]["cluster_key"]
    tomorrow = _cluster([_digest_mail(0), _digest_mail(1)])[0]["cluster_key"]

    assert today == tomorrow
