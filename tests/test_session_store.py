"""Tests for session storage."""

import pytest

from services.session_store import SessionStore


class DummyConn:
    async def fetchrow(self, query, *args):
        return {"id": "00000000-0000-0000-0000-000000000000"}

    async def execute(self, query, *args):
        return None

    async def fetch(self, query, *args):
        return []


class DummyPool:
    def __init__(self):
        self.conn = DummyConn()

    async def acquire(self):
        return self.conn


class DummyAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummyPoolContext(DummyPool):
    def acquire(self):
        return DummyAcquire(self.conn)


@pytest.mark.asyncio
async def test_create_session_returns_id():
    store = SessionStore(DummyPoolContext())
    session_id = await store.create_session("user", "api")
    assert session_id == "00000000-0000-0000-0000-000000000000"


@pytest.mark.asyncio
async def test_list_sessions_returns_list():
    store = SessionStore(DummyPoolContext())
    sessions = await store.list_sessions()
    assert isinstance(sessions, list)
