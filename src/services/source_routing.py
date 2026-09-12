"""Explainable source affinity for project/entity questions."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

SOURCE_AUTO_CONTINUE_THRESHOLD = 0.85
SOURCE_CONFIRM_THRESHOLD = 0.60


@dataclass(frozen=True)
class SourceRoutingDecision:
    entities: tuple[str, ...]
    explicit_sources: tuple[str, ...]
    candidate_sources: tuple[str, ...]
    mode: str
    reason: str
    confidence: float
    needs_confirmation: bool
    confirmation_question: str | None = None
    confidence_band: str = "low"
    action: str = "not_applicable"

    def trace(self) -> dict:
        return {
            "entities": list(self.entities),
            "explicit_sources": list(self.explicit_sources),
            "candidate_sources": list(self.candidate_sources),
            "mode": self.mode,
            "reason": self.reason,
            "confidence": self.confidence,
            "confidence_band": self.confidence_band,
            "action": self.action,
            "needs_confirmation": self.needs_confirmation,
            **({"confirmation_question": self.confirmation_question} if self.confirmation_question else {}),
        }


_PROVIDER_PATTERNS = {
    "jira": r"\bjira\b",
    "gmail": r"\bgmail\b",
    "calendar": r"\b(?:google\s+)?calendar\b",
    "discord": r"\bdiscord\b",
    "tasks": r"\bmondaiy\s+tasks?\b|\btask manager\b|\b(?:trang|tab|muc|nguon|kho)\s+tasks?\b",
    "google_sheets": (
        r"https?://docs\.google\.com/spreadsheets/d/|"
        r"\bgoogle\s+(?:sheet|sheets|spreadsheet)\b|"
        r"\b(?:sheet|sheets|spreadsheet)\s+google\b|"
        r"\bbang\s+tinh\s+google\b"
    ),
    "google_docs": (
        r"https?://docs\.google\.com/document/d/|"
        r"\bgoogle\s+(?:doc|docs|document)\b|"
        r"\b(?:doc|docs|document)\s+google\b|"
        r"\btai\s+lieu\s+google\b"
    ),
}
_DOMAIN_PATTERNS = {
    "jira": r"\bissue\b|\bticket\b|\bbug\b|\bepic\b",
    "gmail": r"\be-?mail\b|\bmail\b|\binbox\b|hop thu|thu dien tu",
    "calendar": r"\blich\b|\bmeeting\b|\bevent\b|cuoc hen|su kien",
    "discord": r"tin nhan|\bkenh\b|\bchannel\b",
    "tasks": r"\btasks?\b|\btodo\b|\bto-do\b|cong viec|viec can lam",
}
_PROJECT = re.compile(r"(?:du an|project)\s+([a-z0-9][a-z0-9_-]*)", re.IGNORECASE)
_ACTIVITY = re.compile(
    r"(?:da lam|thuc hien|tham gia|dong gop|contributed|worked|xu ly|giai quyet|"
    r"lam duoc gi|what did i do|what have i done)",
    re.IGNORECASE,
)
_ALL_SOURCES = re.compile(r"\b(?:tat ca|all|mọi nguồn|every source)\b", re.IGNORECASE)
_SOURCE_NAMES = ("tasks", "jira", "gmail", "calendar", "discord", "google_sheets", "google_docs")


def analyze_source_mentions(text: str) -> SourceRoutingDecision:
    normalized = "".join(
        char for char in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(char)
    )
    normalized = normalized.replace("đ", "d")
    normalized = " ".join(normalized.split())
    extracted = [match.group(1) for match in _PROJECT.finditer(normalized)]
    extracted.extend(
        token
        for token in re.findall(r"\b[A-Z][A-Za-z0-9_-]{2,}\b", text)
        if token.casefold() not in {
            "jira", "gmail", "calendar", "discord", "google", "sheet", "sheets", "spreadsheet",
            "doc", "docs", "document", "park", "trong", "toi", "the", "my",
        }
    )
    entities = tuple(dict.fromkeys(entity.casefold() for entity in extracted))
    explicit = tuple(
        source for source, pattern in _PROVIDER_PATTERNS.items() if re.search(pattern, normalized)
    )
    semantic = tuple(
        source for source, pattern in _DOMAIN_PATTERNS.items() if re.search(pattern, normalized)
    )
    if _ALL_SOURCES.search(normalized):
        return SourceRoutingDecision(
            entities,
            ("all",),
            _SOURCE_NAMES,
            "explicit",
            "all_sources_confirmed_by_user",
            SOURCE_AUTO_CONTINUE_THRESHOLD + 0.08,
            False,
            confidence_band="high",
            action="continue",
        )
    if explicit:
        return SourceRoutingDecision(
            entities,
            explicit,
            explicit,
            "explicit",
            "source_named_by_user",
            SOURCE_AUTO_CONTINUE_THRESHOLD + 0.12,
            False,
            confidence_band="high",
            action="continue",
        )
    if entities and (_ACTIVITY.search(normalized) or _PROJECT.search(normalized)):
        candidates = _SOURCE_NAMES
        name = ", ".join(entity.title() for entity in entities)
        question = (
            f"Mình nhận diện entity/dự án '{name}' nhưng chưa chắc bạn muốn lấy từ nguồn nào. "
            "Bạn xác nhận giúp mình nguồn cần kiểm tra: Tasks, Jira, Gmail, Calendar, Discord, Google Sheets, Google Docs hay tất cả?"
        )
        return SourceRoutingDecision(
            entities, (), candidates, "entity_discovery", "project_activity_without_source",
            SOURCE_CONFIRM_THRESHOLD + 0.12,
            True,
            question,
            confidence_band="medium",
            action="confirm_source",
        )
    if semantic:
        return SourceRoutingDecision(
            entities,
            (),
            semantic,
            "semantic",
            "domain_vocabulary_without_provider",
            SOURCE_CONFIRM_THRESHOLD - 0.02,
            False,
            confidence_band="low",
            action="not_applicable",
        )
    return SourceRoutingDecision(
        entities,
        (),
        (),
        "undetermined",
        "no_project_source_affinity",
        0.35,
        False,
        confidence_band="low",
        action="not_applicable",
    )
