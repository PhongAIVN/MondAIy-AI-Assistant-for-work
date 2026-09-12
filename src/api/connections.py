import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.deps import get_current_user_id
from src.api.rate_limit import limiter
from src.config import allowed_web_origins, get_settings
from src.db import get_db
from src.models.connection import Connection
from src.models.evidence import SourceScope
from src.models.message import Message
from src.models.schemas import (
    ConnectionIntentRequest,
    ConnectionIntentResponse,
    ConnectionListResponse,
    ConnectionProvider,
    ConnectionStatus,
    GmailStatusResponse,
    GmailSyncResponse,
    RunCreateRequest,
    SyncSourceRef,
)
from src.models.source_scope_access import SourceScopeAccess
from src.models.user import User
from src.services import auth as auth_service
from src.services import oauth_state
from src.services.connections import (
    discord,
    google,
    jira,
    microsoft,
    preferred_connection,
    revoke_connection_tokens,
    slack,
    telegram,
)
from src.services.crypto import encrypt_token
from src.services.program_access import (
    classify_discord_identity,
    reconcile_program_access,
    set_program_access,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/connections", tags=["connections"])

_PROVIDERS = ("discord", "google", "telegram", "jira", "outlook", "slack")


def _require_known_provider(provider: str) -> None:
    if provider not in _PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Provider không hỗ trợ: {provider}")


def _allowed_redirect_origins() -> set[str]:
    # Nguồn sự thật nằm ở src/config.allowed_web_origins() — giữ đúng một bản.
    return allowed_web_origins()


def _validate_ext_redirect_uri(uri: str) -> None:
    """Chốt danh sách đích redirect để backend không thành bàn đạp open redirect.

    ext_redirect_uri do client gửi rồi được ký lại trong state token, nên nếu
    không chặn ở đầu vào thì sau khi OAuth xong `_finish` sẽ 302 tới URL bất kỳ.
    Chỉ hai nguồn hợp lệ: đích redirect của extension (chrome.identity hoặc
    chrome-extension://) và origin của web-app — vốn phải trùng allowlist CORS.
    """
    parsed = urlparse(uri)
    # Giữ callback native ổn định kể cả production env còn giá trị cũ.
    # Chỉ cho phép đúng URI này, không nhận wildcard theo scheme.
    mobile_redirects = {get_settings().mobile_app_redirect_uri.strip(), "mondaiy://auth/callback"}
    if uri in mobile_redirects:
        return
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()

    if scheme == "chrome-extension":
        return
    if scheme == "https" and (host == "chromiumapp.org" or host.endswith(".chromiumapp.org")):
        return
    if scheme in ("http", "https"):
        origin = f"{scheme}://{parsed.netloc}".rstrip("/")
        if origin in _allowed_redirect_origins():
            return
    raise HTTPException(status_code=400, detail="ext_redirect_uri không nằm trong danh sách cho phép.")


@router.get("", response_model=ConnectionListResponse)
def list_connections(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ConnectionListResponse:
    reconcile_program_access(db, user_id)
    rows = db.execute(
        select(Connection)
        .where(Connection.user_id == user_id)
        .order_by(Connection.provider, Connection.connected_at.desc(), Connection.id.desc())
    ).scalars().all()
    statuses = [
        ConnectionStatus(
            id=row.id,
            provider=row.provider,
            connected=True,
            account_label=row.account_label,
            expires_at=row.expires_at,
            needs_reconnect=row.status == "expired",
            last_error=row.last_error,
        )
        for row in rows
    ]
    connected_providers = {row.provider for row in rows}
    statuses.extend(
        ConnectionStatus(provider=provider, connected=False)
        for provider in _PROVIDERS
        if provider not in connected_providers
    )
    return ConnectionListResponse(connections=statuses)


def _gmail_status(row: Connection | None) -> GmailStatusResponse:
    if row is None:
        return GmailStatusResponse(status="disconnected")
    oauth_valid = bool(row.refresh_token_encrypted or row.access_token_encrypted)
    mailbox_accessible = row.status in {"connected_pending_sync", "syncing", "connected_ready"}
    return GmailStatusResponse(
        status=row.status,
        account_email=row.account_label,
        permission="readonly" if row.scopes and "gmail.readonly" in row.scopes else None,
        email_count=row.email_count or 0,
        last_synced_at=row.last_synced_at,
        oauth_valid=oauth_valid,
        mailbox_accessible=mailbox_accessible,
        initial_sync_completed=bool(row.initial_sync_completed),
        last_error=row.last_error,
    )


@router.get("/gmail/status", response_model=GmailStatusResponse)
def gmail_status(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> GmailStatusResponse:
    row = preferred_connection(db, user_id, "google")
    return _gmail_status(row)


@router.post("/gmail/oauth/start", response_model=ConnectionIntentResponse)
def gmail_oauth_start(
    payload: ConnectionIntentRequest,
    user_id: str = Depends(get_current_user_id),
) -> ConnectionIntentResponse:
    _validate_ext_redirect_uri(payload.ext_redirect_uri)
    state = oauth_state.sign_intent(user_id, "google", payload.ext_redirect_uri)
    api_base = f"{get_settings().app_public_url}/api/v1"
    return ConnectionIntentResponse(authorize_url=f"{api_base}/connections/google/start?intent={state}")


@router.post("/{provider}/intent", response_model=ConnectionIntentResponse)
def create_connect_intent(
    provider: str,
    payload: ConnectionIntentRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ConnectionIntentResponse:
    _require_known_provider(provider)
    if provider == "telegram":
        return ConnectionIntentResponse(authorize_url=telegram.create_bot_link(db, user_id))
    _validate_ext_redirect_uri(payload.ext_redirect_uri)
    state = oauth_state.sign_intent(user_id, provider, payload.ext_redirect_uri)
    api_base = f"{get_settings().app_public_url}/api/v1"
    return ConnectionIntentResponse(authorize_url=f"{api_base}/connections/{provider}/start?intent={state}")


@router.get("/{provider}/start")
@limiter.limit("20/minute")
def start_connect(request: Request, provider: str, intent: str = Query(...)) -> RedirectResponse:
    _require_known_provider(provider)
    try:
        oauth_state.verify_intent(intent, provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        if provider == "discord":
            target = discord.build_authorize_url(intent)
        elif provider == "google":
            target = google.build_authorize_url(intent)
        elif provider == "jira":
            target = jira.build_authorize_url(intent)
        elif provider == "outlook":
            target = microsoft.build_authorize_url(intent)
        elif provider == "slack":
            target = slack.build_authorize_url(intent)
        else:
            target = telegram.build_authorize_url(intent)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return RedirectResponse(target)


def _finish(ext_redirect_uri: str, provider: str, status: str, message: str | None = None) -> RedirectResponse:
    params = urlencode({"status": status, "provider": provider, **({"message": message} if message else {})})
    separator = "&" if "?" in ext_redirect_uri else "?"
    return RedirectResponse(f"{ext_redirect_uri}{separator}{params}")


def _consent_denied_reason(request: Request) -> str:
    """User từ chối/huỷ consent (hoặc tổ chức chặn bằng chính sách admin-approval,
    xem Outlook/Azure AD) — provider redirect về thiếu `code`, gửi `error=` thay
    vào đó. Trước đây `code` là query param bắt buộc nên FastAPI trả 422 JSON
    thô thẳng ra browser TRƯỚC KHI vào được thân hàm xử lý lỗi — người dùng
    thấy JSON lỗi thay vì quay lại app với thông báo dễ hiểu."""
    return request.query_params.get("error") or "missing_code"


def _upsert_connection(
    db: Session,
    *,
    user_id: str,
    provider: ConnectionProvider,
    account_label: str | None,
    token_data: dict | None,
    provider_user_id: str | None = None,
    external_site_id: str | None = None,
) -> Connection:
    if provider == "google" and provider_user_id:
        provider_user_id = provider_user_id.strip().lower()
    for attempt in range(2):
        lookup = select(Connection).where(Connection.user_id == user_id, Connection.provider == provider)
        if provider == "google" and provider_user_id:
            lookup = lookup.where(Connection.provider_user_id == provider_user_id)
        existing = db.execute(
            lookup.order_by(Connection.connected_at.desc(), Connection.id.desc())
        ).scalars().first()

        row = existing or Connection(user_id=user_id, provider=provider)

        row.account_label = account_label
        if provider_user_id is not None:
            row.provider_user_id = provider_user_id
        if external_site_id is not None:
            row.external_site_id = external_site_id
        if token_data:
            row.access_token_encrypted = encrypt_token(token_data["access_token"])
            refresh_token = token_data.get("refresh_token")
            if refresh_token:
                row.refresh_token_encrypted = encrypt_token(refresh_token)
            if token_data.get("scope"):
                row.scopes = token_data["scope"]
            expires_in = token_data.get("expires_in")
            row.expires_at = datetime.now(UTC) + timedelta(seconds=expires_in) if expires_in else None
        row.connected_at = datetime.now(UTC)
        if provider == "google":
            row.status = "connected_pending_sync"
            row.initial_sync_completed = False
            row.last_error = None

        if not existing:
            db.add(row)
        try:
            db.commit()
        except IntegrityError:
            # Two OAuth callbacks for the same identity can race between the
            # lookup and INSERT. The partial unique index is the final guard;
            # retry once against the row created by the winning callback.
            db.rollback()
            if attempt == 0:
                continue
            raise
        db.refresh(row)
        return row

    raise RuntimeError("Không thể lưu kết nối OAuth sau khi thử lại.")


@router.get("/discord/callback")
@limiter.limit("20/minute")
async def discord_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        data = oauth_state.verify_intent(state, "discord")
    except oauth_state.ExpiredIntentError as exc:
        # Chữ ký state vẫn hợp lệ (chỉ hết hạn) nên ext_redirect_uri khôi phục
        # được an toàn — redirect về web app thay vì trả 400 JSON thô.
        return _finish(exc.data["ext_redirect_uri"], "discord", "error", "state_expired")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if code is None:
        logger.info("Discord connect bị huỷ hoặc thiếu code: %s", _consent_denied_reason(request))
        return _finish(data["ext_redirect_uri"], "discord", "error", "consent_denied")

    try:
        token_data = await discord.exchange_code(code)
        identity = await discord.fetch_account_identity(token_data["access_token"])
        if identity is None:
            raise ValueError("Discord không trả về định danh người dùng.")
        _upsert_connection(
            db,
            user_id=data["user_id"],
            provider="discord",
            account_label=identity.label,
            provider_user_id=identity.user_id,
            token_data=token_data,
        )
        classify_discord_identity(db, data["user_id"], identity.user_id)
    except Exception as exc:  # noqa: BLE001 - vòng OAuth kết thúc bằng redirect báo lỗi, không phải 500
        logger.warning("Discord connect thất bại: %s", exc)
        return _finish(data["ext_redirect_uri"], "discord", "error", "exchange_failed")

    return _finish(data["ext_redirect_uri"], "discord", "connected")


async def _handle_google_login_callback(db: Session, ext_redirect_uri: str, code: str) -> RedirectResponse:
    """flow="login" (xem oauth_state.sign_intent) — chưa có user_id vì chưa ai
    đăng nhập. Tự tạo tài khoản nếu email Google chưa từng đăng ký (đúng yêu
    cầu "ấn Google thì tự đăng ký nếu chưa có"), rồi phát login code ngắn hạn
    thay vì đặt thẳng access/refresh token vào URL redirect."""
    try:
        token_data = await google.exchange_code(code)
        profile = await google.fetch_account_profile(token_data["access_token"])
        if not profile.email:
            raise ValueError("Google không trả về email.")
    except Exception as exc:  # noqa: BLE001 - vòng OAuth kết thúc bằng redirect báo lỗi, không phải 500
        logger.warning("Google login thất bại: %s", exc)
        return _finish(ext_redirect_uri, "google", "error", "exchange_failed")

    email = profile.email.strip().lower()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        # Sentinel giữ tương thích SQLite cũ còn NOT NULL; service auth luôn
        # coi nó như account Google-only, không bao giờ bcrypt-verify.
        user = User(
            email=email,
            password_hash=auth_service.GOOGLE_ONLY_PASSWORD_SENTINEL,
            avatar_url=profile.picture,
        )
        db.add(user)
    elif profile.picture:
        user.avatar_url = profile.picture
    db.commit()
    db.refresh(user)

    if not user.is_active:
        return _finish(ext_redirect_uri, "google", "error", "account_disabled")

    _upsert_connection(
        db,
        user_id=str(user.id),
        provider="google",
        account_label=email,
        token_data=token_data,
        provider_user_id=email,
    )
    reconcile_program_access(db, str(user.id))
    login_code = oauth_state.sign_login_code(user.id)
    # Không tái dùng _finish(): tham số "message" của nó nghĩ cho câu chữ đọc
    # được, còn đây là code bí mật đổi lấy token — đặt tên "code" cho rõ ràng
    # ở phía frontend, tránh nhầm là chuỗi hiển thị lỗi.
    separator = "&" if "?" in ext_redirect_uri else "?"
    return RedirectResponse(f"{ext_redirect_uri}{separator}status=login_success&code={login_code}")


@router.get("/google/callback")
@limiter.limit("20/minute")
async def google_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        data = oauth_state.verify_intent(state, "google", expected_flow="login")
        is_login = True
    except ValueError:
        try:
            data = oauth_state.verify_intent(state, "google")
            is_login = False
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if code is None:
        logger.info("Google connect bị huỷ hoặc thiếu code: %s", _consent_denied_reason(request))
        return _finish(data["ext_redirect_uri"], "google", "error", "consent_denied")

    if is_login:
        return await _handle_google_login_callback(db, data["ext_redirect_uri"], code)

    try:
        token_data = await google.exchange_code(code)
        account_profile = await google.fetch_account_profile(token_data["access_token"])
        account_label = account_profile.email
        user = db.get(User, data["user_id"])
        if user is not None and account_profile.picture:
            user.avatar_url = account_profile.picture
        _upsert_connection(
            db,
            user_id=data["user_id"],
            provider="google",
            account_label=account_label,
            token_data=token_data,
            # Gmail không có ID số như Discord — dùng chính email làm định danh so is_self.
            provider_user_id=account_label.lower() if account_label else None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google connect thất bại: %s", exc)
        return _finish(data["ext_redirect_uri"], "google", "error", "exchange_failed")

    return _finish(data["ext_redirect_uri"], "google", "connected")


@router.get("/jira/callback")
@limiter.limit("20/minute")
async def jira_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        data = oauth_state.verify_intent(state, "jira")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if code is None:
        logger.info("Jira connect bị huỷ hoặc thiếu code: %s", _consent_denied_reason(request))
        return _finish(data["ext_redirect_uri"], "jira", "error", "consent_denied")

    try:
        token_data = await jira.exchange_code(code)
        resource = await jira.fetch_accessible_resource(token_data["access_token"])
        if resource is None:
            raise ValueError("Không tìm thấy site Jira nào được cấp quyền.")
        cloud_id = resource["id"]
        site_url = resource.get("url", "")
        account_id = await jira.fetch_account_id(token_data["access_token"], cloud_id)
        _upsert_connection(
            db,
            user_id=data["user_id"],
            provider="jira",
            account_label=site_url,
            token_data=token_data,
            provider_user_id=(account_id or "").lower() or None,
            external_site_id=cloud_id,
        )
    except Exception as exc:  # noqa: BLE001 - vòng OAuth kết thúc bằng redirect báo lỗi, không phải 500
        logger.warning("Jira connect thất bại: %s", exc)
        return _finish(data["ext_redirect_uri"], "jira", "error", "exchange_failed")

    return _finish(data["ext_redirect_uri"], "jira", "connected")


@router.get("/outlook/callback")
@limiter.limit("20/minute")
async def outlook_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        data = oauth_state.verify_intent(state, "outlook")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if code is None:
        logger.info("Outlook connect bị huỷ hoặc thiếu code: %s", _consent_denied_reason(request))
        return _finish(data["ext_redirect_uri"], "outlook", "error", "consent_denied")

    try:
        token_data = await microsoft.exchange_code(code)
        profile = await microsoft.fetch_account_profile(token_data["access_token"])
        if not profile.email:
            raise ValueError("Không lấy được email tài khoản Outlook.")
        _upsert_connection(
            db,
            user_id=data["user_id"],
            provider="outlook",
            account_label=profile.email,
            token_data=token_data,
            provider_user_id=profile.email,
        )
    except Exception as exc:  # noqa: BLE001 - vòng OAuth kết thúc bằng redirect báo lỗi, không phải 500
        logger.warning("Outlook connect thất bại: %s", exc)
        return _finish(data["ext_redirect_uri"], "outlook", "error", "exchange_failed")

    return _finish(data["ext_redirect_uri"], "outlook", "connected")


@router.get("/slack/callback")
@limiter.limit("20/minute")
async def slack_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        data = oauth_state.verify_intent(state, "slack")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if code is None:
        logger.info("Slack connect bị huỷ hoặc thiếu code: %s", _consent_denied_reason(request))
        return _finish(data["ext_redirect_uri"], "slack", "error", "consent_denied")

    try:
        token_data = await slack.exchange_code(code)
        identity = slack.parse_identity(token_data)
        if identity is None:
            raise ValueError("Slack không trả về định danh user/workspace.")
        authed_user = token_data.get("authed_user") or {}
        access_token = authed_user.get("access_token")
        if not access_token:
            raise ValueError("Slack không cấp user access token — kiểm tra lại user_scope đã xin.")
        # oauth.v2.access không trả expires_in cho user token cổ điển (không
        # rotation) — _upsert_connection() bỏ qua expires_at khi thiếu field,
        # khớp đúng hành vi "không hết hạn" của loại token này.
        team_domain = await slack.fetch_team_domain(access_token)
        _upsert_connection(
            db,
            user_id=data["user_id"],
            provider="slack",
            account_label=team_domain,
            token_data={"access_token": access_token, "scope": authed_user.get("scope")},
            provider_user_id=identity.user_id,
            external_site_id=identity.team_id,
        )
    except Exception as exc:  # noqa: BLE001 - vòng OAuth kết thúc bằng redirect báo lỗi, không phải 500
        logger.warning("Slack connect thất bại: %s", exc)
        return _finish(data["ext_redirect_uri"], "slack", "error", "exchange_failed")

    return _finish(data["ext_redirect_uri"], "slack", "connected")


@router.get("/gmail/oauth/callback")
@limiter.limit("20/minute")
async def gmail_oauth_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    # Friendly Gmail-specific alias; the legacy /google/callback remains valid.
    return await google_callback(request=request, code=code, state=state, db=db)


@router.post("/gmail/initial-sync", response_model=GmailSyncResponse, status_code=202)
async def start_gmail_initial_sync(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> GmailSyncResponse:
    row = preferred_connection(db, user_id, "google")
    if row is None:
        raise HTTPException(status_code=409, detail="Gmail chưa được kết nối.")
    if row.status == "syncing":
        raise HTTPException(status_code=409, detail="Initial sync đang chạy.")

    from src.connectors.gmail import GmailAPIError, GmailConnector
    from src.models.run import Run

    try:
        sources = [source for source in await GmailConnector(row, db).list_sources() if source.id == "INBOX"]
    except GmailAPIError as exc:
        row.status = "error"
        row.last_error = str(exc)[:1024]
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not sources:
        raise HTTPException(status_code=422, detail="Gmail không có source khả dụng.")

    now = datetime.now(UTC)
    body = RunCreateRequest(
        sources=[SyncSourceRef(connection_id=row.id, source_id=source.id) for source in sources],
        time_from=now - timedelta(days=14),
        time_to=now,
        timezone="UTC",
        idempotency_key=f"gmail-initial-{row.id}-{int(now.timestamp())}",
    )
    run = Run(
        user_id=int(user_id),
        sources=[source.model_dump() for source in body.sources],
        range_from=body.time_from,
        range_to=body.time_to,
        idempotency_key=body.idempotency_key,
        timezone=body.timezone,
        mode=body.mode,
        status="queued",
    )
    row.status = "syncing"
    row.last_error = None
    db.add(run)
    db.commit()
    db.refresh(run)
    return GmailSyncResponse(run_id=run.id, status="syncing")


@router.get("/telegram/callback")
@limiter.limit("20/minute")
async def telegram_callback(
    request: Request,
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        data = oauth_state.verify_intent(state, "telegram")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        payload = {k: v for k, v in request.query_params.items() if k != "state"}
        identity = telegram.verify_identity(payload)
        if identity is None:
            raise ValueError("Chữ ký Telegram không hợp lệ hoặc đã hết hạn.")
        linked_elsewhere = db.execute(
            select(Connection).where(
                Connection.provider == "telegram",
                Connection.provider_user_id == identity.user_id,
                Connection.user_id != data["user_id"],
            )
        ).scalar_one_or_none()
        if linked_elsewhere is not None:
            raise ValueError("Tài khoản Telegram này đã liên kết với một tài khoản khác.")
        _upsert_connection(
            db,
            user_id=data["user_id"],
            provider="telegram",
            account_label=identity.account_label,
            provider_user_id=identity.user_id,
            token_data=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram connect thất bại: %s", exc)
        return _finish(data["ext_redirect_uri"], "telegram", "error", "verify_failed")

    return _finish(data["ext_redirect_uri"], "telegram", "connected")


def _purge_provider_cache(db: Session, user_id: str, provider: str) -> None:
    """Xoá cache thô của một provider khi ngắt kết nối.

    `Message`/`SourceScopeAccess` không kiểm tra `Connection` còn sống khi
    retrieval đọc chúng — `_cached_gmail_messages` (src/services/gmail_tools.py)
    tra `messages` thẳng theo user_id+provider, còn `apply_search_scope`
    (src/services/scope.py) cấp quyền đọc chunk Discord theo scope_ids đã cấp
    trong `source_scope_access`, không join `connections`. Xoá Connection thôi
    thì chatbot vẫn trả lời bằng dữ liệu nguồn đã ngắt — phải dọn cả hai bảng
    này ở đây. Không đụng Task/Cluster: đó là quyết định đã xác nhận, có thể
    gộp bằng chứng từ nhiều nguồn khác nhau, không thuộc về riêng provider này.
    ClusterMessage/TaskEvidence tự dọn theo FK ondelete khi Message bị xoá.
    """
    db.execute(delete(Message).where(Message.user_id == user_id, Message.provider == provider))
    # SourceScopeAccess ghi rõ trong docstring: "revoked/expired, not deleted,
    # so an audit trail remains" — thu hồi bằng update, không delete().
    db.execute(
        update(SourceScopeAccess)
        .where(
            SourceScopeAccess.user_id == user_id,
            SourceScopeAccess.status == "confirmed",
            SourceScopeAccess.scope_id.in_(select(SourceScope.id).where(SourceScope.provider == provider)),
        )
        .values(status="revoked", valid_to=datetime.now(UTC))
    )


@router.post("/account/{connection_id}/disconnect", status_code=204)
async def disconnect_account(
    connection_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None:
    row = db.execute(
        select(Connection).where(Connection.id == connection_id, Connection.user_id == user_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy connection của tài khoản này.")
    await revoke_connection_tokens(row)
    provider = row.provider
    db.delete(row)
    _purge_provider_cache(db, user_id, provider)
    db.commit()
    if provider == "discord":
        set_program_access(db, user_id, "C")


@router.post("/{provider}/disconnect", status_code=204)
async def disconnect(
    provider: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None:
    _require_known_provider(provider)
    row = preferred_connection(db, user_id, provider, include_dead=True)
    if row:
        await revoke_connection_tokens(row)
        db.delete(row)
    _purge_provider_cache(db, user_id, provider)
    db.commit()
    if provider == "discord":
        set_program_access(db, user_id, "C")
