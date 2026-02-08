-- Migration 006: Feedback table for detailed user feedback
-- Supplements the inline user_feedback column on conversation_log
-- with a dedicated table supporting comments and structured metadata.

CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    message_id VARCHAR(255),
    feedback_type VARCHAR(20) NOT NULL CHECK (feedback_type IN ('positive', 'negative')),
    comment TEXT,
    agent_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for dashboard queries
CREATE INDEX IF NOT EXISTS idx_feedback_session_id ON feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_feedback_agent ON feedback(agent_type);

-- Materialized view for daily feedback aggregation (Grafana queries)
CREATE MATERIALIZED VIEW IF NOT EXISTS feedback_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    feedback_type,
    agent_type,
    COUNT(*) AS count
FROM feedback
GROUP BY day, feedback_type, agent_type
ORDER BY day DESC;

-- Refresh function (call via cron or after batch inserts)
-- Example: REFRESH MATERIALIZED VIEW CONCURRENTLY feedback_daily;
