"""Mọi tool trong registry phải khai được dưới strict function calling.

Vì sao có file này: `bind_tools` trước đây gọi trần, nên model chỉ bám schema
theo kiểu "cố gắng đúng" — sai tên tool hay bịa tham số không có gì chặn.
Bật `strict=True` đóng lỗ đó, nhưng strict lại từ chối những schema mà chế độ
thường vẫn nhận: thiếu `additionalProperties: false`, hoặc có field không nằm
trong `required`.

Không có test này thì một tool mới khai lỏng lẻo sẽ làm hỏng TOÀN BỘ lượt chọn
tool trên production, chứ không phải chỉ hỏng chính nó — và test đơn vị gọi thẳng
hàm tool sẽ không thấy gì, vì chúng không đi qua bước dựng schema.
"""

from __future__ import annotations

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from src.agents.nodes.core_nodes import _BASE_TOOLS, _bind_tools_strict, _tools


def _schema(tool):
    return convert_to_openai_tool(tool, strict=True)["function"].get("parameters", {})


@pytest.mark.parametrize("tool", _BASE_TOOLS, ids=lambda t: getattr(t, "name", str(t)))
def test_base_tool_khai_duoc_duoi_strict(tool) -> None:
    name = getattr(tool, "name", str(tool))
    params = _schema(tool)

    assert params.get("additionalProperties") is False, (
        f"Tool {name} chưa đóng additionalProperties nên strict từ chối. "
        "Khai schema tham số chặt lại; đừng tắt strict để né."
    )

    missing = set(params.get("properties", {})) - set(params.get("required", []))
    assert not missing, (
        f"Tool {name} có field ngoài required: {sorted(missing)}. "
        "strict đòi mọi field phải required; field tuỳ chọn thì khai kiểu "
        '["<type>", "null"] thay vì bỏ khỏi required.'
    )


def test_web_search_cung_hop_le_khi_bat(monkeypatch: pytest.MonkeyPatch) -> None:
    """web_search chỉ vào registry khi có key, nên dễ lọt khỏi vòng kiểm."""
    from src.config import get_settings

    monkeypatch.setenv("WEB_SEARCH_ENABLED", "true")
    monkeypatch.setenv("TAVILY_API_KEY", "dummy-key-for-schema-check")
    get_settings.cache_clear()
    try:
        tools = _tools()
        names = {getattr(t, "name", str(t)) for t in tools}
        assert "web_search" in names, (
            "Bật WEB_SEARCH_ENABLED mà web_search không vào registry — "
            "điều kiện bật đã đổi, cập nhật lại test này."
        )
        for tool in tools:
            _schema(tool)  # ném ra nếu không khai được dưới strict
    finally:
        get_settings.cache_clear()


def test_ha_cap_chi_khi_client_khong_ho_tro_strict() -> None:
    """Hạ cấp phải hẹp: chỉ cho TypeError về kwarg, không nuốt lỗi schema."""

    class KhongHoTroStrict:
        def bind_tools(self, tools, **kwargs):
            if "strict" in kwargs:
                raise TypeError("bind_tools() got an unexpected keyword argument 'strict'")
            return "đã hạ cấp"

    class SchemaHong:
        def bind_tools(self, tools, **kwargs):
            raise ValueError("schema không hợp lệ")

    assert _bind_tools_strict(KhongHoTroStrict(), []) == "đã hạ cấp"

    with pytest.raises(ValueError, match="schema không hợp lệ"):
        _bind_tools_strict(SchemaHong(), [])
