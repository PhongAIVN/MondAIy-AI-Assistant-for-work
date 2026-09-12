import ast
import logging
import operator
from contextvars import ContextVar
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Phạm vi được phép đọc, do tầng gọi đặt chứ không phải LLM sinh ra.
# retrieval.py ghi rõ bộ lọc quyền không được để model quyết, và CLAUDE.md cảnh
# báo retrieval sai scope là rò dữ liệu giữa người dùng. Vì vậy tham số này nằm
# ngoài chữ ký công cụ, model không có cách nào chạm tới.
_scope_ids: ContextVar[list[int] | None] = ContextVar("scope_ids", default=None)
_scope_da_dat: ContextVar[bool] = ContextVar("scope_da_dat", default=False)
_discord_author_external_id: ContextVar[str | None] = ContextVar("discord_author_external_id", default=None)


def _display_time(moment: datetime) -> str:
    from src.config import get_settings

    aware = moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
    return aware.astimezone(ZoneInfo(get_settings().app_timezone)).strftime("%d/%m/%Y %H:%M")


def set_search_scope(
    scope_ids: list[int] | None,
    author_external_id: str | None = None,
) -> None:
    """Đặt phạm vi truy hồi cho lượt chạy hiện tại.

    Truyền None nghĩa là không giới hạn. Chỉ dùng cho công cụ dòng lệnh và demo
    nội bộ, tuyệt đối không dùng cho đường có nhiều người dùng.
    """
    _scope_ids.set(scope_ids)
    _discord_author_external_id.set(author_external_id)
    _scope_da_dat.set(True)


def reset_search_scope() -> None:
    """Xoá phạm vi đã đặt, đưa công cụ về trạng thái từ chối tìm."""
    _scope_ids.set(None)
    _discord_author_external_id.set(None)
    _scope_da_dat.set(False)


# Safe operator mapping for calculator
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _parse_window(since: str, until: str) -> tuple[dict, str | None]:
    from src.agents.tools.time_tool import parse_timestamp

    window = {}
    for name, value in (("since", since), ("until", until)):
        if not (value or "").strip():
            continue
        parsed = parse_timestamp(value)
        if parsed is None:
            return {}, (
                f"Không hiểu được mốc thời gian {value!r} ở tham số {name}, "
                "nên chưa tìm. Cần dạng ngày/tháng/năm hoặc chuỗi ISO."
            )
        window[name] = parsed.moment
    if "since" in window and "until" in window and window["since"] > window["until"]:
        return {}, "Khoảng thời gian ngược: since muộn hơn until, nên chưa tìm."
    return window, None


def _scope_error(*, require_identity: bool) -> str | None:
    if not _scope_da_dat.get():
        return (
            "Chưa xác định được phạm vi dữ liệu người dùng này được phép đọc, "
            "nên chưa tìm. Tầng gọi phải đặt phạm vi trước."
        )
    if require_identity and not _discord_author_external_id.get():
        return "Tài khoản này chưa kết nối danh tính Discord nên chưa thể tìm tin nhắn của chính bạn."
    if require_identity and not _scope_ids.get():
        return (
            "Discord đã kết nối nhưng danh tính chưa khớp dữ liệu chương trình, "
            "nên chưa có tin nhắn cá nhân nào được phép đọc."
        )
    return None


