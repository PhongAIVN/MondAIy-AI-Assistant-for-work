"""TAPB-122 — gọi DiscordChatExporter cào các kênh trong config, ghi vào kho raw.

    DISCORD_TOKEN=... python scripts/discord/export_dce.py -c scripts/discord/channels.json

Mỗi lần chạy tạo một run riêng dưới `data/discord/raw/<run_id>/`, không đè run
cũ, để còn so được giữa các lần cào và cào bù phần thiếu. Kèm `_run.json` ghi
lại đã chạy lệnh gì, bản DCE nào, kênh nào xong kênh nào lỗi.

Cào tiếp lần sau thì thêm `--incremental`: đọc `last_message_id` của từng kênh,
gộp qua mọi run đã chuẩn hóa, rồi truyền `--after` cho DCE để chỉ kéo tin mới.

Hai lựa chọn không nên đổi nếu vẫn muốn khớp shape của bot:

- `--markdown false` là bắt buộc. Mặc định của DCE viết lại `<@123>` thành
  `@username` ngay trong JSON, làm content khác hẳn bot trả về và mất token để
  suy ra `mention_roles`.
- Token truyền qua biến môi trường chứ không qua tham số dòng lệnh, để nó không
  lọt vào `ps` hay history của shell.

Cào xong thì chuẩn hóa bằng `scripts/discord/dce_to_raw.py`. Cào và chuẩn hóa
tách làm hai bước để sửa logic chuẩn hóa xong chạy lại được mà không phải cào
lại từ đầu.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
RAW_ROOT = REPO / "data" / "discord" / "raw"


def resolve_dce(explicit: str | None) -> list[str]:
    """Tìm cách gọi DCE: tham số, biến môi trường, rồi tới lệnh trong PATH."""
    raw = explicit or os.environ.get("DCE_CMD") or "discordchatexporter"
    parts = shlex.split(raw)
    # Bản tải về dạng .dll thì phải chạy qua dotnet.
    if parts and parts[0].endswith(".dll"):
        parts = ["dotnet", *parts]
    return parts


def dce_version(cmd: list[str]) -> str | None:
    """Hỏi bản DCE để ghi vào run, thất bại thì thôi chứ không chặn việc cào."""
    try:
        out = subprocess.run([*cmd, "--version"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return (out.stdout or out.stderr).strip() or None


def load_channels(path: Path) -> list[dict[str, Any]]:
    """Đọc config, chấp nhận cả danh sách trần lẫn object có khóa `channels`."""
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    channels = data if isinstance(data, list) else data.get("channels") or []
    out: list[dict[str, Any]] = []
    for item in channels:
        entry = {"id": item, "label": item} if isinstance(item, str) else dict(item)
        if not entry.get("id"):
            sys.exit(f"Có mục thiếu `id` trong {path}")
        entry.setdefault("label", entry["id"])
        if entry.get("skip"):
            continue
        out.append(entry)
    if not out:
        sys.exit(f"Không có kênh nào để cào trong {path}")
    return out


def resume_cursors() -> dict[str, str]:
    """Gộp last_message_id theo kênh qua **mọi** run chuẩn hóa, run mới đè run cũ.

    Cơ chế: duyệt manifest theo thứ tự run_id (tên thư mục là giờ UTC nên sắp
    chuỗi là sắp thời gian), ghi đè dần từng kênh, chỉ nhận giá trị khác rỗng.

    Vì sao không đọc mỗi manifest gần nhất: một run tăng dần chỉ chứa tin mới, và
    kênh nào không có tin mới thì `last_message_id` của nó là `null`. Chỉ nhìn
    run cuối thì những kênh im lặng mất con trỏ và lần sau bị cào lại từ đầu —
    vừa tốn thời gian, vừa nạp lại toàn bộ lịch sử vào kho raw mỗi lần.
    """
    normalized = RAW_ROOT.parent / "normalized"
    cursors: dict[str, str] = {}
    for path in sorted(normalized.glob("*/_manifest.json"), key=lambda p: p.parent.name):
        try:
            with path.open(encoding="utf-8") as f:
                manifest = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            # Manifest hỏng của một run cũ không được chặn lần cào này; bỏ qua nó
            # thì cùng lắm là cào thừa, còn dừng lại thì không cào được gì.
            print(f"bỏ qua manifest hỏng {path}: {e}", file=sys.stderr)
            continue
        for row in manifest.get("channels", []):
            if row.get("channel_id") and row.get("last_message_id"):
                cursors[row["channel_id"]] = row["last_message_id"]
    return cursors


def build_command(
    dce: list[str],
    channel_id: str,
    out_dir: Path,
    include_threads: str,
    after: str | None,
    before: str | None,
    media: bool,
) -> list[str]:
    """Dựng lệnh export cho một kênh; token đi qua môi trường nên không có ở đây."""
    cmd = [
        *dce,
        "export",
        "--channel",
        channel_id,
        "--format",
        "Json",
        "--markdown",
        "false",
        "--include-threads",
        include_threads,
        "--output",
        str(out_dir / "%C_%c.json"),
    ]
    if after:
        cmd += ["--after", after]
    if before:
        cmd += ["--before", before]
    if media:
        cmd += ["--media", "--reuse-media", "--media-dir", str(out_dir.parent.parent / "media")]
    return cmd


def main() -> None:
    parser = argparse.ArgumentParser(description="Cào kênh Discord bằng DiscordChatExporter")
    parser.add_argument("-c", "--config", type=Path, required=True, help="file JSON liệt kê kênh cần cào")
    parser.add_argument("--dce", help="lệnh chạy DCE, mặc định lấy DCE_CMD rồi tới discordchatexporter")
    parser.add_argument("--run-id", help="tên run, mặc định theo giờ UTC lúc chạy")
    parser.add_argument(
        "--include-threads",
        default="all",
        choices=["none", "active", "all"],
        help="kéo kèm thread, mặc định all",
    )
    parser.add_argument("--after", help="chỉ lấy tin sau mốc này, nhận ngày hoặc message id")
    parser.add_argument("--before", help="chỉ lấy tin trước mốc này")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="cào tiếp từ last_message_id của từng kênh, gộp qua mọi run đã chuẩn hóa",
    )
    parser.add_argument("--media", action="store_true", help="tải kèm file đính kèm, tốn dung lượng")
    parser.add_argument("--dry-run", action="store_true", help="chỉ in lệnh sẽ chạy")
    args = parser.parse_args()

    token = os.environ.get("DISCORD_TOKEN", "")
    if not token and not args.dry_run:
        sys.exit("Thiếu DISCORD_TOKEN trong môi trường. Xem scripts/discord/README.md.")

    dce = resolve_dce(args.dce)
    channels = load_channels(args.config)
    run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = RAW_ROOT / run_id
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    resume = resume_cursors() if args.incremental else {}
    if args.incremental and not resume:
        print("Chưa có manifest cũ nên lần này cào toàn bộ.", file=sys.stderr)

    env = {**os.environ, "DISCORD_TOKEN": token}
    started = datetime.now(UTC).isoformat()
    results: list[dict[str, Any]] = []

    for channel in channels:
        after = args.after or resume.get(channel["id"])
        cmd = build_command(
            dce, channel["id"], out_dir, args.include_threads, after, args.before, args.media
        )
        label = f"{channel['label']} ({channel['id']})"

        if args.dry_run:
            print(shlex.join(cmd))
            continue

        print(f"cào {label}{' từ ' + after if after else ''}", file=sys.stderr)
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        ok = proc.returncode == 0
        if not ok:
            print(f"LỖI {label}: {proc.stderr.strip()[:500]}", file=sys.stderr)
        results.append(
            {
                "channel_id": channel["id"],
                "label": channel["label"],
                "after": after,
                "ok": ok,
                "returncode": proc.returncode,
                # Giữ lệnh để sau còn dựng lại đúng run này, token không nằm trong đây.
                "command": shlex.join(cmd),
                "stderr": proc.stderr.strip()[-2000:] if not ok else "",
            }
        )

    if args.dry_run:
        return

    files = sorted(p.name for p in out_dir.glob("*.json") if not p.name.startswith("_"))
    run_meta = {
        "run_id": run_id,
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "dce_version": dce_version(dce),
        "config": str(args.config),
        "include_threads": args.include_threads,
        "markdown": False,
        "media": args.media,
        "incremental": args.incremental,
        "channels": results,
        "files": files,
    }
    with (out_dir / "_run.json").open("w", encoding="utf-8") as f:
        json.dump(run_meta, f, ensure_ascii=False, indent=2)

    failed = [r["label"] for r in results if not r["ok"]]
    print(f"\n{len(files)} file -> {out_dir}", file=sys.stderr)
    if failed:
        print(f"CẢNH BÁO: {len(failed)} kênh lỗi: {', '.join(failed)}", file=sys.stderr)
    print(f"Chuẩn hóa: python scripts/discord/dce_to_raw.py {out_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
