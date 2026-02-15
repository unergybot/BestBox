-- LLM Configuration Tables
-- Migration: 006_llm_config
-- Created: 2026-02-14

-- Table: llm_configurations
-- Stores LLM provider configurations with encryption and audit trail
CREATE TABLE IF NOT EXISTS llm_configurations (
    id SERIAL PRIMARY KEY,

    -- Provider config
    provider VARCHAR(50) NOT NULL,  -- 'local_vllm', 'nvidia', 'openrouter'
    is_active BOOLEAN NOT NULL DEFAULT false,

    -- Connection details
    base_url VARCHAR(500),
    api_key_encrypted TEXT,
    model VARCHAR(200) NOT NULL,

    -- LLM parameters (JSONB for flexibility)
    parameters JSONB DEFAULT '{
        "temperature": 0.7,
        "max_tokens": 4096,
        "streaming": true,
        "max_retries": 2
    }'::jsonb,

    -- Audit trail
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

-- Constraint: only one active config (partial unique index)
CREATE UNIQUE INDEX IF NOT EXISTS ux_llm_config_one_active
    ON llm_configurations (is_active)
    WHERE is_active = true;

-- Index for fast active config lookup
CREATE INDEX IF NOT EXISTS idx_llm_config_active ON llm_configurations(is_active)
    WHERE is_active = true;

-- Table: llm_provider_models
-- Predefined model lists for UI dropdowns
CREATE TABLE IF NOT EXISTS llm_provider_models (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    model_id VARCHAR(200) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    is_recommended BOOLEAN DEFAULT false,
    sort_order INT DEFAULT 0,

    UNIQUE(provider, model_id)
);

-- Seed default configuration (local vLLM)
INSERT INTO llm_configurations
    (provider, is_active, base_url, model, created_by)
SELECT 'local_vllm', true, 'http://localhost:8001/v1', 'qwen3-30b', 'system'
WHERE NOT EXISTS (
    SELECT 1 FROM llm_configurations WHERE is_active = true
);

-- Seed provider models
INSERT INTO llm_provider_models
    (provider, model_id, display_name, is_recommended, sort_order)
VALUES
    -- Local vLLM
    ('local_vllm', 'qwen3-30b', 'Qwen3 30B (Local)', true, 1),

    -- NVIDIA API
    ('nvidia', 'minimaxai/minimax-m2', 'Minimax M2', true, 1),
    ('nvidia', 'meta/llama-3.1-nemotron-70b-instruct', 'Llama 3.1 Nemotron 70B', false, 2),
    ('nvidia', 'nvidia/llama-3.1-nemotron-ultra-253b', 'Nemotron Ultra 253B', false, 3),

    -- OpenRouter
    ('openrouter', 'anthropic/claude-3.5-sonnet', 'Claude 3.5 Sonnet', true, 1),
    ('openrouter', 'openai/gpt-4o', 'GPT-4o', false, 2),
    ('openrouter', 'google/gemini-pro-1.5', 'Gemini Pro 1.5', false, 3),
    ('openrouter', 'meta-llama/llama-3.3-70b-instruct', 'Llama 3.3 70B', false, 4)
ON CONFLICT (provider, model_id) DO NOTHING;

-- Optional RBAC migration compatibility: only if table exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'permissions'
    ) THEN
        INSERT INTO permissions (name, description)
        VALUES ('manage_settings', 'Modify system settings including LLM configuration')
        ON CONFLICT (name) DO NOTHING;
    END IF;
END $$;
