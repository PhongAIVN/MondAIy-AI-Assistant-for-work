from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from xml.etree import ElementTree


def _percentage(covered: int, valid: int, component: str) -> float:
    if valid <= 0:
        raise ValueError(f"coverage.xml không có line cho component {component}")
    return round(covered * 100 / valid, 2)


def _agent_coverage(root: ElementTree.Element) -> float:
    lines: dict[tuple[str, str], bool] = {}
    for class_node in root.findall(".//class"):
        filename = str(class_node.get("filename") or "").replace("\\", "/")
        # coverage.py ghi path tương đối với source root (`agents/...`) khi chạy
        # `--cov=src`; một số runner khác giữ nguyên prefix `src/agents/...`.
        if not filename.startswith(("agents/", "src/agents/")):
            continue
        for line in class_node.findall("./lines/line"):
            number = str(line.get("number") or "")
            if number:
                lines[(filename, number)] = int(line.get("hits") or 0) > 0
    return _percentage(sum(lines.values()), len(lines), "agent")


def build_summary(coverage_xml: Path, *, generated_at: int | None = None) -> dict:
    root = ElementTree.parse(coverage_xml).getroot()
    covered = int(root.attrib["lines-covered"])
    valid = int(root.attrib["lines-valid"])
    return {
        "generated_at": int(time.time()) if generated_at is None else generated_at,
        "components": {
            "backend": _percentage(covered, valid, "backend"),
            "agent": _agent_coverage(root),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sinh coverage summary cho Prometheus từ coverage.xml")
    parser.add_argument("--input", type=Path, default=Path("coverage.xml"))
    parser.add_argument("--output", type=Path, default=Path("observability/coverage-summary.json"))
    args = parser.parse_args(argv)

    summary = build_summary(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, separators=(",", ":")) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
