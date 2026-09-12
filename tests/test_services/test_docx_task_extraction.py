from io import BytesIO

from docx import Document

from src.services.docx_task_extraction import collect_docx_assignee_candidates, extract_docx_task_proposals


def _schedule_docx() -> bytes:
    document = Document()
    table = document.add_table(rows=2, cols=3)
    table.rows[0].cells[0].text = "Ngày"
    table.rows[0].cells[1].text = "Sáng"
    table.rows[0].cells[2].text = "Chiều"
    table.rows[1].cells[0].text = "Thứ Hai 18/08/2026"
    table.rows[1].cells[1].text = "08h00 A. Đức họp rà soát kế hoạch\nThành phần: Nguyễn Hồng Đức\nTại Phòng họp A"
    table.rows[1].cells[2].text = "14h00 Nguyễn Thái Hoài họp việc khác"
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def test_extract_docx_schedule_uses_participant_match_and_keeps_schedule_metadata():
    proposals = extract_docx_task_proposals(
        _schedule_docx(),
        filename="lich-tuan.docx",
        display_name="Nguyễn Hồng Đức",
        timezone_name="Asia/Ho_Chi_Minh",
    )

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal["matched_user"] is True
    assert "họp rà soát kế hoạch" in proposal["title"]
    assert "Lịch: Thứ Hai" in proposal["detail"]
    assert "Giờ: 08h00" in proposal["detail"]
    assert proposal["due_at"] is not None


def test_extract_docx_schedule_matches_name_in_unlabelled_block_line():
    document = Document()
    table = document.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Ngày"
    table.rows[0].cells[1].text = "Sáng"
    table.rows[1].cells[0].text = "Thứ Hai 18/08/2026"
    table.rows[1].cells[1].text = (
        "08h00 Họp rà soát kế hoạch\n"
        "A Tuấn-PGĐ\n"
        "Tại Phòng họp A"
    )
    output = BytesIO()
    document.save(output)

    proposals = extract_docx_task_proposals(
        output.getvalue(),
        filename="lich-tuan.docx",
        display_name="A Tuấn-PGĐ",
        timezone_name="Asia/Ho_Chi_Minh",
    )

    assert len(proposals) == 1
    assert proposals[0]["matched_user"] is True
    assert proposals[0]["needs_confirmation"] is True
    assert "Họp rà soát kế hoạch" in proposals[0]["title"]


def test_docx_candidate_list_excludes_participant_departments():
    document = Document()
    table = document.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Ngày"
    table.rows[0].cells[1].text = "Sáng"
    table.rows[1].cells[0].text = "Thứ Hai 18/08/2026"
    table.rows[1].cells[1].text = (
        "08h00 A Tuấn-PGĐ họp rà soát kế hoạch\n"
        "Thành phần: KTĐT, ĐHKD, TTHT."
    )
    output = BytesIO()
    document.save(output)

    assert collect_docx_assignee_candidates(output.getvalue()) == ["A Tuấn-PGĐ"]


def test_extract_docx_generic_task_table_marks_short_name_for_confirmation():
    document = Document()
    table = document.add_table(rows=2, cols=3)
    table.rows[0].cells[0].text = "Nội dung công việc"
    table.rows[0].cells[1].text = "Người phụ trách"
    table.rows[0].cells[2].text = "Hạn chót"
    table.rows[1].cells[0].text = "Duyệt báo cáo"
    table.rows[1].cells[1].text = "Đức"
    table.rows[1].cells[2].text = "15/9"
    output = BytesIO()
    document.save(output)

    proposals = extract_docx_task_proposals(
        output.getvalue(),
        filename="cong-viec.docx",
        display_name="Nguyễn Hồng Đức",
        timezone_name="Asia/Ho_Chi_Minh",
    )

    assert proposals[0]["match_kind"] == "possible"
    assert proposals[0]["needs_confirmation"] is True
    assert proposals[0]["date_ambiguous"] is True


def test_extract_docx_falls_back_to_free_paragraph_with_full_name():
    document = Document()
    document.add_paragraph("Nguyễn Hồng Đức hoàn thiện báo cáo tổng hợp trước thứ Sáu.")
    output = BytesIO()
    document.save(output)

    proposals = extract_docx_task_proposals(
        output.getvalue(),
        filename="ghi-chu.docx",
        display_name="Nguyễn Hồng Đức",
        timezone_name="Asia/Ho_Chi_Minh",
    )

    assert len(proposals) == 1
    assert proposals[0]["needs_confirmation"] is True
    assert proposals[0]["source"].endswith("Đoạn 1")
