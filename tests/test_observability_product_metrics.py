from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

import pytest
from prometheus_client import generate_latest
from prometheus_client.parser import text_string_to_metric_families
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from src import observability
from src.models.app_rating import AppRating
from src.observability import _collect_rating_metrics


def _sample_value(name: str, **labels: str) -> float | None:
    payload = generate_latest().decode("utf-8")
    for family in text_string_to_metric_families(payload):
        for sample in family.samples:
            if sample.name == name and all(sample.labels.get(key) == value for key, value in labels.items()):
                return float(sample.value)
    return None


def test_rating_metrics_reflect_db_without_pii_and_clear_stale_series(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    AppRating.__table__.create(engine)
    now = datetime(2026, 8, 28, 12, tzinfo=UTC)
    sentinel = "thai.rating@example.test"
    user_id_sentinel = "user-id-must-not-be-a-label"
    with Session(engine) as db:
        db.add_all(
            [
                AppRating(user_id=user_id_sentinel, rating=1, feedback=sentinel, trigger="action_count", created_at=now - timedelta(days=31)),
                AppRating(user_id="u2", rating=3, feedback="safe", trigger="manual", created_at=now - timedelta(days=30)),
                AppRating(user_id="u3", rating=5, feedback=None, trigger="time_elapsed", created_at=now),
                AppRating(user_id="u4", rating=4, feedback=sentinel, trigger=sentinel, created_at=now),
                AppRating(user_id="u5", rating=9, feedback=sentinel, trigger="manual", created_at=now),
            ]
        )
        db.commit()

        with caplog.at_level(logging.WARNING, logger="src.observability"):
            _collect_rating_metrics(db, AppRating, now=now)

        assert _sample_value("p004_product_rating_count", rating="1") == 1
        assert _sample_value("p004_product_rating_count", rating="3") == 1
        assert _sample_value("p004_product_rating_count", rating="4") == 1
        assert _sample_value("p004_product_rating_count", rating="5") == 1
        assert _sample_value("p004_product_rating_count", rating="9") is None
        assert _sample_value("p004_product_rating_avg") == pytest.approx(3.25)
        assert _sample_value("p004_product_rating_avg_30d") == pytest.approx(4.0)
        assert _sample_value("p004_product_ratings_by_trigger", trigger="action_count") == 1
        assert _sample_value("p004_product_ratings_by_trigger", trigger="manual") == 1
        assert _sample_value("p004_product_ratings_by_trigger", trigger="time_elapsed") == 1
        assert _sample_value("p004_product_ratings_by_trigger", trigger=sentinel) is None
        assert _sample_value("p004_product_rating_last_timestamp_seconds") == now.timestamp()
        assert sentinel not in generate_latest().decode("utf-8")
        assert user_id_sentinel not in generate_latest().decode("utf-8")
        assert any("rating ngoài allowlist" in record.getMessage() for record in caplog.records)
        assert any("trigger ngoài allowlist" in record.getMessage() for record in caplog.records)

        db.execute(delete(AppRating))
        db.commit()
        _collect_rating_metrics(db, AppRating, now=now)

    assert _sample_value("p004_product_rating_count", rating="1") is None
    assert _sample_value("p004_product_ratings_by_trigger", trigger="manual") is None
    assert _sample_value("p004_product_rating_avg") is None
    assert _sample_value("p004_product_rating_avg_30d") is None
    assert _sample_value("p004_product_rating_last_timestamp_seconds") is None


@pytest.mark.parametrize("case", ["old-only", "invalid-only"], ids=["old-only", "invalid-only"])
def test_rating_scalar_metrics_omit_empty_time_scope(case: str) -> None:
    engine = create_engine("sqlite:///:memory:")
    AppRating.__table__.create(engine)
    now = datetime(2026, 8, 28, 12, tzinfo=UTC)
    with Session(engine) as db:
        if case == "invalid-only":
            db.add(AppRating(user_id="warm", rating=5, trigger="manual", created_at=now))
            db.commit()
            _collect_rating_metrics(db, AppRating, now=now)
            db.execute(delete(AppRating))
        db.add(
            AppRating(
                user_id="test-user",
                rating=2 if case == "old-only" else 9,
                trigger="manual",
                created_at=now - timedelta(days=31),
            )
        )
        db.commit()

        _collect_rating_metrics(db, AppRating, now=now)

        if case == "old-only":
            assert _sample_value("p004_product_rating_avg") == 2
            assert _sample_value("p004_product_rating_avg_30d") is None
            assert _sample_value("p004_product_rating_last_timestamp_seconds") == (now - timedelta(days=31)).timestamp()
        else:
            assert _sample_value("p004_product_rating_avg") is None
            assert _sample_value("p004_product_rating_avg_30d") is None
            assert _sample_value("p004_product_rating_last_timestamp_seconds") is None

        db.execute(delete(AppRating))
        db.commit()
        _collect_rating_metrics(db, AppRating, now=now)


@pytest.mark.parametrize(
    "contents",
    [
        None,
        "{broken",
        '{"generated_at":"bad","components":{}}',
        '{"generated_at":1777777777,"components":{"backend":81.0}}',
    ],
)
def test_coverage_metrics_disappear_when_summary_is_missing_or_corrupt(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    contents: str | None,
) -> None:
    summary = tmp_path / "coverage-summary.json"
    summary.write_text(
        json.dumps({"generated_at": 1_777_777_777, "components": {"backend": 81.0, "agent": 72.5}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(observability, "_COVERAGE_SUMMARY_PATH", summary)
    assert _sample_value("p004_test_coverage_percent", component="backend") == 81.0
    assert _sample_value("p004_test_coverage_percent", component="agent") == 72.5
    assert _sample_value("p004_test_coverage_updated_timestamp_seconds") == 1_777_777_777

    if contents is None:
        summary.unlink()
    else:
        summary.write_text(contents, encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="src.observability"):
        assert _sample_value("p004_test_coverage_percent", component="backend") is None
        assert _sample_value("p004_test_coverage_updated_timestamp_seconds") is None
    assert any("Không đọc được coverage summary" in record.getMessage() for record in caplog.records)


def test_coverage_component_label_is_allowlisted(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sentinel = "thai.coverage@example.test"
    summary = tmp_path / "coverage-summary.json"
    summary.write_text(
        json.dumps(
            {
                "generated_at": 1_777_777_777,
                "components": {"backend": 81.0, "agent": 72.5, sentinel: 99.0},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(observability, "_COVERAGE_SUMMARY_PATH", summary)

    with caplog.at_level(logging.WARNING, logger="src.observability"):
        scrape = generate_latest().decode("utf-8")

    assert sentinel not in scrape
    assert any("component ngoài allowlist" in record.getMessage() for record in caplog.records)
