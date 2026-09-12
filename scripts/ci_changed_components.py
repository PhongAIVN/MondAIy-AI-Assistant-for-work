#!/usr/bin/env python3
"""Classify a Git diff so CI only runs checks affected by the change.

The safe default is to run both language stacks whenever a base revision cannot
be resolved or an automation/configuration file changes.
"""

from __future__ import annotations

import argparse
import subprocess
from collections.abc import Iterable

_ALWAYS_FULL = (
    ".github/",
    "docker-compose",
    "Dockerfile",
    ".gitleaks.toml",
    "pytest.ini",
    "requirements",
    "pyproject.toml",
    "ruff.toml",
)
_BACKEND = ("src/", "tests/", "scripts/", "alembic/", "observability/")
_FRONTEND = ("client/web-app/",)


def classify_paths(paths: Iterable[str]) -> tuple[bool, bool]:
    """Return ``(run_backend, run_frontend)`` for changed repository paths."""
    backend = frontend = False
    for path in paths:
        normalized = path.strip()
        while normalized.startswith("./"):
            normalized = normalized[2:]
        if not normalized:
            continue
        if normalized.startswith(_ALWAYS_FULL) or normalized in _ALWAYS_FULL:
            return True, True
        backend = backend or normalized.startswith(_BACKEND)
        frontend = frontend or normalized.startswith(_FRONTEND)
    return backend, frontend


def requires_full_backend(paths: Iterable[str]) -> bool:
    """Return whether a change needs the full backend gate instead of smoke."""
    for path in paths:
        normalized = path.strip()
        while normalized.startswith("./"):
            normalized = normalized[2:]
        if normalized.startswith(_ALWAYS_FULL) or normalized in _ALWAYS_FULL:
            return True
    return False


def changed_paths(base: str, head: str) -> list[str] | None:
    """Return paths changed from base to head, or ``None`` if comparison is unsafe."""
    if not base or set(base) == {"0"}:
        return None
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base, head],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None
    return result.stdout.splitlines()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("head")
    args = parser.parse_args()
    paths = changed_paths(args.base, args.head)
    backend, frontend = (True, True) if paths is None else classify_paths(paths)
    backend_mode = "full" if paths is None or requires_full_backend(paths) else "smoke"
    print(f"backend={'true' if backend else 'false'}")
    print(f"frontend={'true' if frontend else 'false'}")
    print(f"backend_mode={backend_mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
