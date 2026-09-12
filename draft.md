#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
raci_extract.py  (bản tổng quát - tự nhận diện cấu trúc file)
================================================================
Trích xuất công việc của MỘT người cụ thể + cho biết nên hỏi phòng/ban nào (RACI)
từ BẤT KỲ file Excel nào có dạng bảng công việc, không cần layout cố định.

Khác với bản trước, script này KHÔNG đóng cứng tên sheet hay vị trí cột.
Với mỗi sheet nó sẽ tự:
  1. Tìm dòng tiêu đề (không nhất thiết là dòng 4).
  2. Đoán cột nào là "Người phụ trách/chỉ đạo", "Nội dung công việc",
     "Tiến độ/Hạn", "Kết quả" — dựa theo TỪ KHOÁ trong tiêu đề (danh sách từ khoá
     có thể sửa/thêm ở phần CONFIG).
  3. Đoán cột nào là cột RACI — dựa theo GIÁ TRỊ trong cột (nếu phần lớn ô chỉ
     chứa R/A/C/I/RA/AR...) — nên áp dụng được cho file có tên phòng ban khác nhau.

Nếu script đoán sai ở file nào đó, dùng --diagnose để xem nó hiểu cột thế nào,
rồi override bằng --lead-col / --content-col / --deadline-col / --result-col
(truyền tên cột hoặc chữ cột, vd "D" hoặc "Lãnh đạo chỉ đạo").

CÁCH DÙNG:
    python3 raci_extract.py "file.xlsx" --person duc
    python3 raci_extract.py "file.xlsx" --person duc --sheet "Tuần 31"   # lọc sheet theo tên (chứa chuỗi này)
    python3 raci_extract.py "file.xlsx" --diagnose                       # xem script hiểu cột ra sao (không lọc người)
    python3 raci_extract.py "file.xlsx" --person duc --out ketqua.xlsx

