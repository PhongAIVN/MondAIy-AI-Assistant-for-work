from __future__ import annotations

import json
import time

from scripts.write_coverage_summary import main


def test_write_coverage_summary_uses_weighted_lines_and_real_timestamp(tmp_path) -> None:
    coverage_xml = tmp_path / "coverage.xml"
    output = tmp_path / "coverage-summary.json"
    coverage_xml.write_text(
        """<?xml version="1.0" ?>
<coverage lines-covered="3" lines-valid="4" line-rate="0.75">
  <packages><package name="src"><classes>
    <class filename="agents/a.py"><lines>
      <line number="1" hits="1"/><line number="2" hits="0"/><line number="3" hits="0"/>
    </lines></class>
    <class filename="src/api/b.py"><lines><line number="1" hits="1"/></lines></class>
  </classes></package></packages>
</coverage>
""",
        encoding="utf-8",
    )
    before = int(time.time())

    assert main(["--input", str(coverage_xml), "--output", str(output)]) == 0

    after = int(time.time())
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert before <= payload["generated_at"] <= after
    assert payload["components"] == {"backend": 75.0, "agent": 33.33}
