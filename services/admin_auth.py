"""
Admin authentication & authorization module.

Provides JWT-based auth for all /admin/* endpoints with role-based access control.
Roles: admin, engineer, viewer.

PostgreSQL tables: admin_users, audit_log (created by migrations/005_admin_rbac.sql).
"""

import os
import logging
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

import asyncpg

logger = logging.getLogger(__name__)

# JWT secret — MUST be set in production via environment variable
JWT_SECRET = os.getenv("ADMIN_JWT_SECRET", "bestbox-dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("ADMIN_JWT_EXPIRY_HOURS", "24"))

# Default admin credentials — created on first run
DEFAULT_ADMIN_USER = os.getenv("ADMIN_DEFAULT_USER", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "bestbox-admin")


class Role(str, Enum):
    ADMIN = "admin"
    ENGINEER = "engineer"
    VIEWER = "viewer"


# Permissions per role
ROLE_PERMISSIONS: Dict[str, set] = {
    "admin": {
        "upload", "view", "search", "delete", "reindex",
        "manage_users", "view_audit", "manage_collections", "manage_services",
    },
    "engineer": {
        "upload", "view", "search", "reindex",
    },
    "viewer": {
        "view", "search",
    },
}


def hash_password(password: str) -> str:
    """Hash a password with SHA-256 + random salt."""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored salt:hash."""
    if ":" not in stored_hash:
        return False
    salt, expected_hash = stored_hash.split(":", 1)
    actual_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return secrets.compare_digest(actual_hash, expected_hash)


def create_jwt_token(user_id: str, username: str, role: str) -> str:
    """Create a JWT token with user claims."""
    import json
    import base64
    import hmac

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=JWT_EXPIRY_HOURS)).timestamp()),
    }

    # Simple JWT implementation (header.payload.signature)
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": JWT_ALGORITHM, "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()

    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()

    signing_input = f"{header}.{payload_b64}"
    signature = hmac.new(
        JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()

    return f"{header}.{payload_b64}.{sig_b64}"


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a JWT token. Returns claims or None."""
    import json
    import base64
    import hmac

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, sig_b64 = parts

        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(
            JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256
        ).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_sig).rstrip(b"=").decode()

        if not hmac.compare_digest(sig_b64, expected_b64):
            return None

        # Decode payload (add padding)
        padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))

        # Check expiry
        if payload.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            return None

        return payload

    except Exception as e:
        logger.debug(f"JWT decode error: {e}")
        return None


def check_permission(role: str, permission: str) -> bool:
    """Check if a role has a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())


# ------------------------------------------------------------------
# OIDC integration (Authelia SSO)
# ------------------------------------------------------------------

OIDC_DISCOVERY_URL = os.getenv(
    "OIDC_DISCOVERY_URL",
    "http://localhost:9091/.well-known/openid-configuration",
)
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "bestbox-admin")
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "bestbox-secret")

_oidc_metadata_cache: Optional[Dict[str, Any]] = None
_oidc_cache_time: float = 0


async def get_oidc_metadata() -> Dict[str, Any]:
    """Fetch OIDC discovery metadata (cached for 5 minutes)."""
    global _oidc_metadata_cache, _oidc_cache_time
    import time as _time
    import aiohttp

    now = _time.time()
    if _oidc_metadata_cache and (now - _oidc_cache_time) < 300:
        return _oidc_metadata_cache

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                OIDC_DISCOVERY_URL, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    _oidc_metadata_cache = await resp.json()
                    _oidc_cache_time = now
                    return _oidc_metadata_cache
    except Exception as e:
        logger.warning(f"Failed to fetch OIDC metadata: {e}")

    return _oidc_metadata_cache or {}


async def verify_oidc_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify an OIDC access/id token from Authelia.

    Returns user claims ``{sub, username, role, groups, token_type}`` or ``None``.
    """
    try:
        from authlib.jose import JsonWebToken, JsonWebKey
        from authlib.jose.errors import JoseError
    except ImportError:
        logger.debug("authlib not installed – OIDC verification skipped")
        return None

    import aiohttp

    try:
        metadata = await get_oidc_metadata()
        jwks_uri = metadata.get("jwks_uri")
        if not jwks_uri:
            logger.error("OIDC metadata missing jwks_uri")
            return None

        async with aiohttp.ClientSession() as session:
            async with session.get(
                jwks_uri, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    return None
                jwks = await resp.json()

        jwt = JsonWebToken(["RS256"])
        claims = jwt.decode(token, JsonWebKey.import_key_set(jwks))
        claims.validate()

        username = claims.get("preferred_username") or claims.get("sub")
        groups = claims.get("groups", [])

        # Map Authelia groups → BestBox roles
        role = "viewer"
        if "admin" in groups:
            role = "admin"
        elif "engineer" in groups:
            role = "engineer"

        return {
            "sub": claims["sub"],
            "username": username,
            "role": role,
            "groups": groups,
            "token_type": "oidc",
        }

    except JoseError as e:
        logger.debug(f"OIDC token verification failed: {e}")
        return None
    except Exception as e:
        logger.error(f"OIDC verification error: {e}")
        return None


# ------------------------------------------------------------------
# Database operations
# ------------------------------------------------------------------

async def init_admin_tables(pool: asyncpg.Pool) -> None:
    """Create admin tables if they don't exist."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'engineer', 'viewer')),
                created_at TIMESTAMP DEFAULT NOW(),
                last_login TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                user_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
                action VARCHAR(50) NOT NULL,
                resource_type VARCHAR(50),
                resource_id VARCHAR(255),
                details JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Create default admin user if none exists
        existing = await conn.fetchval(
            "SELECT COUNT(*) FROM admin_users WHERE role = 'admin'"
        )
        if existing == 0:
            pw_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
            await conn.execute(
                """INSERT INTO admin_users (username, password_hash, role)
                   VALUES ($1, $2, 'admin')
                   ON CONFLICT (username) DO NOTHING""",
                DEFAULT_ADMIN_USER, pw_hash,
            )
            logger.info(f"Created default admin user: {DEFAULT_ADMIN_USER}")


async def authenticate_user(
    pool: asyncpg.Pool, username: str, password: str
) -> Optional[Dict[str, Any]]:
    """Authenticate user and return JWT token + user info, or None."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, password_hash, role FROM admin_users WHERE username = $1",
            username,
        )
        if not row:
            return None
        if not verify_password(password, row["password_hash"]):
            return None

        # Update last_login
        await conn.execute(
            "UPDATE admin_users SET last_login = NOW() WHERE id = $1",
            row["id"],
        )

        token = create_jwt_token(str(row["id"]), row["username"], row["role"])
        return {
            "token": token,
            "user": {
                "id": str(row["id"]),
                "username": row["username"],
                "role": row["role"],
            },
        }


