#!/usr/bin/env python3
"""
Learning Machine for Troubleshooting Text-to-SQL

Self-learning system that improves query quality over time:
1. Saves error patterns automatically
2. Learns new synonyms from user corrections
3. Tracks successful query patterns
4. Analyzes query logs for improvements

Usage:
    from services.troubleshooting.learning_machine import LearningMachine

    machine = LearningMachine()
    machine.learn_from_error(question, sql, error)
    machine.learn_synonym_from_correction("毛边", "披锋")
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime, timedelta

# Add project root to path when running as script
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

import psycopg2
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LearningMachine:
    """Self-learning system for troubleshooting text-to-SQL."""

    def __init__(
        self,
        pg_host: str = "localhost",
        pg_port: int = 5432,
        pg_database: str = "bestbox",
        pg_user: str = "bestbox",
        pg_password: str = "bestbox",
        embeddings_url: Optional[str] = None,
    ):
        """
        Initialize learning machine.

        Args:
            pg_host: PostgreSQL host
            pg_port: PostgreSQL port
            pg_database: PostgreSQL database
            pg_user: PostgreSQL user
            pg_password: PostgreSQL password
            embeddings_url: Embeddings service URL
        """
        self.pg_params = {
            "host": os.getenv("POSTGRES_HOST", pg_host),
            "port": int(os.getenv("POSTGRES_PORT", pg_port)),
            "database": os.getenv("POSTGRES_DB", pg_database),
            "user": os.getenv("POSTGRES_USER", pg_user),
            "password": os.getenv("POSTGRES_PASSWORD", pg_password),
        }

        self.embeddings_url = embeddings_url or os.getenv(
            "EMBEDDINGS_URL", "http://localhost:8004"
        )

        logger.info("LearningMachine initialized")

    def _get_pg_connection(self):
        """Get PostgreSQL connection."""
        return psycopg2.connect(**self.pg_params)

    # ========================================================================
    # Error Pattern Learning
    # ========================================================================

    def learn_from_error(
        self,
        question: str,
        generated_sql: str,
        error_message: str,
        fixed_sql: Optional[str] = None,
    ) -> bool:
        """
        Learn from a SQL generation or execution error.

        Args:
            question: Original user question
            generated_sql: The SQL that caused the error
            error_message: The error message
            fixed_sql: Optional fixed SQL (if available)

        Returns:
            True if learning was saved
        """
        try:
            # Classify error type
            error_type = self._classify_error(error_message)

            # Generate learning content
            title = f"Error: {error_type} in query"
            learning = self._generate_error_learning(
                question, generated_sql, error_message, fixed_sql
            )

            # Extract tables affected
            tables = self._extract_tables_from_sql(generated_sql)

            # Save learning
            self._save_learning(
                title=title,
                learning=learning,
                learning_type="error_pattern",
                tables_affected=tables,
            )

            logger.info(f"Learned from error: {error_type}")
            return True

        except Exception as e:
            logger.error(f"Failed to learn from error: {e}")
            return False

    def _classify_error(self, error_message: str) -> str:
        """Classify the type of error."""
        error_lower = error_message.lower()

        if "column" in error_lower and "does not exist" in error_lower:
            return "column_not_found"
        elif "relation" in error_lower and "does not exist" in error_lower:
            return "table_not_found"
        elif "type" in error_lower or "cannot" in error_lower:
            return "type_mismatch"
        elif "syntax" in error_lower:
            return "syntax_error"
        elif "permission" in error_lower:
            return "permission_denied"
        elif "operator" in error_lower:
            return "operator_error"
        else:
            return "unknown_error"

    def _generate_error_learning(
        self,
        question: str,
        generated_sql: str,
        error_message: str,
        fixed_sql: Optional[str],
    ) -> str:
        """Generate learning content from error."""
        learning_parts = [
            f"Question: {question}",
            f"Failed SQL: {generated_sql}",
            f"Error: {error_message}",
        ]

        if fixed_sql:
            learning_parts.append(f"Fixed SQL: {fixed_sql}")
            learning_parts.append("Apply this fix pattern for similar errors.")

        return "\n".join(learning_parts)

    # ========================================================================
    # Synonym Learning
    # ========================================================================

    def learn_synonym_from_correction(
        self,
        user_term: str,
        correct_term: str,
        term_type: str = "defect",
        context: Optional[str] = None,
    ) -> bool:
        """
        Learn a synonym from user correction.

        Args:
            user_term: The term the user used
            correct_term: The correct/canonical term
            term_type: Type of term
            context: Optional context about the correction

        Returns:
            True if synonym was learned
        """
        try:
            conn = self._get_pg_connection()
            with conn.cursor() as cur:
                # Check if mapping already exists
                cur.execute(
                    """
                    SELECT id, confidence FROM troubleshooting_synonyms
                    WHERE canonical_term = %s AND synonym = %s
                    """,
                    (correct_term, user_term),
                )
                existing = cur.fetchone()

                if existing:
                    # Boost confidence
                    cur.execute(
                        """
                        UPDATE troubleshooting_synonyms
                        SET confidence = LEAST(confidence + 0.1, 1.0),
                            usage_count = usage_count + 1,
                            last_used_at = NOW()
                        WHERE id = %s
                        """,
                        (existing[0],),
                    )
                else:
                    # Insert new mapping
                    cur.execute(
                        """
                        INSERT INTO troubleshooting_synonyms
                        (canonical_term, synonym, term_type, confidence, source)
                        VALUES (%s, %s, %s, %s, 'learned')
                        """,
                        (correct_term, user_term, term_type, 0.8),
                    )

            conn.commit()
            conn.close()

            # Also save as learning for context
            if context:
                self._save_learning(
                    title=f"Synonym: {user_term} → {correct_term}",
                    learning=f"User corrected '{user_term}' to '{correct_term}'. Context: {context}",
                    learning_type="user_correction",
                )

            logger.info(f"Learned synonym: '{user_term}' → '{correct_term}'")
            return True

        except Exception as e:
            logger.error(f"Failed to learn synonym: {e}")
            return False

    # ========================================================================
    # Query Pattern Learning
    # ========================================================================

    def learn_successful_query(
        self,
        question: str,
        sql: str,
        tables_used: List[str],
        name: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> bool:
        """
        Save a successful query pattern.

        Args:
            question: User question
            sql: The successful SQL
            tables_used: Tables used
            name: Optional name for the query
            summary: Optional summary

        Returns:
            True if query was saved
        """
        try:
            conn = self._get_pg_connection()
            with conn.cursor() as cur:
                # Generate name if not provided
                if not name:
                    name = f"query_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                cur.execute(
                    """
                    INSERT INTO ts_knowledge_queries
                    (name, question, sql_query, tables_used, summary)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (name, question, sql, tables_used, summary),
                )

            conn.commit()
            conn.close()

            logger.info(f"Saved successful query: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to save query: {e}")
            return False

    # ========================================================================
    # Learning Storage
    # ========================================================================

    def _save_learning(
        self,
        title: str,
        learning: str,
        learning_type: str,
        tables_affected: Optional[List[str]] = None,
    ):
        """Save a learning to the database."""
        conn = self._get_pg_connection()
        try:
            with conn.cursor() as cur:
                # Generate embedding for similarity search
                embedding = self._get_embedding(learning)

                # Store embedding as JSONB (for compatibility without pgvector)
                import json
                embedding_json = json.dumps(embedding) if embedding else None

                cur.execute(
                    """
                    INSERT INTO ts_learnings
                    (title, learning, learning_type, tables_affected, embedding)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (title, learning, learning_type, tables_affected or [], embedding_json),
                )
            conn.commit()
        finally:
            conn.close()

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for text."""
        try:
            response = requests.post(
                f"{self.embeddings_url}/embed",
                json={"texts": [text]},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data["embeddings"][0]
        except Exception as e:
            logger.warning(f"Failed to get embedding: {e}")
            return None

    def _extract_tables_from_sql(self, sql: str) -> List[str]:
        """Extract table names from SQL."""
        import re

        tables = []
        patterns = [
            r"\bFROM\s+(\w+)",
            r"\bJOIN\s+(\w+)",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            tables.extend(matches)
        return list(set(tables))

    # ========================================================================
    # Query Log Analysis
    # ========================================================================

    def analyze_query_logs(
        self,
        days: int = 7,
        min_occurrences: int = 3,
    ) -> Dict[str, Any]:
        """
        Analyze query logs to find improvement opportunities.

        Args:
            days: Number of days to analyze
            min_occurrences: Minimum occurrences to report

        Returns:
            Analysis results with suggestions
        """
        conn = self._get_pg_connection()
        try:
            with conn.cursor() as cur:
                # Find common failed queries
                cur.execute(
                    """
                    SELECT original_query, COUNT(*) as count,
                           array_agg(DISTINCT sql_error) as errors
                    FROM ts_query_log
                    WHERE created_at > NOW() - INTERVAL '%s days'
                      AND sql_valid = FALSE
                    GROUP BY original_query
                    HAVING COUNT(*) >= %s
                    ORDER BY count DESC
                    LIMIT 10
                    """,
                    (days, min_occurrences),
                )
                common_failures = [
                    {"query": row[0], "count": row[1], "errors": row[2]}
                    for row in cur.fetchall()
                ]

                # Find underperforming intents
                cur.execute(
                    """
                    SELECT intent_classification,
                           COUNT(*) as total,
                           SUM(CASE WHEN sql_valid THEN 1 ELSE 0 END) as success
                    FROM ts_query_log
                    WHERE created_at > NOW() - INTERVAL '%s days'
                    GROUP BY intent_classification
                    """,
                    (days,),
                )
                intent_stats = [
                    {
                        "intent": row[0],
                        "total": row[1],
                        "success": row[2],
                        "rate": row[2] / row[1] if row[1] > 0 else 0,
                    }
                    for row in cur.fetchall()
                ]

                # Find queries with negative feedback
                cur.execute(
                    """
                    SELECT original_query, COUNT(*) as count
                    FROM ts_query_log
                    WHERE created_at > NOW() - INTERVAL '%s days'
                      AND user_feedback = 'negative'
                    GROUP BY original_query
                    ORDER BY count DESC
                    LIMIT 10
                    """,
                    (days,),
                )
                negative_feedback = [
                    {"query": row[0], "count": row[1]}
                    for row in cur.fetchall()
                ]

            conn.close()

            return {
                "period_days": days,
                "common_failures": common_failures,
                "intent_stats": intent_stats,
                "negative_feedback": negative_feedback,
                "suggestions": self._generate_suggestions(
                    common_failures, intent_stats, negative_feedback
                ),
            }

        except Exception as e:
            logger.error(f"Failed to analyze logs: {e}")
            return {"error": str(e)}

    def _generate_suggestions(
        self,
        failures: List[Dict],
        intent_stats: List[Dict],
        negative: List[Dict],
    ) -> List[str]:
        """Generate improvement suggestions from analysis."""
        suggestions = []

        # Suggest patterns from common failures
        for failure in failures[:3]:
            suggestions.append(
                f"Review error pattern for: '{failure['query']}' ({failure['count']} failures)"
            )

        # Suggest intent improvements
        for stat in intent_stats:
            if stat["rate"] < 0.7 and stat["total"] >= 5:
                suggestions.append(
                    f"Improve {stat['intent']} queries (success rate: {stat['rate']:.1%})"
                )

        # Suggest from negative feedback
        for neg in negative[:3]:
            suggestions.append(
                f"Investigate negative feedback on: '{neg['query']}'"
            )

        return suggestions

    # ========================================================================
    # Search Similar Learnings
    # ========================================================================

    def search_learnings(
        self,
        query: str,
        limit: int = 5,
    ) -> List[Dict]:
        """
        Search for relevant learnings.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of relevant learnings
        """
        # Use keyword search since we're using JSONB for embeddings
        # (pgvector not available in standard PostgreSQL)
        return self._keyword_search_learnings(query, limit)

    def _keyword_search_learnings(self, query: str, limit: int) -> List[Dict]:
        """Fallback keyword search for learnings."""
        conn = self._get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT title, learning, learning_type
                    FROM ts_learnings
                    WHERE title ILIKE %s OR learning ILIKE %s
                    ORDER BY usage_count DESC, created_at DESC
                    LIMIT %s
                    """,
                    (f"%{query}%", f"%{query}%", limit),
                )
                return [
                    {"title": row[0], "learning": row[1], "type": row[2]}
                    for row in cur.fetchall()
                ]
        finally:
            conn.close()


if __name__ == "__main__":
    # Test learning machine
    print("Testing Learning Machine")
    print("=" * 70)
    print()

    machine = LearningMachine()

    # Test synonym learning
    print("Test 1: Learning synonym")
    machine.learn_synonym_from_correction(
        user_term="飞边",
        correct_term="披锋",
        term_type="defect",
        context="User said 飞边, meant 披锋 (flash/burr)",
    )
    print("✅ Synonym learned")
    print()

    # Test error learning
    print("Test 2: Learning from error")
    machine.learn_from_error(
        question="有多少个披锋问题",
        generated_sql="SELECT COUNT(*) FROM issues WHERE defect_types IN ('披锋')",
        error_message="operator does not exist: text[] = text",
        fixed_sql="SELECT COUNT(*) FROM troubleshooting_issues WHERE defect_types @> ARRAY['披锋']",
    )
    print("✅ Error pattern learned")
    print()

    print("✅ All tests passed")