@tool
def discord_search_program(query: str, since: str = "", until: str = "") -> str:
    """Tìm nội dung chương trình trong kho Discord đã được thu thập.

    Kho vector hiện chỉ chứa Discord. Đây không phải kết nối Discord trực tiếp
    của người dùng và không đại diện cho Gmail, Calendar, Jira hay nguồn khác.

    Muốn giới hạn theo thời gian thì truyền since/until. Không biết hôm nay là
    ngày nào thì gọi current_datetime trước rồi tự tính mốc, đừng đoán.

    Args:
        query: Câu hỏi cần tìm
        since: Chỉ lấy nội dung từ mốc này trở đi, ví dụ "03/08/2026" (bỏ trống là không giới hạn)
        until: Chỉ lấy nội dung tới mốc này, ví dụ "09/08/2026" (bỏ trống là không giới hạn)

    Returns:
        Các đoạn thảo luận liên quan nhất trong những kênh chương trình được cấp quyền
    """
    # Chưa ai đặt phạm vi thì dừng lại. Chạy tiếp với phạm vi rỗng nghĩa là đọc
    # toàn bộ kho của mọi người, hỏng thì hỏng im lặng nên phải chặn từ đầu.
    scope_error = _scope_error(require_identity=False)
    if scope_error:
        return scope_error

    from src.db import engine
    from src.services.retrieval import Filters, retrieve

    # Mốc không hiểu được thì dừng, không lặng lẽ bỏ bộ lọc. Bỏ đi nghĩa là trả
    # về cả kho rồi để model tưởng đó là kết quả của đúng tuần nó hỏi.
    window, window_error = _parse_window(since, until)
    if window_error:
        return window_error

    try:
        ket_qua = retrieve(
            engine,
            query,
            Filters(scope_ids=_scope_ids.get(), **window),
            k=5,
        )
    except Exception as exc:
        logger.warning("Truy hồi hỏng cho câu hỏi %r: %s", query[:80], exc)
        return "Không tìm được trong dữ liệu Discord lúc này. Hệ thống đã ghi nhận lỗi để xử lý."

    if not ket_qua:
        if window:
            return "Không tìm thấy nội dung nào khớp trong khoảng thời gian đó. Ngoài khoảng này có thể vẫn có."
        return "Không tìm thấy tin nhắn Discord nào khớp."

    dong = []
    for r in ket_qua:
        noi_dung = " ".join(r.text.split())[:400]
        dong.append(
            f"[Discord {r.channel} · {_display_time(r.occurred_at)}] {noi_dung}"
            + (f"\n  nguồn: {r.deep_link}" if r.deep_link else "")
        )
    return "\n\n".join(dong)


@tool
def discord_list_announcements(query: str = "", since: str = "", until: str = "", limit: int = 8) -> str:
    """Liệt kê thông báo chương trình trên Discord, mới nhất trước.

    Dùng khi người dùng hỏi có gì mới, chương trình vừa thông báo gì, có đổi lịch
    hay hạn nộp nào không — những câu mà tìm theo độ liên quan sẽ trả về thảo
    luận vụn thay vì thông báo chính thức. Chỉ đọc trong những kênh tài khoản này
    được cấp quyền; học viên chưa khớp danh tính chương trình sẽ không có kênh nào.

    Args:
        query: Lọc thêm theo từ khóa (bỏ trống là lấy toàn bộ thông báo gần nhất)
        since: Chỉ lấy từ mốc này trở đi, ví dụ "03/08/2026"
        until: Chỉ lấy tới mốc này, ví dụ "09/08/2026"
        limit: Số thông báo tối đa, mặc định 8

    Returns:
        Danh sách thông báo kèm kênh, người gửi, thời điểm, link gốc và lý do được coi là thông báo
    """
    scope_error = _scope_error(require_identity=False)
    if scope_error:
        return scope_error
    # Phạm vi rỗng khác với không có thông báo nào: đây là học viên chưa khớp
    # danh tính chương trình (mức B/C), nói đúng lý do thì họ còn biết đường sửa.
    if _scope_ids.get() == []:
        return (
            "Tài khoản này chưa được cấp kênh chương trình nào nên chưa đọc được thông báo. "
            "Kết nối Discord bằng đúng tài khoản đang tham gia chương trình rồi thử lại."
        )
    window, window_error = _parse_window(since, until)
    if window_error:
        return window_error

    from src.db import engine
    from src.services.discord_announcements import list_announcements

    try:
        announcements = list_announcements(
            engine,
            scope_ids=_scope_ids.get(),
            query=query,
            limit=limit,
            **window,
        )
    except Exception as exc:
        logger.warning("Lọc thông báo hỏng cho câu hỏi %r: %s", query[:80], exc)
        return "Không đọc được thông báo Discord lúc này. Hệ thống đã ghi nhận lỗi để xử lý."

    if not announcements:
        if window:
            return "Không có thông báo nào trong khoảng thời gian đó. Ngoài khoảng này có thể vẫn có."
        return "Chưa thấy thông báo nào trong những kênh bạn được phép đọc."

    rows = []
    for item in announcements:
        content = " ".join(item.content.split())[:600]
        rows.append(
            f"[Thông báo · {item.channel} · {_display_time(item.occurred_at)} · {item.author}] "
            f"{content}"
            + (f"\n  nguồn: {item.deep_link}" if item.deep_link else "")
            + (f"\n  vì sao là thông báo: {'; '.join(item.reasons)}" if item.reasons else "")
        )
    return "\n\n".join(rows)


