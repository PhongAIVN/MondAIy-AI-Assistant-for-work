"""Bộ lọc phải nhận ra cùng một loại thư rác dù viết bằng ngôn ngữ nào.

Trước đây các danh sách *_FOLDED_TERMS gần như chỉ có tiếng Việt, nên hộp thư
tiếng Anh (và mọi ngôn ngữ khác) chỉ được lọc bằng vài regex chung — thư biên
lai/OTP/mạng xã hội viết bằng tiếng Anh vẫn lọt vào hộp việc.

File này cũng khoá lại hai quy ước đã phải trả giá bằng 3 lần lọt lỗi thật:
danh sách phủ định quét TOÀN THÂN MAIL, nên không được chứa từ trần mơ hồ,
cũng không được chứa câu boilerplate chân trang.
"""

from datetime import UTC, datetime

import pytest

import src.services.filter_classify as fc
from src.services.filter_classify import FilterConfig, filter_and_classify

NOW = datetime(2026, 8, 20, 12, tzinfo=UTC)
USER = "student@school.edu"

NEGATIVE_LIST_NAMES = (
    "NEWSLETTER_FOLDED_TERMS",
    "SOCIAL_NOTIFICATION_FOLDED_TERMS",
    "NO_ACTION_FOLDED_TERMS",
    "COMPLETED_FOLDED_TERMS",
    "SECURITY_SCAM_FOLDED_TERMS",
    "TRANSACTIONAL_NOTIFICATION_FOLDED_TERMS",
    "OPTIONAL_OR_BROADCAST_FOLDED_TERMS",
)


def _mail(text: str, *, subject: str = "", sender: str = "someone@example.com") -> dict:
    return {
        "id": "m1",
        "thread_id": "t1",
        "author_id": sender,
        "author_name": "Someone",
        "subject": subject,
        "text": text,
        "to": [USER],
        "cc": [],
        "sent_at": NOW,
    }


def _kept(text: str, **kwargs) -> bool:
    result = filter_and_classify([_mail(text, **kwargs)], FilterConfig(user_email=USER), now=NOW)
    return bool(result["items"])


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("en", "Your one-time password is 402913. Please do not share this security code."),
        ("es", "Su codigo de verificacion es 402913."),
        ("fr", "Votre code de verification est 402913."),
        ("de", "Ihr Bestatigungscode lautet 402913."),
        ("ja", "認証コードは402913です。"),
        ("zh", "您的验证码是 402913。"),
        ("ko", "인증번호는 402913 입니다."),
    ],
)
def test_one_time_codes_are_dropped_in_every_language(language, text):
    assert not _kept(text), language


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("en", "Order confirmation. Your order has shipped and payment received. Thank you."),
        ("es", "Confirmacion de pago recibida. Gracias por su compra."),
        ("fr", "Confirmation de paiement recue. Merci pour votre achat."),
        ("de", "Zahlungsbestatigung. Vielen Dank fur Ihren Einkauf."),
        ("zh", "支付成功，感谢您的购买。"),
        ("ko", "결제가 완료되었습니다. 감사합니다."),
    ],
)
def test_payment_and_shipping_receipts_are_dropped_in_every_language(language, text):
    assert not _kept(text), language


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("en", "Weekly newsletter. Click unsubscribe or view this email in your browser."),
        ("vi", "Bản tin tuần này. Nhấn huy dang ky nhan tin nếu không muốn nhận nữa."),
        ("es", "Boletin informativo semanal. Puede darse de baja cuando quiera."),
        ("fr", "Notre lettre hebdomadaire. Vous pouvez vous desabonner a tout moment."),
        ("de", "Sie konnen den Newsletter abbestellen."),
        ("ja", "配信停止をご希望の場合はこちら。"),
        ("zh", "如需退订，请点击这里。"),
        ("ko", "수신거부를 원하시면 여기를 클릭하세요."),
    ],
)
def test_newsletters_are_dropped_in_every_language(language, text):
    assert not _kept(text), language


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("en", "Heads up: no action is needed, the ticket has been resolved already."),
        ("es", "No se requiere ninguna accion, el caso ha sido resuelto."),
        ("fr", "Aucune action requise, le ticket a ete resolu."),
        ("de", "Keine Aktion erforderlich, das Ticket wurde abgeschlossen."),
        ("ja", "対応不要です。完了しました。"),
        ("zh", "无需操作，已完成。"),
        ("ko", "조치가 필요하지 않습니다. 완료되었습니다."),
    ],
)
def test_already_done_notices_are_dropped_in_every_language(language, text):
    assert not _kept(text), language


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("en", "Hoai An invited you to connect on LinkedIn. See who viewed your profile."),
        ("vi", "Hoai An da moi ban ket noi. Xem ai da thich bai viet cua ban."),
        ("ko", "새로운 팔로워가 있습니다."),
    ],
)
def test_social_pings_are_dropped_in_every_language(language, text):
    assert not _kept(text), language


