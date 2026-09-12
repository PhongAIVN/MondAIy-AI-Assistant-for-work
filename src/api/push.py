"""Đăng ký/huỷ đăng ký thiết bị nhận Web Push.

Endpoint của trình duyệt là bí mật giao vận, nên mọi thao tác ở đây đều gắn với
người dùng đang đăng nhập: không có đường nào đọc hay xoá được subscription của
người khác dù biết chuỗi endpoint.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import get_current_user_id
from src.config import get_settings
from src.db import get_db
from src.models.push_subscription import PushSubscription
from src.models.schemas import (
    PushPublicKeyResponse,
    PushSubscribeRequest,
    PushSubscriptionResponse,
    PushUnsubscribeRequest,
)

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/public-key", response_model=PushPublicKeyResponse)
def get_public_key() -> PushPublicKeyResponse:
    """Trả khoá công khai VAPID để trình duyệt đăng ký nhận thông báo.

    Không yêu cầu đăng nhập vì khoá này vốn công khai và client cần nó trước cả
    khi hỏi người dùng có muốn bật thông báo hay không. Chưa cấu hình thì trả
    chuỗi rỗng kèm ``enabled=false`` — nói thật trạng thái còn hơn để client
    đăng ký rồi hỏng ở tầng trình duyệt.
    """
    settings = get_settings()
    public_key = settings.vapid_public_key.strip()
    return PushPublicKeyResponse(
        public_key=public_key,
        enabled=bool(public_key) and settings.web_push_enabled,
    )


@router.post("/subscribe", response_model=PushSubscriptionResponse, status_code=201)
def subscribe(
    payload: PushSubscribeRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> PushSubscriptionResponse:
    """Lưu hoặc cập nhật subscription của thiết bị đang gọi.

    Tra theo ``endpoint`` chứ không theo user: trình duyệt cấp lại đúng endpoint
    cũ sau mỗi lần tải trang, nên chèn mù sẽ sinh trùng và người dùng nhận thông
    báo nhân đôi. Nếu endpoint đang thuộc tài khoản khác thì chuyển quyền sở hữu
    sang tài khoản vừa đăng nhập — cùng một máy đổi người dùng mà giữ chủ cũ là
    đẩy thông báo của người này sang màn hình người kia.

    Khoá mã hoá cũng được ghi đè mỗi lần: trình duyệt xoay khoá khi service
    worker đăng ký lại, giữ khoá cũ là gửi ra payload mà máy không giải nổi.
    """
    row = db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    ).scalar_one_or_none()
    if row is None:
        row = PushSubscription(endpoint=payload.endpoint, user_id=user_id)
        db.add(row)
    row.user_id = user_id
    row.p256dh = payload.keys.p256dh
    row.auth = payload.keys.auth
    row.user_agent = payload.user_agent
    row.last_error_class = None
    row.last_used_at = datetime.now(UTC)
    db.commit()
    return PushSubscriptionResponse(subscribed=True)


@router.delete("/subscribe", response_model=PushSubscriptionResponse)
def unsubscribe(
    payload: PushUnsubscribeRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> PushSubscriptionResponse:
    """Huỷ đăng ký một endpoint của chính người dùng đang đăng nhập.

    Điều kiện lọc gồm cả ``user_id``: biết endpoint của người khác cũng không
    tắt được thông báo của họ. Không tìm thấy thì trả 404 chung, không phân biệt
    "không tồn tại" với "của người khác" để không biến endpoint thành công cụ dò.
    """
    row = db.execute(
        select(PushSubscription).where(
            PushSubscription.endpoint == payload.endpoint,
            PushSubscription.user_id == user_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đăng ký thông báo này.")
    db.delete(row)
    db.commit()
    return PushSubscriptionResponse(subscribed=False)
