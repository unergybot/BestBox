#!/usr/bin/env python3
"""
Seed Troubleshooting PostgreSQL Tables

Sets up the text-to-SQL infrastructure:
1. Creates PostgreSQL tables (cases, issues, synonyms, knowledge, learnings)
2. Seeds synonym data for ASR term expansion
3. Optionally backfills data from existing Qdrant collections

Usage:
    python scripts/seed_troubleshooting_pg.py          # Create tables + seed synonyms
    python scripts/seed_troubleshooting_pg.py --backfill  # Also backfill from Qdrant
    python scripts/seed_troubleshooting_pg.py --reset     # Drop and recreate tables
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def get_pg_connection(database: str = "bestbox"):
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        database=database,
        user=os.getenv("POSTGRES_USER", "bestbox"),
        password=os.getenv("POSTGRES_PASSWORD", "bestbox"),
    )


def ensure_database_exists():
    """Ensure the bestbox database exists."""
    # Connect to default postgres database
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        database="postgres",
        user=os.getenv("POSTGRES_USER", "bestbox"),
        password=os.getenv("POSTGRES_PASSWORD", "bestbox"),
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

    try:
        with conn.cursor() as cur:
            # Check if database exists
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (os.getenv("POSTGRES_DB", "bestbox"),),
            )
            if not cur.fetchone():
                print(f"Creating database '{os.getenv('POSTGRES_DB', 'bestbox')}'...")
                cur.execute(f"CREATE DATABASE {os.getenv('POSTGRES_DB', 'bestbox')}")
                print("✅ Database created")
            else:
                print(f"✅ Database '{os.getenv('POSTGRES_DB', 'bestbox')}' exists")
    finally:
        conn.close()


def run_sql_file(conn, filepath: Path):
    """Execute SQL file."""
    print(f"   Running {filepath.name}...")
    with open(filepath, "r", encoding="utf-8") as f:
        sql = f.read()

    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print(f"   ✅ {filepath.name} completed")


def drop_tables(conn):
    """Drop all troubleshooting tables."""
    print("🗑️ Dropping existing tables...")
    with conn.cursor() as cur:
        # Drop in reverse order of dependencies
        tables = [
            "ts_query_log",
            "ts_learnings",
            "ts_knowledge_queries",
            "troubleshooting_synonyms",
            "troubleshooting_issues",
            "troubleshooting_cases",
        ]
        for table in tables:
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            print(f"   Dropped {table}")
    conn.commit()
    print("✅ Tables dropped")


def create_tables(conn):
    """Create all troubleshooting tables."""
    print("\n📊 Creating tables...")
    sql_dir = project_root / "services" / "troubleshooting" / "sql"

    # Run schema migration
    schema_file = sql_dir / "001_text_to_sql_schema.sql"
    if schema_file.exists():
        run_sql_file(conn, schema_file)
    else:
        print(f"   ❌ Schema file not found: {schema_file}")
        sys.exit(1)


def seed_synonyms(conn):
    """Seed synonym data."""
    print("\n🌱 Seeding synonyms...")
    sql_dir = project_root / "services" / "troubleshooting" / "sql"

    seed_file = sql_dir / "002_seed_synonyms.sql"
    if seed_file.exists():
        run_sql_file(conn, seed_file)
    else:
        print(f"   ❌ Seed file not found: {seed_file}")
        sys.exit(1)


def verify_tables(conn):
    """Verify tables were created correctly."""
    print("\n🔍 Verifying tables...")
    with conn.cursor() as cur:
        tables = [
            "troubleshooting_cases",
            "troubleshooting_issues",
            "troubleshooting_synonyms",
            "ts_knowledge_queries",
            "ts_learnings",
            "ts_query_log",
        ]

        for table in tables:
            cur.execute(
                f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = %s",
                (table,),
            )
            exists = cur.fetchone()[0] > 0
            if exists:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"   ✅ {table}: {count} rows")
            else:
                print(f"   ❌ {table}: NOT FOUND")


def backfill_from_qdrant():
    """Backfill PostgreSQL from Qdrant."""
    print("\n🔄 Backfilling from Qdrant...")

    from services.troubleshooting.data_sync import TroubleshootingDataSync

    sync = TroubleshootingDataSync()
    stats = sync.backfill_from_qdrant()

    print(f"\n📊 Backfill Results:")
    print(f"   Cases synced: {stats['cases_synced']}")
    print(f"   Issues synced: {stats['issues_synced']}")
    if stats["errors"]:
        print(f"   Errors: {len(stats['errors'])}")
        for error in stats["errors"][:5]:
            print(f"     - {error}")
        if len(stats["errors"]) > 5:
            print(f"     ... and {len(stats['errors']) - 5} more")


def main():
    parser = argparse.ArgumentParser(
        description="Seed Troubleshooting PostgreSQL Tables"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate all tables",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Backfill PostgreSQL from existing Qdrant data",
    )
    parser.add_argument(
        "--skip-synonyms",
        action="store_true",
        help="Skip seeding synonyms",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Troubleshooting PostgreSQL Setup")
    print("=" * 70)
    print()

    # Step 1: Ensure database exists
    print("🔌 Connecting to PostgreSQL...")
    ensure_database_exists()

    # Step 2: Connect to bestbox database
    conn = get_pg_connection()
    print(f"✅ Connected to PostgreSQL")

    try:
        # Step 3: Drop tables if reset requested
        if args.reset:
            drop_tables(conn)

        # Step 4: Create tables
        create_tables(conn)

        # Step 5: Seed synonyms
        if not args.skip_synonyms:
            seed_synonyms(conn)

        # Step 6: Verify
        verify_tables(conn)

        # Step 7: Backfill if requested
        if args.backfill:
            backfill_from_qdrant()

    finally:
        conn.close()

    print("\n" + "=" * 70)
    print("✅ Setup complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Run with --backfill to sync existing Qdrant data")
    print("  2. Test synonym expansion: SELECT * FROM troubleshooting_synonyms WHERE synonym = '毛边';")
    print()


if __name__ == "__main__":
    main()