def test_real_work_in_english_is_still_kept():
    """Đối chứng: mở rộng danh sách phủ định không được kéo theo thư việc thật."""
    assert _kept(
        "Please review the attached benchmark sheet and send back the updated version before Friday.",
        subject="Benchmark review",
        sender="mentor@school.edu",
    )


# --------------------------------------------------------------------------
# Hai quy ước bên dưới đã phải trả giá bằng 3 lần lọt lỗi thật — khoá lại để
# một lần sửa danh sách sau này không lặng lẽ dựng chúng lên lại.
# --------------------------------------------------------------------------

# Câu chỉ xuất hiện ở chân trang thư hệ thống. Gần như MỌI thư tự động đều có,
# kể cả thư Jira giao việc đích danh — dùng làm căn cứ loại là chặn nhầm hết.
FOOTER_BOILERPLATE = (
    "do not reply",
    "do not reply to this email",
    "this is an automated message",
    "you are receiving this",
    "you're receiving this",
    "opt out",
    "email preferences",
    "notification",
    "sent from my",
)


@pytest.mark.parametrize("list_name", NEGATIVE_LIST_NAMES)
def test_negative_lists_contain_no_footer_boilerplate(list_name):
    terms = set(getattr(fc, list_name))
    offenders = terms.intersection(FOOTER_BOILERPLATE)
    assert not offenders, f"{list_name} chứa câu chân trang: {sorted(offenders)}"


# Từ trần mơ hồ: rất hay chỉ là một ô trạng thái trong danh sách hoặc một mệnh
# đề phụ, không chứng minh nội dung mail. Bug thật: bản nhắc Jira liệt kê 1 việc
# "Resolved" bị coi là cả mail đã xong; "gửi lại bản đã cập nhật" bị coi là hết
# việc.
AMBIGUOUS_BARE_TERMS = (
    "resolved",
    "closed",
    "cancelled",
    "canceled",
    "done",
    "complete",
    "completed",
    "updated",
    "da cap nhat",
    "da duoc cap nhat",
    "update",
    "received",
    "confirmed",
)


@pytest.mark.parametrize("list_name", NEGATIVE_LIST_NAMES)
def test_negative_lists_contain_no_ambiguous_bare_terms(list_name):
    terms = set(getattr(fc, list_name))
    offenders = terms.intersection(AMBIGUOUS_BARE_TERMS)
    assert not offenders, f"{list_name} chứa từ trần mơ hồ: {sorted(offenders)}"


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("ja", "ドラフトファイルを確認してもらえますか？金曜までにご返信をお願いします。"),
        ("zh", "请确认草稿文件，并在本周五截止前回复。"),
        ("ko", "초안 파일 확인 부탁드립니다. 금요일 마감까지 회신해 주세요."),
        ("es", "Por favor revisa el borrador antes de la fecha limite del viernes."),
        ("fr", "Veuillez relire le brouillon avant la date limite de vendredi."),
        ("de", "Bitte prufen Sie den Entwurf bis zum Freitag, die Frist gilt."),
    ],
)
def test_work_requests_score_as_actionable_in_every_language(language, text):
    """Các danh sách PHỦ ĐỊNH đã đa ngôn ngữ nhưng danh sách TÍCH CỰC thì chưa
    — mail giao việc tiếng Nhật chỉ còn điểm người-nhận (30), tụt xuống
    "ignore". Tín hiệu action/deadline phải nhận được ở mọi thứ tiếng."""
    result = filter_and_classify([_mail(text)], FilterConfig(user_email=USER), now=NOW)
    assert result["items"], language
    reasons = set(result["items"][0]["classification_reasons"])
    assert {"action_signal", "deadline_signal"} & reasons, language


def test_common_japanese_particle_is_not_treated_as_a_deadline():
    """"まで" trần là trợ từ "đến/tới", có trong hầu hết câu tiếng Nhật — đúng
    loại từ trần bị cấm. Chỉ "までに" mới là dạng chỉ hạn chót."""
    assert "まで" not in fc.DEADLINE_FOLDED_TERMS
    assert "までに" in fc.DEADLINE_FOLDED_TERMS

