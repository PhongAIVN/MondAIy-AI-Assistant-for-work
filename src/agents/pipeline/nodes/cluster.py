from __future__ import annotations

import hashlib
import re
from datetime import datetime
from difflib import SequenceMatcher

from src.agents.pipeline.state import PipelineState

_TITLE_SIMILARITY_THRESHOLD = 0.72
_DUE_DATE_PROXIMITY_SECONDS = 24 * 3600

# Mã issue kiểu Jira: "TAPB-131", "PROJ-7". Đây là định danh XUYÊN NGUỒN — cùng
# một việc xuất hiện ở Jira lẫn trong mail nhắc hạn đều mang mã này.
_ISSUE_KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d+\b")

# Ngày tháng trong tiêu đề thư nhắc định kỳ. Jira gửi mỗi ngày một thư với nội
# dung y hệt, chỉ khác ngày — và mỗi thư là một threadId riêng nên không có
# đường nào gộp chúng lại.
_DATE_IN_TITLE_RE = re.compile(r"\d{1,4}[/-]\d{1,2}([/-]\d{1,4})?|\d{1,2}:\d{2}")

# Ngưỡng RIÊNG, cao hơn hẳn `_TITLE_SIMILARITY_THRESHOLD`, dùng cho thư nhắc
# lặp lại. 0.72 quá lỏng để dùng xuyên thread (đã gây gộp nhầm "Biên lai thanh
# toán" với "Mã OTP", ratio 0.756); nhắc định kỳ thì sau khi xoá ngày tháng hai
# tiêu đề gần như trùng khít, nên đòi gần tuyệt đối là an toàn.
_RECURRING_TITLE_THRESHOLD = 0.95


def _issue_keys(item: dict) -> frozenset[str]:
    """Mã issue mà item này nói tới.

    Item Jira: chính là key của nó. Mail: mọi mã tìm thấy trong tiêu đề/thân —
    thư nhắc hằng ngày của Jira liệt kê đủ mã các việc còn treo.
    """
    message = item.get("message") or {}
    if message.get("provider") == "jira":
        key = str(message.get("id") or "").strip().upper()
        return frozenset({key}) if _ISSUE_KEY_RE.fullmatch(key) else frozenset()
    haystack = f"{message.get('subject', '')} {message.get('text', '')}"
    return frozenset(_ISSUE_KEY_RE.findall(haystack.upper()))


def _recurring_title(title: str) -> str:
    """Tiêu đề sau khi xoá ngày/giờ — chữ ký của một thư nhắc định kỳ."""
    return " ".join(_DATE_IN_TITLE_RE.sub(" ", title).lower().split())


def _same_sender(a: dict, b: dict) -> bool:
    left = str((a.get("message") or {}).get("author_id") or "").lower()
    right = str((b.get("message") or {}).get("author_id") or "").lower()
    return bool(left) and left == right


def _is_recurring_reminder_of(item: dict, group: dict) -> bool:
    """Cùng người gửi + tiêu đề trùng khít sau khi xoá ngày = thư nhắc lặp lại.

    Đây là ngoại lệ CÓ KIỂM SOÁT cho luật "khác thread thì khác việc": thư nhắc
    định kỳ cố ý tạo thread mới mỗi ngày, nên bám theo thread sẽ đẻ ra một task
    mỗi ngày cho cùng một việc.

    MÃ ISSUE THẮNG TIÊU ĐỀ. Hai việc mang mã khác nhau là hai việc khác nhau, dù
    câu chữ giống tới đâu — bảng thật có cả cụm "[Cadence] Weekly report W3/W4/
    W5/W6" chỉ khác đúng một ký tự, và issue Jira thì không bao giờ là "thư nhắc
    lặp lại" cả.
    """
    item_keys = _issue_keys(item)
    group_keys = group["issue_keys"]
    if item_keys and group_keys and not (item_keys & group_keys):
        return False

    sample = group["items"][0]
    if not _same_sender(item, sample):
        return False
    left = _recurring_title(item.get("title", ""))
    right = _recurring_title(group["title"])
    if not left or not right:
        return False
    return SequenceMatcher(None, left, right).ratio() >= _RECURRING_TITLE_THRESHOLD


def _jira_covered_keys(items: list[dict]) -> frozenset[str]:
    """Mã issue đã có mặt với tư cách issue Jira THẬT trong cùng lần chạy."""
    covered: set[str] = set()
    for item in items:
        if (item.get("message") or {}).get("provider") == "jira":
            covered.update(_issue_keys(item))
    return frozenset(covered)


def _normalize_title(title: str) -> str:
    return " ".join(title.lower().split())


def _titles_match(a: str, b: str) -> bool:
    return SequenceMatcher(None, _normalize_title(a), _normalize_title(b)).ratio() >= _TITLE_SIMILARITY_THRESHOLD


