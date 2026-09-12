from io import BytesIO

import openpyxl

from src.services.spreadsheet_task_extraction import extract_excel_task_proposals, name_match_kind


def _workbook_bytes() -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Tuần 31"
    sheet.append(["BẢNG CÔNG VIỆC TRỌNG ĐIỂM"])
    sheet.append(["STT", "Nội dung công việc", "Lãnh đạo chỉ đạo", "Hạn hoàn thành", "Kết quả", "Kế hoạch", "Kỹ thuật"])
    sheet.append([1, "Chốt kế hoạch pilot", "Nguyễn Văn An", "31/08/2026", "Đang làm", "A", "R"])
    sheet.append([2, "Việc người khác", "Nguyễn Thái Hoài", "01/09/2026", "Chưa làm", "R", "A"])
    sheet.append([3, "Rà soát tài liệu", "Văn An", "15/9", "", "A", "C"])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_extract_excel_finds_flexible_headers_raci_and_safe_name_matches():
    proposals = extract_excel_task_proposals(
        _workbook_bytes(),
        filename="cong-viec.xlsx",
        display_name="Nguyễn Văn An",
        timezone_name="Asia/Ho_Chi_Minh",
    )

    assert [proposal["title"] for proposal in proposals] == ["Chốt kế hoạch pilot", "Rà soát tài liệu"]
    assert proposals[0]["matched_user"] is True
    assert proposals[0]["match_kind"] == "exact"
    assert "Liên hệ chính (A): Kế hoạch (A)" in proposals[0]["detail"]
    assert "Phối hợp (R): Kỹ thuật (R)" in proposals[0]["detail"]
    assert proposals[1]["match_kind"] == "close"
    assert proposals[1]["date_ambiguous"] is True
    assert proposals[1]["needs_confirmation"] is True


def test_name_match_only_marks_single_final_name_as_confirmation_needed():
    assert name_match_kind("A. Đức", "Nguyễn Hồng Đức") == "possible"
    assert name_match_kind("An", "Nguyễn Văn Anh") == "none"
    assert name_match_kind("Thái Hoài An", "Nguyễn Thái Hoài") == "none"


def test_extract_excel_falls_back_to_full_name_mention_when_layout_has_no_header():
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["Lịch tuần"])
    sheet.append(["Nguyễn Văn An cần hoàn thiện báo cáo trước thứ Sáu"])
    output = BytesIO()
    workbook.save(output)

    proposals = extract_excel_task_proposals(
        output.getvalue(),
        filename="lich.xlsx",
        display_name="Nguyễn Văn An",
        timezone_name="Asia/Ho_Chi_Minh",
    )

    assert len(proposals) == 1
    assert proposals[0]["needs_confirmation"] is True
    assert proposals[0]["matched_user"] is False


def test_header_detection_does_not_treat_a_long_task_row_as_column_headers():
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["STT", "Nội dung công việc", "Tiến độ", "Kết quả triển khai"])
    task = "Xây dựng phương án và giao cá nhân chịu trách nhiệm hoàn thành chiến dịch"
    result = "Đến hết tháng 6 hoàn thành thêm 30 nghìn thuê bao"
    sheet.append([1, task, "05/06/2026", result])
    output = BytesIO()
    workbook.save(output)

    proposals = extract_excel_task_proposals(
        output.getvalue(),
        filename="theo-doi.xlsx",
        display_name=task,
        timezone_name="Asia/Ho_Chi_Minh",
    )

    assert proposals == []
