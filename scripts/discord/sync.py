"""TAPB-122 — cào tiếp phần Discord mới và đưa thẳng vào kho, một lệnh duy nhất.

    DISCORD_TOKEN=... DCE_CMD=~/tools/dce/DiscordChatExporter.Cli \\
        python scripts/discord/sync.py -c scripts/discord/channels.json

Chạy lần lượt bốn bước vốn phải gõ tay: cào tăng dần -> chuẩn hóa -> chunk ->
nạp DB, và `--embed` thì thêm bước nhúng vector. Mặc định là **tăng dần**: mỗi
kênh chỉ kéo phần sau `last_message_id` đã cào được ở những lần trước, nên chạy
lại nhiều lần chỉ tốn đúng phần mới.

Mỗi bước vẫn là một script chạy độc lập được. Sync chỉ gọi lại chúng theo thứ tự
chứ không nhân bản logic — hỏng ở bước nào thì chạy lại đúng script đó với run_id
in ra ở dòng đầu, không phải cào lại từ đầu.

Không có tin mới thì DCE không ghi file nào; lúc đó sync dừng sạch với mã 0 chứ
không coi là lỗi. Đây là trạng thái bình thường của một lần chạy định kỳ.

Xem `--dry-run` để biết chính xác nó sẽ chạy những lệnh gì trước khi chạy thật.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DATA = REPO / "data" / "discord"


def raw_dir(run_id: str) -> Path:
    return DATA / "raw" / run_id


def normalized_dir(run_id: str) -> Path:
    return DATA / "normalized" / run_id


def export_step(run_id: str, config: Path, *, full: bool, media: bool) -> list[str]:
    """Lệnh cào. Không có `--incremental` nghĩa là cào lại toàn bộ lịch sử."""
    cmd = [
        sys.executable,
        str(HERE / "export_dce.py"),
        "-c",
        str(config),
        "--run-id",
        run_id,
    ]
    if not full:
        cmd.append("--incremental")
    if media:
        cmd.append("--media")
    return cmd


def downstream_steps(run_id: str, *, embed: bool) -> list[list[str]]:
    """Ba (hoặc bốn) bước sau khi đã có raw: chuẩn hóa, chunk, nạp, nhúng.

    Tách khỏi bước cào để chạy lại được phần xử lý trên một run đã cào xong —
    đúng cái vòng lặp hay gặp khi sửa luật chunk.
    """
    steps = [
        [sys.executable, str(HERE / "dce_to_raw.py"), str(raw_dir(run_id))],
        [sys.executable, str(HERE / "chunker.py"), str(normalized_dir(run_id))],
        [sys.executable, str(HERE / "load_to_db.py"), run_id],
    ]
    if embed:
        steps.append([sys.executable, str(HERE / "embed_chunks.py"), run_id])
    return steps


def has_raw_files(run_id: str) -> bool:
    """Run này có file nào để chuẩn hóa không; `_run.json` không tính."""
    directory = raw_dir(run_id)
    if not directory.is_dir():
        return False
    return any(p for p in directory.glob("*.json") if not p.name.startswith("_"))


def run_steps(
    steps: list[list[str]],
    runner: Callable[[list[str]], int] = lambda cmd: subprocess.run(cmd).returncode,
) -> int:
    """Chạy lần lượt, dừng ngay ở bước đầu tiên hỏng.

    Chạy tiếp sau khi một bước hỏng chỉ tạo ra kho nửa vời: nạp DB từ một thư mục
    chunk chưa sinh xong nghĩa là kho thiếu tin mà không ai biết là thiếu.
    `runner` tách ra để test kiểm được thứ tự lệnh mà không phải cào thật.
    """
    for cmd in steps:
        print(f"\n$ {' '.join(cmd)}", file=sys.stderr)
        code = runner(cmd)
        if code != 0:
            print(f"Dừng: bước trên thoát với mã {code}.", file=sys.stderr)
            return code
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Cào tiếp Discord rồi nạp vào kho")
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=HERE / "channels.json",
        help="file JSON liệt kê kênh, mặc định scripts/discord/channels.json",
    )
    parser.add_argument("--run-id", help="tên run, mặc định theo giờ UTC lúc chạy")
    parser.add_argument(
        "--full",
        action="store_true",
        help="cào lại toàn bộ lịch sử thay vì chỉ phần mới",
    )
    parser.add_argument("--embed", action="store_true", help="nhúng vector sau khi nạp")
    parser.add_argument("--media", action="store_true", help="tải kèm file đính kèm")
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="bỏ bước cào, chỉ xử lý lại một run đã có (bắt buộc kèm --run-id)",
    )
    parser.add_argument("--dry-run", action="store_true", help="chỉ in các lệnh sẽ chạy")
    args = parser.parse_args()

    if args.skip_export and not args.run_id:
        sys.exit("--skip-export cần --run-id của run đã cào trước đó.")
    if not args.skip_export and not args.config.is_file():
        sys.exit(f"Không thấy {args.config}. Xem scripts/discord/README.md.")

    run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    print(f"run_id: {run_id}", file=sys.stderr)

    if args.dry_run:
        steps = [] if args.skip_export else [export_step(run_id, args.config, full=args.full, media=args.media)]
        for cmd in [*steps, *downstream_steps(run_id, embed=args.embed)]:
            print(" ".join(cmd))
        return

    if not args.skip_export:
        code = run_steps([export_step(run_id, args.config, full=args.full, media=args.media)])
        if code != 0:
            sys.exit(code)

    if not has_raw_files(run_id):
        # Kênh nào cũng im lặng từ lần cào trước. Không có gì để chuẩn hóa, và
        # đây không phải lỗi — báo rồi thoát sạch để cron không kêu.
        print("Không có tin mới nào kể từ lần cào trước.", file=sys.stderr)
        return

    code = run_steps(downstream_steps(run_id, embed=args.embed))
    if code != 0:
        sys.exit(code)
    print(f"\nXong. run_id {run_id} đã nằm trong kho.", file=sys.stderr)


if __name__ == "__main__":
    main()
