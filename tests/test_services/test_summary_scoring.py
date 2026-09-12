"""Phần TẤT ĐỊNH của bộ chấm tóm tắt — chạy được trong CI, không gọi LLM.

Ba nhánh đầy đủ nằm ở scripts/eval_summary_arms.py và cần model thật. Ở đây chỉ
khoá lại những gì không cần model: bộ chấm có bắt đúng lỗi nó nói là bắt không,
và nhánh rule có giữ nguyên điểm không.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from src.agents.pipeline.nodes.reduce import _mock_reduce
from src.services.summary_scoring import aggregate, anchors, fold, score_case

CASES_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "eval"
    / "golden_dataset"
    / "summary"
    / "summary_cases.json"
)


@pytest.fixture(scope="module")
def cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]


def test_fold_bo_dau_de_ten_tieng_viet_van_khop():
    assert "yen nhi" in fold("Lê Thị Yến Nhi")
    assert fold("Đã cập nhật").startswith("da cap nhat")


def test_anchor_khong_nuot_dau_cau():
    # Regex email tham lam tung nuot ca dau cham cuoi cau, khien dia chi that bi
    # cham la bia dat. Day la lan cham sai da quan sat duoc, khong phai gia dinh.
    assert "nhi@example.com" in anchors("gui den nhi@example.com.")


def test_anchor_tach_thanh_phan_ngay():
    # "August 21" viet lai tu "21/08" la dien dat, khong phai bia.
    assert {"21", "8"} <= anchors("21/08")


def test_ban_rong_truot_het():
    case = {"id": "x", "language": "vi", "items": [], "must_mention": []}
    score = score_case(case, "")
    assert not score.passed
    assert not score.language_ok


def test_bat_duoc_bia_dat():
    case = {
        "id": "x",
        "language": "vi",
        "items": [{"message": {"author_name": "An"}, "evidence_quote": "Chuẩn bị tài liệu."}],
        "must_mention": [],
        "must_not_invent": ["15/09"],
    }
    assert not score_case(case, "An nhắc chuẩn bị tài liệu trước 15/09.").faithful
    assert score_case(case, "An nhắc chuẩn bị tài liệu.").faithful


def test_bat_duoc_sai_ngon_ngu():
    case = {
        "id": "x",
        "language": "en",
        "items": [{"message": {"author_name": "An"}, "evidence_quote": "Nộp báo cáo."}],
        "must_mention": [],
    }
    assert not score_case(case, "An nhắc nộp báo cáo.").language_ok
    assert score_case(case, "An asks for the report.").language_ok


def test_must_mention_chap_nhan_nhieu_cach_viet():
    case = {
        "id": "x",
        "language": "en",
        "items": [{"message": {"author_name": "An"}, "evidence_quote": "Nộp trước 22/08."}],
        "must_mention": ["22/08|august 22"],
    }
    assert score_case(case, "An asks to submit before August 22.").coverage


def test_golden_du_kho_de_phan_biet_cac_nhanh(cases):
    """Nhánh rule phải trượt MỘT SỐ case — không phải tất cả, không phải không case nào.

    Bộ golden mà nhánh nào cũng đạt hết thì không so sánh được gì; nhánh nào
    cũng trượt hết thì bộ chấm hỏng. Chốt lại con số đã đo để lần sau sửa bộ
    chấm mà làm lệch thì test kêu.
    """
    scores = [score_case(case, _mock_reduce({"items": case["items"]})) for case in cases]
    passed = sum(score.passed for score in scores)
    assert passed == 8, [s.case_id for s in scores if not s.passed]
    assert aggregate(scores)["paraphrased"] < 0.5  # rule chỉ nối, không viết lại
