import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import get_current_user
from src.api.rate_limit import limiter
from src.config import allowed_web_origins, get_settings
from src.db import get_db
from src.models.schemas import (
    AppleSessionRequest,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    GoogleSessionRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
    UserResponse,
)
from src.models.user import User
from src.services import account_deletion, apple_auth, oauth_state
from src.services import auth as auth_service
from src.services import email as email_service
from src.services.connections import google
from src.services.crypto import decrypt_token, encrypt_token
from src.services.program_access import reconcile_program_access

logger = logging.getLogger(__name__)

# Thông điệp cố định bất kể email có tồn tại hay không — tránh lộ danh sách
# email đã đăng ký qua chênh lệch nội dung phản hồi (user enumeration).
_FORGOT_PASSWORD_GENERIC_MESSAGE = (
    "Nếu tài khoản tồn tại cho email này, hướng dẫn đặt lại mật khẩu đã được gửi."
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Hash giả dùng khi email không tồn tại, để verify_password luôn tốn thời
# gian bcrypt như trường hợp email có thật — tránh lộ email nào đã đăng ký
# qua chênh lệch thời gian phản hồi (response time vẫn generic 401 nhưng
# timing side-channel thì không, nếu thiếu bước này).
_DUMMY_PASSWORD_HASH = auth_service.hash_password("no-such-account-timing-guard")


def _issue_tokens(user: User) -> TokenResponse:
    access_token, expires_in = auth_service.create_access_token(user.id)
    refresh_token = auth_service.create_refresh_token(user.id)
    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        refresh_token=refresh_token,
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        avatar_url=user.avatar_url,
        program_access_level=user.program_access_level,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("5/minute")
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = payload.email.strip().lower()
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email đã được đăng ký.")

    # Không nhận role từ payload đăng ký: cho client tự khai role là ai cũng
    # đăng ký được tài khoản admin. Nâng quyền chỉ qua /admin/users/{id}/role.
    user = User(
        email=email,
        password_hash=auth_service.hash_password(payload.password),
        display_name=(payload.display_name or "").strip()[:120],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_tokens(user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = payload.email.strip().lower()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    # Account Google-only (NULL hoặc sentinel) dùng dummy hash y hệt email
    # không tồn tại, để
    # không lộ qua timing hay message rằng email này chỉ đăng nhập được bằng Google.
    password_hash = (
        user.password_hash
        if user and auth_service.has_usable_password(user.password_hash)
        else _DUMMY_PASSWORD_HASH
    )
    password_ok = auth_service.verify_password(payload.password, password_hash)
    if not user or not password_ok:
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng.")
    reconcile_program_access(db, str(user.id))
    db.refresh(user)
    return _issue_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
def refresh(request: Request, payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user_id = auth_service.decode_token(payload.refresh_token, "refresh")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User không tồn tại.")
    reconcile_program_access(db, str(user.id))
    db.refresh(user)
    return _issue_tokens(user)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
@limiter.limit("5/minute")
def forgot_password(
    request: Request, payload: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> ForgotPasswordResponse:
    email = payload.email.strip().lower()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    # Luôn trả cùng message + 200 dù email có tồn tại hay không (chặn user
    # enumeration) — chỉ khác nhau ở việc có thật sự tạo token/gửi mail phía sau.
    if user is not None and user.is_active:
        settings = get_settings()
        now = datetime.now(UTC)

        # Khoá per-user (không phải theo IP) khi spam quá ngưỡng — limiter ở
        # rate_limit.py chỉ chặn theo IP nên đổi IP là bypass được, không bảo
        # vệ nạn nhân bị nhắm tới bằng email cụ thể.
        if user.reset_locked_until is not None and user.reset_locked_until > now:
            logger.warning("Bỏ qua yêu cầu quên mật khẩu — user_id=%s đang bị khoá tạm.", user.id)
            return ForgotPasswordResponse(message=_FORGOT_PASSWORD_GENERIC_MESSAGE)

        window_expired = (
            user.reset_request_window_started_at is None
            or now
            - (
                user.reset_request_window_started_at
                if user.reset_request_window_started_at.tzinfo is not None
                else user.reset_request_window_started_at.replace(tzinfo=UTC)
            )
            > timedelta(minutes=settings.forgot_password_window_minutes)
        )
        if window_expired:
            user.reset_request_window_started_at = now
            user.reset_request_count = 0
        user.reset_request_count += 1

        if user.reset_request_count > settings.forgot_password_max_attempts:
            user.reset_locked_until = now + timedelta(minutes=settings.forgot_password_lockout_minutes)
            db.commit()
            logger.warning(
                "Khoá tạm quên-mật-khẩu cho user_id=%s — vượt %d lần trong %d phút.",
                user.id,
                settings.forgot_password_max_attempts,
                settings.forgot_password_window_minutes,
            )
            return ForgotPasswordResponse(message=_FORGOT_PASSWORD_GENERIC_MESSAGE)

        token = auth_service.generate_reset_token()
        user.reset_token_hash = auth_service.hash_reset_token(token)
        user.reset_token_expires_at = now + timedelta(minutes=settings.password_reset_token_expire_minutes)
        db.commit()

        base_url = (settings.web_app_public_url or settings.app_public_url).rstrip("/")
        reset_link = f"{base_url}/reset-password?token={token}"
        try:
            email_service.send_password_reset_email(user.email, reset_link)
        except Exception:
            # Lỗi gửi mail (SMTP sập, sai config...) không được lộ ra response —
            # log để vận hành biết, còn client vẫn thấy message chung như trên.
            logger.exception("Gửi email đặt lại mật khẩu thất bại cho user_id=%s", user.id)

    return ForgotPasswordResponse(message=_FORGOT_PASSWORD_GENERIC_MESSAGE)


@router.post("/reset-password", response_model=ResetPasswordResponse)
@limiter.limit("10/minute")
def reset_password(
    request: Request, payload: ResetPasswordRequest, db: Session = Depends(get_db)
) -> ResetPasswordResponse:
    token_hash = auth_service.hash_reset_token(payload.token)
    user = db.execute(select(User).where(User.reset_token_hash == token_hash)).scalar_one_or_none()

    expires_at = user.reset_token_expires_at if user is not None else None
    # SQLite trả DateTime(timezone=True) dạng naive — phải gán lại UTC trước
    # khi so sánh, không thì lệch giờ hệ thống ném TypeError offset-naive vs
    # offset-aware (xem pattern y hệt ở src/services/reminders.py).
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    is_expired = user is None or expires_at is None or expires_at < datetime.now(UTC)
    if is_expired:
        raise HTTPException(status_code=400, detail="Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.")

    user.password_hash = auth_service.hash_password(payload.new_password)
    # Token chỉ dùng được một lần — xoá ngay sau khi đổi mật khẩu thành công.
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    db.commit()
    return ResetPasswordResponse(message="Cập nhật mật khẩu thành công.")


def _is_allowed_redirect_target(ext_redirect_uri: str) -> bool:
    """Chặn open-redirect: login code chỉ được redirect về đúng origin frontend
    của chính mình. Không có bước này, ai cũng truyền `ext_redirect_uri` trỏ
    sang domain riêng của họ, hứng login code của nạn nhân rồi tự đổi lấy
    token — vì endpoint này KHÔNG yêu cầu Bearer token (chưa ai đăng nhập).
    So khớp (scheme, netloc) chính xác, không dùng str.startswith — chuỗi
    "https://mondaiy.com.evil.com" cũng "bắt đầu bằng" "https://mondaiy.com"."""
    settings = get_settings()
    mobile_redirects = {settings.mobile_app_redirect_uri.strip(), "mondaiy://auth/callback"}
    if ext_redirect_uri in mobile_redirects:
        return True
    target = urlsplit(ext_redirect_uri)
    if target.scheme not in ("http", "https"):
        return False
    origin = f"{target.scheme}://{target.netloc}".rstrip("/")
    return origin in allowed_web_origins()


@router.get("/google/login")
@limiter.limit("20/minute")
def google_login(
    request: Request, ext_redirect_uri: str = Query(..., alias="extRedirectUri")
) -> RedirectResponse:
    """Bắt đầu "Đăng nhập với Google" — chưa có ai đăng nhập nên không cần
    Authorization header, khác /connections/{provider}/intent (yêu cầu user
    đã login). Redirect thẳng sang Google, không qua bước /start trung gian
    vì không có gì cần bảo vệ bằng Bearer token ở bước này."""
    if not _is_allowed_redirect_target(ext_redirect_uri):
        raise HTTPException(status_code=400, detail="ext_redirect_uri không hợp lệ.")
    state = oauth_state.sign_intent(None, "google", ext_redirect_uri, flow="login")
    try:
        target = google.build_login_authorize_url(state)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RedirectResponse(target)


@router.post("/google/session", response_model=TokenResponse)
@limiter.limit("20/minute")
def google_session(request: Request, payload: GoogleSessionRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Đổi login code ngắn hạn (từ src.api.connections.google_callback sau khi
    OAuth thành công) lấy access/refresh token thật."""
    try:
        user_id = oauth_state.verify_login_code(payload.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User không tồn tại.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khoá.")
    reconcile_program_access(db, str(user.id))
    db.refresh(user)
    return _issue_tokens(user)


@router.post("/apple/session", response_model=TokenResponse)
@limiter.limit("20/minute")
async def apple_session(request: Request, payload: AppleSessionRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Đổi credential native Apple lấy JWT của P-004, không gửi token Apple về app."""
    try:
        claims = apple_auth.verify_identity_token(payload.identity_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    subject = claims["sub"]
    user = db.execute(select(User).where(User.apple_subject == subject)).scalar_one_or_none()
    if user is None:
        email_claim = claims.get("email")
        email = email_claim.strip().lower() if isinstance(email_claim, str) else ""
        if not email:
            raise HTTPException(status_code=400, detail="Apple không trả về email để tạo tài khoản mới.")
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                apple_subject=subject,
                password_hash=auth_service.GOOGLE_ONLY_PASSWORD_SENTINEL,
                display_name=payload.display_name.strip(),
            )
            db.add(user)
        else:
            user.apple_subject = subject
            if payload.display_name.strip() and not user.display_name:
                user.display_name = payload.display_name.strip()
        db.commit()
        db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khoá.")
    if payload.authorization_code:
        try:
            user.apple_refresh_token_encrypted = encrypt_token(await apple_auth.exchange_authorization_code(payload.authorization_code))
            db.commit()
        except Exception:
            logger.exception("Không lưu được Apple refresh token user_id=%s", user.id)
            raise HTTPException(status_code=502, detail="Không thể hoàn tất xác thực Apple.") from None
    reconcile_program_access(db, str(user.id))
    db.refresh(user)
    return _issue_tokens(user)


@router.get("/me", response_model=UserResponse)
def me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    reconcile_program_access(db, str(user.id))
    db.refresh(user)
    return UserResponse(
        id=str(user.id),
        email=user.email,
        role=user.role,
        display_name=user.display_name or "",
        avatar_url=user.avatar_url,
        program_access_level=user.program_access_level,
    )


@router.delete("/me", status_code=204)
@limiter.limit("3/minute")
async def delete_me(
    request: Request,
    payload: DeleteAccountRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Tự phục vụ xoá vĩnh viễn tài khoản — không hoàn tác được.

    Yêu cầu đúng password hiện tại nếu tài khoản có đặt password (chặn kẻ
    chiếm được access token ngắn hạn xoá sạch tài khoản người khác). Tài
    khoản chỉ đăng nhập Google không có gì để xác nhận
    thêm ngoài JWT đã hợp lệ — cùng ranh giới đã chấp nhận cho luồng login
    hiện có (xem _DUMMY_PASSWORD_HASH ở login()).
    """
    if auth_service.has_usable_password(user.password_hash):
        if not payload.password or not auth_service.verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=403, detail="Mật khẩu không đúng.")

    if user.apple_refresh_token_encrypted:
        try:
            await apple_auth.revoke_refresh_token(decrypt_token(user.apple_refresh_token_encrypted))
        except Exception:
            logger.exception("Không thu hồi được Apple token user_id=%s", user.id)
            raise HTTPException(status_code=502, detail="Apple chưa xác nhận thu hồi quyền. Vui lòng thử lại.") from None

    await account_deletion.delete_user_account(db, str(user.id))
