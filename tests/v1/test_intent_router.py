from datetime import UTC, datetime

from src.services.intent_router import (
    GmailIntent,
    ToolPlanContext,
    ToolRisk,
    calendar_window,
    gmail_window,
    plan_tool_calls,
    route_calendar_intent,
    route_gmail_intent,
)
from src.services.temporal_understanding import resolve_temporal


def test_calendar_summary_routes_to_search_tool():
    plan = route_calendar_intent("tóm tắt lịch tháng 8 trên calendar")
    assert plan.intent.value == "summary"
    assert plan.tool == "calendar_search_events"
    assert plan.risk.value == "read"


def test_calendar_create_requires_approval():
    plan = route_calendar_intent("tạo event họp mentor ngày mai")
    assert plan.tool == "calendar_create_event"
    assert plan.needs_clarification is True
    assert plan.risk.value == "external_write"


def test_calendar_delete_is_destructive():
    plan = route_calendar_intent("xóa event này trên calendar")
    assert plan.tool == "calendar_delete_event"
    assert plan.risk.value == "destructive"


def test_general_chat_does_not_call_gmail():
    plan = route_gmail_intent("hi")
    assert plan.intent == GmailIntent.NONE
    assert plan.tool is None


def test_summary_routes_to_search_with_rest_fallback():
    plan = route_gmail_intent("tóm tắt nội dung ngày 8-8-2026 trên gmail")
    assert plan.intent == GmailIntent.SUMMARY
    assert plan.tool == "gmail_search_emails"
    assert plan.fallback_tool == "search_gmail"
    assert plan.risk == ToolRisk.READ


def test_thread_attachment_and_writes_are_distinct():
    assert route_gmail_intent("đọc thread Gmail này").tool == "gmail_read_email_thread"
    assert route_gmail_intent("đọc file đính kèm trong email Gmail").tool == "gmail_read_attachment"
    assert route_gmail_intent("soạn email Gmail cho mentor").tool == "gmail_create_draft"
    assert route_gmail_intent("xóa email Gmail").risk == ToolRisk.DESTRUCTIVE


def test_gmail_mention_without_operation_clarifies():
    plan = route_gmail_intent("Gmail của tôi")
    assert plan.intent == GmailIntent.NONE
    assert plan.needs_clarification is True


def test_luat_dieu_huong_agent_khop_ca_khi_go_khong_dau():
    """Regression: luật cũ nằm trong node và chỉ khớp chữ có dấu.

    Người gõ nhanh thường bỏ dấu. Trước khi gộp về đây, "tom tat hom nay" trượt
    hết luật nên câu trả lời chỉ có mốc ngày mà không có nội dung nguồn.
    """
    now = datetime(2026, 8, 10, 9, 30, tzinfo=UTC)

    co_dau = plan_tool_calls([], ToolPlanContext(query="Tóm tắt hôm nay có gì", now=now))
    khong_dau = plan_tool_calls([], ToolPlanContext(query="Tom tat hom nay co gi", now=now))

    assert [call["name"] for call in co_dau] == [call["name"] for call in khong_dau]
    # Cả hai đều phải bị đóng khung vào đúng ngày hôm nay theo múi giờ ứng dụng.
    discord_co_dau = next(c for c in co_dau if c["name"] == "discord_search_program")
    discord_khong_dau = next(c for c in khong_dau if c["name"] == "discord_search_program")
    assert discord_co_dau["args"]["since"] == discord_khong_dau["args"]["since"]
    assert discord_co_dau["args"]["since"] == "2026-08-10T00:00:00+00:00"


def test_cua_so_gmail_va_calendar_doc_duoc_chu_khong_dau():
    now = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)

    assert gmail_window("tuan nay", now) == gmail_window("tuần này", now)
    assert calendar_window("ngay mai", now) == calendar_window("ngày mai", now)


def test_cau_hoi_chuong_trinh_mai_phai_lam_gi_la_agenda():
    """Regression: không nhầm "phải làm" thành cụm tìm kiếm "AI là"."""
    now = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)
    query = "Chương trình AI thực chiến mai tôi phải làm gì"

    planned = plan_tool_calls([], ToolPlanContext(query=query, now=now))

    assert resolve_temporal(query, now).kind == "tomorrow"
    assert [call["name"] for call in planned] == [
        "list_tasks",
        "calendar_search_events",
        "gmail_deadline_sweep",
        "jira_search_issues",
        "discord_search_program",
    ]
    calendar = next(call for call in planned if call["name"] == "calendar_search_events")
    assert calendar["args"]["time_from"] == "2026-08-17T00:00:00+00:00"
    assert calendar["args"]["time_to"] == "2026-08-18T00:00:00+00:00"
    jira = next(call for call in planned if call["name"] == "jira_search_issues")
    assert jira["args"] == {
        "query": "",
        "due_after": "2026-08-17T00:00:00+00:00",
        "due_before": "2026-08-18T00:00:00+00:00",
    }


def test_agenda_dong_khung_ca_loi_goi_jira_do_model_de_xuat():
    now = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)

    planned = plan_tool_calls(
        [{"name": "jira_search_issues", "args": {}, "id": "model-jira"}],
        ToolPlanContext(query="mai tôi cần làm gì", now=now),
    )

    jira = next(call for call in planned if call["name"] == "jira_search_issues")
    assert jira["args"] == {
        "query": "",
        "due_after": "2026-08-17T00:00:00+00:00",
        "due_before": "2026-08-18T00:00:00+00:00",
    }


