"""Nhập lịch chương trình từ ICS feed của ban tổ chức vào bảng `program_events`.

Ban tổ chức không mở API; feed `.ics` trên trang lịch là nguồn duy nhất lấy được
bằng máy. URL feed chứa token cá nhân nên **không được commit** — đặt trong
`.env` qua biến `PHOENIX_ICS_FEED_URL`, hoặc truyền thẳng khi chạy tay.

    python scripts/import_program_calendar.py                    # đọc URL từ .env
    python scripts/import_program_calendar.py <url-hoac-duong-dan-file>
    python scripts/import_program_calendar.py <url> cohort-iii   # chỉ định cohort

Chạy lại nhiều lần là an toàn: khóa upsert là (cohort_slug, UID của ICS), nội
dung không đổi thì chỉ dời mốc quan sát. Script không xóa mốc vắng mặt trong
feed — xem lý do trong `src/services/program_calendar.py`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.db import SessionLocal  # noqa: E402
from src.services.program_calendar import import_program_calendar  # noqa: E402


def _read_source(source: str) -> str:
    """Đọc feed từ URL hoặc từ file trên đĩa.

    Cho phép đường dẫn file để chạy lại được trên một bản feed đã tải về, ví dụ
    khi cần dựng lại dữ liệu mà không muốn gọi ra ngoài mạng.
    """
    if source.startswith(("http://", "https://")):
        response = httpx.get(source, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        return response.text
    return Path(source).read_text(encoding="utf-8")


def main(argv: list[str]) -> int:
    settings = get_settings()
    source = argv[0] if argv else settings.phoenix_ics_feed_url
    cohort = argv[1] if len(argv) > 1 else settings.program_cohort_slug

    if not source:
        print(
            "Chưa có nguồn lịch. Đặt PHOENIX_ICS_FEED_URL trong .env hoặc truyền "
            "URL/đường dẫn file làm tham số đầu tiên."
        )
        return 2

    try:
        raw = _read_source(source)
    except Exception as exc:
        print(f"Không đọc được feed: {exc}")
        return 1

    with SessionLocal() as db:
        result = import_program_calendar(db, raw, cohort_slug=cohort)

    print(
        f"Cohort {cohort}: {result.created} mốc mới, {result.updated} cập nhật, "
        f"{result.unchanged} không đổi (tổng {result.total})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
