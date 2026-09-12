"""Nghiệp vụ kho thông tin chương trình có phiên bản và phạm vi chặt."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.orm import Session, aliased

from src.models.program_information import (
    ProgramInformationItem,
    ProgramInformationRequest,
    ProgramInformationVersion,
)
from src.services.program_cohorts import normalize_program_cohort_slug
from src.services.telemetry import emit_audit


class VersionConflictError(ValueError):
    """Bản người sửa đang nhìn đã cũ hơn bản trong cơ sở dữ liệu."""


class InvalidProgramInformationError(ValueError):
    """Nội dung không còn dữ liệu hợp lệ sau bước chuẩn hoá an toàn."""


class _PlainTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def sanitize_plain_text(value: str) -> str:
    """Chuyển nội dung nhập tay thành văn bản thuần, không lưu HTML thực thi."""
    parser = _PlainTextExtractor()
    parser.feed(value)
    parser.close()
    return re.sub(r"[ \t\r\f\v]+", " ", "".join(parser.parts)).strip()


def _normalized_aliases(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = sanitize_plain_text(raw)[:200]
        key = value.casefold()
        if value and key not in seen:
            result.append(value)
            seen.add(key)
    return result


def _content_hash(
    *,
    category: str,
    visibility: str,
    title: str,
    body: str,
    aliases: list[str],
    source_url: str | None,
    valid_from: datetime | None,
    valid_to: datetime | None,
) -> str:
    canonical = json.dumps(
        {
            "aliases": aliases,
            "body": body,
            "category": category,
            "source_url": source_url,
            "title": title,
            "valid_from": valid_from.isoformat() if valid_from else None,
            "valid_to": valid_to.isoformat() if valid_to else None,
            "visibility": visibility,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _new_version(
    *,
    item_id: int,
    version: int,
    category: str,
    visibility: str,
    actor_id: str,
    title: str,
    body: str,
    aliases: list[str],
    source_url: str | None,
    valid_from: datetime | None,
    valid_to: datetime | None,
) -> ProgramInformationVersion:
    clean_title = sanitize_plain_text(title)
    clean_body = sanitize_plain_text(body)
    if not clean_title or not clean_body:
        raise InvalidProgramInformationError("Tiêu đề và nội dung phải có văn bản thuần.")
    clean_aliases = _normalized_aliases(aliases)
    return ProgramInformationVersion(
        item_id=item_id,
        version=version,
        category=category,
        visibility=visibility,
        title=clean_title,
        body=clean_body,
        aliases=clean_aliases,
        source_url=source_url,
        valid_from=valid_from,
        valid_to=valid_to,
        content_hash=_content_hash(
            category=category,
            visibility=visibility,
            title=clean_title,
            body=clean_body,
            aliases=clean_aliases,
            source_url=source_url,
            valid_from=valid_from,
            valid_to=valid_to,
        ),
        created_by=actor_id,
    )


def create_information_item(
    db: Session,
    *,
    cohort_slug: str,
    category: str,
    visibility: str,
    actor_id: str,
    title: str,
    body: str,
    aliases: list[str],
    source_url: str | None,
    valid_from: datetime | None,
    valid_to: datetime | None,
) -> ProgramInformationItem:
    cohort_slug = normalize_program_cohort_slug(cohort_slug)
    now = datetime.now(UTC)
    item = ProgramInformationItem(
        cohort_slug=cohort_slug,
        category=category,
        visibility=visibility,
        status="draft",
        latest_version=1,
        created_by=actor_id,
        updated_by=actor_id,
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.flush()
    db.add(
        _new_version(
            item_id=item.id,
            version=1,
            category=category,
            visibility=visibility,
            actor_id=actor_id,
            title=title,
            body=body,
            aliases=aliases,
            source_url=source_url,
            valid_from=valid_from,
            valid_to=valid_to,
        )
    )
    emit_audit(
        db,
        action="program_information_created",
        object_type="program_information",
        object_id=str(item.id),
        actor_type="admin",
        actor_id=actor_id,
        version_label="1",
        after={"category": category, "visibility": visibility, "status": "draft"},
    )
    db.commit()
    db.refresh(item)
    return item


def update_information_item(
    db: Session,
    item: ProgramInformationItem,
    *,
    expected_version: int,
    category: str,
    visibility: str,
    actor_id: str,
    title: str,
    body: str,
    aliases: list[str],
    source_url: str | None,
    valid_from: datetime | None,
    valid_to: datetime | None,
) -> ProgramInformationItem:
    if item.latest_version != expected_version:
        raise VersionConflictError(f"Bản hiện tại là {item.latest_version}, không phải {expected_version}.")
    next_version = item.latest_version + 1
    db.add(
        _new_version(
            item_id=item.id,
            version=next_version,
            category=category,
            visibility=visibility,
            actor_id=actor_id,
            title=title,
            body=body,
            aliases=aliases,
            source_url=source_url,
            valid_from=valid_from,
            valid_to=valid_to,
        )
    )
    item.latest_version = next_version
    item.category = category
    item.visibility = visibility
    # Bản phát hành trước tiếp tục phục vụ trong lúc soạn bản mới. Item đã gỡ
    # thì chỉ mở lại thành nháp, không tự phát hành lại.
    item.status = "published" if item.published_version is not None and item.status != "archived" else "draft"
    item.archived_at = None
    item.updated_by = actor_id
    item.updated_at = datetime.now(UTC)
    emit_audit(
        db,
        action="program_information_version_created",
        object_type="program_information",
        object_id=str(item.id),
        actor_type="admin",
        actor_id=actor_id,
        version_label=str(next_version),
        before={"version": expected_version},
        after={"version": next_version, "category": category, "visibility": visibility},
    )
    db.commit()
    db.refresh(item)
    return item


def publish_information_item(
    db: Session, item: ProgramInformationItem, *, expected_version: int, actor_id: str
) -> ProgramInformationItem:
    if item.latest_version != expected_version:
        raise VersionConflictError(f"Bản hiện tại là {item.latest_version}, không phải {expected_version}.")
    now = datetime.now(UTC)
    item.published_version = item.latest_version
    item.status = "published"
    item.published_at = now
    item.archived_at = None
    item.updated_by = actor_id
    item.updated_at = now
    emit_audit(
        db,
        action="program_information_published",
        object_type="program_information",
        object_id=str(item.id),
        actor_type="admin",
        actor_id=actor_id,
        version_label=str(item.latest_version),
        after={"status": "published", "version": item.latest_version},
    )
    db.commit()
    db.refresh(item)
    return item


def archive_information_item(
    db: Session, item: ProgramInformationItem, *, expected_version: int, actor_id: str
) -> ProgramInformationItem:
    if item.latest_version != expected_version:
        raise VersionConflictError(f"Bản hiện tại là {item.latest_version}, không phải {expected_version}.")
    now = datetime.now(UTC)
    item.status = "archived"
    item.archived_at = now
    item.updated_by = actor_id
    item.updated_at = now
    emit_audit(
        db,
        action="program_information_archived",
        object_type="program_information",
        object_id=str(item.id),
        actor_type="admin",
        actor_id=actor_id,
        version_label=str(item.latest_version),
        after={"status": "archived"},
    )
    db.commit()
    db.refresh(item)
    return item


def get_version(db: Session, item: ProgramInformationItem, *, published: bool) -> ProgramInformationVersion:
    version_number = item.published_version if published else item.latest_version
    if version_number is None:
        raise LookupError("Đầu mục chưa có bản phát hành.")
    version = db.scalar(
        select(ProgramInformationVersion).where(
            ProgramInformationVersion.item_id == item.id,
            ProgramInformationVersion.version == version_number,
        )
    )
    if version is None:
        raise LookupError("Không tìm thấy phiên bản nội dung.")
    return version


@dataclass(frozen=True)
class PublishedInformation:
    item: ProgramInformationItem
    version: ProgramInformationVersion


def search_published_information(
    db: Session,
    *,
    cohort_slug: str,
    allowed_visibilities: frozenset[str],
    query: str = "",
    category: str | None = None,
    limit: int = 10,
    now: datetime | None = None,
) -> list[PublishedInformation]:
    """Chỉ lấy bản đã phát hành, còn hiệu lực và đúng cohort/phạm vi."""
    cohort_slug = normalize_program_cohort_slug(cohort_slug)
    current = now or datetime.now(UTC)
    version = aliased(ProgramInformationVersion)
    filters = [
        func.lower(ProgramInformationItem.cohort_slug) == cohort_slug,
        ProgramInformationItem.status == "published",
        version.visibility.in_(allowed_visibilities),
        ProgramInformationItem.published_version.is_not(None),
        version.version == ProgramInformationItem.published_version,
        or_(version.valid_from.is_(None), version.valid_from <= current),
        or_(version.valid_to.is_(None), version.valid_to > current),
    ]
    if category:
        filters.append(version.category == category)
    normalized_query = sanitize_plain_text(query)
    if normalized_query:
        tokens = [token for token in re.findall(r"\w+", normalized_query) if len(token) >= 3][:8]
        needles = [f"%{token}%" for token in tokens] or [f"%{normalized_query}%"]
        filters.append(
            or_(
                *[
                    field.ilike(needle)
                    for needle in needles
                    for field in (version.title, version.body, cast(version.aliases, String))
                ]
            )
        )
    rows = db.execute(
        select(ProgramInformationItem, version)
        .join(
            version,
            and_(
                version.item_id == ProgramInformationItem.id,
                version.version == ProgramInformationItem.published_version,
            ),
        )
        .where(*filters)
        .order_by(ProgramInformationItem.published_at.desc(), ProgramInformationItem.id.desc())
        .limit(max(1, min(limit, 50)))
    ).all()
    return [PublishedInformation(item=row[0], version=row[1]) for row in rows]


def list_admin_information(
    db: Session, *, cohort_slug: str, status: str | None = None
) -> list[tuple[ProgramInformationItem, ProgramInformationVersion]]:
    cohort_slug = normalize_program_cohort_slug(cohort_slug)
    version = aliased(ProgramInformationVersion)
    filters = [func.lower(ProgramInformationItem.cohort_slug) == cohort_slug]
    if status:
        filters.append(ProgramInformationItem.status == status)
    return list(
        db.execute(
            select(ProgramInformationItem, version)
            .join(
                version,
                and_(
                    version.item_id == ProgramInformationItem.id,
                    version.version == ProgramInformationItem.latest_version,
                ),
            )
            .where(*filters)
            .order_by(ProgramInformationItem.updated_at.desc())
        ).all()
    )


def create_human_request(
    db: Session, *, cohort_slug: str, requester_id: int, shared_question: str
) -> ProgramInformationRequest:
    cohort_slug = normalize_program_cohort_slug(cohort_slug)
    now = datetime.now(UTC)
    clean_question = sanitize_plain_text(shared_question)
    if len(clean_question) < 3:
        raise InvalidProgramInformationError("Câu hỏi chia sẻ phải có ít nhất 3 ký tự.")
    existing = db.scalar(
        select(ProgramInformationRequest).where(
            func.lower(ProgramInformationRequest.cohort_slug) == cohort_slug,
            ProgramInformationRequest.requester_id == requester_id,
            ProgramInformationRequest.status == "open",
            ProgramInformationRequest.shared_question == clean_question,
        )
    )
    if existing is not None:
        return existing
    request = ProgramInformationRequest(
        cohort_slug=cohort_slug,
        requester_id=requester_id,
        shared_question=clean_question,
        status="open",
        consented_at=now,
        created_at=now,
    )
    db.add(request)
    db.flush()
    emit_audit(
        db,
        action="program_information_help_requested",
        object_type="program_information_request",
        object_id=str(request.id),
        actor_type="user",
        actor_id=str(requester_id),
        # Không ghi câu hỏi, hồ sơ hay hội thoại vào audit dùng chung.
        after={"status": "open", "consent": True},
    )
    db.commit()
    db.refresh(request)
    return request


def list_human_requests(
    db: Session, *, cohort_slug: str, status: str | None = "open"
) -> list[ProgramInformationRequest]:
    cohort_slug = normalize_program_cohort_slug(cohort_slug)
    filters = [func.lower(ProgramInformationRequest.cohort_slug) == cohort_slug]
    if status:
        filters.append(ProgramInformationRequest.status == status)
    return list(
        db.scalars(
            select(ProgramInformationRequest).where(*filters).order_by(ProgramInformationRequest.created_at.asc())
        ).all()
    )


def resolve_human_request(
    db: Session,
    request: ProgramInformationRequest,
    item: ProgramInformationItem,
    *,
    expected_version: int,
    actor_id: str,
) -> ProgramInformationRequest:
    if request.status != "open":
        raise VersionConflictError("Yêu cầu này đã được xử lý.")
    if item.status != "published" or item.published_version != expected_version:
        raise VersionConflictError("Chỉ có thể trả lời bằng đúng bản đang phát hành.")
    if normalize_program_cohort_slug(item.cohort_slug) != normalize_program_cohort_slug(request.cohort_slug):
        raise LookupError("Thông tin và yêu cầu không cùng cohort.")
    now = datetime.now(UTC)
    request.status = "resolved"
    request.resolved_item_id = item.id
    request.resolved_by = actor_id
    request.resolved_at = now
    emit_audit(
        db,
        action="program_information_help_resolved",
        object_type="program_information_request",
        object_id=str(request.id),
        actor_type="admin",
        actor_id=actor_id,
        version_label=str(expected_version),
        after={"status": "resolved", "item_id": item.id},
    )
    db.commit()
    db.refresh(request)
    return request
