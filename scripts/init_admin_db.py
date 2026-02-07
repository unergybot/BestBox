"""
Initialize the admin database tables and create the default admin user.

Usage:
    python scripts/init_admin_db.py

Reads PostgreSQL connection details from environment variables:
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg


async def main():
    pool = await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "bestbox"),
        password=os.getenv("POSTGRES_PASSWORD", "bestbox"),
        database=os.getenv("POSTGRES_DB", "bestbox"),
    )

    # Run the SQL migration
    migration_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "migrations",
        "005_admin_rbac.sql",
    )
    with open(migration_path) as f:
        sql = f.read()

    async with pool.acquire() as conn:
        await conn.execute(sql)
    print("✅ Admin RBAC tables created")

    # Initialize admin tables and default user via the auth module
    from services.admin_auth import init_admin_tables
    await init_admin_tables(pool)
    print("✅ Default admin user created (if not exists)")

    await pool.close()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