Chỗ cần sửa khi dùng cho công ty/người khác: phần PEOPLE ở CONFIG bên dưới.
"""

import argparse
import re
import sys
import unicodedata
from collections import defaultdict

import openpyxl
from openpyxl.utils import column_index_from_string, get_column_letter

# =============================================================================
# CONFIG 1 — Danh sách người cần tra cứu. SỬA Ở ĐÂY khi có người mới / alias mới.
# =============================================================================

PEOPLE = {
    "phuong": {"aliases": ["A. Phương", "Anh Phương", "GĐ VTNB"], "title": "Giám đốc VTNB"},
    "sy":     {"aliases": ["A. Sỹ", "Anh Sỹ"], "title": "Phó Giám đốc VTNB (PGĐ VTNB)"},
    "duc":    {"aliases": ["A. Đức", "Anh Đức", "Nguyễn Hồng Đức", "Sếp Đức"], "title": "Phó Giám đốc VTNB (PGĐ VTNB)"},
    "hung":   {"aliases": ["A. Hưng", "Anh Hưng"], "title": "Phó Giám đốc VTNB (PGĐ VTNB)"},
    "tan":    {"aliases": ["A. Tấn", "Anh Tấn"], "title": "Phó Giám đốc VTNB (PGĐ VTNB)"},
    "tuan":   {"aliases": ["A. Tuấn", "Anh Tuấn"], "title": "Phó Giám đốc VTNB (PGĐ VTNB) kiêm Chủ tịch CĐ VNPT NBH"},
}

# =============================================================================
# CONFIG 2 — Từ khoá nhận diện vai trò cột theo TIÊU ĐỀ (mở rộng được, không phân
# biệt dấu/hoa-thường, script tự so khớp dạng "chứa chuỗi con").
# =============================================================================

HEADER_KEYWORDS = {
    "stt":      ["stt", "so tt", "no.", "#"],
    "lead":     ["lanh dao chi dao", "lanh dao phu trach", "nguoi phu trach", "nguoi chi dao",
                 "chu tri", "phu trach", "chi dao", "owner", "pic", "assignee", "responsible person"],
    "content":  ["noi dung cong viec", "noi dung", "cong viec", "hang muc", "dau viec",
                 "task", "description", "mo ta"],
    "deadline": ["tien do", "han hoan thanh", "ngay hoan thanh", "thoi gian", "deadline",
                 "due date", "han"],
    "result":   ["ket qua", "trien khai", "ghi chu", "note", "status", "tinh trang"],
}

# Mã RACI hợp lệ khi đoán cột theo giá trị (không phân biệt hoa/thường)
RACI_TOKENS = {"r", "a", "c", "i", "ra", "ar", "ri", "ci", "ai"}

RACI_MEANING = {
    "R": "Responsible - đơn vị/người trực tiếp thực hiện",
    "A": "Accountable - đơn vị/người chịu trách nhiệm chính, phê duyệt kết quả",
    "RA": "Vừa Responsible vừa Accountable",
    "C": "Consulted - được tham vấn ý kiến",
    "I": "Informed - chỉ cần được thông báo kết quả",
}

# =============================================================================
# Helpers chung
# =============================================================================


def norm(s):
    """Bỏ dấu tiếng Việt, lower(), gộp khoảng trắng — dùng để so khớp bất kể dấu/hoa-thường."""
    if s is None:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("Đ", "D").replace("đ", "d")
    s = re.sub(r"\s+", " ", s.replace("\n", " ")).strip().lower()
    return s


def cell_text(v):
    return "" if v is None else str(v).strip()


def resolve_col_arg(ws, header_row, arg):
    """Cho phép người dùng override cột bằng chữ cột (vd 'D') hoặc bằng tên tiêu đề."""
    if arg is None:
        return None
    arg = arg.strip()
    if re.fullmatch(r"[A-Za-z]+", arg):
        try:
            return column_index_from_string(arg.upper())
        except Exception:
            pass
    target = norm(arg)
    for c in range(1, ws.max_column + 1):
        if norm(ws.cell(row=header_row, column=c).value) == target:
            return c
    sys.exit(f"Không tìm thấy cột '{arg}' ở sheet '{ws.title}'.")


# =============================================================================
# Bước 1: Tìm dòng tiêu đề của mỗi sheet (không giả định vị trí cố định)
# =============================================================================


def find_header_row(ws, max_scan=20):
    """
    Chấm điểm từng dòng trong max_scan dòng đầu: dòng nào có nhiều ô khớp
    HEADER_KEYWORDS nhất (đặc biệt là có cả 'stt' lẫn 'content') thì là header.
    """
    best_row, best_score = None, 0
    for r in range(1, min(max_scan, ws.max_row) + 1):
        score = 0
        has_stt = has_content = False
        for c in range(1, ws.max_column + 1):
            txt = norm(ws.cell(row=r, column=c).value)
            if not txt:
                continue
            for role, kws in HEADER_KEYWORDS.items():
                if any(kw in txt for kw in kws):
                    score += 1
                    if role == "stt":
                        has_stt = True
                    if role == "content":
                        has_content = True
                    break
        if has_stt and has_content:
            score += 5  # ưu tiên mạnh dòng có cả 2 cột cốt lõi
        if score > best_score:
            best_score, best_row = score, r
    return best_row


# =============================================================================
# Bước 2: Phân loại từng cột theo tiêu đề + theo giá trị (cho cột RACI)
# =============================================================================


def classify_columns(ws, header_row, sample_rows=40):
    """
    Trả về:
      roles: dict role -> col_index  (stt/lead/content/deadline/result)
      raci_cols: dict col_index -> header_text  (các cột được đoán là cột RACI)
    """
    roles = {}
    header_texts = {}
    for c in range(1, ws.max_column + 1):
        raw = cell_text(ws.cell(row=header_row, column=c).value).replace("\n", " ").strip()
        if not raw:
            continue
        header_texts[c] = raw
        n = norm(raw)
        for role, kws in HEADER_KEYWORDS.items():
            if role in roles:
                continue
            if any(kw in n for kw in kws):
                roles[role] = c

    # Đoán cột RACI theo GIÁ TRỊ (áp dụng cho các cột chưa được gán role khác,
    # và không phải cột content/result vì các cột đó chứa văn bản dài)
    raci_cols = {}
    excluded = set(roles.values())
    last_row = min(header_row + sample_rows, ws.max_row)
    for c in range(1, ws.max_column + 1):
        if c in excluded or c not in header_texts:
            continue
        total, matched = 0, 0
        for r in range(header_row + 1, last_row + 1):
            v = cell_text(ws.cell(row=r, column=c).value)
            if not v:
                continue
            total += 1
            tokens = re.split(r"[\/,;+&\s]+", v.strip())
            if tokens and all(t.lower() in RACI_TOKENS for t in tokens if t):
                matched += 1
        if total >= 2 and matched / total >= 0.7:
            raci_cols[c] = header_texts[c]

    return roles, raci_cols, header_texts


# =============================================================================
# Bước 3: Trích xuất theo người
# =============================================================================


def person_matches(cell_value, aliases_norm):
    text_norm = norm(cell_value)
    return any(a in text_norm for a in aliases_norm)


def raci_contacts(raci_by_dept):
    primary, secondary, other = [], [], []
    for dept, code in raci_by_dept.items():
        code_up = code.upper()
        if "A" in code_up:
            primary.append((dept, code_up))
        elif "R" in code_up:
            secondary.append((dept, code_up))
        else:
            other.append((dept, code_up))
    return primary, secondary, other


def extract_for_person(path, person_key, sheet_filter=None, overrides=None):
    if person_key not in PEOPLE:
        known = ", ".join(PEOPLE.keys())
        sys.exit(f"Không nhận diện được người '{person_key}'. Các key đã cấu hình: {known}.")

    profile = PEOPLE[person_key]
    aliases_norm = [norm(a) for a in profile["aliases"]]
    overrides = overrides or {}

    wb = openpyxl.load_workbook(path, data_only=True)
    results = []

    for sheet_name in wb.sheetnames:
        if sheet_filter and sheet_filter.lower() not in sheet_name.lower():
            continue
        ws = wb[sheet_name]
        header_row = find_header_row(ws)
        if header_row is None:
            continue
        roles, raci_cols, header_texts = classify_columns(ws, header_row)

        col_lead = resolve_col_arg(ws, header_row, overrides.get("lead")) or roles.get("lead")
        col_content = resolve_col_arg(ws, header_row, overrides.get("content")) or roles.get("content")
        col_deadline = resolve_col_arg(ws, header_row, overrides.get("deadline")) or roles.get("deadline")
        col_result = resolve_col_arg(ws, header_row, overrides.get("result")) or roles.get("result")
        col_stt = roles.get("stt")

        if col_lead is None or col_content is None:
            # Sheet này không có cấu trúc đủ để trích xuất theo người -> bỏ qua
            continue

        for r in range(header_row + 1, ws.max_row + 1):
            lead_val = cell_text(ws.cell(row=r, column=col_lead).value)
            if not lead_val or not person_matches(lead_val, aliases_norm):
                continue
            content = cell_text(ws.cell(row=r, column=col_content).value)
            if not content:
                continue

            stt = cell_text(ws.cell(row=r, column=col_stt).value) if col_stt else ""
            deadline = cell_text(ws.cell(row=r, column=col_deadline).value) if col_deadline else ""
            result = cell_text(ws.cell(row=r, column=col_result).value) if col_result else ""

            raci_by_dept = {}
            for c, dept_name in raci_cols.items():
                code = cell_text(ws.cell(row=r, column=c).value)
                if code:
                    raci_by_dept[dept_name] = code

            results.append({
                "sheet": sheet_name, "stt": stt, "content": content,
                "deadline": deadline, "lead_raw": lead_val,
                "raci": raci_by_dept, "result": result,
            })

    return profile, results


# =============================================================================
# Chế độ chẩn đoán: xem script hiểu file thế nào (không lọc theo người)
# =============================================================================


def diagnose(path, sheet_filter=None):
    wb = openpyxl.load_workbook(path, data_only=True)
    for sheet_name in wb.sheetnames:
        if sheet_filter and sheet_filter.lower() not in sheet_name.lower():
            continue
        ws = wb[sheet_name]
        header_row = find_header_row(ws)
        print(f"\n=== Sheet: {sheet_name} ===")
        if header_row is None:
            print("  -> Không tìm được dòng tiêu đề phù hợp, sẽ BỎ QUA sheet này.")
            continue
        roles, raci_cols, header_texts = classify_columns(ws, header_row)
        print(f"  Dòng tiêu đề: hàng {header_row}")
        for role in ["stt", "lead", "content", "deadline", "result"]:
            c = roles.get(role)
            label = f"{get_column_letter(c)} = '{header_texts.get(c)}'" if c else "(không tìm thấy)"
            print(f"  - Cột {role:9s}: {label}")
        if raci_cols:
            cols_str = ", ".join(f"{get_column_letter(c)}='{name}'" for c, name in raci_cols.items())
            print(f"  - Cột RACI đoán được ({len(raci_cols)}): {cols_str}")
        else:
            print("  - Không đoán được cột RACI nào ở sheet này.")


# =============================================================================
# Output
# =============================================================================


def print_report(person_key, profile, results):
    print("=" * 90)
    print(f"CÔNG VIỆC LIÊN QUAN TỚI: {person_key.upper()}  ({profile['title']})")
    print(f"Tổng số đầu mục tìm thấy: {len(results)}")
    print("=" * 90)

    by_sheet = defaultdict(list)
    for item in results:
        by_sheet[item["sheet"]].append(item)

    for sheet_name, items in by_sheet.items():
        print(f"\n### {sheet_name} ###")
        for item in items:
            print(f"\n[{item['stt']}] {item['content'][:300]}")
            if item["deadline"]:
                print(f"   - Hạn/Tiến độ : {item['deadline']}")
            primary, secondary, other = raci_contacts(item["raci"])
            if primary:
                print("   - HỎI TRƯỚC (A - chịu trách nhiệm chính): " + ", ".join(f"{d} ({c})" for d, c in primary))
            if secondary:
                print("   - Phối hợp/thực hiện (R)                : " + ", ".join(f"{d} ({c})" for d, c in secondary))
            if other:
                print("   - Khác (C/I)                            : " + ", ".join(f"{d} ({c})" for d, c in other))
            if not primary and not secondary and not other:
                print("   - (Không có phân RACI theo cột ở dòng này)")
            if item["result"]:
                snippet = item["result"][:200].replace("\n", " ")
                print(f"   - Kết quả/tiến độ hiện tại: {snippet}...")

    print("\n" + "-" * 90)
    print("Chú giải RACI:")
    for code, meaning in RACI_MEANING.items():
        print(f"  {code:3s}: {meaning}")


def export_xlsx(results, out_path):
    wb_out = openpyxl.Workbook()
    ws = wb_out.active
    ws.title = "Ket qua"
    ws.append(["Sheet", "STT", "Nội dung công việc", "Hạn/Tiến độ",
               "Hỏi trước (Accountable)", "Phối hợp (Responsible)", "Khác (C/I)",
               "Kết quả/Tiến độ hiện tại"])
    for item in results:
        primary, secondary, other = raci_contacts(item["raci"])
        ws.append([
            item["sheet"], item["stt"], item["content"], item["deadline"],
            ", ".join(f"{d} ({c})" for d, c in primary),
            ", ".join(f"{d} ({c})" for d, c in secondary),
            ", ".join(f"{d} ({c})" for d, c in other),
            item["result"],
        ])
    for col_cells in ws.columns:
        length = max((len(str(c.value)) if c.value else 0) for c in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max(length + 2, 12), 60)
    wb_out.save(out_path)
    print(f"\nĐã xuất kết quả ra: {out_path}")


# =============================================================================
# CLI
# =============================================================================


def main(argv=None):
    ap = argparse.ArgumentParser(description="Trích xuất công việc + RACI cho 1 người, tự nhận diện cấu trúc file.")
    ap.add_argument("file", help="Đường dẫn file Excel")
    ap.add_argument("--person", default=None, help=f"Key người cần tra. Các key hiện có: {', '.join(PEOPLE)}")
    ap.add_argument("--sheet", default=None, help="Chỉ xử lý các sheet có tên chứa chuỗi này (tuỳ chọn)")
    ap.add_argument("--out", default=None, help="Xuất kết quả ra file .xlsx (tuỳ chọn)")
    ap.add_argument("--diagnose", action="store_true",
                     help="Chỉ in ra script hiểu cấu trúc từng sheet thế nào, không lọc theo người")
    ap.add_argument("--lead-col", default=None, help="Ép cột 'người phụ trách' (vd 'D' hoặc tên tiêu đề)")
    ap.add_argument("--content-col", default=None, help="Ép cột 'nội dung công việc'")
    ap.add_argument("--deadline-col", default=None, help="Ép cột 'tiến độ/hạn'")
    ap.add_argument("--result-col", default=None, help="Ép cột 'kết quả'")
    # Use parse_known_args to ignore unrecognized arguments from the Colab environment
    args, unknown = ap.parse_known_args(args=argv)

    if args.diagnose:
        diagnose(args.file, args.sheet)
        return

    if not args.person:
        # If running in Colab and person is not set via argv, prompt for it
        if argv is None or "--person" not in argv:
             # This assumes a default person if none is provided via command line or Colab args
            print("Cần truyền --person (hoặc dùng --diagnose để xem cấu trúc file trước).")
            print(f"Sử dụng người mặc định 'duc' và file '/content/Nội dung công việc trọng điểm_Tuần 31-2026.xlsx'.")
            args.person = "duc"
            args.file = "/content/Nội dung công việc trọng điểm_Tuần 31-2026.xlsx"
        else:
             sys.exit("Cần truyền --person (hoặc dùng --diagnose để xem cấu trúc file trước).")


    overrides = {
        "lead": args.lead_col, "content": args.content_col,
        "deadline": args.deadline_col, "result": args.result_col,
    }
    profile, results = extract_for_person(args.file, args.person, args.sheet, overrides)
    if not results:
        print(f"Không tìm thấy đầu mục công việc nào của '{args.person}' trong file này.\n"
              f"Gợi ý: chạy thêm '--diagnose' để kiểm tra script có nhận đúng cột 'người phụ trách' không.")
        return
    print_report(args.person, profile, results)
    if args.out:
        export_xlsx(results, args.out)


if __name__ == "__main__":
    # Example of how to call main with required arguments in Colab
    # Use the file from the previous cell's context
    excel_file_path = "/content/Nội dung công việc trọng điểm_Tuần 31-2026.xlsx"
    person_key = "duc"

    # Pass arguments as a list to main
    try:
        main(argv=[excel_file_path, "--person", person_key])
    except SystemExit as e:
        # Catch SystemExit which is raised by argparse.ArgumentParser on error
        if e.code != 0: # Only re-raise if it's an actual error (code 0 is for --help or successful exit)
            raise

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_lich_tuan.py  (bản tổng quát)
======================================
Trích xuất công việc từ file "Lịch công tác tuần" (.docx dạng bảng: cột/hàng
ngày + cột/hàng buổi làm việc), rồi lọc theo tên 1 người (tự gộp luôn task
ghi chung cho cả "Ban Giám đốc"/nhóm mà người đó thuộc về).

SO VỚI BẢN TRƯỚC — những chỗ đã tổng quát hoá để "loại doc nào cũng xử lý được":
  1. KHÔNG giả định cột 0 luôn là ngày/tháng — tự dò cột nào chứa ngày-tháng
     hoặc tên thứ trong tuần; sessions lấy từ các cột còn lại theo header.
  2. KHÔNG bỏ dòng khi ô không có giờ (trước đây bị SKIP mất dữ liệu) — nếu
     cả ô không có mốc giờ nào, coi cả ô là 1 task với time=None.
  3. Nhận thêm các kiểu mốc "giờ": "08h00", "8:00", "8h-9h30", "Sáng:",
     "Chiều:", "Cả ngày:", "Từ 8h đến 9h30"...
  4. Danh sách động từ để tách "người phụ trách" khỏi nội dung được mở rộng
     và có thể thêm dễ dàng (ASSIGNEE_TRAILING_VERBS).
  5. So khớp tên người bỏ qua dấu câu/hoa-thường/dấu tiếng Việt (đề phòng
     văn bản gõ thiếu dấu, hoặc dấu bị lỗi font khi convert).
  6. Có --diagnose: in ra từng bảng trong file được hiểu ra sao (bao nhiêu
     cột, cột nào là ngày, sessions là gì, bắt được bao nhiêu task) để kiểm
     tra TRƯỚC khi tin tưởng kết quả trên 1 mẫu file lạ.
  7. Chạy được cả trong Colab (tự upload) lẫn ngoài Colab (truyền path qua
     tham số dòng lệnh) — không bắt buộc phải có google.colab.
  8. Không còn in hàng loạt debug ra console; có --verbose nếu cần xem chi tiết.

CÁCH DÙNG:
  Trong Colab (giữ nguyên luồng upload như cũ):
      python3 extract_lich_tuan.py --colab --person duc

  Ngoài Colab / máy local:
      python3 extract_lich_tuan.py "lich_tuan_31.docx" "lich_tuan_32.docx" --person duc
      python3 extract_lich_tuan.py "lich_tuan_31.docx" --diagnose
      python3 extract_lich_tuan.py "lich_tuan_31.docx" --person duc --out ketqua.xlsx

Chỗ cần sửa khi dùng cho người/công ty khác: PERSON_GROUPS ở CONFIG bên dưới.
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import docx
import pandas as pd

# =============================================================================
# CONFIG — sửa/mở rộng ở đây khi gặp mẫu văn bản khác
# =============================================================================

# Các dạng "mốc giờ" hay gặp: 08h00 / 14h30 / 08h30: / 8:00 / 08.30 / 8h-9h30 /
# Sáng: / Chiều: / Tối: / Cả ngày:
TIME_NUMERIC_PATTERN = re.compile(
    r"^\s*(\d{1,2}[h:\.]\d{2}(?:\s*[-–]\s*\d{1,2}[h:\.]?\d{0,2})?)\s*[:\.]?\s*"
)
SESSION_WORD_PATTERN = re.compile(
    r"^\s*(Sáng|Chiều|Tối|Cả ngày|Cả ngày và tối)\s*[:\.]?\s*", re.IGNORECASE
)

# Tiền tố coi là dòng địa điểm
LOCATION_PREFIX = re.compile(r"^\s*(Tại|Địa điểm|Location)\b[\s:]*", re.IGNORECASE)

# Tiền tố coi là dòng thành phần tham dự
PARTICIPANTS_PREFIX = re.compile(r"^\s*(Thành phần|Đại biểu|Attendees?|Mời)\s*:\s*", re.IGNORECASE)

# Các động từ/cụm hay đứng NGAY SAU tên người phụ trách trong câu — mở rộng tự do
ASSIGNEE_TRAILING_VERBS = [
    "dự", "tham dự", "họp", "làm việc", "khảo sát", "tham gia", "dự lễ", "đi",
    "kiểm tra", "thăm", "chủ trì", "báo cáo", "tiếp", "ký kết", "nghiệm thu",
    "giám sát", "chỉ đạo", "trao đổi", "hội ý", "hội nghị", "gặp", "đón tiếp",
    "tổng kết", "sơ kết", "dự thảo", "duyệt", "phê duyệt", "nghe báo cáo",
    "làm trưởng đoàn", "trực",
]
_VERB_ALT = "|".join(re.escape(v) for v in ASSIGNEE_TRAILING_VERBS)

# Danh xưng người phụ trách thường gặp: A/Anh/Chị/Ông/Bà/Đ/c + Tên - Chức vụ
ASSIGNEE_NAME_PREFIX = re.compile(
    r"^\s*((?:A\.?|Anh|Chị|Ông|Bà|Đ/c|Đồng chí)\s+[^\-,.;]+?(?:\s*-\s*[A-ZĐ][^\-,.;]*)?)"
    rf"(?=\s+(?:{_VERB_ALT})\b)",
    re.UNICODE,
)

# Nhóm/tập thể hay xuất hiện làm chủ ngữ mà không nêu tên cá nhân
GROUP_ASSIGNEE_PATTERN = re.compile(
    r"^\s*(Ban Giám đốc|BGĐ|Lãnh đạo\s+\S+|Toàn thể\s+[^\-,.;]+|Các\s+[^\-,.;]+?)"
    rf"(?=\s+(?:{_VERB_ALT})\b)",
    re.UNICODE,
)

# Fallback nếu không match 2 mẫu trên: lấy phần trước dấu "-" đầu tiên (kiểu "Tên - chức vụ")
ASSIGNEE_FALLBACK = re.compile(r"^\s*([^,.;]{1,40}?-[^,.;]{1,30})")

DAY_DATE_PATTERN = re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})")
WEEKDAY_PATTERN = re.compile(
    r"\b(Thứ\s*(?:Hai|Ba|Tư|Năm|Sáu|Bảy)|Chủ\s*nhật|CN)\b", re.IGNORECASE
)

# ---- Sơ đồ Người -> Chức vụ / Nhóm/Ban trực thuộc ----
# Khi lọc task theo TÊN một người, script tự hiểu người đó thuộc nhóm nào
# (vd "Ban Giám đốc") nên cũng lấy luôn các task ghi chung cho cả nhóm dù
# không nêu đích danh tên (vd "08h30 Hội ý Ban Giám đốc").
#
# "exclude": các cụm từ RIÊNG (tên địa danh/dự án/bệnh viện...) có chứa alias
# nhưng KHÔNG liên quan tới người này — vd "Đức" là tên PGĐ nhưng cũng là 1 phần
# của "Bệnh viện Việt Đức", nếu không loại trừ sẽ bị match nhầm mọi task nhắc
# tới bệnh viện đó thành task của "Đức". Khi gặp false-positive tương tự, thêm
# cụm gây nhầm vào đây (không phân biệt dấu/hoa-thường).
PERSON_GROUPS = {
    "duc":    {"aliases": ["Đức"], "groups": ["Ban Giám đốc", "BGĐ"], "title": "PGĐ VTNB",
               "exclude": ["Việt Đức", "BV Việt Đức", "Bệnh viện Việt Đức"]},
    "sy":     {"aliases": ["Sỹ"], "groups": ["Ban Giám đốc", "BGĐ"], "title": "PGĐ VTNB", "exclude": []},
    "hung":   {"aliases": ["Hưng"], "groups": ["Ban Giám đốc", "BGĐ"], "title": "PGĐ VTNB", "exclude": []},
    "tuan":   {"aliases": ["Tuấn"], "groups": ["Ban Giám đốc", "BGĐ"], "title": "PGĐ VTNB", "exclude": []},
    "tan":    {"aliases": ["Tấn"], "groups": ["Ban Giám đốc", "BGĐ"], "title": "PGĐ VTNB", "exclude": []},
    "phuong": {"aliases": ["Phương"], "groups": ["Ban Giám đốc", "BGĐ", "Ban Giám đốc VTNB"], "title": "GĐ VTNB",
               "exclude": []},
    # Thêm người khác ở đây theo mẫu trên nếu cần. Nếu tên người dễ trùng vào
    # tên riêng khác (địa danh, dự án, tên đơn vị...), nhớ khai báo "exclude".
}

VERBOSE = False

# =============================================================================
# Helpers chung
# =============================================================================


def norm(s):
    """Bỏ dấu tiếng Việt, lower(), gộp khoảng trắng — so khớp bất kể dấu/hoa-thường/lỗi font."""
    if s is None:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("Đ", "D").replace("đ", "d")
    return re.sub(r"\s+", " ", s).strip().lower()


def vlog(*args):
    if VERBOSE:
        print(*args)


def match_time_marker(line):
    """Trả về (time_str_or_None, phần còn lại của dòng sau khi bỏ mốc giờ)."""
    m = TIME_NUMERIC_PATTERN.match(line)
    if m:
        return m.group(1), TIME_NUMERIC_PATTERN.sub("", line, count=1)
    m = SESSION_WORD_PATTERN.match(line)
    if m:
        return m.group(1), SESSION_WORD_PATTERN.sub("", line, count=1)
    return None, line


def extract_paragraph_lines(cell):
    """Lấy list các dòng text (đã trim) không rỗng trong 1 ô bảng."""
    return [p.text.strip() for p in cell.paragraphs if p.text.strip()]


# =============================================================================
# Bước 1: Dò cấu trúc bảng (cột ngày, cột sessions) — không giả định cố định
# =============================================================================


def looks_like_day_cell(text):
    return bool(DAY_DATE_PATTERN.search(text) or WEEKDAY_PATTERN.search(text))


def detect_day_column(table):
    """
    Trả về chỉ số cột (0-based) nhiều khả năng là cột Ngày/Thứ nhất trong bảng.
    Mặc định ưu tiên cột 0 (kiểu phổ biến nhất), nhưng nếu cột 0 không hề có
    dấu hiệu ngày/thứ ở bất kỳ hàng nào thì dò các cột khác.
    """
    n_cols = len(table.columns)
    scores = [0] * n_cols
    for row in table.rows[1:]:
        cells = row.cells
        for c in range(min(n_cols, len(cells))):
            text = " ".join(extract_paragraph_lines(cells[c]))
            if looks_like_day_cell(text):
                scores[c] += 1
    if max(scores, default=0) == 0:
        return 0  # không dò được gì, dùng mặc định cột 0
    return scores.index(max(scores))


def detect_header_row(table, day_col, max_scan=3):
    """Hàng tiêu đề thường là hàng 0; nhưng phòng khi có hàng tiêu đề phụ, dò thêm."""
    for r in range(min(max_scan, len(table.rows))):
        cells = table.rows[r].cells
        non_day_texts = [
            " ".join(extract_paragraph_lines(cells[c])).strip()
            for c in range(len(cells)) if c != day_col
        ]
        if any(non_day_texts) and not any(looks_like_day_cell(t) for t in non_day_texts):
            return r
    return 0


# =============================================================================
# Bước 2: Gom dòng trong 1 ô thành các block task
# =============================================================================


def group_into_tasks(lines):
    """
    Gom các dòng trong 1 ô thành các block. Mỗi khi gặp dòng có mốc giờ/buổi,
    bắt đầu block mới. Nếu CẢ Ô không có mốc giờ nào, toàn bộ ô là 1 block
    duy nhất (không bỏ sót dữ liệu như bản cũ).
    """
    has_any_marker = any(match_time_marker(l)[0] for l in lines)
    if not has_any_marker:
        return [lines] if lines else []

    blocks, current = [], []
    for line in lines:
        marker, _ = match_time_marker(line)
        if marker:
            if current:
                blocks.append(current)
            current = [line]
        else:
            if current:
                current.append(line)
            else:
                current = [line]
    if current:
        blocks.append(current)
    return blocks


def parse_task_block(block_lines):
    """Nhận 1 block (list dòng), trả về dict: time, assignee, content, participants, location."""
    first_line = block_lines[0]
    time_str, rest_first_line = match_time_marker(first_line)

    location_parts, participants_parts = [], []
    content_parts = [rest_first_line] if rest_first_line else []

    for line in block_lines[1:]:
        if LOCATION_PREFIX.match(line):
            location_parts.append(LOCATION_PREFIX.sub("", line).strip())
        elif PARTICIPANTS_PREFIX.match(line):
            participants_parts.append(PARTICIPANTS_PREFIX.sub("", line).strip())
        else:
            if participants_parts and not LOCATION_PREFIX.match(line):
                participants_parts.append(line)
            else:
                content_parts.append(line)

    content_full = " ".join(p for p in content_parts if p).strip()

    # Đôi khi "Tại ..." nằm ngay trong content_full (không tách dòng riêng)
    inline_loc = re.search(r"\bTại\s+[^.;]+", content_full)
    if inline_loc and not location_parts:
        location_parts.append(inline_loc.group(0)[len("Tại "):].strip())
        content_full = (content_full[:inline_loc.start()] + content_full[inline_loc.end():]).strip()

    assignee = None
    for pattern in (ASSIGNEE_NAME_PREFIX, GROUP_ASSIGNEE_PATTERN):
        m = pattern.match(content_full)
        if m:
            assignee = m.group(1).strip(" -")
            break
    if assignee is None:
        m3 = ASSIGNEE_FALLBACK.match(content_full)
        if m3:
            assignee = m3.group(1).strip(" -")

    return {
        "time": time_str,
        "assignee": assignee,
        "content": content_full,
        "participants": "; ".join(participants_parts) if participants_parts else None,
        "location": "; ".join(location_parts) if location_parts else None,
    }


# =============================================================================
# Bước 3: Đọc toàn bộ bảng trong 1 file .docx
# =============================================================================


def extract_tasks_from_docx(path):
    """Đọc 1 file .docx lịch tuần, trả về DataFrame các task."""
    document = docx.Document(path)
    all_rows = []

    for t_idx, table in enumerate(document.tables):
        n_cols = len(table.columns)
        if n_cols < 2 or len(table.rows) < 2:
            continue

        day_col = detect_day_column(table)
        header_row = detect_header_row(table, day_col)
        header_cells = table.rows[header_row].cells
        session_cols = [c for c in range(len(header_cells)) if c != day_col]
        session_names = {
            c: (" ".join(extract_paragraph_lines(header_cells[c])) or f"Cột{c}")
            for c in session_cols
        }
        if not any(session_names.values()):
            continue

        vlog(f"[{path}] Bảng #{t_idx}: day_col={day_col}, header_row={header_row}, "
             f"sessions={list(session_names.values())}")

        current_day, current_date = None, None

        for row in table.rows[header_row + 1:]:
            cells = row.cells
            if day_col >= len(cells):
                continue
            day_cell_text = " ".join(extract_paragraph_lines(cells[day_col]))
            date_match = DAY_DATE_PATTERN.search(day_cell_text)
            day_text = DAY_DATE_PATTERN.sub("", day_cell_text).strip(" ,/-")

            if day_text:
                current_day = day_text
            if date_match:
                current_date = date_match.group(1)

            for col_idx in session_cols:
                if col_idx >= len(cells):
                    continue
                session = session_names.get(col_idx, f"Cột{col_idx}")
                lines = extract_paragraph_lines(cells[col_idx])
                if not lines:
                    continue
                for block in group_into_tasks(lines):
                    task = parse_task_block(block)
                    if not task["content"] or len(task["content"]) < 2:
                        continue
                    task.update({
                        "source_file": str(path),
                        "table_index": t_idx,
                        "day": current_day,
                        "date": current_date,
                        "session": session,
                    })
                    all_rows.append(task)

    cols = ["source_file", "table_index", "day", "date", "session", "time",
            "assignee", "content", "participants", "location"]
    return pd.DataFrame(all_rows, columns=cols)


def extract_tasks_from_files(paths):
    dfs = []
    for p in paths:
        p = Path(p)
        if p.suffix.lower() == ".doc":
            print(f"CẢNH BÁO: '{p}' là định dạng .doc cũ, script chỉ đọc .docx. "
                  f"Hãy 'Save As' sang .docx trong Word rồi thử lại.")
            continue
        if p.suffix.lower() != ".docx":
            print(f"Bỏ qua '{p}' (không phải .docx).")
            continue
        try:
            dfs.append(extract_tasks_from_docx(str(p)))
        except Exception as e:
            print(f"Lỗi khi đọc '{p}': {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


# =============================================================================
# Chế độ chẩn đoán
# =============================================================================


def diagnose(paths):
    global VERBOSE
    old = VERBOSE
    VERBOSE = True
    for p in paths:
        p = Path(p)
        if p.suffix.lower() != ".docx":
            print(f"\n=== {p} ===\n  Bỏ qua (không phải .docx)")
            continue
        print(f"\n=== {p} ===")
        try:
            document = docx.Document(str(p))
        except Exception as e:
            print(f"  Lỗi mở file: {e}")
            continue
        if not document.tables:
            print("  Không tìm thấy bảng nào trong file.")
            continue
        df = extract_tasks_from_docx(str(p))
        print(f"  Tổng số bảng: {len(document.tables)}")
        print(f"  Tổng số task trích xuất được: {len(df)}")
        if len(df):
            print(f"  Số ngày khác nhau nhận diện được: {df['day'].nunique()}")
            print(f"  Ví dụ 3 dòng đầu:")
            with pd.option_context("display.max_colwidth", 60):
                print(df.head(3).to_string())
    VERBOSE = old


# =============================================================================
# Bước 4: Lọc task theo người (đã bỏ debug print, dùng --verbose nếu cần)
# =============================================================================


def filter_tasks_by_person(df, person_key):
    """
    Lọc các task liên quan tới 1 người, gồm:
      1. Task ghi rõ tên người đó ở assignee/content/participants.
      2. Task không ghi tên ai cụ thể nhưng nhắc tới nhóm/ban mà người đó
         thuộc về (tra theo PERSON_GROUPS).
    Nếu 'content' có nhiều phần phân tách bởi ; hoặc "và", chỉ giữ phần liên
    quan trực tiếp tới người đang lọc.
    """
    info = PERSON_GROUPS.get(person_key, {"aliases": [person_key], "groups": [], "exclude": []})
    aliases_norm = [norm(a) for a in info.get("aliases", [person_key])]
    groups_norm = [norm(g) for g in info.get("groups", [])]
    exclude_norm = [norm(e) for e in info.get("exclude", [])]

    def strip_excluded(n):
        for e in exclude_norm:
            n = n.replace(e, " ")
        return n

    def has_alias(text):
        n = strip_excluded(norm(text))
        return any(a in n for a in aliases_norm)

    def has_group(text):
        n = strip_excluded(norm(text))
        return any(g in n for g in groups_norm)

    def relevant(text):
        return bool(text) and (has_alias(text) or has_group(text))

    filtered_records = []
    for _, row in df.iterrows():
        new_row = row.copy()

        assignee_matches = relevant(str(new_row.get("assignee") or ""))
        participants_matches = relevant(str(new_row.get("participants") or ""))

        original_content = str(new_row.get("content") or "")
        content_parts = re.split(r"[;,]\s*|\s+và\s+", original_content, flags=re.IGNORECASE)
        content_parts = [part.strip() for part in content_parts if part.strip()]
        relevant_content_parts = [part for part in content_parts if relevant(part)]
        content_mentions_person = bool(relevant_content_parts)

        row_is_relevant = assignee_matches or participants_matches or content_mentions_person
        if not row_is_relevant:
            continue

        vlog(f"[match] {new_row.get('date')} {new_row.get('time')} | "
             f"assignee={new_row.get('assignee')!r} content={original_content[:80]!r}")

        if relevant_content_parts:
            new_row["content"] = "; ".join(relevant_content_parts)
        elif not content_mentions_person and (assignee_matches or participants_matches):
            # Người được nêu ở assignee/participants nhưng content không tách được
            # theo cụm riêng -> giữ nguyên toàn bộ content (không xoá mất thông tin).
            new_row["content"] = original_content
        filtered_records.append(new_row)

    return pd.DataFrame(filtered_records, columns=df.columns)


# =============================================================================
# CLI
# =============================================================================


def run_colab(person_key, out_prefix):
    from google.colab import files as colab_files

    uploaded = colab_files.upload()
    docx_paths = [p for p in uploaded.keys() if p.lower().endswith(".docx")]
    print("Đã upload:", docx_paths)

    df_all = extract_tasks_from_files(docx_paths)
    print(f"Tổng số task trích xuất được: {len(df_all)}")
    try:
        display(df_all)  # noqa: F821 - chỉ tồn tại trong môi trường notebook
    except NameError:
        print(df_all.head(10))

    all_path = f"{out_prefix}_all.xlsx"
    df_all.to_excel(all_path, index=False)
    df_all.to_csv(f"{out_prefix}_all.csv", index=False, encoding="utf-8-sig")
    print("Đã lưu:", all_path)
    colab_files.download(all_path)

    if person_key:
        df_person = filter_tasks_by_person(df_all, person_key)
        print(f"\nSố task liên quan tới '{person_key}': {len(df_person)}")
        try:
            display(df_person)  # noqa: F821
        except NameError:
            print(df_person.head(10))
        person_path = f"{out_prefix}_{person_key}.xlsx"
        df_person.to_excel(person_path, index=False)
        colab_files.download(person_path)


def main():
    global VERBOSE
    ap = argparse.ArgumentParser(description="Trích xuất công việc từ Lịch công tác tuần (.docx), lọc theo người.")
    ap.add_argument("files", nargs="*", help="Đường dẫn (các) file .docx")
    ap.add_argument("--person", default=None, help=f"Key người cần lọc. Đã cấu hình: {', '.join(PERSON_GROUPS)}")
    ap.add_argument("--out", default="tasks_extracted.xlsx", help="Đường dẫn file .xlsx xuất TOÀN BỘ task")
    ap.add_argument("--diagnose", action="store_true", help="Chỉ chẩn đoán cấu trúc file, không lọc người")
    ap.add_argument("--colab", action="store_true", help="Chạy theo luồng Colab (upload file trong notebook)")
    ap.add_argument("--verbose", action="store_true", help="In chi tiết quá trình dò cấu trúc/lọc")
    args = ap.parse_args()
    VERBOSE = args.verbose

    if args.colab:
        run_colab(args.person, Path(args.out).stem)
        return

    if not args.files:
        sys.exit("Cần truyền ít nhất 1 file .docx (hoặc dùng --colab nếu đang chạy trong Colab).")

    if args.diagnose:
        diagnose(args.files)
        return

    df_all = extract_tasks_from_files(args.files)
    print(f"Tổng số task trích xuất được: {len(df_all)}")
    df_all.to_excel(args.out, index=False)
    print(f"Đã lưu toàn bộ task ra: {args.out}")

    if args.person:
        df_person = filter_tasks_by_person(df_all, args.person)
        print(f"Số task liên quan tới '{args.person}': {len(df_person)}")
        person_out = f"{Path(args.out).stem}_{args.person}.xlsx"
        df_person.to_excel(person_out, index=False)
        print(f"Đã lưu task của '{args.person}' ra: {person_out}")


if __name__ == "__main__":
    main()