"""Small, fail-closed Hugging Face classifier client for mail triage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from src.config import Settings, get_settings


@dataclass(frozen=True)
class HfMailPrediction:
    label: str
    score: float
    source: str = "hf_xlmr"


def _labels(value: str) -> frozenset[str]:
    return frozenset(part.strip().casefold() for part in value.split(",") if part.strip())


def _input_text(item: dict[str, Any], max_chars: int) -> str:
    subject = str(item.get("subject") or "").strip()
    body = str(item.get("normalized_text") or item.get("text") or item.get("snippet") or "").strip()
    text = f"Subject: {subject}\n\n{body}" if subject else body
    return text[:max_chars]


def _parse_prediction(payload: Any) -> HfMailPrediction | None:
    if isinstance(payload, list) and payload and isinstance(payload[0], list):
        payload = payload[0]
    if not isinstance(payload, list) or not payload:
        return None
    candidates = [row for row in payload if isinstance(row, dict) and row.get("label") is not None]
    if not candidates:
        return None
    def score_of(value: dict[str, Any]) -> float:
        try:
            return float(value.get("score", 0.0))
        except (TypeError, ValueError):
            return -1.0

    row = max(candidates, key=score_of)
    try:
        score = float(row.get("score", 0.0))
    except (TypeError, ValueError):
        return None
    if not 0.0 <= score <= 1.0:
        return None
    return HfMailPrediction(str(row["label"]), score)


def classify_mail(item: dict[str, Any], settings: Settings | None = None) -> HfMailPrediction | None:
    settings = settings or get_settings()
    if not settings.hf_mail_filter_enabled or not settings.hf_mail_filter_token:
        return None
    endpoint = settings.hf_mail_filter_endpoint or (
        f"https://api-inference.huggingface.co/models/{settings.hf_mail_filter_model}"
    )
    try:
        response = httpx.post(
            endpoint,
            headers={"Authorization": f"Bearer {settings.hf_mail_filter_token}"},
            json={"inputs": _input_text(item, settings.hf_mail_filter_max_chars)},
            timeout=settings.hf_mail_filter_timeout_seconds,
        )
        response.raise_for_status()
        return _parse_prediction(response.json())
    except (httpx.HTTPError, ValueError, TypeError):
        return None


def apply_prediction(prediction: HfMailPrediction | None, *, settings: Settings | None = None) -> tuple[str, float, str] | None:
    if prediction is None:
        return None
    settings = settings or get_settings()
    if prediction.score < settings.hf_mail_filter_min_confidence:
        return None
    label = prediction.label.casefold().strip()
    if label in _labels(settings.hf_mail_filter_keep_labels):
        return "keep", prediction.score, "hf_keep"
    if label in _labels(settings.hf_mail_filter_drop_labels):
        return "drop", prediction.score, "hf_drop"
    return None
