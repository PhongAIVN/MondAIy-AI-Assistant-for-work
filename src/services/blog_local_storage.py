"""Lưu media blog trên đĩa local khi MinIO chưa sẵn sàng."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from uuid import uuid4

from src.config import get_settings

_ALLOWED_PREFIX = "blog/local/"


def blog_assets_root() -> Path:
    """Thư mục gốc cho asset blog local (nằm trong data/, đã gitignore)."""
    root = Path(get_settings().chroma_persist_dir).resolve().parent / "blog-assets"
    root.mkdir(parents=True, exist_ok=True)
    return root


def create_local_object_key(filename: str) -> str:
    """Tạo object key an toàn trong namespace blog/local/."""
    clean = PurePosixPath(filename.replace("\\", "/")).name.strip() or "upload"
    return f"{_ALLOWED_PREFIX}{uuid4()}-{clean[:180]}"


def is_local_blog_key(object_key: str) -> bool:
    """Chỉ cho phép key thuộc blog/local/ và không thoát path."""
    if not object_key.startswith(_ALLOWED_PREFIX):
        return False
    if ".." in object_key or object_key.startswith("/") or "\\" in object_key:
        return False
    return True


def resolve_local_path(object_key: str) -> Path:
    """Map object key → đường dẫn file trên đĩa."""
    if not is_local_blog_key(object_key):
        raise ValueError("Object key local không hợp lệ.")
    relative = object_key.removeprefix("blog/")
    path = (blog_assets_root() / relative).resolve()
    root = blog_assets_root().resolve()
    if not str(path).startswith(str(root)):
        raise ValueError("Object key thoát khỏi thư mục blog-assets.")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save_local_bytes(object_key: str, data: bytes) -> Path:
    """Ghi bytes upload vào đĩa local."""
    path = resolve_local_path(object_key)
    path.write_bytes(data)
    return path


def read_local_bytes(object_key: str) -> bytes:
    """Đọc file local; FileNotFoundError nếu chưa có."""
    path = resolve_local_path(object_key)
    return path.read_bytes()
