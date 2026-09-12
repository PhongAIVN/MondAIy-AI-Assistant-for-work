"""Admin paste, preview và publish candidate; không ghi Calendar."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AnyHttpUrl, Field, field_validator
from sqlalchemy.orm import Session

from src.api.deps import require_admin
from src.config import get_settings
from src.db import get_db
from src.models.announcement_candidate import AnnouncementCandidate
from src.models.program_information_schemas import CamelModel, Category
from src.models.user import User
from src.services.announcement_candidates import create_or_get, publish

router = APIRouter(
    prefix="/admin/discord-announcements",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


class Paste(CamelModel):
    raw_text: str = Field(min_length=1, max_length=20000)
    channel: str = Field(default="#announcements", max_length=200)
    deep_link: AnyHttpUrl | None = None
    reference_date: datetime | None = None

    @field_validator("deep_link")
    @classmethod
    def require_https(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is not None and value.scheme != "https":
            raise ValueError("deepLink phải dùng HTTPS.")
        return value


class PublishReview(CamelModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    category: Category
    aliases: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        default_factory=list,
        max_length=30,
    )
    items: list["PublishActionReview"] | None = Field(default=None, min_length=1, max_length=30)

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for raw in values:
            value = " ".join(raw.split()).strip()
            if not value:
                raise ValueError("Alias không được để trống.")
            key = value.casefold()
            if key not in seen:
                result.append(value)
                seen.add(key)
        return result


class PublishActionReview(CamelModel):
    title: str = Field(min_length=1, max_length=500)
    kind: str = Field(pattern=r"^(task|calendar|change|resource)$")
    due_at: str | None = None
    all_day: bool = False

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("dueAt phải là ISO datetime hoặc ISO date.") from exc
        return value


def out(row: AnnouncementCandidate) -> dict:
    return {
        "id": row.id,
        "status": row.status,
        "rawText": row.raw_text,
        "evidence": row.evidence,
        "preview": row.preview,
        "informationItemId": row.information_item_id,
    }


@router.post("/preview")
async def paste(payload: Paste, db: Session = Depends(get_db), actor: User = Depends(require_admin)) -> dict:
    if payload.reference_date is not None and payload.reference_date.tzinfo is None:
        raise HTTPException(422, "referenceDate phải có múi giờ.")
    row = await create_or_get(
        db,
        cohort_slug=get_settings().program_cohort_slug,
        raw_text=payload.raw_text,
        evidence={
            "channel": payload.channel,
            "deepLink": str(payload.deep_link) if payload.deep_link else None,
        },
        actor_id=str(actor.id),
        reference_date=payload.reference_date,
    )
    return out(row)


@router.post("/{candidate_id}/publish")
def confirm(
    candidate_id: int,
    review: PublishReview | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> dict:
    row = db.get(AnnouncementCandidate, candidate_id)
    if row is None or row.cohort_slug != get_settings().program_cohort_slug:
        raise HTTPException(404, "Thông báo không tồn tại.")
    return out(
        publish(
            db,
            row,
            actor_id=str(actor.id),
            title=review.title if review else None,
            category=review.category if review else None,
            aliases=review.aliases if review else None,
            items=[item.model_dump(by_alias=True) for item in review.items] if review and review.items is not None else None,
        )
    )
