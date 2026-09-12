"""Kiểm tra contract hướng dẫn dùng chung cho coding agent."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _resolve_shell_path(raw: str) -> Path:
    """Chuẩn hoá output `pwd` từ shell POSIX về Path so sánh được với REPO_ROOT.

    Git Bash (MSYS2) tự dịch đường dẫn Windows sang dạng "/c/Users/..." —
    pathlib trên Windows không hiểu dạng này, `Path("/c/...").resolve()` ghép
    nhầm thành "<ổ đĩa hiện tại>:/c/Users/...". Chỉ Windows cần dịch ngược;
    Unix thật thì "/..." đã đúng path hệ thống, không đụng vào.
    """
    raw = raw.strip()
    if os.name == "nt" and len(raw) > 2 and raw[0] == "/" and raw[2] == "/":
        raw = f"{raw[1].upper()}:{raw[2:]}"
    return Path(raw).resolve()


@pytest.fixture(scope="session", autouse=True)
def _create_tables() -> None:
    """Tắt fixture DB toàn cục vì contract test chỉ đọc Markdown tĩnh."""


def test_claude_imports_agents_without_duplicating_old_contract() -> None:
    """CLAUDE.md chỉ làm shim và không giữ lại các section vận hành cũ."""
    claude_text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")

    assert "@AGENTS.md" in claude_text
    assert "## Quy ước code" not in claude_text
    assert len(claude_text.splitlines()) <= 12


def test_agents_contract_contains_required_delivery_gates() -> None:
    """AGENTS.md phải giữ các gate test, orchestration và change evidence."""
    agents_text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    required_markers = (
        "Research, planning and parallel work",
        "Required evidence",
        "New or changed code gets an observable test",
        "Tests and completion",
        "Merge and deploy",
        "No external approval",
        "`client/web-app` uses npm",
        "`client/extension` uses pnpm",
    )
    for marker in required_markers:
        assert marker in agents_text

    assert "Không dùng `pnpm`" not in agents_text


def test_claude_hooks_return_to_project_root_before_running(tmp_path: Path) -> None:
    """Hook phải chạy đúng repo dù Claude phát sự kiện từ một thư mục con.

    Hook command là cú pháp POSIX sh — trên Windows không có "/bin/sh" cố
    định như Unix, nhưng Git Bash (bắt buộc phải cài để dùng Claude Code trên
    Windows — xem Bash tool description) cung cấp "sh" hợp lệ qua PATH. Tra
    qua shutil.which thay vì hardcode "/bin/sh" để chạy đúng trên cả 2 hệ,
    thay vì skip hẳn trên Windows và mất coverage ngay tại máy dev chính.
    """
    sh_executable = shutil.which("sh")
    if sh_executable is None:
        pytest.skip("Không tìm thấy shell POSIX (sh) khả dụng qua PATH trên máy này.")

    settings = json.loads((REPO_ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for event_hooks in settings["hooks"].values()
        for matcher in event_hooks
        for hook in matcher["hooks"]
    ]
    assert commands

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_bash = fake_bin / "bash"
    fake_bash.write_text("#!/bin/sh\npwd\n", encoding="utf-8")
    fake_bash.chmod(0o755)
    env = {
        **os.environ,
        "CLAUDE_PROJECT_DIR": str(REPO_ROOT),
        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
    }

    for command in commands:
        result = subprocess.run(
            [sh_executable, "-c", command],
            cwd=tmp_path,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        assert _resolve_shell_path(result.stdout) == REPO_ROOT.resolve()
