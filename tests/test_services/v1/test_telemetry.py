import logging

from src.services import telemetry


def test_allowlist_matches_prd_event_names():
    # Bảng PRD §13 là nguồn chuẩn; thiếu một sự kiện ở đây là im lặng mất số liệu.
    prd = {
        "capture_enqueued",
        "capture_synced",
        "capture_failed",
        "memory_candidate_created",
        "memory_status_changed",
        "brief_generated",
        "brief_opened",
        "ask_submitted",
        "answer_rendered",
        "answer_feedback",
        "action_draft_created",
        "action_confirmed",
        "calendar_handoff_opened",
        "consent_changed",
    }
    assert prd <= set(telemetry.ALLOWED_ATTRS)


def test_blocks_attribute_outside_allowlist():
    kept, blocked = telemetry._filter_attrs("answer_rendered", {"citation_count": 3, "question": "hạn nộp là khi nào"})
    assert kept == {"citation_count": 3}
    assert blocked == ["question"]


def test_unknown_event_keeps_nothing():
    kept, blocked = telemetry._filter_attrs("khong_co_trong_prd", {"a": 1})
    assert kept == {}
    assert blocked == ["a"]


def test_emit_refuses_unknown_event():
    assert telemetry.emit(None, "khong_co_trong_prd", a=1) is None


def test_emit_drops_content_and_never_logs_its_value(caplog):
    with caplog.at_level(logging.WARNING):
        ev = telemetry.emit(None, "answer_rendered", citation_count=1, answer_text="bí mật")
    assert ev is not None
    assert ev.attributes == {"citation_count": 1}
    # Cảnh báo chỉ được nêu tên trường bị chặn, không được in giá trị.
    assert "answer_text" in caplog.text
    assert "bí mật" not in caplog.text


def test_trace_id_shared_across_events():
    tid = telemetry.start_trace(surface="discord", user_id="u1")
    a = telemetry.emit(None, "ask_submitted", intent="deadline")
    b = telemetry.emit(None, "answer_rendered", citation_count=0, abstained=True)
    assert a.trace_id == b.trace_id == tid
    assert a.surface == b.surface == "discord"
    assert a.user_id == "u1"


def test_timed_records_latency_even_when_body_raises():
    telemetry.start_trace()
    ghi: list = []
    goc = telemetry.emit
    telemetry.emit = lambda db, name, **kw: ghi.append((name, kw))  # type: ignore[assignment]
    try:
        try:
            with telemetry.timed(None, "retrieval_ran"):
                raise ValueError("hỏng giữa chừng")
        except ValueError:
            pass
    finally:
        telemetry.emit = goc  # type: ignore[assignment]

    assert ghi and ghi[0][0] == "retrieval_ran"
    assert "latency" in ghi[0][1]
