"""Đường thoát cho installation PWA mắc kẹt trong service-worker cache cũ."""

import pytest


@pytest.mark.asyncio
async def test_pwa_recovery_public_no_store_and_clears_static_cache(client):
    response = await client.get("/api/v1/pwa/recover")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "no-store" in response.headers["cache-control"]
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert "navigator.serviceWorker.getRegistrations" in response.text
    assert "window.caches.delete" in response.text
    assert "localStorage.clear" not in response.text
    assert "sessionStorage.clear" not in response.text
    assert "window.location.replace('/api/v1/pwa/recover?clean=1&ts='" in response.text
    assert "navigator.serviceWorker.controller" in response.text
    assert "đóng hẳn mondaiy khỏi màn hình đa nhiệm" in response.text
    assert "window.location.replace('/briefing?pwaRecovered='" in response.text


@pytest.mark.asyncio
async def test_pwa_recovery_does_not_require_authentication(client):
    response = await client.get("/api/v1/pwa/recover")

    assert response.status_code == 200
    assert "Đang làm mới mondaiy" in response.text
