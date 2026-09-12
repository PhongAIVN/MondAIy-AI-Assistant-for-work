"""Chuẩn hoá định danh cohort dùng chung cho mọi luồng chương trình."""

import re

from src.config import get_settings

_COHORT_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def normalize_program_cohort_slug(value: str | None) -> str:
    """Trả slug lowercase duy nhất; thiếu hoặc sai định dạng thì nổ rõ."""
    cohort = (value or "").strip().lower()
    if not _COHORT_SLUG.fullmatch(cohort):
        raise ValueError("cohortSlug phải là slug chữ thường, số và dấu gạch ngang.")
    return cohort


def configured_program_cohort_slug() -> str:
    """Đọc cohort vận hành và kiểm tra ngay, không fallback sang giá trị đoán."""
    return normalize_program_cohort_slug(get_settings().program_cohort_slug)


def resolve_program_cohort_slug(user_cohort_slug: str | None) -> str:
    """Dùng cohort đã gán; user cũ chưa có thì dùng cohort vận hành bắt buộc."""
    if user_cohort_slug is not None:
        return normalize_program_cohort_slug(user_cohort_slug)
    return configured_program_cohort_slug()
