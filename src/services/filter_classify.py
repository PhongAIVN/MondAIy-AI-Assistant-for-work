"""Rule-based Gmail filtering, scoring, thread grouping and deduplication."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import getaddresses
from functools import cache
from typing import Any, Literal

from src.config import Settings, get_settings
from src.services.hf_mail_classifier import apply_prediction, classify_mail

ACTION_RE = re.compile(
    r"(?i)(?<![-\w])\b(please|reply|respond|submit|send|complete|review|confirm|register|update|vui lòng|yêu cầu|cần|phản hồi|nộp|duyệt|xác nhận|hoàn thành)\b"
)
DEADLINE_RE = re.compile(
    r"(?i)\b(deadline|due|by|before|until|hạn chót|hạn nộp|trước|thứ hai|thứ ba|thứ tư|thứ năm|thứ sáu|thứ bảy|chủ nhật|monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|today|\d{1,2}[/-]\d{1,2})\b"
)
# \b không có tác dụng với chữ Nhật/Trung/Hàn (không có ranh giới từ kiểu
# Latin) nên nhóm CJK để riêng, không bọc \b.
URGENCY_RE = re.compile(
    r"(?i)(\b(urgent|asap|action required|immediate|urgente|dringend|gấp|khẩn cấp)\b|至急|大至急|緊急|紧急|加急|긴급)"
)
PROGRAM_RE = re.compile(
    r"(?i)\b(program|course|class|cohort|assignment|project|milestone|proposal|demo|mentor|vlearn|canvas|jira|deadline|bài tập|môn|nhóm|đồ án|chương trình)\b"
)
NEWSLETTER_RE = re.compile(r"(?i)\b(newsletter|unsubscribe|digest|sale|offer|% off|khuyến mãi)\b")
# Ngoài no-reply/notification, thêm các local-part bot phổ biến gửi thư
# định kỳ dạng digest (routine@, digest@, mailer@, bounce@...). Bug thật:
# "routine@littlebird.ai" gửi bản tổng hợp hằng ngày "everything looks
# under control" mà vẫn đạt 70 điểm -> important -> vào hộp việc.
AUTOMATED_RE = re.compile(
    r"(?i)(no-?reply|donotreply|automated|notification|noreply@|(?:^|[<\s])(?:routine|digest|mailer|mailer-daemon|bounce|updates)@)"
)
TRANSACTIONAL_RE = re.compile(r"(?i)\b(receipt|order|purchase|invoice|payment|delivery|shipping|total)\b")
QUOTE_SPLIT_RE = re.compile(
    r"(?i)(?:\n|^)\s*(?:---+\s*(?:previous|original|email truoc|email trước)|from: .+\n|on .+ wrote:)"
)
SIGNATURE_SPLIT_RE = re.compile(r"(?i)(?:\n|^)\s*--\s*\n")

# ---------------------------------------------------------------------------
# Quy ước cho mọi danh sách *_FOLDED_TERMS bên dưới
#
# 1. So khớp trên chuỗi đã đi qua `_fold()`: NFKD, bỏ dấu thanh, "đ" -> "d",
#    casefold. Vì vậy phải viết SẴN dạng đã bỏ dấu — "désabonner" ghi thành
#    "desabonner", "bestätigungscode" thành "bestatigungscode", tiếng Đức "ß"
#    thành "ss". Chữ Hán/Kana/Hangul không bị ảnh hưởng, ghi nguyên.
# 2. Nhóm theo ngôn ngữ. Thêm ngôn ngữ mới = thêm một khối `# -- xx --`, không
#    phải sửa logic.
# 3. Các danh sách PHỦ ĐỊNH (NEWSLETTER/NO_ACTION/COMPLETED/SOCIAL/SECURITY/
#    TRANSACTIONAL/OPTIONAL) quét TOÀN THÂN MAIL và kéo theo -65 điểm
#    negative_state. Hai luật bắt buộc:
#      - KHÔNG dùng từ trần mơ hồ ("resolved", "closed", "da cap nhat"). Nó
#        bắt nhầm một ô trạng thái trong danh sách hoặc một mệnh đề phụ, kéo
#        cả mail mang việc thật xuống vực. Đã gây 3 lần lọt lỗi thật.
#      - KHÔNG dùng câu boilerplate chân trang ("do not reply to this email",
#        "this is an automated message", "you are receiving this because").
#        Gần như mọi thư hệ thống đều có, kể cả thư giao việc thật của Jira.
# ---------------------------------------------------------------------------

ACTION_FOLDED_TERMS = (
    "please",
    "reply",
    "respond",
    "submit",
    "send",
    "complete",
    "review",
    "confirm",
    "register",
    "update",
    "approve",
    "required",
    "vui long",
    "yeu cau",
    "can",
    "phan hoi",
    "nop",
    "duyet",
    "xac nhan",
    "hoan thanh",
    "chuan bi",
    "kiem tra",
    "tham gia",
    "xu ly",
    "dung so",
    "dung ban",
    "thay bang",
    "trien khai",
    # -- es / fr / de --
    "por favor",
    "revisa",
    "confirmar",
    "s'il vous plait",
    "merci de",
    "veuillez",
    "bitte",
    "prufen sie",
    "bestatigen sie",
    # -- ja --
    # Kính ngữ nhờ vả là tín hiệu "cần làm" rõ nhất trong mail công việc tiếng
    # Nhật; không có nhóm này thì mail giao việc chỉ còn điểm người-nhận.
    "してください",
    "していただけますか",
    "してもらえますか",
    "お願いします",
    "ご確認",
    "ご対応",
    "ご返信",
    "提出",
    "確認をお願い",
    # -- zh --
    "请确认",
    "请回复",
    "请提交",
    "请审阅",
    "麻烦",
    # -- ko --
    "확인 부탁",
    "회신 부탁",
    "제출해",
    "검토해",
)
DEADLINE_FOLDED_TERMS = (
    "deadline",
    "due",
    "before",
    "until",
    "today",
    "tomorrow",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "han chot",
    "han nop",
    "truoc",
    "thu hai",
    "thu ba",
    "thu tu",
    "thu nam",
    "thu sau",
    "thu bay",
    "chu nhat",
    "hom nay",
    "ngay mai",
    # -- es / fr / de --
    "fecha limite",
    "antes del",
    "date limite",
    "avant le",
    "frist",
    "bis zum",
    # -- ja --
    "締切",
    "締め切り",
    "期限",
    # "まで" trần là trợ từ "đến/tới", có mặt trong hầu hết câu tiếng Nhật —
    # đúng loại từ trần bị cấm. "までに" mới là dạng chỉ hạn chót.
    "までに",
    "本日",
    "明日",
    "月曜",
    "火曜",
    "水曜",
    "木曜",
    "金曜",
    # -- zh --
    "截止",
    "今天",
    "明天",
    "周一",
    "周五",
    # -- ko --
    "마감",
    "기한",
    "오늘",
    "내일",
)
PROGRAM_FOLDED_TERMS = (
    "program",
    "course",
    "class",
    "cohort",
    "assignment",
    "project",
    "milestone",
    "proposal",
    "mentor",
    "vlearn",
    "canvas",
    "jira",
    "bai tap",
    "mon",
    "nhom",
    "do an",
    "chuong trinh",
    "du an",
    # -- es / fr / de --
    "proyecto",
    "tarea",
    "projet",
    "devoir",
    "projekt",
    "aufgabe",
    # -- ja / zh / ko --
    "プロジェクト",
    "課題",
    "タスク",
    "项目",
    "作业",
    "프로젝트",
    "과제",
)
NEWSLETTER_FOLDED_TERMS = (
    # -- en --
    "newsletter",
    "unsubscribe",
    "digest",
    "sale",
    "offer",
    "% off",
    "book a demo",
    "marketing communication",
    "promotional",
    "complimentary",
    "discounted",
    "manage your email preferences",
    "update your email preferences",
    "view this email in your browser",
    # Không thêm "opt out"/"email preferences" trần: đó là câu chân trang,
    # cảnh báo chi phí AWS cũng có -> loại oan. Chỉ giữ cụm dài đặc trưng
    # thư quảng cáo.
    "view in browser",
    "limited time",
    "early bird",
    # Thư gợi ý nội dung định kỳ của Confluence/Jira: cùng domain với thư việc
    # thật nên không loại được theo người gửi, phải nhận ra bằng giọng văn.
    "content recommendations",
    "weekly content",
    "ready to explore",
    # -- vi --
    "khuyen mai",
    "uu dai",
    "ban tin",
    "dang ky ngay",
    "huy dang ky nhan tin",
    "ngung nhan email",
    "xem email tren trinh duyet",
    # -- es --
    "darse de baja",
    "cancelar la suscripcion",
    "boletin informativo",
    # -- fr --
    "desabonner",
    "desabonnement",
    "voir dans le navigateur",
    # -- de --
    "newsletter abbestellen",
    "abmeldelink",
    "im browser ansehen",
    # -- ja / zh / ko --
    "配信停止",
    "メルマガ",
    "退订",
    "取消订阅",
    "수신거부",
    "수신 거부",
)
SECURITY_SCAM_FOLDED_TERMS = (
    # -- en --
    "gift card",
    "purchase gift cards",
    "wire transfer immediately",
    "keep this between us",
    "your account will be suspended",
    "click here to verify your account",
    # -- vi --
    "chuyen khoan gap cho toi",
    "dung noi voi ai",
    # -- es / fr / de --
    "su cuenta sera suspendida",
    "votre compte sera suspendu",
    "ihr konto wird gesperrt",
    "the qua tang",
    "client secret",
    "ma the",
    "tuyet mat",
    "khong hoi finance",
    "do not use the normal",
    "reply to this email with",
)
SOCIAL_NOTIFICATION_FOLDED_TERMS = (
    # -- en --
    "invited you to connect",
    "endorsed you for",
    "liked your post",
    "reacted to your post",
    "started following you",
    "new follower",
    "sent you a friend request",
    "tagged you in a photo",
    "see who viewed",
    "trending in your network",
    "jobs you may be interested in",
    # -- vi --
    "da moi ban ket noi",
    "da thich bai viet cua ban",
    "nguoi theo doi moi",
    # -- ja / zh / ko --
    "つながり申請",
    "邀请你加入",
    "새로운 팔로워",
    "linkedin",
    "thong bao moi tren linkedin",
    "nguoi da xem ho so",
    "ket noi da dang bai moi",
    "new notifications",
    "people viewed your profile",
    "connections posted",
    "view your notifications",
)
NO_ACTION_FOLDED_TERMS = (
    # -- en --
    # Thư digest định kỳ khẳng định KHÔNG có việc gì đang chờ — đúng nghĩa
    # "không cần hành động", nhưng lại đầy từ khoá action ("reply",
    # "merging", "deploying") nên regex một mình chấm nhầm thành việc thật.
    "everything looks under control",
    "no overdue",
    "nothing needs your attention",
    "nothing is waiting on your reply",
    "no action needed",
    "no action is needed",
    "no response is needed",
    "no response required",
    "nothing to do on your end",
    "you do not need to do anything",
    "no action required",
    "no action is required",
    "no action is currently required",
    "no review is currently requested",
    "no acknowledgment is required",
    "no retry",
    "no investigation is required",
    "automatic reply",
    "tra loi tu dong",
    "khong can hanh dong",
    "khong can thuc hien",
    "chua can thuc hien",
    "khong can xu ly",
    "khong co muc nao can",
    "khong co action nao",
    "khong can chuan bi",
    "hien tai khong can",
    "khong can dang ky",
    "khong can migrate",
    "khong can gui",
    "chua can ai",
    "chua can",
    "co the bo qua",
    "bo qua toan bo yeu cau",
    "khong con follow-up",
    "khong con user nao",
    "khong can approve",
    "khong can an",
    "reference only",
    "for reference only",
    "for your information",
    "fyi only",
    "fyi thoi",
    "optional",
    "du roi",
    # -- es / fr / de --
    "no se requiere ninguna accion",
    "no es necesario responder",
    "aucune action n'est requise",
    "aucune action requise",
    "keine aktion erforderlich",
    "keine reaktion erforderlich",
    # -- ja / zh / ko --
    "対応不要",
    "返信不要",
    "无需操作",
    "无需回复",
    "조치가 필요하지 않습니다",
)
COMPLETED_FOLDED_TERMS = (
    # Từ trạng thái đứng MỘT MÌNH ("resolved", "closed", "cancelled") không
    # chứng minh mail nói việc đã xong — nó rất hay chỉ là 1 ô trạng thái
    # trong danh sách. Bug thật: bản nhắc Jira liệt kê nhiều việc, 1 việc
    # mang trạng thái Resolved là cả mail bị coi "đã xong" rồi drop cứng,
    # kéo theo cả những việc CHƯA xong nằm cùng mail. Chỉ nhận dạng bằng cụm
    # khẳng định trạng thái của chính mail đó.
    # -- en --
    "completed successfully",
    "successfully completed",
    "upload complete",
    "has been resolved",
    "have been resolved",
    "was resolved",
    "is resolved",
    "has been closed",
    "have been closed",
    "was closed",
    "is closed",
    "has been cancelled",
    "has been canceled",
    "has been completed",
    "was completed",
    "has been delivered",
    "marked as done",
    "no further action",
    "nothing further is needed",
    # -- vi --
    "da duoc resolve",
    "da xu ly hoan tat",
    "da duoc xu ly",
    "da hoan tat",
    "da ghi nhan",
    "da nhan duoc xac nhan",
    # KHÔNG có biến thể nào của "cập nhật" ở đây. Cụm này không bao giờ
    # chứng minh "hết việc", mà thường là ngược lại:
    #   - "gửi lại bản đã cập nhật để cô review tiếp" -> yêu cầu làm bản mới.
    #   - "Sự kiện đã được cập nhật. Địa điểm mới: ..." -> thay đổi PHẢI biết.
    # Trường hợp thật sự xong đã có "da hoan tat"/"da xu ly hoan tat"/
    # "da hoan thanh"/"da duoc xu ly" lo.
    "da huy",
    "superseded",
    "ignore email",
    "ignore email ben duoi",
    "was cancelled",
    "was superseded",
    "da hoan thanh",
    "chuc mung",
    "an mung",
    # -- es / fr / de --
    "se ha completado",
    "ha sido resuelto",
    "a ete resolu",
    "a ete traite",
    "wurde abgeschlossen",
    "wurde erledigt",
    # -- ja / zh / ko --
    "完了しました",
    "対応済み",
    "已完成",
    "已处理",
    "완료되었습니다",
    "처리되었습니다",
)
TRANSACTIONAL_NOTIFICATION_FOLDED_TERMS = (
    # -- en --
    "your receipt",
    "order confirmation",
    "your order has shipped",
    "shipping confirmation",
    "delivery confirmation",
    "payment received",
    "payment successful",
    "transaction completed",
    "your subscription has renewed",
    "your invoice is ready",
    # -- es / fr / de --
    "confirmacion de pago",
    "confirmation de paiement",
    "zahlungsbestatigung",
    # -- ja / zh / ko --
    "ご購入ありがとうございます",
    "支付成功",
    "결제가 완료되었습니다",
    # -- vi --
    # Giọng văn biên nhận/thông báo tự động (bên thứ 3 báo lại 1 sự kiện đã
    # xảy ra) — khác hẳn giọng yêu cầu hành động thật ("cần chuyển khoản học
    # phí trước..."). Dùng cụm nhiều từ, không dùng từ đơn ("chuyen khoan",
    # "hoa don") để tránh dập luôn task thật có nhắc các từ này.
    "giao dich thanh cong",
    "chuyen khoan thanh cong",
    "bien dong so du",
    "so du kha dung",
    "noi dung chuyen khoan",
    "don hang cua ban da duoc giao",
    "giao hang thanh cong",
    "xac nhan dat ve thanh cong",
    "xac nhan dat phong thanh cong",
    "thanh toan thanh cong",
    "hoa don dien tu",
    # OTP/mã xác thực — không bao giờ là task thật, luôn là mã dùng 1 lần cho
    # 1 giao dịch khác, không phải việc cần làm.
    "ma otp",
    "otp cua ban",
    "otp co hieu luc",
    # Mã xác thực dùng 1 lần — không bao giờ là việc thật, ở mọi ngôn ngữ.
    "verification code",
    "one-time password",
    "authentication code",
    "your otp",
    "security code",
    "codigo de verificacion",
    "code de verification",
    "bestatigungscode",
    "認証コード",
    "ワンタイムパスワード",
    "验证码",
    "인증번호",
    # Tip an toàn/bảo mật ngân hàng đính kèm CUỐI mọi email (Vietcombank...) —
    # giọng khuyến cáo chung, không phải yêu cầu hành động cho 1 việc cụ thể.
    "safe transaction",
    "safe when transacting online",
    "an toan giao dich",
    "bao mat tai khoan",
)
NEGATIVE_OVERRIDE_FOLDED_TERMS = (
    "tuy nhien",
    "ngoai le",
    "ap dung cho ban",
    "ap dung cho an",
    "pre-read",
    "doc truoc",
    "read before",
    "steering committee",
    "level-2 approver resolved",
    "sla remaining",
    "approve / reject",
    "approve/reject",
    "se gui lich moi",
    "will send a new",
    "reschedule",
    "trien khai theo",
    "cho phe duyet cua ban",
    "waiting for your approval",
    "nho kiem tra",
    "se phai",
    "dau moi moi",
    "luong moi",
    "open items",
    "an: xac nhan",
    "quy tac moi",
    "quyet dinh da",
    "da duoc coo phe duyet",
    "vui long chuyen",
    "da ban giao case",
    "khi finance gui",
    "trong vong 1 ngay",
    "nho em",
)
OPTIONAL_OR_BROADCAST_FOLDED_TERMS = (
    # -- en --
    "all employees",
    "all staff",
    "company-wide",
    "all hands",
    "town hall",
    "everyone at",
    # -- es / fr / de --
    "para todo el personal",
    "a tout le personnel",
    "an alle mitarbeiter",
    "all vietnam",
    "engineering all",
    "product team",
    "product leads",
    "toan cong ty",
    "ca cong ty",
    "moi nguoi",
    "ca nha",
    "khong co thay doi",
    "chua co quyet dinh",
    "chua phai quyet dinh",
    "chua can ai",
    "chua can chuan bi",
)
COMMON_LANGUAGE_FOLDED_TERMS = (
    "the",
    "and",
    "you",
    "your",
    "for",
    "with",
    "that",
    "this",
    "please",
    "can",
    "will",
    "are",
    "is",
    "to",
    "from",
    "vui",
    "long",
    "ban",
    "toi",
    "minh",
    "anh",
    "chi",
    "em",
    "hay",
    "voi",
    "cho",
    "can",
    "se",
    "la",
)

# Domain deep_link hợp lệ theo provider — Jira Cloud không có 1 domain cố
# định (mỗi site 1 subdomain *.atlassian.net) nên validate theo pattern chứ
# không theo domain đơn như Gmail. Provider chưa có trong bảng này thì không
# chặn (tránh lặp lại lỗi hardcode chỉ-Gmail chặn luôn mọi nguồn khác).
VALID_DEEP_LINK_PATTERNS: dict[str, re.Pattern[str]] = {
    "google": re.compile(r"^https://mail\.google\.com/"),
    "google_calendar": re.compile(r"^https://calendar\.google\.com/"),
    "jira": re.compile(r"^https://[a-zA-Z0-9][a-zA-Z0-9-]*\.atlassian\.net/browse/"),
    # SlackConnector.deep_link() dựng link thủ công (chat.getPermalink() tốn
    # thêm 1 call/message, xem comment trong src/connectors/slack.py) —
    # 2 dạng hợp lệ: subdomain workspace (team_domain đã resolve) hoặc
    # app.slack.com/client/{team_id} (fallback khi chưa resolve được domain).
    "slack": re.compile(r"^https://([a-zA-Z0-9][a-zA-Z0-9-]*\.slack\.com/archives/|app\.slack\.com/client/)"),
}


def has_valid_deep_link(item: dict[str, Any]) -> bool:
    deep_link = item.get("deep_link")
    if not deep_link:
        return True
    pattern = VALID_DEEP_LINK_PATTERNS.get(item.get("provider"))
    if pattern is None:
        return True
    return bool(pattern.match(str(deep_link)))


@dataclass(frozen=True)
class FilterConfig:
    user_email: str | None = None
    trusted_senders: frozenset[str] = frozenset()
    trusted_sender_domains: frozenset[str] = frozenset()
    program_domains: frozenset[str] = frozenset()
    approved_labels: frozenset[str] = frozenset()
    lookback_days: int = 14
    min_relevant_score: int = 35


@dataclass(frozen=True)
class Classification:
    importance_score: int
    importance: str
    brief_section: str
    must_not_miss: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)
    component_scores: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class TriageDecision:
    decision: Literal["keep", "drop", "llm_judge"]
    probability: float
    stage: str
    reason: str
    classification: Classification


def _addresses(value: str | list[str] | None) -> set[str]:
    if not value:
        return set()
    return {email.lower() for _, email in getaddresses(value if isinstance(value, list) else [value]) if email}


def _text(item: dict[str, Any]) -> str:
    return " ".join(str(item.get(key, "")) for key in ("subject", "normalized_text", "text", "snippet")).strip()


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).replace("đ", "d").replace("Đ", "d")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold()


def _active_text(item: dict[str, Any]) -> str:
    content = _text(item)
    content = QUOTE_SPLIT_RE.split(content, maxsplit=1)[0]
    content = SIGNATURE_SPLIT_RE.split(content, maxsplit=1)[0]
    return content.strip()


@cache
def _folded_terms(terms: tuple[str, ...]) -> tuple[str, ...]:
    """Chuẩn hoá TỪ KHOÁ bằng đúng `_fold()` đang dùng cho thân mail.

    Bắt buộc với chữ không phải Latin: NFKD phân rã âm tiết Hangul thành Jamo,
    và tách dấu đục của Katakana ("ド" -> "ト" + dấu) mà `_fold` lại bỏ dấu
    kết hợp. Từ khoá viết ở dạng tổ hợp sẵn — cách người ta gõ bình thường —
    sẽ không bao giờ khớp nếu không fold cùng một kiểu. Với từ khoá Latin đã
    bỏ dấu sẵn thì đây là phép đồng nhất.
    """
    return tuple(_fold(term) for term in terms)


def _has_any(folded: str, terms: tuple[str, ...]) -> bool:
    return any(term in folded for term in _folded_terms(terms))


def _looks_obfuscated_or_stripped(folded: str) -> bool:
    """Detect anonymized/hand-stripped corpora where keywords are unreliable."""
    tokens = re.findall(r"[a-z]{3,}", folded)
    if len(tokens) < 25:
        return False

    common_hits = sum(1 for term in COMMON_LANGUAGE_FOLDED_TERMS if re.search(rf"\b{re.escape(term)}\b", folded))
    vowel_sparse = sum(1 for token in tokens if len(token) >= 4 and sum(ch in "aeiouy" for ch in token) <= 1)
    long_randomish = sum(1 for token in tokens if len(token) >= 7 and sum(ch in "aeiouy" for ch in token) <= 2)
    randomish_ratio = (vowel_sparse + long_randomish) / len(tokens)

    return common_hits <= 2 and randomish_ratio >= 0.28


def _sender_score(sender: str, config: FilterConfig) -> int:
    domain = sender.rsplit("@", 1)[-1] if "@" in sender else ""
    return 30 if sender in config.trusted_senders or domain in config.trusted_sender_domains else 0


def classify_email(item: dict[str, Any], config: FilterConfig | None = None) -> Classification:
    config = config or FilterConfig()
    content = _active_text(item)
    folded = _fold(content)
    sender = str(item.get("author_id") or item.get("from") or "").lower()
    sender_domain = sender.rsplit("@", 1)[-1] if "@" in sender else ""
    recipients = _addresses(item.get("to"))
    cc = _addresses(item.get("cc"))
    # Địa chỉ mailbox THẬT SỰ đang đồng bộ (gmail.py/outlook.py normalize()
    # stamp sẵn) — KHÔNG dùng config.user_email (identity đăng nhập app) để so
    # khớp to/cc: user login app bằng 1 email nhưng connect Gmail/Outlook
    # account khác là chuyện bình thường, 2 địa chỉ không nhất thiết trùng
    # nhau. Bug thật đã xảy ra: dùng nhầm config.user_email khiến TOÀN BỘ mail
    # thật bị coi là "không gửi cho mình" dù đúng là mailbox đang sync.
    mailbox_email = str(item.get("mailbox_email") or config.user_email or "").lower() or None
    # Chỉ áp dụng khi provider thật sự cung cấp ĐỊA CHỈ người nhận
    # (Gmail/Outlook). Hai trường hợp không được kết luận "không gửi cho
    # mình", vì cả hai đều là thiếu bằng chứng chứ không phải bằng chứng
    # ngược lại:
    #  - Slack/Jira normalize luôn trả to=[] cc=[] (không có khái niệm người
    #    nhận).
    #  - Mail gửi tới alias/nhóm hiện ra dưới dạng TÊN chứ không phải địa chỉ
    #    ("Engineering All", "Team Sản phẩm"). Người dùng vẫn nhận mail vì
    #    nằm trong nhóm đó, nên loại thẳng là cắt đúng phần mail công việc
    #    thật (golden dataset: 18/57 mail KEEP bị rơi hết vào đây).
    resolved_recipients = {address for address in recipients | cc if "@" in address}
    addressed_to_user = (
        not mailbox_email or not resolved_recipients or mailbox_email in resolved_recipients
    )
    not_addressed = not addressed_to_user
    has_action_signal = ACTION_RE.search(content) is not None or _has_any(folded, ACTION_FOLDED_TERMS)
    has_deadline_signal = DEADLINE_RE.search(content) is not None or _has_any(folded, DEADLINE_FOLDED_TERMS)
    has_program_signal = PROGRAM_RE.search(content) is not None or _has_any(folded, PROGRAM_FOLDED_TERMS)
    # has_marketing_boilerplate (gmail.py normalize()) chấm unsubscribe/
    # preferences-link TRƯỚC khi text hiển thị bị làm sạch — text ở đây có thể
    # đã mất chữ "unsubscribe" nên NEWSLETTER_RE/FOLDED_TERMS một mình không
    # đủ bắt (bug thật: mail marketing lọt vì đúng phần bị cắt lại là phần
    # mang tín hiệu).
    has_newsletter_signal = (
        NEWSLETTER_RE.search(content) is not None
        or _has_any(folded, NEWSLETTER_FOLDED_TERMS)
        or bool(item.get("has_marketing_boilerplate"))
    )
    # Sender bot/hệ thống (no-reply, notifications@github.com...) — tách khỏi
    # automated_penalty (chỉ trừ điểm) để chặn CỨNG như negative_state. Bug
    # thật: comment bot GitHub/CI có chữ "review"/"please" (boilerplate PR
    # template) đủ để has_action_signal=True, mà has_action một mình lại đủ
    # override automated_penalty ở noise_only bên dưới — sender bot vẫn lọt.
    #
    # Chặn cứng chỉ được xét TRÊN ĐỊA CHỈ NGƯỜI GỬI. Quét cả thân mail biến
    # nó thành lưỡi dao cùn: gần như mọi thư hệ thống đều có chữ
    # "notification" ở chân trang, kể cả thư mang việc thật. Bug thật: mail
    # Jira "HoàiAn Thái assigned this work item to you" gửi từ
    # jira@<site>.atlassian.net bị chấm 0 điểm và drop thẳng, chỉ vì chân
    # trang có chữ "notification" — việc giao đích danh cho người dùng biến
    # mất khỏi hộp việc.
    is_automated_sender = bool(AUTOMATED_RE.search(sender))
    # Trừ điểm (mềm) thì vẫn xét cả thân mail như trước — giọng văn tự động
    # là tín hiệu thật để hạ ưu tiên, chỉ không đủ chắc để xoá sổ.
    has_automated_tone = is_automated_sender or bool(AUTOMATED_RE.search(content))
    negative_state_raw = any(
        (
            has_newsletter_signal and sender_domain not in config.trusted_sender_domains,
            is_automated_sender and sender_domain not in config.trusted_sender_domains,
            _has_any(folded, SOCIAL_NOTIFICATION_FOLDED_TERMS),
            _has_any(folded, NO_ACTION_FOLDED_TERMS),
            _has_any(folded, COMPLETED_FOLDED_TERMS),
            _has_any(folded, SECURITY_SCAM_FOLDED_TERMS),
            _has_any(folded, TRANSACTIONAL_NOTIFICATION_FOLDED_TERMS),
            _has_any(folded, OPTIONAL_OR_BROADCAST_FOLDED_TERMS) and not has_action_signal,
        )
    )
    negative_override = _has_any(folded, NEGATIVE_OVERRIDE_FOLDED_TERMS)
    negative_state = negative_state_raw and not negative_override
    parts = {
        "sender": _sender_score(sender, config),
        "recipient": 20 if mailbox_email and mailbox_email in recipients else 0,
        "cc_penalty": -10 if mailbox_email and mailbox_email in cc and mailbox_email not in recipients else 0,
        "action": 25 if has_action_signal else 0,
        "deadline": 25 if has_deadline_signal else 0,
        "urgency": 15 if URGENCY_RE.search(content) else 0,
        "unread": 10 if item.get("is_unread") else 0,
        "program_relevance": 20
        if has_program_signal or sender_domain in config.program_domains
        else 0,
        "newsletter_penalty": -40 if has_newsletter_signal else 0,
        "automated_penalty": -30 if has_automated_tone else 0,
        "thread_penalty": -20 if item.get("thread_replied_without_change") else 0,
        "thread_change": 20 if item.get("thread_has_new_change") else 0,
        "negative_state_penalty": -65 if negative_state else 0,
        # Mail thật sự có header to/cc nhưng user không nằm trong đó — không
        # phải gửi cho user, chỉ là nội dung nhắc tới ai đó khác. Action/
        # deadline/trusted-sender không đủ để override việc này (khác với
        # negative_state, đây không phải noise mà là "không phải việc của tôi").
        "not_addressed_penalty": -65 if not_addressed else 0,
    }
    score = max(0, min(100, sum(parts.values())))
    has_deadline = bool(parts["deadline"])
    has_action = bool(parts["action"])
    direct = parts["recipient"] > 0
    trusted = parts["sender"] > 0
    relevant = parts["program_relevance"] > 0
    newsletter_noise = parts["newsletter_penalty"] < 0
    automated_noise = parts["automated_penalty"] < 0
    transactional_noise = bool(TRANSACTIONAL_RE.search(content)) and not any(
        (has_action, has_deadline, trusted, relevant)
    )
    stale_thread = bool(item.get("thread_replied_without_change") and not item.get("thread_has_new_change"))
    # trusted một mình không còn đủ để dập noise — sender tin cậy gửi newsletter/
    # thông báo tự động broadcast (không gửi riêng cho user) vẫn phải bị loại;
    # chỉ miễn noise khi trusted VÀ thật sự gửi cho user.
    noise_only = (newsletter_noise or automated_noise or transactional_noise) and not any(
        (has_action, trusted and addressed_to_user, item.get("thread_has_new_change"), item.get("conflict_with_other_source"))
    )
    weak_direct_only = direct and not any((has_action, has_deadline, trusted, relevant, item.get("thread_has_new_change")))
    must_not_miss = any(
        (
            has_deadline,
            has_action,
            trusted,
            item.get("thread_has_new_change"),
            item.get("conflict_with_other_source"),
            item.get("is_unread") and sender_domain in config.program_domains,
            item.get("is_unread") and score >= 35 and relevant,
        )
    ) and not any((noise_only, stale_thread, negative_state, weak_direct_only, not_addressed))
    reasons = [
        name
        for name, value in (
            ("deadline_signal", has_deadline),
            ("action_signal", has_action),
            ("direct_recipient", direct),
            ("trusted_sender", trusted),
            ("program_relevance", relevant),
            ("thread_changed", bool(item.get("thread_has_new_change"))),
            ("stale_thread", stale_thread),
            ("negative_state", negative_state),
            ("weak_direct_only", weak_direct_only),
            ("not_addressed", not_addressed),
        )
        if value
    ]
    importance = "critical" if score >= 80 else "important" if score >= 60 else "relevant" if score >= 35 else "ignore"
    section = (
        "changes"
        if item.get("thread_has_new_change") or item.get("conflict_with_other_source")
        else "needs_action"
        if must_not_miss and (has_action or has_deadline or direct)
        else "reference"
        if score >= 35 or must_not_miss
        else "ignore"
    )
    return Classification(score, importance, section, bool(must_not_miss), tuple(reasons), parts)


def triage_email(item: dict[str, Any], config: FilterConfig | None = None) -> TriageDecision:
    """Stage [1]/[2] mail triage before any expensive LLM judge.

    The binary filter only keeps deterministic candidates. This triage layer is
    deliberately more expressive: low-signal but not-obviously-noisy mail can be
    routed to a later LLM judge instead of being auto-dropped.
    """
    config = config or FilterConfig()
    classification = classify_email(item, config)
    reasons = set(classification.reasons)
    score = classification.importance_score

    if {"negative_state", "stale_thread", "not_addressed"}.intersection(reasons):
        return TriageDecision("drop", 0.95, "rule", "obvious_drop", classification)

    if _looks_obfuscated_or_stripped(_fold(_active_text(item))):
        return TriageDecision("llm_judge", 0.50, "cheap_classifier", "uncertain_stripped_text", classification)

    if classification.must_not_miss:
        probability = 0.90 if score >= 60 else 0.78
        return TriageDecision("keep", probability, "rule", "must_not_miss", classification)

    if score >= max(config.min_relevant_score, 50):
        return TriageDecision("keep", min(0.88, 0.55 + score / 200), "cheap_classifier", "high_keep", classification)

    if "weak_direct_only" in reasons or 15 <= score < config.min_relevant_score:
        return TriageDecision("llm_judge", 0.50, "cheap_classifier", "uncertain", classification)

    if any(item.get(key) for key in ("is_unread", "thread_has_new_change", "conflict_with_other_source")):
        return TriageDecision("llm_judge", 0.45, "cheap_classifier", "uncertain_low_signal", classification)

    return TriageDecision("drop", 0.90, "cheap_classifier", "high_drop_low_signal", classification)


def _dedupe_and_group(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda x: x.get("sent_at") or datetime.min.replace(tzinfo=UTC), reverse=True):
        fingerprint = hashlib.sha256(
            (str(item.get("thread_id") or item.get("id")) + "\n" + str(item.get("text", ""))).encode()
        ).hexdigest()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(item)
    counts: dict[str, int] = {}
    for item in unique:
        key = str(item.get("thread_id") or item.get("id"))
        counts[key] = counts.get(key, 0) + 1
    for item in unique:
        key = str(item.get("thread_id") or item.get("id"))
        item["thread_size"] = counts[key]
    return unique


# Nguồn tự có rule engine ở bước extract (jira_rules.py / slack_rules.py).
_RULE_ENGINE_PROVIDERS = frozenset({"jira", "slack"})


def _rule_engine_candidate(item: dict[str, Any]) -> dict[str, Any]:
    """Cho item đi tiếp với phân loại TRUNG TÍNH, không phải điểm kiểu email.

    `importance` vẫn phải có mặt: `attachment_extract_node` dùng nó làm
    cost-gate, thiếu thì file đính kèm trên issue không bao giờ được trích.
    Đặt "relevant" — đủ để qua cổng khi có file thuộc allow-list, không tự nhận
    là việc gấp khi chưa engine nào chấm.
    """
    enriched = dict(item)
    enriched.update(
        {
            "importance_score": 0,
            "importance": "relevant",
            "brief_section": "reference",
            "must_not_miss": False,
            "classification_reasons": ["rule_engine_provider"],
            "component_scores": {},
            "triage_decision": "keep",
            "triage_probability": 1.0,
            "triage_stage": "rule_engine_provider",
            "triage_reason": "delegated_to_source_rules",
            "classifier_source": "rule_engine_provider",
            "filter_route": "source_rule_engine",
        }
    )
    return enriched


def filter_and_classify(
    items: list[dict[str, Any]],
    config: FilterConfig | None = None,
    *,
    now: datetime | None = None,
    model_classifier: Any | None = None,
    model_settings: Settings | None = None,
) -> dict[str, Any]:
    config = config or FilterConfig()
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=config.lookback_days)
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in _dedupe_and_group(list(items)):
        if not has_valid_deep_link(item):
            rejected.append({"id": str(item.get("id")), "reason": "invalid_source_url"})
            continue
        if isinstance(item.get("sent_at"), datetime) and item["sent_at"] < cutoff:
            rejected.append({"id": str(item.get("id")), "reason": "outside_lookback"})
            continue
        labels = set(item.get("label_ids") or item.get("labels") or [])
        if config.approved_labels and labels and not labels.intersection(config.approved_labels):
            rejected.append({"id": str(item.get("id")), "reason": "label_not_approved"})
            continue

        # Nguồn có RULE ENGINE RIÊNG không đi qua bộ chấm điểm kiểu email.
        #
        # `classify_email` được thiết kế cho thư: nó tìm "vui lòng", "deadline",
        # người gửi/người nhận, giọng newsletter. Issue Jira thì tiêu đề chỉ là
        # tên việc ("fix các tính năng ui lỗi vặt"), không có ngữ điệu nào trong
        # số đó, nên rơi thẳng vào `high_drop_low_signal`. Đo trên bảng thật:
        # 31 issue giao cho người dùng thì 27 bị giết ở đây, TRƯỚC khi
        # `jira_rules` — engine có assignee/priority/due-bucket — kịp nhìn thấy.
        #
        # `verify_node` đã miễn jira/slack từ lâu vì cùng lý do; chỗ này bị bỏ
        # sót. Cho đi thẳng, và để chính rule engine của nguồn đó quyết định.
        if item.get("provider") in _RULE_ENGINE_PROVIDERS:
            candidates.append(_rule_engine_candidate(item))
            continue

        triage = triage_email(item, config)
        if triage.decision == "llm_judge":
            settings = model_settings or get_settings()
            prediction = (model_classifier or classify_mail)(item, settings)
            mapped = apply_prediction(prediction, settings=settings)
            if mapped is not None:
                decision, probability, reason = mapped
                triage = TriageDecision(decision, probability, "hf_xlmr", reason, triage.classification)
        classification = triage.classification
        enriched = dict(item)
        enriched.update(
            {
                "importance_score": classification.importance_score,
                "importance": classification.importance,
                "brief_section": classification.brief_section,
                "must_not_miss": classification.must_not_miss,
                "classification_reasons": list(classification.reasons),
                "component_scores": classification.component_scores,
                "triage_decision": triage.decision,
                "triage_probability": triage.probability,
                "triage_stage": triage.stage,
                "triage_reason": triage.reason,
                "classifier_source": triage.stage,
            }
        )
        blocking_reasons = {"stale_thread", "negative_state", "weak_direct_only", "not_addressed"}
        if triage.decision in {"keep", "llm_judge"}:
            # ``llm_judge`` is an escalation route, not a rejection.  The
            # existing Gmail extraction LLM will make the semantic decision
            # later; dropping here would make the LLM path unreachable.
            enriched["filter_route"] = (
                "deterministic_keep"
                if triage.decision == "keep" and triage.stage != "hf_xlmr"
                else "hf_classifier_keep"
                if triage.decision == "keep"
                else "llm_extraction"
            )
            candidates.append(enriched)
        else:
            reason = next((name for name in classification.reasons if name in blocking_reasons), None)
            if reason is None:
                reason = "low_importance"
            rejected.append(
                {
                    "id": str(item.get("id")),
                    # provider + source_id đi kèm để persist_node tra ngược ra
                    # đúng hàng Message — external_id một mình không duy nhất
                    # giữa các nguồn.
                    "provider": item.get("provider"),
                    "source_id": item.get("source_id"),
                    "reason": reason,
                    "triage_decision": triage.decision,
                    "triage_probability": triage.probability,
                    "triage_stage": triage.stage,
                    "triage_reason": triage.reason,
                }
            )
    return {
        "items": candidates,
        "rejected": rejected,
        "candidate_count": len(candidates),
        "rejected_count": len(rejected),
    }
