"""API admin cho soạn/đăng blog — MinIO khi có, local disk khi chưa."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from src.api.deps import require_admin
from src.config import get_settings
from src.models.blog_schemas import (
    BlogParseMarkdownRequest,
    BlogParseMarkdownResponse,
    BlogPostListResponse,
    BlogPostPayload,
    BlogPostResponse,
    BlogPresignAssetRequest,
    BlogPresignAssetResponse,
    BlogStorageStatusResponse,
)
from src.services.blog_local_storage import (
    create_local_object_key,
    is_local_blog_key,
    save_local_bytes,
)
from src.services.blog_markdown import parse_markdown_draft
from src.services.blog_store import list_posts, publish_post
from src.services.object_storage import ObjectStorage, get_object_storage

router = APIRouter(
    prefix="/admin/blog",
    tags=["admin-blog"],
    dependencies=[Depends(require_admin)],
)

_MAX_LOCAL_UPLOAD_BYTES = 8 * 1024 * 1024


def _to_response(post: dict, storage_mode: str = "mock") -> BlogPostResponse:
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
        storage_mode=storage_mode,
        public_path=f"/blog/{post['slug']}",
    )


def _safe_storage() -> ObjectStorage | None:
    """Lấy MinIO client; trả None nếu package/config chưa dùng được."""
    try:
        return get_object_storage()
    except Exception:
        return None


def _probe_storage(storage: ObjectStorage | None) -> BlogStorageStatusResponse:
    settings = get_settings()
    if storage is None:
        return BlogStorageStatusResponse(
            available=False,
            mode="local",
            endpoint=settings.minio_endpoint,
            bucket="data/blog-assets",
            detail="MinIO client unavailable; using local disk.",
        )

    # TCP check nhanh để khỏi chờ urllib3 retry dài khi MinIO chưa chạy.
    host, _, port_raw = settings.minio_endpoint.partition(":")
    port = int(port_raw or "9000")
    try:
        import socket

        with socket.create_connection((host, port), timeout=0.4):
            pass
    except OSError:
        return BlogStorageStatusResponse(
            available=False,
            mode="local",
            endpoint=settings.minio_endpoint,
            bucket="data/blog-assets",
            detail="MinIO port closed; using local disk.",
        )

    try:
        storage.ensure_bucket()
        return BlogStorageStatusResponse(
            available=True,
            mode="live",
            endpoint=settings.minio_endpoint,
            bucket=settings.minio_bucket,
            detail=None,
        )
    except Exception as exc:
        return BlogStorageStatusResponse(
            available=False,
            mode="local",
            endpoint=settings.minio_endpoint,
            bucket="data/blog-assets",
            detail=f"MinIO unavailable ({exc.__class__.__name__}); using local disk.",
        )


@router.get("/storage-status", response_model=BlogStorageStatusResponse)
def blog_storage_status() -> BlogStorageStatusResponse:
    """Cho UI biết đang dùng MinIO hay local disk."""
    return _probe_storage(_safe_storage())


@router.post("/presign-asset", response_model=BlogPresignAssetResponse)
def blog_presign_asset(payload: BlogPresignAssetRequest) -> BlogPresignAssetResponse:
    """Cấp URL PUT: MinIO live hoặc backend local-upload."""
    storage = _safe_storage()
    status = _probe_storage(storage)
    if status.available and storage is not None:
        try:
            object_key = storage.create_blog_object_key(payload.filename)
            url = storage.upload_url(object_key)
            return BlogPresignAssetResponse(
                object_key=object_key,
                url=url,
                expires_in=storage.settings.minio_presign_expiry_seconds,
                storage_mode="live",
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Object storage chưa sẵn sàng.") from exc

    settings = get_settings()
    object_key = create_local_object_key(payload.filename)
    url = f"{settings.app_public_url.rstrip('/')}/api/v1/admin/blog/local-upload/{object_key}"
    return BlogPresignAssetResponse(
        object_key=object_key,
        url=url,
        expires_in=settings.minio_presign_expiry_seconds,
        storage_mode="local",
    )


@router.put("/local-upload/{object_key:path}", status_code=204)
async def blog_local_upload(object_key: str, request: Request) -> Response:
    """Nhận PUT body và ghi vào data/blog-assets (fallback khi chưa có MinIO)."""
    if not is_local_blog_key(object_key):
        raise HTTPException(status_code=400, detail="Object key local không hợp lệ.")
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="File rỗng.")
    if len(data) > _MAX_LOCAL_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File quá lớn (tối đa 8MB).")
    try:
        save_local_bytes(object_key, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)


@router.post("/parse-markdown", response_model=BlogParseMarkdownResponse)
def blog_parse_markdown(payload: BlogParseMarkdownRequest) -> BlogParseMarkdownResponse:
    """Parse file markdown (frontmatter + body) thành draft form."""
    draft = parse_markdown_draft(payload.markdown)
    return BlogParseMarkdownResponse(
        title=draft.title,
        title_vi=draft.title_vi,
        slug=draft.slug,
        author=draft.author,
        excerpt=draft.excerpt,
        excerpt_vi=draft.excerpt_vi,
        tags=draft.tags,
        body=draft.body,
        body_vi=draft.body_vi,
    )


@router.get("/posts", response_model=BlogPostListResponse)
def admin_list_blog_posts() -> BlogPostListResponse:
    """Liệt kê bài đã đăng mock trong process hiện tại."""
    items = [_to_response(p) for p in list_posts()]
    return BlogPostListResponse(items=items, total=len(items), storage_mode="mock")


@router.post("/posts", response_model=BlogPostResponse)
def admin_publish_blog_post(payload: BlogPostPayload) -> BlogPostResponse:
    """Đăng bài mock — chưa ghi DB/static; dùng để xem luồng publish."""
    for key in payload.asset_object_keys:
        if not ObjectStorage.belongs_to_blog(key):
            raise HTTPException(status_code=400, detail=f"Object key không thuộc blog: {key}")
    if payload.cover_object_key and not ObjectStorage.belongs_to_blog(payload.cover_object_key):
        raise HTTPException(status_code=400, detail="Cover object key không thuộc blog.")

    post = publish_post(
        {
            "slug": payload.slug.strip(),
            "title": payload.title.strip(),
            "title_vi": payload.title_vi.strip(),
            "excerpt": payload.excerpt.strip(),
            "excerpt_vi": payload.excerpt_vi.strip(),
            "body": payload.body,
            "body_vi": payload.body_vi,
            "author": payload.author.strip(),
            "tags": [t.strip() for t in payload.tags if t.strip()][:12],
            "cover_object_key": payload.cover_object_key,
            "asset_object_keys": payload.asset_object_keys,
            "markdown_source_name": payload.markdown_source_name,
        }
    )
    return _to_response(post, storage_mode="mock")
