"""Tests for admin API endpoints."""

import os
from fastapi.testclient import TestClient

import services.agent_api as agent_api


class DummySessionStore:
    async def list_sessions(self, *args, **kwargs):
        return [{"id": "session-1"}]

    async def get_session(self, session_id: str):
        return {"id": session_id, "messages": []}

    async def add_rating(self, session_id: str, rating: str, note: str):
        return None


def test_admin_endpoints(monkeypatch):
    os.environ["ADMIN_TOKEN"] = "test-token"
    os.environ["SESSION_STORE_ENABLED"] = "false"
    client = TestClient(agent_api.app)
    monkeypatch.setattr(agent_api, "session_store", DummySessionStore())

    list_resp = client.get("/admin/sessions", headers={"admin-token": "test-token"})
    assert list_resp.status_code == 200

    detail_resp = client.get("/admin/sessions/session-1", headers={"admin-token": "test-token"})
    assert detail_resp.status_code == 200

    rating_resp = client.post(
        "/admin/sessions/session-1/rating",
        headers={"admin-token": "test-token"},
        json={"rating": "good"},
    )
    assert rating_resp.status_code == 200
