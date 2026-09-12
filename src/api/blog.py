"""API public đọc bài blog đã đăng mock (chưa thay static FE)."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.models.blog_schemas import BlogPostListResponse, BlogPostResponse
from src.services.blog_local_storage import is_local_blog_key, resolve_local_path
from src.services.blog_store import get_post_by_slug, list_posts

router = APIRouter(prefix="/blog", tags=["blog"])

_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".md": "text/markdown; charset=utf-8",
}


def _to_response(post: dict) -> BlogPostResponse:
    return BlogPostResponse(
        id=post["id"],
        slug=post["slug"],
        title=post["title"],
        title_vi=post.get("title_vi", ""),
        excerpt=post.get("excerpt", ""),
        excerpt_vi=post.get("excerpt_vi", ""),
        body=post["body"],
        body_vi=post.get("body_vi", ""),
        author=post["author"],
        tags=post.get("tags", []),
        published_at=post["publishedAt"],
        status=post.get("status", "published_mock"),
        cover_object_key=post.get("cover_object_key"),
        asset_object_keys=post.get("asset_object_keys", []),
        storage_mode="mock",
        public_path=f"/blog/{post['slug']}",
    )


@router.get("/posts", response_model=BlogPostListResponse)
def list_public_blog_posts() -> BlogPostListResponse:
    """Danh sách bài mock đã publish trong process backend."""
    items = [_to_response(p) for p in list_posts()]
    return BlogPostListResponse(items=items, total=len(items), storage_mode="mock")


@router.get("/posts/{slug}", response_model=BlogPostResponse)
def get_public_blog_post(slug: str) -> BlogPostResponse:
    """Chi tiết một bài mock theo slug."""
    post = get_post_by_slug(slug)
    if not post:
        raise HTTPException(status_code=404, detail="Bài blog không tồn tại.")
    return _to_response(post)


@router.get("/assets/{object_key:path}")
def get_blog_local_asset(object_key: str) -> FileResponse:
    """Phục vụ file đã upload local (fallback MinIO)."""
    if not is_local_blog_key(object_key):
        raise HTTPException(status_code=404, detail="Asset không tồn tại.")
    try:
        path = resolve_local_path(object_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Asset không tồn tại.")
    media_type = _CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=Path(path.name).name)
