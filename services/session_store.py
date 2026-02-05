"""
Session store for BestBox agent conversations.

Persists session metadata and messages (including ReAct traces) to PostgreSQL.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)


class SessionStore:
    """PostgreSQL-backed session store."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    @classmethod
    async def create(cls) -> "SessionStore":
        """Create a SessionStore with a new connection pool."""
        pool = await asyncpg.create_pool(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "bestbox"),
            password=os.getenv("POSTGRES_PASSWORD", "bestbox"),
            database=os.getenv("POSTGRES_DB", "bestbox"),
            min_size=1,
            max_size=5,
        )
        return cls(pool)

    async def create_session(self, user_id: str, channel: str) -> str:
        """Create a new session and return session_id."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO sessions (user_id, channel)
                VALUES ($1, $2)
                RETURNING id
                """,
                user_id,
                channel,
            )
            return str(row["id"])

    async def ensure_session(self, session_id: str, user_id: str, channel: str) -> None:
        """Ensure a session exists, creating it if necessary."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sessions (id, user_id, channel)
                VALUES ($1, $2, $3)
                ON CONFLICT (id) DO NOTHING
                """,
                session_id,
                user_id,
                channel,
            )

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        reasoning_trace: Optional[List[Dict[str, Any]]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a message to a session."""
        metrics = metrics or {}
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO session_messages (
                    session_id, role, content, reasoning_trace, tool_calls,
                    tokens_prompt, tokens_completion, latency_ms
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                session_id,
                role,
                content,
                json.dumps(reasoning_trace) if reasoning_trace else None,
                json.dumps(tool_calls) if tool_calls else None,
                metrics.get("tokens_prompt"),
                metrics.get("tokens_completion"),
                metrics.get("latency_ms"),
            )
            await conn.execute(
                """
                UPDATE sessions
                SET message_count = message_count + 1,
                    ended_at = NULL,
                    status = 'active'
                WHERE id = $1
                """,
                session_id,
            )

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get session metadata with all messages."""
        async with self._pool.acquire() as conn:
            session = await conn.fetchrow(
                """
                SELECT * FROM sessions WHERE id = $1
                """,
                session_id,
            )
            if not session:
                return {}

            messages = await conn.fetch(
                """
                SELECT * FROM session_messages
                WHERE session_id = $1
                ORDER BY created_at ASC
                """,
                session_id,
            )

        return {
            **dict(session),
            "messages": [dict(row) for row in messages],
        }

    async def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List sessions for admin view."""
        filters = []
        params: List[Any] = []

        if user_id:
            params.append(user_id)
            filters.append(f"user_id = ${len(params)}")
        if status:
            params.append(status)
            filters.append(f"status = ${len(params)}")

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        params.extend([limit, offset])

        query = f"""
            SELECT * FROM sessions
            {where_clause}
            ORDER BY started_at DESC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [dict(row) for row in rows]

    async def update_session_status(self, session_id: str, status: str) -> None:
        """Update session status."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE sessions
                SET status = $1, ended_at = CASE WHEN $1 = 'completed' THEN NOW() ELSE ended_at END
                WHERE id = $2
                """,
                status,
                session_id,
            )

    async def add_rating(self, session_id: str, rating: str, note: Optional[str]) -> None:
        """Store a rating on a session."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE sessions
                SET rating = $1, rating_note = $2
                WHERE id = $3
                """,
                rating,
                note,
                session_id,
            )

    async def close(self) -> None:
        """Close underlying pool."""
        await self._pool.close()
