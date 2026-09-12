"""Schema cho đăng bài blog (admin + public mock)."""

from pydantic import Field

from src.models.schemas import CamelModel


class BlogStorageStatusResponse(CamelModel):
    """Trạng thái MinIO cho media blog."""

    available: bool
    mode: str = Field(description="live | mock")
    endpoint: str
    bucket: str
    detail: str | None = None


class BlogPresignAssetRequest(CamelModel):
    """Chuẩn bị upload ảnh/file đính kèm bài blog."""

    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream", max_length=120)


class BlogPresignAssetResponse(CamelModel):
    """URL PUT (thật hoặc mock) để client upload asset."""

    object_key: str
    url: str
    expires_in: int
    storage_mode: str


class BlogPostPayload(CamelModel):
    """Nội dung bài blog admin chuẩn bị đăng."""

    slug: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    title_vi: str = Field(default="", max_length=240)
    excerpt: str = Field(default="", max_length=600)
    excerpt_vi: str = Field(default="", max_length=600)
    body: str = Field(min_length=1)
    body_vi: str = Field(default="")
    author: str = Field(min_length=1, max_length=120)
    tags: list[str] = Field(default_factory=list, max_length=12)
    cover_object_key: str | None = None
    asset_object_keys: list[str] = Field(default_factory=list, max_length=40)
    markdown_source_name: str | None = Field(default=None, max_length=255)


class BlogPostResponse(CamelModel):
    """Bài đã đăng (mock hoặc sau này live)."""

    id: str
    slug: str
    title: str
    title_vi: str
    excerpt: str
    excerpt_vi: str
    body: str
    body_vi: str
    author: str
    tags: list[str]
    published_at: str
    status: str
    cover_object_key: str | None = None
    asset_object_keys: list[str] = Field(default_factory=list)
    storage_mode: str = "mock"
    public_path: str


class BlogPostListResponse(CamelModel):
    """Danh sách bài blog mock đã đăng."""

    items: list[BlogPostResponse]
    total: int
    storage_mode: str = "mock"


class BlogParseMarkdownRequest(CamelModel):
    """Nội dung file markdown thô để parse thử ở server."""

    markdown: str = Field(min_length=1, max_length=200_000)
    filename: str | None = Field(default=None, max_length=255)


class BlogParseMarkdownResponse(CamelModel):
    """Draft sau khi parse markdown."""

    title: str
    title_vi: str
    slug: str
    author: str
    excerpt: str
    excerpt_vi: str
    tags: list[str]
    body: str
    body_vi: str
