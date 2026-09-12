"""Hỏi thử kho chunk từ dòng lệnh, để nhìn kết quả truy hồi bằng mắt.

    python scripts/discord/search.py "hạn nộp gate 2 là khi nào"

Chỉ là công cụ nội bộ: không lọc quyền, không kiểm consent. Đừng dùng lại đường
này cho API — bước lọc quyền phải nằm ở tầng gọi, xem retrieval.py.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.db import engine  # noqa: E402
from src.services.retrieval import Filters, retrieve  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Tìm thử trong kho chunk Discord")
    p.add_argument("question")
    p.add_argument("-k", type=int, default=5, help="số kết quả")
    p.add_argument("--role", action="append", help="chỉ lấy chunk có người gửi giữ role này")
    p.add_argument("--tier", action="append", help="chỉ lấy nguồn mức này, A hoặc B")
    p.add_argument("--since", help="YYYY-MM-DD")
    p.add_argument("--full", action="store_true", help="in đầy đủ nội dung chunk")
    args = p.parse_args()

    filters = Filters(
        roles=args.role,
        tier=args.tier,
        since=datetime.fromisoformat(args.since).astimezone() if args.since else None,
    )
    results = retrieve(engine, args.question, filters, k=args.k)
    if not results:
        print("không có kết quả nào")
        return

    for i, r in enumerate(results, 1):
        d = r.score
        nguon = []
        if d.fts_rank:
            nguon.append(f"fts#{d.fts_rank}")
        if d.vector_rank:
            nguon.append(f"vec#{d.vector_rank}")
        print(f"\n{'─' * 78}")
        print(
            f"{i}. [{r.channel}] mức {r.tier} · {r.mode} · {r.message_count} tin"
            f" · {r.occurred_at:%Y-%m-%d %H:%M}"
        )
        print(
            f"   điểm {d.total:.5f} = rrf {d.rrf:.5f} × mức {d.tier_weight}"
            f" × mới {d.recency_weight:.3f}   [{', '.join(nguon) or 'không khớp nhánh nào'}]"
        )
        if r.roles:
            print(f"   role người gửi: {', '.join(r.roles[:6])}")
        if r.deep_link:
            print(f"   {r.deep_link}")
        noi_dung = r.text if args.full else r.text[:520]
        print("   " + noi_dung.replace("\n", "\n   "))


if __name__ == "__main__":
    main()
