-- BestBox Observability Tables Migration
-- Creates tables for user session tracking and conversation audit logging

-- User session tracking
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id UUID PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    started_at TIMESTAMP DEFAULT NOW(),
    last_active_at TIMESTAMP DEFAULT NOW(),
    total_messages INT DEFAULT 0,
    agents_used JSONB DEFAULT '{}',  -- {"erp": 5, "crm": 2, "itops": 1}
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON user_sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_last_active ON user_sessions(last_active_at DESC);

-- Conversation audit log
CREATE TABLE IF NOT EXISTS conversation_log (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES user_sessions(session_id),
    timestamp TIMESTAMP DEFAULT NOW(),
    user_message TEXT NOT NULL,
    agent_response TEXT NOT NULL,
    agent_type VARCHAR(50) NOT NULL,
    tool_calls JSONB DEFAULT '[]',  -- [{"tool": "search_kb", "args": {...}, "result": {...}}]
    latency_ms INT NOT NULL,
    confidence FLOAT,
    user_feedback VARCHAR(20),  -- 'positive', 'negative', null
    trace_id VARCHAR(255)  -- Links to Jaeger trace for debugging
);

CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversation_log(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversation_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_agent ON conversation_log(agent_type);
CREATE INDEX IF NOT EXISTS idx_conversations_feedback ON conversation_log(user_feedback) WHERE user_feedback IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_conversations_trace ON conversation_log(trace_id) WHERE trace_id IS NOT NULL;

-- Grant permissions (if bestbox user exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bestbox') THEN
        GRANT ALL PRIVILEGES ON TABLE user_sessions TO bestbox;
        GRANT ALL PRIVILEGES ON TABLE conversation_log TO bestbox;
        GRANT USAGE, SELECT ON SEQUENCE conversation_log_id_seq TO bestbox;
    END IF;
END
$$;

-- Summary
DO $$
BEGIN
    RAISE NOTICE 'Observability tables created successfully!';
    RAISE NOTICE '- user_sessions: Track user session metadata';
    RAISE NOTICE '- conversation_log: Complete audit trail of all conversations';
END
$$;
