from functools import lru_cache

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.config import get_settings

INTENT_MAX_AGE_SECONDS = 5 * 60
# Login code chỉ sống đủ 1 lượt redirect từ callback về frontend rồi đổi lấy
# token ngay — ngắn hơn hẳn intent (5 phút) để giảm cửa sổ lộ nếu URL bị log lại.
LOGIN_CODE_MAX_AGE_SECONDS = 60


@lru_cache
def _serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    if not settings.app_secret_key:
        raise RuntimeError("APP_SECRET_KEY chưa cấu hình — bắt buộc để ký state token OAuth.")
    return URLSafeTimedSerializer(settings.app_secret_key, salt="connections-oauth")


@lru_cache
def _login_code_serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    if not settings.app_secret_key:
        raise RuntimeError("APP_SECRET_KEY chưa cấu hình — bắt buộc để ký login code.")
    # Salt riêng với _serializer(): 1 token ký cho "ý định OAuth" (state) không
    # được đổi lấy phiên đăng nhập dù cùng khoá bí mật ký nền.
    return URLSafeTimedSerializer(settings.app_secret_key, salt="google-login-code")


class ExpiredIntentError(ValueError):
    """State đã hết hạn nhưng chữ ký hợp lệ, nên payload gốc được khôi phục an toàn.

    itsdangerous xác thực HMAC trước khi kiểm tra tuổi token, nên khi
    ``SignatureExpired`` được raise thì payload (kèm ``ext_redirect_uri``) chắc
    chắn chưa bị giả mạo — caller có thể dùng nó để redirect người dùng về đúng
    web app kèm thông báo lỗi, thay vì trả 400 thô. Kế thừa ``ValueError`` để các
    caller cũ (`except ValueError`) không cần đổi behavior.
    """

    def __init__(self, message: str, data: dict[str, str]):
        super().__init__(message)
        self.data = data


def sign_intent(
    user_id: str | None,
    provider: str,
    ext_redirect_uri: str,
    *,
    flow: str = "connect",
) -> str:
    """`user_id=None` chỉ hợp lệ với `flow="login"` — luồng "Đăng nhập với
    Google" bắt đầu khi chưa có ai đăng nhập, khác `flow="connect"` (mặc định)
    vốn luôn cần user_id của người đang gắn thêm 1 nguồn dữ liệu."""
    return _serializer().dumps(
        {"user_id": user_id, "provider": provider, "ext_redirect_uri": ext_redirect_uri, "flow": flow}
    )


def verify_intent(token: str, expected_provider: str, *, expected_flow: str = "connect") -> dict[str, str]:
    try:
        data = _serializer().loads(token, max_age=INTENT_MAX_AGE_SECONDS)
    except SignatureExpired as exc:
        message = "Yêu cầu kết nối đã hết hạn, thử lại."
        try:
            recovered = _serializer().load_payload(exc.payload)
        except Exception:  # noqa: BLE001 - payload hỏng thì coi như không khôi phục được
            recovered = None
        if isinstance(recovered, dict) and recovered.get("provider") == expected_provider:
            raise ExpiredIntentError(message, data=recovered) from exc
        raise ValueError(message) from exc
    except BadSignature as exc:
        raise ValueError("State token không hợp lệ.") from exc

    if data.get("provider") != expected_provider:
        raise ValueError("State token không khớp provider.")
    # State ký trước khi có "flow" (dữ liệu cũ) mặc định "connect" — giữ tương
    # thích ngược, không chặn nhầm những state đang bay giữa chừng lúc deploy.
    if data.get("flow", "connect") != expected_flow:
        raise ValueError("State token không khớp luồng xử lý.")
    return data


def sign_login_code(user_id: int) -> str:
    """Mã ngắn hạn cho callback OAuth redirect về frontend rồi đổi lấy token
    thật qua POST — không đặt access/refresh token thẳng vào URL (lộ qua
    lịch sử trình duyệt, log server, Referer)."""
    return _login_code_serializer().dumps({"user_id": user_id})


def verify_login_code(code: str) -> int:
    try:
        data = _login_code_serializer().loads(code, max_age=LOGIN_CODE_MAX_AGE_SECONDS)
    except SignatureExpired as exc:
        raise ValueError("Mã đăng nhập đã hết hạn, thử lại.") from exc
    except BadSignature as exc:
        raise ValueError("Mã đăng nhập không hợp lệ.") from exc
    return int(data["user_id"])
