"""Kho bài blog mock — RAM + file data/blog-posts.json để còn sau restart."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from src.config import get_settings

_LOCK = Lock()
_POSTS: list[dict[str, Any]] | None = None


def _store_path() -> Path:
    root = Path(get_settings().chroma_persist_dir).resolve().parent
    root.mkdir(parents=True, exist_ok=True)
    return root / "blog-posts.json"


def _load() -> list[dict[str, Any]]:
    global _POSTS
    if _POSTS is not None:
        return _POSTS
    path = _store_path()
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            _POSTS = data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            _POSTS = []
    else:
        _POSTS = []
    return _POSTS


def _persist(posts: list[dict[str, Any]]) -> None:
    path = _store_path()
    path.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def list_posts() -> list[dict[str, Any]]:
    """Trả bản sao danh sách bài đã đăng (mock)."""
    with _LOCK:
        return deepcopy(_load())


def get_post_by_slug(slug: str) -> dict[str, Any] | None:
    """Tìm bài theo slug; ưu tiên bản mới nhất nếu trùng."""
    with _LOCK:
        for post in _load():
            if post.get("slug") == slug:
                return deepcopy(post)
    return None


def publish_post(payload: dict[str, Any]) -> dict[str, Any]:
    """Lưu bài mock (file + RAM) và trả bản ghi đã gán id/publishedAt."""
    global _POSTS
    post = {
        **payload,
        "id": f"blog-{uuid4().hex[:10]}",
        "publishedAt": datetime.now(UTC).date().isoformat(),
        "status": "published_mock",
    }
    with _LOCK:
        posts = [p for p in _load() if p.get("slug") != post["slug"]]
        posts.insert(0, post)
        _POSTS = posts
        _persist(posts)
        return deepcopy(post)


def clear_posts() -> None:
    """Xoá kho mock — chỉ dùng trong test."""
    global _POSTS
    with _LOCK:
        _POSTS = []
        path = _store_path()
        if path.is_file():
            path.unlink()
