"""Smoke test luồng blog local upload (TestClient — không cần server đang chạy đúng code)."""

from pathlib import Path
from urllib.parse import urlparse

from fastapi.testclient import TestClient

from src.db import SessionLocal
from src.main import app
from src.models.user import User
from src.services.blog_store import clear_posts

MD = Path("fixtures/blog/sample-post.md").read_text(encoding="utf-8")
PNG = Path("fixtures/blog/sample-cover.png").read_bytes()


def main() -> None:
    clear_posts()
    client = TestClient(app)
    email = "blog-local-ui@example.com"

    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1"},
    )
    if reg.status_code == 201:
        token = reg.json()["accessToken"]
        uid = reg.json()["userId"]
    else:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "correct-horse-1"},
        )
        login.raise_for_status()
        token = login.json()["accessToken"]
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        me.raise_for_status()
        uid = me.json()["id"]

    db = SessionLocal()
    try:
        user = db.get(User, int(uid))
        assert user is not None
        user.role = "admin"
        db.commit()
        print("promoted", user.email)
    finally:
        db.close()

    headers = {"Authorization": f"Bearer {token}"}
    status = client.get("/api/v1/admin/blog/storage-status", headers=headers)
    print("storage", status.status_code, status.json())
    status.raise_for_status()

    presign = client.post(
        "/api/v1/admin/blog/presign-asset",
        headers=headers,
        json={"filename": "sample-cover.png", "contentType": "image/png"},
    )
    print("presign", presign.status_code, presign.json())
    presign.raise_for_status()
    pdata = presign.json()

    upload_path = urlparse(pdata["url"]).path
    put = client.put(
        upload_path,
        headers={**headers, "Content-Type": "image/png"},
        content=PNG,
    )
    print("put", put.status_code)
    put.raise_for_status()

    asset = client.get(f"/api/v1/blog/assets/{pdata['objectKey']}")
    print("asset", asset.status_code, len(asset.content), asset.headers.get("content-type"))
    asset.raise_for_status()

    body = MD.split("---", 2)[-1].strip() if MD.startswith("---") else MD
    published = client.post(
        "/api/v1/admin/blog/posts",
        headers=headers,
        json={
            "slug": "testing-blog-publish-flow",
            "title": "Testing the Mondaiy blog publish flow",
            "titleVi": "Thử luồng đăng bài blog Mondaiy",
            "excerpt": "sample",
            "excerptVi": "mau",
            "body": body,
            "bodyVi": "Nội dung tiếng Việt mẫu.",
            "author": "Admin Tester",
            "tags": ["product", "ops"],
            "coverObjectKey": pdata["objectKey"],
            "assetObjectKeys": [pdata["objectKey"]],
            "markdownSourceName": "sample-post.md",
        },
    )
    print("publish", published.status_code, published.json().get("publicPath"))
    published.raise_for_status()

    root = Path("data/blog-assets")
    files = list(root.rglob("*")) if root.exists() else []
    print("local files", [str(f) for f in files if f.is_file()])
    print("OK")


if __name__ == "__main__":
    main()
