import uuid
from datetime import UTC, datetime

from src.agents.tools.core_tools import (
    discord_list_announcements,
    reset_search_scope,
    set_search_scope,
)
from src.db import SessionLocal
from src.models.evidence import SourceItem, SourceScope
from src.services.intent_router import ToolPlanContext, plan_tool_calls


def _seed_announcement(suffix: str) -> int:
    """Tạo một kênh thông báo kèm một tin, trả về scope_id để cấp quyền cho test."""
    now = datetime.now(UTC)
    with SessionLocal() as db:
        scope = SourceScope(provider="discord", external_id=f"tool-ann-{suffix}", name="thông-báo", kind=5)
        db.add(scope)
        db.flush()
        db.add(
            SourceItem(
                provider="discord",
                external_id=f"tool-ann-item-{suffix}",
                scope_id=scope.id,
                author_external_id="btc",
                author_name="BTC AI20K",
                content="Hạn nộp Gate 2 dời sang 23h59 ngày 20/08, mọi người lưu ý giúp",
                item_type=0,
                deep_link="https://discord.com/channels/g/c/m",
                content_hash=f"tool-ann-hash-{suffix}",
                source_updated_at=now,
                observed_at=now,
                run_id="test",
            )
        )
        db.commit()
        return scope.id


def test_tool_tu_choi_khi_chua_dat_pham_vi():
    reset_search_scope()
    ket_qua = discord_list_announcements.invoke({})
    assert "phạm vi" in ket_qua.lower()


def test_hoc_vien_chua_khop_danh_tinh_duoc_bao_dung_ly_do():
    """Mức B/C có phạm vi rỗng — phải nói là chưa được cấp kênh, không phải 'không có thông báo'."""
    set_search_scope([])
    try:
        ket_qua = discord_list_announcements.invoke({})
    finally:
        reset_search_scope()
    assert "chưa được cấp kênh" in ket_qua


def test_tra_ve_thong_bao_kem_nguon_va_ly_do():
    scope_id = _seed_announcement(uuid.uuid4().hex)
    set_search_scope([scope_id])
    try:
        ket_qua = discord_list_announcements.invoke({})
    finally:
        reset_search_scope()
    assert "Gate 2" in ket_qua
    assert "nguồn: https://discord.com/channels" in ket_qua
    assert "kênh thông báo" in ket_qua


def test_moc_thoi_gian_khong_hieu_thi_dung_lai():
    set_search_scope([1])
    try:
        ket_qua = discord_list_announcements.invoke({"since": "tuần rồi ấy"})
    finally:
        reset_search_scope()
    assert "không hiểu được mốc thời gian" in ket_qua.lower()


def _plan(query: str, tool_calls: list[dict] | None = None) -> list[str]:
    planned = plan_tool_calls(
        tool_calls or [],
        ToolPlanContext(query=query, now=datetime.now(UTC)),
    )
    return [call["name"] for call in planned]


def test_router_doi_cau_hoi_thong_bao_sang_dung_tool():
    assert _plan("chương trình có thông báo gì mới không") == ["discord_list_announcements"]
    # "đổi lịch" chạm cả luật Calendar, và để cả hai cùng chạy là đúng: cái nào
    # cũng chỉ đọc. Điều phải đúng là truy hồi chung bị thay bằng luồng thông báo.
    doi_lich = _plan(
        "có đổi lịch buổi nào không",
        [{"name": "discord_search_program", "args": {"query": "đổi lịch"}, "id": "x"}],
    )
    assert "discord_list_announcements" in doi_lich
    assert "discord_search_program" not in doi_lich


def test_router_van_uu_tien_cau_hoi_ca_nhan_hon_thong_bao():
    """Hỏi 'tôi đã nhắn gì' thì danh tính người hỏi quan trọng hơn luồng thông báo."""
    assert _plan("tôi đã nhắn gì về thông báo hôm qua") == ["discord_search_my_messages"]


def test_router_khong_dung_tool_thong_bao_cho_cau_hoi_thuong():
    assert _plan("nhóm đã chốt kiến trúc thế nào") == ["discord_search_program"]
