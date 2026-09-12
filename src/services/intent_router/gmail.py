"""Định tuyến ý định Gmail bằng luật, không gọi LLM — xem package __init__.py."""

from __future__ import annotations

import re

from src.services.intent_router._shared import _fold
from src.services.intent_router.types import GmailIntent, GmailIntentPlan, ToolRisk

_MAILBOX = re.compile(r"(?i)\b(gmail|email|e-mail|mail|inbox|hộp thư|thư điện tử)\b")
_SUMMARY = re.compile(r"(?i)(tóm tắt|tổng hợp|summary|brief|nội dung|điểm chính|what happened)")
_SEARCH = re.compile(r"(?i)(tìm|search|find|email nào|show|liệt kê|list|from:|subject:)")
_THREAD = re.compile(r"(?i)(thread|chuỗi|cuộc hội thoại|reply|trả lời|phản hồi)")
_ATTACHMENT = re.compile(r"(?i)(attachment|file đính kèm|tệp đính kèm|pdf|ảnh|document)")
_TRIAGE = re.compile(r"(?i)(cần xử lý|ưu tiên|important|urgent|unread|chưa đọc|không nên bỏ lỡ)")
_LABELS = re.compile(r"(?i)(label|nhãn|folder|thư mục|bao nhiêu email|count)")
_DRAFT = re.compile(r"(?i)(soạn|draft|viết nháp|prepare a reply)")
_REPLY = re.compile(r"(?i)(reply|trả lời|phản hồi email)")
_FORWARD = re.compile(r"(?i)(forward|chuyển tiếp)")
_SEND = re.compile(r"(?i)(gửi|send email|send it)")
_ARCHIVE = re.compile(r"(?i)(archive|lưu trữ)")
_DELETE = re.compile(r"(?i)(delete|trash|xóa|thùng rác)")


def _has_gmail_link(text: str) -> bool:
    return bool(
        re.search(
            r"https://mail\.google\.com/mail/(?:u/\d+/)?#(?:all|inbox|sent|starred|snoozed|drafts|trash|spam|important)/[^\s]+",
            text,
        )
    )


def route_gmail_intent(text: str) -> GmailIntentPlan:
    normalized = " ".join(text.strip().split())
    folded = _fold(normalized)
    if not normalized or not (_MAILBOX.search(normalized) or _has_gmail_link(normalized)):
        return GmailIntentPlan(
            GmailIntent.NONE, None, None, 0.99, False, ToolRisk.NONE, None, "no explicit Gmail scope"
        )

    if _DELETE.search(normalized) or re.search(r"(?i)(delete|trash|xoa|thung rac)", folded):
        return GmailIntentPlan(
            GmailIntent.DELETE,
            "gmail_delete_emails",
            "delete_email",
            0.96,
            False,
            ToolRisk.DESTRUCTIVE,
            None,
            "explicit destructive Gmail request",
        )
    if _ARCHIVE.search(normalized) or re.search(r"(?i)(archive|luu tru)", folded):
        return GmailIntentPlan(
            GmailIntent.ARCHIVE,
            "gmail_archive_emails",
            "archive_email",
            0.94,
            False,
            ToolRisk.EXTERNAL_WRITE,
            None,
            "explicit archive request",
        )
    if _FORWARD.search(normalized) or re.search(r"(?i)(forward|chuyen tiep)", folded):
        return GmailIntentPlan(
            GmailIntent.FORWARD,
            "gmail_forward_emails",
            "forward_email",
            0.94,
            True,
            ToolRisk.EXTERNAL_WRITE,
            None,
            "forward requires recipient/thread clarification",
        )
    if _REPLY.search(normalized) or re.search(r"(?i)(reply|tra loi|phan hoi email)", folded):
        return GmailIntentPlan(
            GmailIntent.REPLY,
            "gmail_create_draft",
            "draft_reply",
            0.92,
            True,
            ToolRisk.DRAFT,
            None,
            "reply is draft-first and requires a target thread",
        )
    if (_SEND.search(normalized) or re.search(r"(?i)(gui email|gui no)", folded)) and not (
        _DRAFT.search(normalized) or re.search(r"(?i)(soan|viet nhap)", folded)
    ):
        return GmailIntentPlan(
            GmailIntent.SEND,
            "gmail_create_draft",
            "draft_email",
            0.90,
            True,
            ToolRisk.EXTERNAL_WRITE,
            None,
            "send request is draft-first and requires approval",
        )
    if _ATTACHMENT.search(normalized) or re.search(r"(?i)(attachment|file dinh kem|tep dinh kem)", folded):
        return GmailIntentPlan(
            GmailIntent.ATTACHMENT,
            "gmail_read_attachment",
            "fetch_attachment_metadata",
            0.90,
            True,
            ToolRisk.READ,
            None,
            "attachment target is required",
        )
    if _LABELS.search(normalized) or re.search(r"(?i)(nhan|thu muc|bao nhieu email)", folded):
        return GmailIntentPlan(
            GmailIntent.LABELS,
            "gmail_list_labels",
            "list_gmail_labels",
            0.91,
            False,
            ToolRisk.READ,
            None,
            "label/count lookup",
        )
    if _DRAFT.search(normalized) or re.search(r"(?i)(soan|viet nhap)", folded):
        return GmailIntentPlan(
            GmailIntent.DRAFT,
            "gmail_create_draft",
            "draft_email",
            0.90,
            True,
            ToolRisk.DRAFT,
            None,
            "draft requires recipient and content",
        )
    if _SUMMARY.search(normalized) or re.search(r"(?i)(tom tat|tong hop|noi dung|diem chinh)", folded):
        return GmailIntentPlan(
            GmailIntent.SUMMARY,
            "gmail_search_emails",
            "search_gmail",
            0.96,
            False,
            ToolRisk.READ,
            normalized,
            "summary of explicitly requested Gmail content",
        )
    if _TRIAGE.search(normalized) or re.search(r"(?i)(can xu ly|uu tien|chua doc|khong nen bo lo)", folded):
        return GmailIntentPlan(
            GmailIntent.TRIAGE,
            "gmail_search_emails",
            "search_gmail",
            0.91,
            False,
            ToolRisk.READ,
            normalized,
            "inbox triage/search",
        )
    if _THREAD.search(normalized) or re.search(r"(?i)(chuoi|cuoc hoi thoai|doc thread)", folded):
        return GmailIntentPlan(
            GmailIntent.READ_THREAD,
            "gmail_read_email_thread",
            "open_message",
            0.86,
            True,
            ToolRisk.READ,
            None,
            "thread target is required",
        )
    if _SEARCH.search(normalized):
        return GmailIntentPlan(
            GmailIntent.SEARCH,
            "gmail_search_emails",
            "search_gmail",
            0.88,
            False,
            ToolRisk.READ,
            normalized,
            "explicit Gmail search",
        )

    # Mentioning Gmail without a verb is not enough to call a tool.
    return GmailIntentPlan(
        GmailIntent.NONE, None, None, 0.70, True, ToolRisk.NONE, None, "Gmail mentioned without a supported operation"
    )
