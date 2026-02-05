import asyncio
import asyncpg
import os

async def migrate():
    print("Starting migration...")
    conn = await asyncpg.connect(
        user="bestbox",
        password="bestbox",
        database="bestbox",
        host="localhost",
        port=5432
    )
    
    print("Connected to DB.")
    
    schema = """
    CREATE TABLE IF NOT EXISTS sessions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id VARCHAR(255),
        channel VARCHAR(50),
        started_at TIMESTAMP DEFAULT NOW(),
        ended_at TIMESTAMP,
        message_count INT DEFAULT 0,
        status VARCHAR(20) DEFAULT 'active',
        rating VARCHAR(10),
        rating_note TEXT,
        metadata JSONB
    );

    CREATE TABLE IF NOT EXISTS session_messages (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
        role VARCHAR(20),
        content TEXT,
        reasoning_trace JSONB,
        tool_calls JSONB,
        tokens_prompt INT,
        tokens_completion INT,
        latency_ms INT,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at DESC);
    CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
    CREATE INDEX IF NOT EXISTS idx_messages_session ON session_messages(session_id);
    """
    
    try:
        await conn.execute(schema)
        print("✅ Migration executed successfully.")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