def _due_dates_close(a: datetime | None, b: datetime | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs((a - b).total_seconds()) <= _DUE_DATE_PROXIMITY_SECONDS


def _thread_key(item: dict) -> str | None:
    """Định danh hội thoại ổn định (Gmail threadId không đổi qua các lần
    resync/reply) — dùng làm cluster_key chính khi có, thay vì hash theo
    title LLM sinh ra (đổi câu chữ mỗi lần chạy -> vỡ idempotent, xem
    FR-012/013 và bug thực tế: mail đã sync vẫn tạo task trùng)."""
    message = item.get("message") or {}
    thread_id = message.get("thread_id")
    if not thread_id:
        return None
    return f"{message.get('provider', '')}:{thread_id}"


def _more_recent(candidate, current) -> bool:
    if not isinstance(candidate, datetime):
        return False
    if not isinstance(current, datetime):
        return True
    return candidate > current


def _cluster_key(
    user_id: str,
    title: str,
    due_at: datetime | None,
    thread_keys: frozenset[str],
    issue_keys: frozenset[str] = frozenset(),
) -> str:
    # Mã issue đứng TRƯỚC thread: nó ổn định xuyên nguồn (Jira lẫn mail nhắc)
    # và xuyên ngày (thư nhắc hôm nay và hôm qua là 2 thread khác nhau). Bám
    # thread thì mỗi ngày sinh một task mới cho cùng một việc.
    if issue_keys:
        raw = f"{user_id}:issue:{'|'.join(sorted(issue_keys))}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
    if thread_keys:
        # Không đưa due_bucket vào khoá thread-based: reply đổi hạn vẫn phải
        # map lại đúng task cũ (rồi persist_node ghi đè due_at mới), không
        # được tạo task khác chỉ vì ngày lệch.
        identity = "|".join(sorted(thread_keys))
        raw = f"{user_id}:{identity}"
    else:
        due_bucket = due_at.date().isoformat() if due_at else "none"
        raw = f"{user_id}:{_normalize_title(title)}:{due_bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def cluster_node(state: PipelineState) -> dict:
    """Gộp task trùng nhau (cùng thread hội thoại, hoặc fuzzy title + gần
    ngày khi không có thread). cluster_key ổn định để persist idempotent
    (FR-012/013 — resync không tạo task trùng)."""
    user_id = state["user_id"]
    resolved = state.get("resolved", [])
    groups: list[dict] = []

    # Mã issue đã có bản Jira THẬT trong lần chạy này. Thư nhắc của Jira chỉ
    # liệt kê tên việc, còn issue mang mô tả đầy đủ + file đính kèm — nên khi cả
    # hai cùng có mặt, bản mail là thừa.
    jira_covered = _jira_covered_keys(resolved)

    for item in resolved:
        title = item.get("title", "")
        due_at = item.get("due_at")
        sent_at = (item.get("message") or {}).get("sent_at")
        thread_key = _thread_key(item)
        issue_keys = _issue_keys(item)
        is_jira = (item.get("message") or {}).get("provider") == "jira"

        # Thư TỔNG HỢP nhắc nhiều việc (>= 2 mã) mà mọi mã đều đã có issue Jira
        # thật: bỏ hẳn, không tạo task riêng. Gộp nó vào một trong các issue là
        # sai (nó nói về cả 4), mà để nguyên thì người dùng có thêm một task
        # "4 công việc cần cập nhật" chồng lên 4 task thật.
        if not is_jira and len(issue_keys) >= 2 and issue_keys <= jira_covered:
            continue

        match = None
        if thread_key is not None:
            match = next((g for g in groups if thread_key in g["thread_keys"]), None)

        # Mã issue là định danh XUYÊN NGUỒN và XUYÊN NGÀY: issue Jira TAPB-131
        # và thư nhắc nói về TAPB-131 là cùng một việc, dù khác nguồn khác
        # thread. Chỉ dùng khi item nói về ĐÚNG MỘT việc — thư tổng hợp mang 4
        # mã mà gộp theo giao nhau sẽ kéo 4 việc khác nhau vào chung một cụm.
        if match is None and len(issue_keys) == 1:
            match = next((g for g in groups if issue_keys & g["issue_keys"]), None)

        # Thư nhắc định kỳ: cùng người gửi, tiêu đề trùng khít sau khi xoá ngày.
        # Không có nhánh này thì mỗi ngày Jira nhắc là thêm một task mới.
        if match is None:
            match = next((g for g in groups if _is_recurring_reminder_of(item, g)), None)

        if match is None:
            # Fuzzy title CHỈ được dùng khi ít nhất một bên chưa có định danh
            # hội thoại. Hai mail thuộc 2 thread khác nhau là 2 việc khác
            # nhau, dù câu chữ tiêu đề giống tới đâu — và chúng rất hay giống
            # nhau: tiêu đề lưới an toàn dùng chung tiền tố dài
            # ("Cần xem lại — có hạn và yêu cầu hành động: ") nên 2 mail chẳng
            # liên quan gì cũng đạt ratio > 0.72. Bug thật: 1 task mang tiêu
            # đề "Biên lai thanh toán" nhưng nội dung lại là review bài báo.
            match = next(
                (
                    g
                    for g in groups
                    if (thread_key is None or not g["thread_keys"])
                    and _titles_match(g["title"], title)
                    and _due_dates_close(g["due_at"], due_at)
                ),
                None,
            )

        if match:
            match["items"].append(item)
            if thread_key is not None:
                match["thread_keys"].add(thread_key)
            match["issue_keys"].update(issue_keys)
            # Tiêu đề/hạn hiển thị lấy theo tin MỚI NHẤT trong cụm — task được
            # mở lại bởi 1 reply mới phải phản ánh nội dung reply đó, không
            # kẹt ở câu chữ của tin cũ nhất khởi tạo cụm.
            # Nguồn Jira thắng về câu chữ dù cũ hơn: issue mang mô tả đầy đủ,
            # thư nhắc chỉ có tên việc. Ngoài ra mới nhất mới được đổi tiêu đề.
            if is_jira and not match["has_jira"]:
                match["title"] = title
                match["due_at"] = due_at
                match["latest_sent_at"] = sent_at
            elif not (match["has_jira"] and not is_jira) and _more_recent(sent_at, match["latest_sent_at"]):
                match["title"] = title
                match["due_at"] = due_at
                match["latest_sent_at"] = sent_at
            match["has_jira"] = match["has_jira"] or is_jira
        else:
            groups.append(
                {
                    "title": title,
                    "due_at": due_at,
                    "items": [item],
                    "thread_keys": {thread_key} if thread_key is not None else set(),
                    "issue_keys": set(issue_keys),
                    "has_jira": is_jira,
                    "latest_sent_at": sent_at,
                }
            )

    clusters = []
    for group in groups:
        source_count = len({item["message"]["id"] for item in group["items"]})
        signal_strength = min(1.0, source_count / 3)
        # 1 nguồn xác nhận được người phụ trách là đủ bằng chứng cho cả cụm — cùng
        # tinh thần với signal_strength: nhiều nguồn xác nhận, không cần TẤT CẢ.
        assignee = next((item.get("assignee") for item in group["items"] if item.get("assignee")), None)
        # Tóm tắt hiển thị ở Task inbox — lấy detail dài nhất trong cụm, tránh
        # rớt về item có summary rỗng/ngắn khi gộp nhiều nguồn.
        detail = max((item.get("detail", "") for item in group["items"]), key=len, default="")

        # Explainability rule-based (chỉ item nguồn Jira có "decision") — cụm
        # gộp cả KEEP lẫn REVIEW thì ưu tiên KEEP (đã có ít nhất 1 nguồn chắc
        # chắn). Item nguồn LLM (Gmail) không có "decision" -> None, không suy diễn.
        decisions = [item["decision"] for item in group["items"] if item.get("decision")]
        cluster_decision = "KEEP" if "KEEP" in decisions else (decisions[0] if decisions else None)
        reasons = sorted({reason for item in group["items"] for reason in item.get("reasons", [])})
        rule_version = next((item.get("rule_version") for item in group["items"] if item.get("rule_version")), None)
        # all_day đúng nghĩa chỉ khi MỌI nguồn trong cụm đều không có giờ cụ
        # thể (vd. Jira duedate) — 1 nguồn có giờ rõ ràng thì cả cụm không
        # còn là "cả ngày" nữa.
        all_day = bool(group["items"]) and all(item.get("all_day", False) for item in group["items"])
        action_types = sorted({item.get("action_type", "direct_action") for item in group["items"]})
        statuses = sorted({item.get("status", "open") for item in group["items"]})
        conditions = sorted({item.get("condition", "") for item in group["items"] if item.get("condition")})

        clusters.append(
            {
                "cluster_key": _cluster_key(
                    user_id,
                    group["title"],
                    group["due_at"],
                    frozenset(group["thread_keys"]),
                    frozenset(group["issue_keys"]),
                ),
                "title": group["title"],
                "detail": detail,
                "due_at": group["due_at"],
                "all_day": all_day,
                "action_types": action_types,
                "statuses": statuses,
                "conditions": conditions,
                "requires_user_action": any(item.get("requires_user_action", True) for item in group["items"]),
                "ambiguous": any(item.get("ambiguous") for item in group["items"]),
                "assignee": assignee,
                "assignee_ambiguous": assignee is None,
                "source_count": source_count,
                "signal_strength": signal_strength,
                "decision": cluster_decision,
                "reasons": reasons,
                "rule_version": rule_version,
                "items": group["items"],
            }
        )

    return {"clusters": clusters}
