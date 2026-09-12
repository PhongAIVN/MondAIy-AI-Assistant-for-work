"""Nhận diện hàng tiêu đề phải chịu được nhiều format, không chỉ đúng một bảng alias.

Ca lỗi thật: Thái gửi Google Sheet, app báo "Không tìm thấy hàng tiêu đề công việc
trong Google Sheet" rồi lặng lẽ quay sang trả lời bằng email/Jira. Gốc: `_find_header`
khớp BẰNG ĐÚNG alias và bắt buộc phải có title + (assignee hoặc due).
"""

import pytest

from src.connectors.google_sheets import (
    _find_header,
    _validate_llm_header,
    find_header_with_llm,
)


class TestKhopMem:
    def test_tieu_de_co_hau_to_van_nhan_ra(self):
        values = [
            ["Tên công việc", "Người thực hiện chính", "Hạn chót (dd/mm)"],
            ["Viết báo cáo", "Thái", "16/08/2026"],
        ]
        row, mapping = _find_header(values)
        assert row == 0
        assert mapping["title"] == 0 and mapping["assignee"] == 1 and mapping["due"] == 2

    def test_chi_co_cot_ten_viec_van_doc_duoc(self):
        # Trước đây trượt vì thiếu assignee lẫn due, dù bảng hoàn toàn đọc được.
        values = [["Nhiệm vụ"], ["Chuẩn bị slide"], ["Gửi email khách"]]
        row, mapping = _find_header(values)
        assert row == 0 and mapping["title"] == 0

    def test_bo_qua_dong_trang_tri_phia_tren(self):
        values = [
            ["BẢNG THEO DÕI CÔNG VIỆC THÁNG 8"],
            [],
            ["Task", "Owner", "Deadline"],
            ["Fix bug", "An", "20/08/2026"],
        ]
        row, _ = _find_header(values)
        assert row == 2

    def test_alias_ngan_khong_duoc_khop_bay(self):
        # "id" nằm trong "identity", "name" nằm trong "filename" — khớp mềm mà
        # nhận alias ngắn thì sẽ ánh xạ bậy sang cột không liên quan.
        values = [["identity", "filename"], ["a", "b"]]
        with pytest.raises(ValueError, match="Không tìm thấy hàng tiêu đề"):
            _find_header(values)


class TestKhongTinLLM:
    values = [["Việc", "Ai làm"], ["Viết test", "Thái"], ["Review", "An"]]

    def test_chi_so_ngoai_bang_thi_tu_choi(self):
        assert _validate_llm_header(self.values, 0, {"title": 99}) is None

    def test_thieu_title_thi_tu_choi(self):
        assert _validate_llm_header(self.values, 0, {"assignee": 1}) is None

    def test_cot_title_rong_thi_tu_choi(self):
        empty = [["Việc", "Ai làm"], ["", "Thái"], ["", "An"]]
        assert _validate_llm_header(empty, 0, {"title": 0}) is None

    def test_ket_qua_hop_le_thi_nhan(self):
        assert _validate_llm_header(self.values, 0, {"title": 0, "assignee": 1}) == (
            0,
            {"title": 0, "assignee": 1},
        )


class _FakeLLM:
    def __init__(self, content: str):
        self._content = content

    async def ainvoke(self, _messages):
        return type("R", (), {"content": self._content})()


@pytest.mark.asyncio
async def test_llm_doc_duoc_format_la(monkeypatch):
    # Tiêu đề hoàn toàn không có trong bảng alias — chỉ LLM mới hiểu.
    values = [["Hạng mục triển khai", "Phụ trách"], ["Dựng CI", "An"]]
    monkeypatch.setattr(
        "src.services.llm.get_llm",
        lambda lane=None: _FakeLLM('{"header_row": 0, "columns": {"title": 0, "assignee": 1}}'),
    )
    assert await find_header_with_llm(values) == (0, {"title": 0, "assignee": 1})


@pytest.mark.asyncio
async def test_llm_tra_rac_thi_bao_loi_chu_khong_doan(monkeypatch):
    values = [["a", "b"], ["1", "2"]]
    monkeypatch.setattr("src.services.llm.get_llm", lambda lane=None: _FakeLLM("xin lỗi tôi không biết"))
    with pytest.raises(ValueError, match="Không tìm thấy hàng tiêu đề"):
        await find_header_with_llm(values)


def test_structural_inference_does_not_promote_ordinary_data_row():
    """Bắt được nhờ chạy trên file demo thật, không phải nhờ nghĩ ra.

    Ô "Demo nhận diện task đa định dạng" chứa chữ "task" nên từng bị khớp mềm
    nhận là hàng tiêu đề, khiến header nhảy từ hàng 4 xuống hàng 7 và đọc ra bảng rác.
    """
    values = [
        ["LỘ TRÌNH DỰ ÁN"],
        [],
        [],
        ["M3", "Demo nhận diện task đa định dạng", "Lê Minh Đức"],
        ["M4", "Hoàn thiện báo cáo", "An Hoài Thái"],
    ]
    with pytest.raises(ValueError, match="Không tìm thấy hàng tiêu đề"):
        _find_header(values)


def test_structural_header_infers_unfamiliar_title_column():
    values = [
        ["BACKLOG — QUẢN LÝ CÔNG VIỆC"],
        ["Mọi công việc của dự án Mondai"],
        [],
        ["Mã", "Mốc quan trọng", "Người chịu trách nhiệm"],
        ["M3", "Demo nhận diện task đa định dạng", "Lê Minh Đức"],
        ["M4", "Hoàn thiện báo cáo", "An Hoài Thái"],
    ]

    row, mapping = _find_header(values)

    assert row == 3
    assert mapping == {"key": 0, "assignee": 2, "title": 1}


def test_structural_header_is_label_and_order_agnostic():
    values = [
        ["Owner", "Deliverable", "ID", "Status"],
        ["An", "Publish release notes", "R-1", "Doing"],
        ["Binh", "Verify production", "R-2", "Todo"],
    ]

    row, mapping = _find_header(values)

    assert row == 0
    assert mapping == {"assignee": 0, "key": 2, "status": 3, "title": 1}
