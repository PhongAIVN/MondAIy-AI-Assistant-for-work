"""Parse markdown blog draft — frontmatter YAML tối giản + slug."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)


@dataclass
class ParsedMarkdownDraft:
    """Kết quả parse một file markdown blog."""

    title: str = ""
    title_vi: str = ""
    slug: str = ""
    author: str = ""
    excerpt: str = ""
    excerpt_vi: str = ""
    tags: list[str] = field(default_factory=list)
    body: str = ""
    body_vi: str = ""
    raw_frontmatter: dict[str, str] = field(default_factory=dict)


def slugify(value: str) -> str:
    """Chuẩn hoá chuỗi thành slug URL an toàn."""
    cleaned = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return cleaned[:80] or "untitled"


def _parse_frontmatter_block(block: str) -> dict[str, str]:
    """Đọc key: value đơn giản; tags tách bằng dấu phẩy."""
    result: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        result[key.strip().lower()] = raw.strip().strip("\"'")
    return result


def parse_markdown_draft(raw: str) -> ParsedMarkdownDraft:
    """Tách frontmatter (nếu có) và body markdown thành draft blog."""
    text = raw.replace("\r\n", "\n").strip()
    match = _FRONTMATTER_RE.match(text)
    meta: dict[str, str] = {}
    body = text
    if match:
        meta = _parse_frontmatter_block(match.group(1))
        body = match.group(2).strip()

    title = meta.get("title") or meta.get("title_en") or ""
    if not title:
        for line in body.splitlines():
            heading = line.strip()
            if heading.startswith("# "):
                title = heading[2:].strip()
                break

    tags_raw = meta.get("tags", "")
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    slug = meta.get("slug") or (slugify(title) if title else "untitled")
    return ParsedMarkdownDraft(
        title=title,
        title_vi=meta.get("title_vi", ""),
        slug=slug,
        author=meta.get("author", ""),
        excerpt=meta.get("excerpt") or meta.get("excerpt_en", ""),
        excerpt_vi=meta.get("excerpt_vi", ""),
        tags=tags,
        body=body,
        body_vi=meta.get("body_vi", ""),
        raw_frontmatter=meta,
    )
