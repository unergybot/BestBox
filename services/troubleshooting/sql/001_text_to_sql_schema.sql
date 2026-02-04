-- Text-to-SQL Integration Schema for BestBox Troubleshooting
-- Migration 001: Core tables for hybrid search

-- Enable pgvector extension for embeddings (optional - may not be available)
-- If using standard PostgreSQL image, this will fail silently
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pgvector extension not available - embedding columns will not work';
END
$$;

-- ============================================================================
-- Core Tables
-- ============================================================================

-- Cases (one per Excel file)
CREATE TABLE IF NOT EXISTS troubleshooting_cases (
    id SERIAL PRIMARY KEY,
    case_id VARCHAR(100) UNIQUE NOT NULL,
    part_number VARCHAR(50),
    internal_number VARCHAR(50),
    mold_type VARCHAR(100),
    material VARCHAR(100),
    color VARCHAR(50),
    total_issues INTEGER DEFAULT 0,
    source_file TEXT,
    -- VLM enrichment fields
    vlm_processed BOOLEAN DEFAULT FALSE,
    vlm_summary TEXT,
    vlm_confidence FLOAT DEFAULT 0.0,
    key_insights TEXT[],
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Issues (one per problem/solution)
CREATE TABLE IF NOT EXISTS troubleshooting_issues (
    id SERIAL PRIMARY KEY,
    issue_id VARCHAR(150) UNIQUE NOT NULL,
    case_id VARCHAR(100) REFERENCES troubleshooting_cases(case_id) ON DELETE CASCADE,
    issue_number INTEGER NOT NULL,
    excel_row INTEGER,
    trial_version VARCHAR(10),  -- T0, T1, T2
    category VARCHAR(100),
    problem TEXT NOT NULL,
    solution TEXT,
    result_t1 VARCHAR(20),
    result_t2 VARCHAR(20),
    cause_classification VARCHAR(100),
    defect_types TEXT[],
    -- VLM enrichment fields
    vlm_processed BOOLEAN DEFAULT FALSE,
    vlm_confidence FLOAT DEFAULT 0.0,
    severity VARCHAR(20),
    tags TEXT[],
    key_insights TEXT[],
    suggested_actions TEXT[],
    has_images BOOLEAN DEFAULT FALSE,
    image_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- Synonym System for ASR Term Expansion
-- ============================================================================

-- Synonyms for ASR term expansion
CREATE TABLE IF NOT EXISTS troubleshooting_synonyms (
    id SERIAL PRIMARY KEY,
    canonical_term VARCHAR(100) NOT NULL,
    synonym VARCHAR(100) NOT NULL,
    term_type VARCHAR(50) DEFAULT 'defect',  -- defect, material, process, mold
    confidence FLOAT DEFAULT 1.0,
    source VARCHAR(50) DEFAULT 'manual',  -- manual, learned, asr
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(canonical_term, synonym)
);

-- Index for fast synonym lookups
CREATE INDEX IF NOT EXISTS idx_synonyms_synonym ON troubleshooting_synonyms(synonym);
CREATE INDEX IF NOT EXISTS idx_synonyms_canonical ON troubleshooting_synonyms(canonical_term);
CREATE INDEX IF NOT EXISTS idx_synonyms_term_type ON troubleshooting_synonyms(term_type);

-- ============================================================================
-- Text-to-SQL Knowledge Base
-- ============================================================================

-- Validated queries (knowledge base for similar pattern matching)
CREATE TABLE IF NOT EXISTS ts_knowledge_queries (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    question TEXT NOT NULL,
    sql_query TEXT NOT NULL,
    tables_used TEXT[],
    summary TEXT,
    data_quality_notes TEXT,
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    embedding JSONB,  -- Store as JSONB for compatibility (use vector type if pgvector available)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for embedding search (only works with pgvector)
-- CREATE INDEX IF NOT EXISTS idx_knowledge_queries_embedding
-- ON ts_knowledge_queries USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Learnings (error patterns, type gotchas, user corrections)
CREATE TABLE IF NOT EXISTS ts_learnings (
    id SERIAL PRIMARY KEY,
    title VARCHAR(300) NOT NULL,
    learning TEXT NOT NULL,
    learning_type VARCHAR(50),  -- error_pattern, type_gotcha, user_correction, date_format
    tables_affected TEXT[],
    embedding JSONB,  -- Store as JSONB for compatibility (use vector type if pgvector available)
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for learnings
CREATE INDEX IF NOT EXISTS idx_learnings_type ON ts_learnings(learning_type);

-- ============================================================================
-- Query Logging for Analysis
-- ============================================================================

-- Log all text-to-SQL queries for analysis and improvement
CREATE TABLE IF NOT EXISTS ts_query_log (
    id SERIAL PRIMARY KEY,
    original_query TEXT NOT NULL,
    expanded_query TEXT,
    intent_classification VARCHAR(20),  -- STRUCTURED, SEMANTIC, HYBRID
    generated_sql TEXT,
    sql_valid BOOLEAN,
    sql_error TEXT,
    execution_time_ms INTEGER,
    result_count INTEGER,
    user_feedback VARCHAR(20),  -- positive, negative, null
    session_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for query analysis
CREATE INDEX IF NOT EXISTS idx_query_log_intent ON ts_query_log(intent_classification);
CREATE INDEX IF NOT EXISTS idx_query_log_created ON ts_query_log(created_at);

-- ============================================================================
-- Indexes for Common Queries
-- ============================================================================

-- Cases indexes
CREATE INDEX IF NOT EXISTS idx_cases_part_number ON troubleshooting_cases(part_number);
CREATE INDEX IF NOT EXISTS idx_cases_material ON troubleshooting_cases(material);
CREATE INDEX IF NOT EXISTS idx_cases_created ON troubleshooting_cases(created_at);

-- Issues indexes
CREATE INDEX IF NOT EXISTS idx_issues_case_id ON troubleshooting_issues(case_id);
CREATE INDEX IF NOT EXISTS idx_issues_trial_version ON troubleshooting_issues(trial_version);
CREATE INDEX IF NOT EXISTS idx_issues_result_t1 ON troubleshooting_issues(result_t1);
CREATE INDEX IF NOT EXISTS idx_issues_result_t2 ON troubleshooting_issues(result_t2);
CREATE INDEX IF NOT EXISTS idx_issues_defect_types ON troubleshooting_issues USING gin(defect_types);
CREATE INDEX IF NOT EXISTS idx_issues_severity ON troubleshooting_issues(severity);

-- ============================================================================
-- Trigger for updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to tables with updated_at
DROP TRIGGER IF EXISTS update_cases_updated_at ON troubleshooting_cases;
CREATE TRIGGER update_cases_updated_at
    BEFORE UPDATE ON troubleshooting_cases
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_issues_updated_at ON troubleshooting_issues;
CREATE TRIGGER update_issues_updated_at
    BEFORE UPDATE ON troubleshooting_issues
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_queries_updated_at ON ts_knowledge_queries;
CREATE TRIGGER update_queries_updated_at
    BEFORE UPDATE ON ts_knowledge_queries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