async def list_users(pool: asyncpg.Pool) -> List[Dict[str, Any]]:
    """List all admin users."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, username, role, created_at, last_login
               FROM admin_users ORDER BY created_at DESC"""
        )
        return [
            {
                "id": str(r["id"]),
                "username": r["username"],
                "role": r["role"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "last_login": r["last_login"].isoformat() if r["last_login"] else None,
            }
            for r in rows
        ]


async def create_user(
    pool: asyncpg.Pool, username: str, password: str, role: str
) -> Dict[str, Any]:
    """Create a new admin user."""
    if role not in ("admin", "engineer", "viewer"):
        raise ValueError(f"Invalid role: {role}")
    pw_hash = hash_password(password)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO admin_users (username, password_hash, role)
               VALUES ($1, $2, $3) RETURNING id, username, role, created_at""",
            username, pw_hash, role,
        )
        return {
            "id": str(row["id"]),
            "username": row["username"],
            "role": row["role"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }


async def update_user_role(
    pool: asyncpg.Pool, user_id: str, role: str
) -> Optional[Dict[str, Any]]:
    """Update a user's role."""
    if role not in ("admin", "engineer", "viewer"):
        raise ValueError(f"Invalid role: {role}")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE admin_users SET role = $1 WHERE id = $2::uuid
               RETURNING id, username, role""",
            role, user_id,
        )
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "username": row["username"],
            "role": row["role"],
        }


async def delete_user(pool: asyncpg.Pool, user_id: str) -> bool:
    """Delete a user by ID."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM admin_users WHERE id = $1::uuid", user_id
        )
        return result == "DELETE 1"


async def log_audit(
    pool: asyncpg.Pool,
    user_id: Optional[str],
    action: str,
    resource_type: str = "",
    resource_id: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Write an entry to the audit log."""
    import json
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO audit_log (user_id, action, resource_type, resource_id, details)
                   VALUES ($1::uuid, $2, $3, $4, $5::jsonb)""",
                user_id if user_id else None,
                action,
                resource_type,
                resource_id,
                json.dumps(details) if details else None,
            )
    except Exception as e:
        logger.warning(f"Audit log write failed: {e}")


async def get_audit_log(
    pool: asyncpg.Pool, limit: int = 50, offset: int = 0
) -> List[Dict[str, Any]]:
    """Retrieve paginated audit log entries."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT a.id, a.user_id, u.username, a.action,
                      a.resource_type, a.resource_id, a.details, a.created_at
               FROM audit_log a
               LEFT JOIN admin_users u ON a.user_id = u.id
               ORDER BY a.created_at DESC
               LIMIT $1 OFFSET $2""",
            limit, offset,
        )
        return [
            {
                "id": r["id"],
                "user_id": str(r["user_id"]) if r["user_id"] else None,
                "username": r["username"],
                "action": r["action"],
                "resource_type": r["resource_type"],
                "resource_id": r["resource_id"],
                "details": dict(r["details"]) if r["details"] else None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
