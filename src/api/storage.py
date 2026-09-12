"""API presigned URL cho object storage."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.deps import get_current_user
from src.models.user import User
from src.services.object_storage import ObjectStorage, get_object_storage

router = APIRouter(prefix="/storage", tags=["storage"])


class PresignUploadRequest(BaseModel):
    """Thông tin tối thiểu để chuẩn bị một lần upload."""

    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream", max_length=120)


class PresignResponse(BaseModel):
    """Thông tin client cần để upload/download object."""

    object_key: str
    url: str
    expires_in: int


def _check_owner(object_key: str, user: User, storage: ObjectStorage) -> None:
    if not storage.belongs_to_user(object_key, user.id):
        raise HTTPException(status_code=404, detail="Object không tồn tại.")


@router.post("/presign-upload", response_model=PresignResponse)
def presign_upload(
    payload: PresignUploadRequest,
    user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> PresignResponse:
    """Chuẩn bị URL PUT để client upload trực tiếp lên MinIO."""
    try:
        storage.ensure_bucket()
        object_key = storage.create_object_key(user.id, payload.filename)
        url = storage.upload_url(object_key)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Object storage chưa sẵn sàng.") from exc
    return PresignResponse(
        object_key=object_key,
        url=url,
        expires_in=storage.settings.minio_presign_expiry_seconds,
    )


@router.get("/download/{object_key:path}", response_model=PresignResponse)
def presign_download(
    object_key: str,
    user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> PresignResponse:
    """Chuẩn bị URL GET có thời hạn cho object của user hiện tại."""
    _check_owner(object_key, user, storage)
    try:
        url = storage.download_url(object_key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Object không tồn tại.") from exc
    return PresignResponse(
        object_key=object_key,
        url=url,
        expires_in=storage.settings.minio_presign_expiry_seconds,
    )


@router.delete("/{object_key:path}", status_code=204)
def delete_object(
    object_key: str,
    user: User = Depends(get_current_user),
    storage: ObjectStorage = Depends(get_object_storage),
) -> None:
    """Xoá object của user hiện tại."""
    _check_owner(object_key, user, storage)
    try:
        storage.delete(object_key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Object không tồn tại.") from exc