def test_cau_hoi_chi_can_nho_lai_thi_khong_tra_nguon():
    """Hỏi tên mình thì không có lý do gì phải quét kho Discord."""
    now = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)

    assert plan_tool_calls([], ToolPlanContext(query="Tôi tên gì?", now=now)) == []
    assert plan_tool_calls([], ToolPlanContext(query="Toi ten gi?", now=now)) == []


def test_khong_goi_lai_tool_da_quan_sat_voi_dung_tham_so():
    now = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
    de_xuat = [{"name": "list_tasks", "args": {"status": "proposed"}, "id": "x"}]
    da_chay = [{"name": "list_tasks", "args": {"status": "proposed"}, "output": "..."}]

    ket_qua = plan_tool_calls(de_xuat, ToolPlanContext(query="còn việc gì", now=now, observations=da_chay))

    assert ket_qua == []


def test_cau_hoi_tin_nhan_discord_cua_toi_dung_tool_da_khoa_danh_tinh():
    now = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
    model_de_xuat = [{"name": "discord_search_program", "args": {"query": "An đã nói gì"}, "id": "mixed"}]

    ket_qua = plan_tool_calls(
        model_de_xuat,
        ToolPlanContext(
            query="Tôi đã nhắn gì trên Discord?",
            now=now,
            available_tools=frozenset(
                {"discord_search_program", "discord_search_my_messages", "discord_get_my_activity"}
            ),
        ),
    )

    assert ket_qua == [
        {
            "name": "discord_search_my_messages",
            "args": {"query": "Tôi đã nhắn gì trên Discord?"},
            "id": "mixed",
        }
    ]


def test_incoming_updates_do_not_match_my_authored_discord_messages():
    now = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)

    announcements = plan_tool_calls(
        [],
        ToolPlanContext(query="Tôi nhận được thông báo gì mới?", now=now),
    )
    gmail = plan_tool_calls(
        [{"name": "gmail_search_emails", "args": {}, "id": "gmail"}],
        ToolPlanContext(query="Tôi nhận email gì hôm nay?", now=now),
    )

    assert [call["name"] for call in announcements] == ["discord_list_announcements"]
    assert "discord_search_my_messages" not in [call["name"] for call in gmail]

def test_cau_khong_lien_quan_discord_khong_bi_gan_tool_tin_nhan_ca_nhan():
    """Regression: "tôi đã viết…" là động từ chung, không riêng cho nhắn tin
    Discord. Không có từ khóa discord/tin nhắn/kênh gần đó thì không được tự
    thêm discord_search_my_messages vào kế hoạch tool.
    """
    now = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
    model_de_xuat = [{"name": "list_tasks", "args": {"status": "proposed"}, "id": "x"}]

    ket_qua = plan_tool_calls(
        model_de_xuat,
        ToolPlanContext(
            query="Tôi đã viết yêu cầu này trong Jira rồi, kiểm tra giúp em",
            now=now,
        ),
    )

    ten_tool = [call["name"] for call in ket_qua]
    assert "discord_search_my_messages" not in ten_tool


def test_nhan_diem_bai_tap_khong_bi_hieu_nham_thanh_hoat_dong_discord():
    """Regression: "nhắn" (message) và "nhận" (receive) đều rụng dấu về "nhan".
    "tôi nhận bao nhiêu điểm bài tập" nói về điểm số, không phải hoạt động
    nhắn tin trên Discord, nên không được route vào discord_get_my_activity.
    """
    now = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
    model_de_xuat = [{"name": "list_tasks", "args": {"status": "proposed"}, "id": "x"}]

    ket_qua = plan_tool_calls(
        model_de_xuat,
        ToolPlanContext(query="tôi nhận bao nhiêu điểm bài tập", now=now),
    )

    ten_tool = [call["name"] for call in ket_qua]
    assert "discord_get_my_activity" not in ten_tool


def test_router_khong_tra_tool_khong_duoc_agent_cung_cap():
    now = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)

    ket_qua = plan_tool_calls(
        [],
        ToolPlanContext(
            query="Tìm thông tin chương trình",
            now=now,
            available_tools=frozenset({"list_tasks"}),
        ),
    )

    assert ket_qua == []


def test_gmail_bridge_is_opt_in_and_does_not_replace_existing_sweep(monkeypatch):
    from src.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "anythingllm_gmail_bridge_enabled", True)
    monkeypatch.setattr(settings, "anythingllm_gmail_bridge_user_id", "user-1")
    calls = plan_tool_calls(
        [],
        ToolPlanContext(
            query="Email deadline month 8",
            now=datetime(2026, 8, 12, 9, 0, tzinfo=UTC),
            available_tools=frozenset({"gmail_deadline_sweep", "gmail_bridge_search"}),
        ),
    )
    names = [call["name"] for call in calls]
    assert names == ["gmail_deadline_sweep", "gmail_bridge_search"]
    assert calls[1]["args"]["time_from"].startswith("2026-08-01T00:00:00")


def test_temporal_windows_cover_relative_month_and_week_cases():
    now = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)

    assert gmail_window("tuần này", now) == ("2026-08-10T00:00:00+00:00", "2026-08-17T00:00:00+00:00")
    assert gmail_window("tuần sau", now) == ("2026-08-17T00:00:00+00:00", "2026-08-24T00:00:00+00:00")
    assert gmail_window("tháng này", now) == ("2026-08-01T00:00:00+00:00", "2026-09-01T00:00:00+00:00")
    assert gmail_window("tháng sau", now) == ("2026-09-01T00:00:00+00:00", "2026-10-01T00:00:00+00:00")
    assert gmail_window("tháng 7 năm 2026", now) == ("2026-07-01T00:00:00+00:00", "2026-08-01T00:00:00+00:00")
