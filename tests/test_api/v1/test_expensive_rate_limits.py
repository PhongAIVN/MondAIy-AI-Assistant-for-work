"""Observable regression tests for distributed limits on expensive/public routes."""

from unittest.mock import patch

import pytest

from src.services import oauth_state


@pytest.mark.asyncio
async def test_oauth_start_is_rate_limited_by_ip(client):
    intent = oauth_state.sign_intent("123", "discord", "https://frontend.example/sources")
    with patch(
        "src.api.connections.discord.build_authorize_url",
        return_value="https://discord.example/authorize",
    ):
        responses = [
            await client.get(
                "/api/v1/connections/discord/start",
                params={"intent": intent},
                follow_redirects=False,
            )
            for _ in range(21)
        ]

    assert all(response.status_code == 307 for response in responses[:20])
    assert responses[0].headers["location"] == "https://discord.example/authorize"
    assert responses[-1].status_code == 429
