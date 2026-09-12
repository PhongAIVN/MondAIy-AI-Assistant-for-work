"""Lớp truy cập object storage dùng MinIO."""

from datetime import timedelta
from functools import lru_cache
from pathlib import PurePosixPath
from uuid import uuid4

from src.config import Settings, get_settings


class ObjectStorage:
    """Quản lý object theo namespace của từng user."""

    def __init__(self, settings: Settings) -> None:
        # Import trễ để các command/test không dùng storage vẫn chạy được khi
        # dependency object storage chưa được cài trong môi trường tối giản.
        from minio import Minio

        self.settings = settings
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.presign_client = Minio(
            settings.minio_presign_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def ensure_bucket(self) -> None:
        """Tạo bucket nếu chưa tồn tại."""
        if not self.client.bucket_exists(self.settings.minio_bucket):
            self.client.make_bucket(self.settings.minio_bucket)

    def create_object_key(self, user_id: int, filename: str) -> str:
        """Tạo key an toàn, không cho filename điều khiển đường dẫn object."""
        clean_name = PurePosixPath(filename.replace("\\", "/")).name.strip() or "upload"
        return f"users/{user_id}/{uuid4()}-{clean_name[:180]}"

    def create_blog_object_key(self, filename: str) -> str:
        """Tạo key cho media blog — tách namespace khỏi file cá nhân user."""
        clean_name = PurePosixPath(filename.replace("\\", "/")).name.strip() or "upload"
        return f"blog/{uuid4()}-{clean_name[:180]}"

    @staticmethod
    def belongs_to_blog(object_key: str) -> bool:
        """Kiểm tra object key thuộc namespace blog."""
        return object_key.startswith("blog/")

    def upload_url(self, object_key: str) -> str:
        """Tạo URL PUT có thời hạn cho client upload trực tiếp."""
        return self.presign_client.presigned_put_object(
            self.settings.minio_bucket,
            object_key,
            expires=timedelta(seconds=self.settings.minio_presign_expiry_seconds),
        )

    def download_url(self, object_key: str) -> str:
        """Tạo URL GET có thời hạn cho client tải object."""
        return self.presign_client.presigned_get_object(
            self.settings.minio_bucket,
            object_key,
            expires=timedelta(seconds=self.settings.minio_presign_expiry_seconds),
        )

    def delete(self, object_key: str) -> None:
        """Xoá một object."""
        self.client.remove_object(self.settings.minio_bucket, object_key)

    @staticmethod
    def belongs_to_user(object_key: str, user_id: int) -> bool:
        """Kiểm tra object key có thuộc namespace của user hay không."""
        return object_key.startswith(f"users/{user_id}/")


@lru_cache
def get_object_storage() -> ObjectStorage:
    """Lấy singleton object storage theo cấu hình hiện tại."""
    return ObjectStorage(get_settings())