@tool
def discord_search_my_messages(query: str = "", since: str = "", until: str = "") -> str:
    """Tìm chính xác các tin Discord do người dùng đang đăng nhập gửi.

    Author ID được backend lấy từ Discord OAuth và không xuất hiện trong chữ ký
    tool, nên model không thể chọn ID của người khác. Bỏ trống query để lấy các
    tin gần nhất; dùng since/until để giới hạn thời gian.
    """
    scope_error = _scope_error(require_identity=True)
    if scope_error:
        return scope_error
    window, window_error = _parse_window(since, until)
    if window_error:
        return window_error

    from src.db import engine
    from src.services.discord_messages import search_my_discord_messages

    messages = search_my_discord_messages(
        engine,
        scope_ids=_scope_ids.get() or [],
        author_external_id=_discord_author_external_id.get() or "",
        query=query,
        **window,
    )
    if not messages:
        return "Không tìm thấy tin nhắn nào do chính bạn gửi phù hợp với điều kiện đó."
    rows = []
    for message in messages:
        content = " ".join(message.content.split())[:500]
        rows.append(
            f"[Discord của bạn · {message.channel} · {_display_time(message.occurred_at)}] "
            f"{content}" + (f"\n  nguồn: {message.deep_link}" if message.deep_link else "")
        )
    return "\n\n".join(rows)


@tool
def discord_get_my_activity(since: str = "", until: str = "") -> str:
    """Thống kê số tin Discord của chính người dùng theo kênh và thời gian."""
    scope_error = _scope_error(require_identity=True)
    if scope_error:
        return scope_error
    window, window_error = _parse_window(since, until)
    if window_error:
        return window_error

    from src.db import engine
    from src.services.discord_messages import get_my_discord_activity

    activities = get_my_discord_activity(
        engine,
        scope_ids=_scope_ids.get() or [],
        author_external_id=_discord_author_external_id.get() or "",
        **window,
    )
    if not activities:
        return "Không có hoạt động Discord nào của bạn trong khoảng đã chọn."
    total = sum(item.message_count for item in activities)
    rows = [f"Tổng cộng {total} tin nhắn của bạn trong {len(activities)} kênh:"]
    rows.extend(
        f"- {item.channel}: {item.message_count} tin, gần nhất {_display_time(item.last_message_at)}"
        for item in activities
    )
    return "\n".join(rows)


# Compatibility import for older callers; the model only sees the clearer
# `discord_search_program` name through the tool registry.
discord_search_messages = discord_search_program


@tool
def calculate(expression: str) -> str:
    """Tính toán biểu thức toán học an toàn (không dùng eval).

    Hỗ trợ: +, -, *, /, //, %, ** và dấu ngoặc.

    Args:
        expression: Biểu thức cần tính (ví dụ: "2 + 3 * 4")

    Returns:
        Kết quả tính toán
    """
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_node(tree.body)
        return str(result)
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError) as e:
        return f"Lỗi tính toán: {e}"


def _eval_node(node: ast.AST) -> float:
    """Recursively evaluate AST node using safe operators only."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, int | float):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value)}")
    elif isinstance(node, ast.UnaryOp):
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op_func(_eval_node(node.operand))
    elif isinstance(node, ast.BinOp):
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op_func(_eval_node(node.left), _eval_node(node.right))
    else:
        raise ValueError(f"Unsupported expression: {type(node).__name__}")
