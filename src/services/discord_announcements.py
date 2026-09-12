"""Lọc thông báo chương trình ra khỏi kho Discord đã cào.

Trả lời một câu hỏi khác hẳn `retrieval.py`: ở đó là "đoạn thảo luận nào liên
quan tới câu hỏi", ở đây là "chương trình đã phát ra thông báo gì". Học viên mức
A cần cái thứ hai để không bỏ lỡ hạn nộp hay đổi lịch, và xếp hạng theo độ liên
quan không phục vụ việc đó — thông báo phải xếp theo thời gian và phải lấy được
cả khi người dùng không biết mà hỏi đúng từ khóa.

Luật nhận diện là luật tường minh, không gọi LLM: mỗi kết quả kèm `reasons` để
người đọc kiểm lại được vì sao một tin bị coi là thông báo. Đây là bằng chứng,
không phải phán đoán — BR-04 cấm suy thẩm quyền từ hoạt động quan sát được, nên
role của người gửi chỉ là một tín hiệu cộng điểm, không phải điều kiện đủ.

Đọc thẳng `source_items` chứ không đọc `chunks`: chunker cố tình bỏ tin của bot
và tin quá ngắn, mà thông báo thì hay do bot đăng và hay ngắn.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.models.evidence import SourceItem, SourceScope

# Kênh thể loại "Announcement" của Discord. Kênh này sinh ra để phát thông báo
# nên mọi tin trong đó mặc nhiên là thông báo.
ANNOUNCEMENT_CHANNEL_KIND = 5

# Tên kênh mang nghĩa thông báo. So khớp trên chuỗi đã bỏ dấu nên "thông báo",
# "thong-bao" và "THONG BAO" đều khớp cùng một mục.
CHANNEL_NAME_HINTS = (
    "thong bao",
    "thongbao",
    "announcement",
    "announce",
    "notice",
    "bang tin",
    "thong tin chung",
)

# Vai trò của người phát thông báo. Chỉ cộng điểm, không tự nó đủ để kết luận.
STAFF_ROLE_HINTS = (
    "btc",
    "ban to chuc",
    "mentor",
    "admin",
    "staff",
    "moderator",
    "organizer",
    "giang vien",
    "tro giang",
    "dieu phoi",
    "quan tri",
)

# Nhắc cả kênh. Vì `export_dce.py` luôn chạy `--markdown false`, chuỗi này còn
# nguyên trong content chứ không bị viết lại thành tên người.
BROADCAST_TOKENS = ("@everyone", "@here")

# Từ khóa nội dung thường thấy trong thông báo của chương trình.
CONTENT_HINTS = (
    "thong bao",
    "luu y",
    "nhac nho",
    "nhac lai",
    "deadline",
    "han nop",
    "han chot",
    "het han",
    "nop bai",
    "submit",
    "lich hoc",
    "doi lich",
    "nghi hoc",
    "diem danh",
    "bat buoc",
    "yeu cau",
    "link zoom",
    "link meet",
    "gate",
    "demo day",
)

# Điểm của từng tín hiệu, đặt sao cho một tín hiệu mạnh tự nó đủ vượt ngưỡng còn
# tín hiệu yếu thì phải đủ ba cái mới đủ. Người điều phối nói "deadline" giữa lúc
# chat (điều hành 2 + từ khóa 2 = 4) không được thành thông báo chỉ vì họ là
# mentor; thêm file đính kèm nữa (=5) thì mới coi là phát ra một thứ chính thức.
SCORE_ANNOUNCEMENT_CHANNEL = 5
SCORE_BROADCAST = 5
SCORE_STAFF_AUTHOR = 2
SCORE_CONTENT_HINT = 2
SCORE_ATTACHMENT = 1

# Ngưỡng để một tin được gọi là thông báo.
MIN_SCORE = 5

# Tin quá ngắn mà không có tín hiệu mạnh thì bỏ: "ok mọi người nhớ nhé" không
# mang thông tin nào cho học viên đọc lại sau.
MIN_CHARS = 25

# Số ký tự thật tối thiểu, tính sau khi bỏ mention và @everyone. Dưới mức này thì
# tin không còn chữ nào để đọc — gặp thật trong kênh thông báo của ban tổ chức:
# bot đăng embed nên `content` rỗng hoặc chỉ có `<@744497566581915730>`, lọt vào
# danh sách thì agent đưa cho học viên một dòng trống. Có file đính kèm thì vẫn
# giữ, vì lúc đó ít nhất còn cái link để mở.
MIN_SUBSTANCE_CHARS = 12

# Tin hệ thống (thành viên tham gia, ghim tin) không phải thông báo chương trình.
KEPT_ITEM_TYPES = (0, 19, None)

# Số ứng viên kéo về trước khi chấm điểm ở Python. Rộng hơn `limit` nhiều lần vì
# tầng SQL chỉ lọc thô; hẹp đủ để không kéo cả bảng về.
CANDIDATE_MULTIPLIER = 8
CANDIDATE_CAP = 400

# Mẫu LIKE cho tầng lọc thô. Không thay được cho việc chấm điểm — nó chỉ cần thu
# hẹp đủ để phần chấm điểm chạy trên tập nhỏ, và luôn phải rộng hơn luật thật.
# Giữ cả bản có dấu lẫn bản không dấu vì ILIKE của sqlite chỉ bỏ qua hoa thường
# với ASCII; tin viết hoa toàn phần có dấu chỉ lọt qua tầng này trên Postgres,
# còn tin trong kênh thông báo thì đã vào bằng nhánh scope nên không phụ thuộc.
_PREFILTER_PATTERNS = (
    "%@everyone%",
    "%@here%",
    "%thông báo%",
    "%thong bao%",
    "%deadline%",
    "%hạn nộp%",
    "%han nop%",
    "%hạn chót%",
    "%nộp bài%",
    "%lịch học%",
    "%đổi lịch%",
)


@dataclass(frozen=True)
class DiscordAnnouncement:
    """1 thông báo đã nhận diện, kèm lý do để người đọc kiểm lại."""

    message_id: str
    channel: str
    author: str
    content: str
    occurred_at: datetime
    deep_link: str | None
    score: int
    reasons: tuple[str, ...]


def _fold(text: str | None) -> str:
    """Hạ chữ thường và bỏ dấu tiếng Việt để so khớp từ khóa cho ổn định.

    Cào về là chữ người gõ tay: "Thông báo", "THONG BAO", "thong-bao" là cùng
    một thứ. Tách dấu bằng NFD rồi bỏ ký tự dấu, sau đó gom mọi ký tự không phải
    chữ số về khoảng trắng để "thong-bao" khớp được với "thong bao".
    """
    if not text:
        return ""
    stripped = "".join(ch for ch in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(ch))
    # đ/Đ không tách được bằng NFD nên phải đổi tay.
    stripped = stripped.replace("đ", "d")
    return re.sub(r"[^0-9a-z@]+", " ", stripped).strip()


def _substance(content: str) -> str:
    """Phần chữ thật của tin, sau khi bỏ mention và lời nhắc cả kênh.

    `<@123>`, `<@&456>`, `<#789>` và `@everyone` còn nguyên trong content vì
    pipeline cào bằng `--markdown false`. Chúng là tín hiệu để chấm điểm chứ
    không phải nội dung người đọc cần, nên đếm độ dài thì phải bỏ ra.
    """
    return re.sub(r"<[@#][!&]?\d+>|@everyone|@here", "", content or "").strip()


def is_announcement_scope(scope: SourceScope) -> bool:
    """Kênh này có phải nơi phát thông báo không, xét theo thể loại và tên."""
    if scope.kind == ANNOUNCEMENT_CHANNEL_KIND:
        return True
    name = _fold(scope.name)
    return any(hint in name for hint in CHANNEL_NAME_HINTS)


def classify_announcement(
    *,
    content: str,
    author_roles: list | None,
    attachment_count: int = 0,
    in_announcement_channel: bool = False,
) -> tuple[int, tuple[str, ...]]:
    """Chấm điểm một tin và nêu lý do; điểm dưới `MIN_SCORE` không phải thông báo.

    Cơ chế: cộng điểm theo từng tín hiệu độc lập — đăng ở kênh thông báo, nhắc cả
    kênh, người gửi mang vai trò điều hành, nội dung chứa từ khóa thông báo, có
    file đính kèm. Một tín hiệu mạnh (kênh thông báo hoặc @everyone) là đủ vượt
    ngưỡng; các tín hiệu yếu phải đi cùng nhau. Trả về cả điểm lẫn lý do để tầng
    trên hiển thị được vì sao tin này nằm trong danh sách.
    """
    folded = _fold(content)
    substance = _substance(content)

    # Không còn chữ nào để đọc thì không đưa vào danh sách, dù nó nằm ở kênh
    # thông báo. Trừ khi có file đính kèm — lúc đó vẫn còn cái link để mở.
    if len(substance) < MIN_SUBSTANCE_CHARS and not attachment_count:
        return 0, ()

    score = 0
    reasons: list[str] = []

    if in_announcement_channel:
        score += SCORE_ANNOUNCEMENT_CHANNEL
        reasons.append("đăng ở kênh thông báo")

    if any(token in folded for token in BROADCAST_TOKENS):
        score += SCORE_BROADCAST
        reasons.append("nhắc cả kênh (@everyone/@here)")

    roles = " ".join(_fold(str(role)) for role in (author_roles or []))
    if roles and any(hint in roles for hint in STAFF_ROLE_HINTS):
        score += SCORE_STAFF_AUTHOR
        reasons.append("người gửi mang vai trò điều hành")

    hit = [hint for hint in CONTENT_HINTS if hint in folded]
    if hit:
        score += SCORE_CONTENT_HINT
        reasons.append(f"nội dung có từ khóa: {', '.join(hit[:3])}")

    if attachment_count:
        score += SCORE_ATTACHMENT
        reasons.append("có file đính kèm")

    # Tin ngắn chỉ được giữ khi có tín hiệu mạnh về nơi đăng hoặc cách phát.
    if len(substance) < MIN_CHARS and not (
        in_announcement_channel or any(token in folded for token in BROADCAST_TOKENS)
    ):
        return 0, ()

    return score, tuple(reasons)


def list_announcements(
    engine: Engine,
    *,
    scope_ids: list[int] | None,
    query: str = "",
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 10,
) -> list[DiscordAnnouncement]:
    """Liệt kê thông báo mới nhất trong những kênh người dùng được cấp quyền.

    Cơ chế ba bước. Một, hỏi SQL lấy tập ứng viên: đúng phạm vi được cấp, đúng
    cửa sổ thời gian, và hoặc nằm trong kênh thông báo hoặc chứa từ khóa phát
    thông báo. Hai, chấm điểm từng ứng viên bằng `classify_announcement` ở Python
    vì role người gửi nằm trong cột JSON, lọc bằng SQL không di động giữa
    Postgres và sqlite. Ba, xếp theo thời gian giảm dần — thông báo cũ không có
    giá trị hơn thông báo mới dù khớp từ khóa nhiều hơn.

    `scope_ids` rỗng nghĩa là không được đọc gì và trả về danh sách rỗng; `None`
    nghĩa là không giới hạn và chỉ dùng cho công cụ dòng lệnh, giống `retrieve`.
    """
    if scope_ids is not None and not scope_ids:
        return []

    filters = [SourceItem.provider == "discord", SourceItem.item_type.in_(KEPT_ITEM_TYPES)]
    if scope_ids is not None:
        filters.append(SourceItem.scope_id.in_(scope_ids))
    if since is not None:
        filters.append(SourceItem.source_updated_at >= since)
    if until is not None:
        filters.append(SourceItem.source_updated_at <= until)

    with Session(engine) as db:
        scope_rows = db.scalars(
            select(SourceScope).where(
                SourceScope.provider == "discord",
                *([SourceScope.id.in_(scope_ids)] if scope_ids is not None else []),
            )
        ).all()
        announcement_scope_ids = [s.id for s in scope_rows if is_announcement_scope(s)]
        scope_names = {s.id: s.name or s.external_id for s in scope_rows}

        coarse = [SourceItem.content.ilike(pattern) for pattern in _PREFILTER_PATTERNS]
        if announcement_scope_ids:
            coarse.append(SourceItem.scope_id.in_(announcement_scope_ids))
        filters.append(or_(*coarse))

        candidate_limit = min(max(limit, 1) * CANDIDATE_MULTIPLIER, CANDIDATE_CAP)
        items = db.scalars(
            select(SourceItem)
            .where(*filters)
            .order_by(SourceItem.source_updated_at.desc(), SourceItem.id.desc())
            .limit(candidate_limit)
        ).all()

        terms = [t for t in re.split(r"\s+", _fold(query)) if len(t) >= 2]
        found: list[DiscordAnnouncement] = []
        for item in items:
            score, reasons = classify_announcement(
                content=item.content or "",
                author_roles=item.author_roles,
                attachment_count=item.attachment_count or 0,
                in_announcement_channel=item.scope_id in announcement_scope_ids,
            )
            if score < MIN_SCORE:
                continue
            if terms:
                haystack = _fold(item.content)
                if not any(term in haystack for term in terms):
                    continue
            found.append(
                DiscordAnnouncement(
                    message_id=item.external_id,
                    channel=scope_names.get(item.scope_id, str(item.scope_id)),
                    author=item.author_name or "không rõ",
                    content=item.content or "",
                    occurred_at=item.source_updated_at,
                    deep_link=item.deep_link,
                    score=score,
                    reasons=reasons,
                )
            )
            if len(found) >= max(1, min(limit, 50)):
                break
    return found
