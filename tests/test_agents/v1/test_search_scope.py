"""Chốt chặn phạm vi của bộ tool Discord crawl.

Đây là ranh giới quyền: retrieval.py ghi rõ bộ lọc quyền do tầng gọi đặt, không
để LLM sinh ra. Nếu công cụ chạy khi chưa ai đặt phạm vi thì nó sẽ đọc toàn bộ
kho của mọi người, và hỏng kiểu đó không có dấu hiệu gì để phát hiện.
"""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from src.agents.tools import core_tools
from src.agents.tools.core_tools import (
    discord_get_my_activity,
    discord_search_my_messages,
    discord_search_program,
    reset_search_scope,
    set_search_scope,
)


@pytest.fixture(autouse=True)
def _pham_vi_sach():
    reset_search_scope()
    yield
    reset_search_scope()


def test_tu_choi_tim_khi_chua_dat_pham_vi():
    ket_qua = discord_search_program.invoke({"query": "prompt injection"})
    assert "Chưa xác định được phạm vi" in ket_qua


def test_khong_goi_truy_hoi_khi_chua_dat_pham_vi(monkeypatch):
    da_goi = False

    def _khong_duoc_goi(*args, **kwargs):
        nonlocal da_goi
        da_goi = True
        return []

    monkeypatch.setattr("src.services.retrieval.retrieve", _khong_duoc_goi)
    discord_search_program.invoke({"query": "bất kỳ"})
    assert da_goi is False


def test_truyen_dung_pham_vi_xuong_tang_truy_hoi(monkeypatch):
    ghi_nhan = {}

    def _gia_lap(engine, question, filters, k=10, db=None):
        ghi_nhan["scope_ids"] = filters.scope_ids
        ghi_nhan["question"] = question
        return []

    monkeypatch.setattr("src.services.retrieval.retrieve", _gia_lap)
    set_search_scope([7, 9])
    discord_search_program.invoke({"query": "hạn nộp"})

    assert ghi_nhan["scope_ids"] == [7, 9]
    assert ghi_nhan["question"] == "hạn nộp"


def test_khong_lo_loi_ky_thuat_khi_truy_hoi_hong(monkeypatch):
    def _no(*args, **kwargs):
        raise RuntimeError("mất kết nối")

    monkeypatch.setattr("src.services.retrieval.retrieve", _no)
    set_search_scope(None)
    ket_qua = discord_search_program.invoke({"query": "x"})
    assert "Không tìm được trong dữ liệu Discord" in ket_qua
    assert "mất kết nối" not in ket_qua


def test_ket_qua_luon_ghi_ro_la_du_lieu_discord(monkeypatch):
    monkeypatch.setattr(
        "src.services.retrieval.retrieve",
        lambda *args, **kwargs: [
            SimpleNamespace(
                channel="#announcements",
                occurred_at=datetime(2026, 8, 11, 9, 30, tzinfo=UTC),
                text="Mentor nhắc review bản demo.",
                deep_link="https://discord.com/channels/example/message",
            )
        ],
    )
    set_search_scope([7])

    ket_qua = discord_search_program.invoke({"query": "review demo"})

    assert ket_qua.startswith("[Discord #announcements · 11/08/2026 16:30]")


def test_pham_vi_khong_nam_trong_chu_ky_cong_cu():
    # Model được truyền query và cửa sổ thời gian — đó là thu hẹp câu hỏi, ai
    # hỏi cũng thu hẹp được, không phải quyền. Phạm vi quyền (scope_ids) thì
    # tuyệt đối không, vì model tự đặt được nghĩa là tự đọc kho của người khác.
    # So khớp cả tập chứ không chỉ kiểm scope_ids: tham số mới nào lọt vào cũng
    # phải có người đọc lại xem nó có phải quyền trá hình không.
    assert core_tools.discord_search_program.name == "discord_search_program"
    assert set(core_tools.discord_search_program.args) == {"query", "since", "until"}
    assert set(core_tools.discord_search_my_messages.args) == {"query", "since", "until"}
    assert set(core_tools.discord_get_my_activity.args) == {"since", "until"}


def test_personal_tools_require_backend_identity_and_never_accept_author_id(monkeypatch):
    set_search_scope([7])
    result = discord_search_my_messages.invoke({"query": "Jira"})
    assert "chưa kết nối danh tính Discord" in result

    captured = {}
    monkeypatch.setattr(
        "src.services.discord_messages.search_my_discord_messages",
        lambda engine, **kwargs: captured.update(kwargs) or [],
    )
    set_search_scope([7], author_external_id="oauth-snowflake")
    discord_search_my_messages.invoke({"query": "Jira"})
    assert captured["author_external_id"] == "oauth-snowflake"
    assert "author_external_id" not in core_tools.discord_search_my_messages.args


def test_activity_tool_uses_same_locked_identity(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "src.services.discord_messages.get_my_discord_activity",
        lambda engine, **kwargs: captured.update(kwargs) or [],
    )
    set_search_scope([3, 4], author_external_id="oauth-user")
    discord_get_my_activity.invoke({})
    assert captured["scope_ids"] == [3, 4]
    assert captured["author_external_id"] == "oauth-user"
