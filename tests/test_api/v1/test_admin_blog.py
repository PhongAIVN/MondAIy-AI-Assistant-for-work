"""Kiểm tra parse markdown blog và đăng bài mock (admin + public)."""

import uuid

import pytest

from src.db import SessionLocal
from src.models.user import User
from src.services.blog_markdown import parse_markdown_draft, slugify
from src.services.object_storage import ObjectStorage

ADMIN_BLOG = "/api/v1/admin/blog"
PUBLIC_BLOG = "/api/v1/blog"


def _unique_email() -> str:
    return f"blog-admin-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client, email: str | None = None) -> tuple[str, str]:
    email = email or _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201, response.text
    data = response.json()
    return data["userId"], data["accessToken"]


def _promote(user_id: str) -> None:
    db = SessionLocal()
    try:
        user = db.get(User, int(user_id))
        user.role = "admin"
        db.commit()
    finally:
        db.close()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _reset_blog_store(tmp_path, monkeypatch):
    from src.services import blog_store as store

    monkeypatch.setattr(store, "_store_path", lambda: tmp_path / "blog-posts.json")
    store.clear_posts()
    yield
    store.clear_posts()


def test_slugify_va_parse_frontmatter():
    raw = """---
title: Hello Mondaiy
title_vi: Xin chào Mondaiy
slug: hello-mondaiy
author: Admin
tags: product, design
excerpt: Short note
---

# Ignored heading

Body paragraph one.

Body paragraph two.
"""
    draft = parse_markdown_draft(raw)
    assert draft.slug == "hello-mondaiy"
    assert draft.title == "Hello Mondaiy"
    assert draft.title_vi == "Xin chào Mondaiy"
    assert draft.tags == ["product", "design"]
    assert "Body paragraph one." in draft.body
    assert slugify("Hello Mondaiy!") == "hello-mondaiy"


def test_blog_object_key_namespace():
    storage = ObjectStorage.__new__(ObjectStorage)
    key = ObjectStorage.create_blog_object_key(storage, "../evil/cover.png")
    assert key.startswith("blog/")
    assert ".." not in key
    assert key.endswith("cover.png")
    assert ObjectStorage.belongs_to_blog(key)
    assert not ObjectStorage.belongs_to_blog("users/1/x.png")


@pytest.mark.asyncio
async def test_participant_khong_presign_blog(client):
    _, token = await _register(client)
    response = await client.post(
        f"{ADMIN_BLOG}/presign-asset",
        headers=_auth(token),
        json={"filename": "a.png", "content_type": "image/png"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_parse_markdown(client):
    user_id, token = await _register(client)
    _promote(user_id)
    response = await client.post(
        f"{ADMIN_BLOG}/parse-markdown",
        headers=_auth(token),
        json={
            "markdown": "---\ntitle: From API\n---\n\nHello body.\n",
            "filename": "post.md",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["title"] == "From API"
    assert data["slug"] == "from-api"
    assert "Hello body." in data["body"]


@pytest.mark.asyncio
async def test_admin_publish_mock_va_public_doc_duoc(client):
    user_id, token = await _register(client)
    _promote(user_id)

    publish = await client.post(
        f"{ADMIN_BLOG}/posts",
        headers=_auth(token),
        json={
            "slug": "mock-flow-post",
            "title": "Mock flow post",
            "title_vi": "Bài mock",
            "excerpt": "Excerpt EN",
            "excerpt_vi": "Tóm tắt VI",
            "body": "Paragraph one.\n\nParagraph two.",
            "body_vi": "Đoạn một.",
            "author": "Admin Tester",
            "tags": ["product"],
            "asset_object_keys": ["blog/mock/file.png"],
            "cover_object_key": "blog/mock/cover.png",
        },
    )
    assert publish.status_code == 200, publish.text
    published = publish.json()
    assert published["slug"] == "mock-flow-post"
    assert published["status"] == "published_mock"
    assert published["publicPath"] == "/blog/mock-flow-post"
    assert published["storageMode"] == "mock"

    listed = await client.get(f"{PUBLIC_BLOG}/posts")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    assert any(item["slug"] == "mock-flow-post" for item in listed.json()["items"])

    detail = await client.get(f"{PUBLIC_BLOG}/posts/mock-flow-post")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Mock flow post"


@pytest.mark.asyncio
async def test_publish_tu_choi_object_key_ngoai_blog(client):
    user_id, token = await _register(client)
    _promote(user_id)
    response = await client.post(
        f"{ADMIN_BLOG}/posts",
        headers=_auth(token),
        json={
            "slug": "bad-asset",
            "title": "Bad",
            "body": "x",
            "author": "Admin",
            "asset_object_keys": ["users/1/secret.png"],
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_presign_va_upload_local_khi_minio_loi(client, tmp_path, monkeypatch):
    user_id, token = await _register(client)
    _promote(user_id)

    from src.api import admin_blog as admin_blog_mod
    from src.services import blog_local_storage as local_mod

    monkeypatch.setattr(local_mod, "blog_assets_root", lambda: tmp_path)
    monkeypatch.setattr(admin_blog_mod, "_safe_storage", lambda: None)

    response = await client.post(
        f"{ADMIN_BLOG}/presign-asset",
        headers=_auth(token),
        json={"filename": "hero.png", "content_type": "image/png"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["storageMode"] == "local"
    assert data["objectKey"].startswith("blog/local/")
    assert "/api/v1/admin/blog/local-upload/" in data["url"]

    put = await client.put(
        f"{ADMIN_BLOG}/local-upload/{data['objectKey']}",
        headers={**_auth(token), "Content-Type": "image/png"},
        content=b"\x89PNG\r\n\x1a\nfake-png-bytes",
    )
    assert put.status_code == 204, put.text

    public = await client.get(f"{PUBLIC_BLOG}/assets/{data['objectKey']}")
    assert public.status_code == 200
    assert public.content.startswith(b"\x89PNG")


def test_publish_persist_qua_file(tmp_path, monkeypatch):
    from src.services import blog_store as store

    monkeypatch.setattr(store, "_store_path", lambda: tmp_path / "blog-posts.json")
    store.clear_posts()
    published = store.publish_post(
        {
            "slug": "persist-me",
            "title": "Persist",
            "title_vi": "",
            "excerpt": "",
            "excerpt_vi": "",
            "body": "hi",
            "body_vi": "",
            "author": "Admin",
            "tags": [],
        }
    )
    assert published["slug"] == "persist-me"
    assert (tmp_path / "blog-posts.json").is_file()
    with store._LOCK:
        store._POSTS = None
    listed = store.list_posts()
    assert any(p["slug"] == "persist-me" for p in listed)
