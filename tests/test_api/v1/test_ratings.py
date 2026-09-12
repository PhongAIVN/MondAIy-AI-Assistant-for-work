import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.db import SessionLocal
from src.models.app_rating import AppRating
from src.models.user import User
from src.services.auth import decode_token
from src.services.feedback_quality import FeedbackAssessment


@pytest.mark.asyncio
async def test_rating_requires_authentication(client):
    response = await client.post("/api/v1/ratings", json={"rating": 5, "feedback": "ok"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rating_accepts_feedback_and_awards_bonus(client):
    email = f"rating-{uuid.uuid4().hex[:10]}@example.com"
    registered = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = registered.json()["accessToken"]

    with patch(
        "src.api.ratings.assess_feedback_quality",
        AsyncMock(return_value=FeedbackAssessment(True, "Có trải nghiệm cụ thể.")),
    ):
        response = await client.post(
            "/api/v1/ratings",
            headers={"Authorization": f"Bearer {token}"},
            json={"rating": 4, "feedback": "Giao diện rõ ràng và dễ theo dõi công việc."},
        )

    assert response.status_code == 201
    assert response.json()["feedback"] == "Giao diện rõ ràng và dễ theo dõi công việc."
    assert response.json()["bonusQuestionsAwarded"] == 5
    user_id = int(decode_token(token, "access"))
    with SessionLocal() as db:
        assert db.get(User, user_id).llm_bonus_questions == 5
        assert db.query(AppRating).filter(AppRating.user_id == str(user_id)).count() == 1


@pytest.mark.asyncio
async def test_rating_rejects_repeated_feedback_without_duplicate_reward(client):
    email = f"rating-repeat-{uuid.uuid4().hex[:10]}@example.com"
    registered = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = registered.json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    feedback = "Giao diện rõ ràng và dễ theo dõi công việc."
    with patch(
        "src.api.ratings.assess_feedback_quality",
        AsyncMock(return_value=FeedbackAssessment(True, "Có trải nghiệm cụ thể.")),
    ):
        first = await client.post("/api/v1/ratings", headers=headers, json={"rating": 5, "feedback": feedback})
        second = await client.post("/api/v1/ratings", headers=headers, json={"rating": 5, "feedback": feedback})

    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_feedback_uses_strict_quality_gate_twice_then_only_requires_40_chars(client):
    email = f"rating-fallback-{uuid.uuid4().hex[:10]}@example.com"
    registered = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = registered.json()["accessToken"]
    classifier = AsyncMock(return_value=FeedbackAssessment(False, "Chưa đủ cụ thể.", "too_generic"))

    with patch("src.api.ratings.assess_feedback_quality", classifier):
        for index in range(2):
            response = await client.post(
                "/api/v1/ratings",
                headers={"Authorization": f"Bearer {token}"},
                json={"rating": 4, "feedback": f"Trải nghiệm lần {index} còn hơi khó dùng."},
            )
            assert response.status_code == 422
        too_short = await client.post(
            "/api/v1/ratings",
            headers={"Authorization": f"Bearer {token}"},
            json={"rating": 4, "feedback": "Feedback lần ba vẫn ngắn."},
        )
        accepted = await client.post(
            "/api/v1/ratings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "rating": 4,
                "feedback": "Feedback lần ba đủ dài nên được chấp nhận ngay lập tức.",
            },
        )

    assert too_short.status_code == 422
    assert "40 ký tự" in too_short.json()["detail"]
    assert accepted.status_code == 201
    assert classifier.await_count == 2

    user_id = int(decode_token(token, "access"))
    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user.feedback_attempts == 2
        assert user.feedback_quality_day is not None
        db.commit()


@pytest.mark.asyncio
async def test_feedback_quality_gate_resets_for_user_on_next_day(client):
    email = f"rating-reset-{uuid.uuid4().hex[:10]}@example.com"
    registered = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = registered.json()["accessToken"]
    user_id = int(decode_token(token, "access"))
    with SessionLocal() as db:
        user = db.get(User, user_id)
        user.feedback_quality_day = "2000-01-01"
        user.feedback_attempts = 2
        db.commit()

    classifier = AsyncMock(return_value=FeedbackAssessment(False, "Chưa đủ cụ thể.", "too_generic"))
    with patch("src.api.ratings.assess_feedback_quality", classifier):
        response = await client.post(
            "/api/v1/ratings",
            headers={"Authorization": f"Bearer {token}"},
            json={"rating": 4, "feedback": "Trải nghiệm hôm nay chưa ổn ở phần lịch."},
        )

    assert response.status_code == 422
    assert classifier.await_count == 1
    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user.feedback_attempts == 1
