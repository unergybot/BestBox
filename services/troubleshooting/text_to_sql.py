#!/usr/bin/env python3
"""
Text-to-SQL Generator for Troubleshooting

Generates SQL queries from natural language using 6-layer context:
1. Table schemas (from knowledge/tables/)
2. Business rules (defect definitions, gotchas)
3. Validated queries (similar patterns)
4. Synonym mappings
5. Learnings (error patterns)
6. Runtime schema (introspection)

Usage:
    from services.troubleshooting.text_to_sql import TextToSQLGenerator

    generator = TextToSQLGenerator()
    result = generator.generate("有多少个披锋问题")
    # result = {
    #     "sql": "SELECT COUNT(*) FROM troubleshooting_issues WHERE defect_types @> ARRAY['披锋']",
    #     "valid": True,
    #     "tables_used": ["troubleshooting_issues"],
    #     "context_used": ["table_schema", "validated_query"]
    # }
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

# Add project root to path when running as script
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

import psycopg2
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TextToSQLGenerator:
    """Generate SQL from natural language queries with 6-layer context."""

    # SQL safety patterns
    DANGEROUS_PATTERNS = [
        r"\bDROP\b",
        r"\bDELETE\b",
        r"\bTRUNCATE\b",
        r"\bINSERT\b",
        r"\bUPDATE\b",
        r"\bALTER\b",
        r"\bCREATE\b",
        r"\bGRANT\b",
        r"\bREVOKE\b",
        r"--",  # SQL comments
        r";.*;",  # Multiple statements
    ]

    def __init__(
        self,
        pg_host: str = "localhost",
        pg_port: int = 5432,
        pg_database: str = "bestbox",
        pg_user: str = "bestbox",
        pg_password: str = "bestbox",
        llm_url: Optional[str] = None,
        knowledge_dir: Optional[Path] = None,
    ):
        """
        Initialize text-to-SQL generator.

        Args:
            pg_host: PostgreSQL host
            pg_port: PostgreSQL port
            pg_database: PostgreSQL database
            pg_user: PostgreSQL user
            pg_password: PostgreSQL password
            llm_url: LLM service URL
            knowledge_dir: Path to knowledge directory
        """
        self.pg_params = {
            "host": os.getenv("POSTGRES_HOST", pg_host),
            "port": int(os.getenv("POSTGRES_PORT", pg_port)),
            "database": os.getenv("POSTGRES_DB", pg_database),
            "user": os.getenv("POSTGRES_USER", pg_user),
            "password": os.getenv("POSTGRES_PASSWORD", pg_password),
        }

        # LLM for SQL generation
        if llm_url:
            self.llm_url = llm_url
        else:
            llm_base = os.getenv("LLM_BASE_URL", "http://localhost:8001/v1")
            self.llm_url = llm_base[:-3] if llm_base.endswith("/v1") else llm_base

        # Knowledge directory
        if knowledge_dir:
            self.knowledge_dir = knowledge_dir
        else:
            self.knowledge_dir = (
                Path(__file__).parent / "knowledge"
            )

        # Load static knowledge
        self._table_schemas = self._load_table_schemas()
        self._business_rules = self._load_business_rules()
        self._common_queries = self._load_common_queries()

        logger.info("TextToSQLGenerator initialized")

    def _get_pg_connection(self):
        """Get PostgreSQL connection."""
        return psycopg2.connect(**self.pg_params)

    # ========================================================================
    # Layer 1: Table Schemas
    # ========================================================================

    def _load_table_schemas(self) -> Dict[str, Any]:
        """Load table schema metadata from JSON files."""
        schemas = {}
        tables_dir = self.knowledge_dir / "tables"

        if not tables_dir.exists():
            logger.warning(f"Tables directory not found: {tables_dir}")
            return schemas

        for filepath in tables_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    schema = json.load(f)
                table_name = schema.get("table_name")
                if table_name:
                    schemas[table_name] = schema
            except Exception as e:
                logger.error(f"Failed to load {filepath}: {e}")

        logger.info(f"Loaded {len(schemas)} table schemas")
        return schemas

    def _format_table_schemas(self) -> str:
        """Format table schemas for prompt."""
        if not self._table_schemas:
            return "No table schemas available."

        lines = ["## Available Tables\n"]

        for table_name, schema in self._table_schemas.items():
            lines.append(f"### {table_name}")
            if schema.get("table_description"):
                lines.append(schema["table_description"])

            # Key columns
            if schema.get("columns"):
                lines.append("\n**Key Columns:**")
                for col in schema["columns"]:
                    if col.get("important"):
                        lines.append(f"- `{col['name']}` ({col['type']}): {col.get('description', '')}")

            # Data quality notes
            if schema.get("data_quality_notes"):
                lines.append("\n**Data Quality Notes:**")
                for note in schema["data_quality_notes"]:
                    lines.append(f"- {note}")

            lines.append("")

        return "\n".join(lines)

    # ========================================================================
    # Layer 2: Business Rules
    # ========================================================================

    def _load_business_rules(self) -> Dict[str, Any]:
        """Load business rules from JSON files."""
        rules = {"metrics": [], "business_rules": [], "common_gotchas": [], "defect_definitions": {}}
        business_dir = self.knowledge_dir / "business"

        if not business_dir.exists():
            logger.warning(f"Business directory not found: {business_dir}")
            return rules

        for filepath in business_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for key in rules:
                    if key in data:
                        if isinstance(rules[key], list):
                            rules[key].extend(data[key])
                        elif isinstance(rules[key], dict):
                            rules[key].update(data[key])
            except Exception as e:
                logger.error(f"Failed to load {filepath}: {e}")

        return rules

    def _format_business_rules(self) -> str:
        """Format business rules for prompt."""
        lines = ["## Business Rules\n"]

        # Business rules
        if self._business_rules.get("business_rules"):
            for rule in self._business_rules["business_rules"]:
                lines.append(f"- {rule}")
            lines.append("")

        # Common gotchas
        if self._business_rules.get("common_gotchas"):
            lines.append("## Common Gotchas\n")
            for gotcha in self._business_rules["common_gotchas"]:
                lines.append(f"**{gotcha.get('issue', 'Unknown')}**")
                if gotcha.get("solution"):
                    lines.append(f"  Solution: {gotcha['solution']}")
            lines.append("")

        return "\n".join(lines)

    # ========================================================================
    # Layer 3: Validated Queries
    # ========================================================================

    def _load_common_queries(self) -> List[Dict[str, str]]:
        """Load common validated queries."""
        queries = []
        queries_dir = self.knowledge_dir / "queries"

        if not queries_dir.exists():
            return queries

        for filepath in queries_dir.glob("*.sql"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                # Parse SQL file with comments as metadata
                current_query = {}
                for line in content.split("\n"):
                    if line.startswith("-- Q:"):
                        if current_query.get("sql"):
                            queries.append(current_query)
                        current_query = {"question": line[5:].strip(), "sql": ""}
                    elif line.startswith("-- Name:"):
                        current_query["name"] = line[8:].strip()
                    elif not line.startswith("--") and line.strip():
                        current_query["sql"] = current_query.get("sql", "") + line + "\n"

                if current_query.get("sql"):
                    queries.append(current_query)

            except Exception as e:
                logger.error(f"Failed to load {filepath}: {e}")

        return queries

    def _find_similar_queries(self, question: str, limit: int = 3) -> List[Dict]:
        """Find similar validated queries from knowledge base."""
        # For now, use simple keyword matching
        # TODO: Use embedding similarity when ts_knowledge_queries has embeddings
        similar = []
        question_lower = question.lower()

        for query in self._common_queries:
            q_question = query.get("question", "").lower()
            # Count word overlap
            overlap = sum(1 for word in question_lower.split() if word in q_question)
            if overlap > 0:
                similar.append({"query": query, "score": overlap})

        similar.sort(key=lambda x: x["score"], reverse=True)
        return [s["query"] for s in similar[:limit]]

    def _format_similar_queries(self, question: str) -> str:
        """Format similar queries for prompt."""
        similar = self._find_similar_queries(question)
        if not similar:
            return ""

        lines = ["## Similar Validated Queries\n"]
        for q in similar:
            lines.append(f"**Q:** {q.get('question', 'Unknown')}")
            lines.append(f"```sql\n{q.get('sql', '').strip()}\n```\n")

        return "\n".join(lines)

    # ========================================================================
    # Layer 4: Synonym Mappings
    # ========================================================================

    def _get_synonym_mappings(self, query: str) -> Dict[str, List[str]]:
        """Get relevant synonym mappings for the query."""
        mappings = {}
        try:
            conn = self._get_pg_connection()
            with conn.cursor() as cur:
                # Get all defect synonyms that might be relevant
                cur.execute(
                    """
                    SELECT canonical_term, array_agg(synonym) as synonyms
                    FROM troubleshooting_synonyms
                    WHERE term_type = 'defect'
                    GROUP BY canonical_term
                    """
                )
                for row in cur.fetchall():
                    canonical, synonyms = row
                    # Check if any synonym appears in query
                    if any(syn in query for syn in synonyms) or canonical in query:
                        mappings[canonical] = synonyms
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to get synonyms: {e}")

        return mappings

    def _format_synonym_mappings(self, query: str) -> str:
        """Format synonym mappings for prompt."""
        mappings = self._get_synonym_mappings(query)
        if not mappings:
            return ""

        lines = ["## Relevant Synonyms\n"]
        lines.append("These terms are equivalent in the database:")
        for canonical, synonyms in mappings.items():
            lines.append(f"- **{canonical}**: {', '.join(synonyms)}")

        return "\n".join(lines)

    # ========================================================================
    # Layer 5: Learnings
    # ========================================================================

    def _get_relevant_learnings(self, query: str, limit: int = 3) -> List[Dict]:
        """Get relevant learnings (error patterns, gotchas)."""
        learnings = []
        try:
            conn = self._get_pg_connection()
            with conn.cursor() as cur:
                # Simple keyword matching for now
                # TODO: Use embedding similarity
                cur.execute(
                    """
                    SELECT title, learning, learning_type
                    FROM ts_learnings
                    ORDER BY usage_count DESC, created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                for row in cur.fetchall():
                    learnings.append({
                        "title": row[0],
                        "learning": row[1],
                        "type": row[2],
                    })
            conn.close()
        except Exception as e:
            logger.debug(f"No learnings available: {e}")

        return learnings

    def _format_learnings(self, query: str) -> str:
        """Format learnings for prompt."""
        learnings = self._get_relevant_learnings(query)
        if not learnings:
            return ""

        lines = ["## Learnings (Past Mistakes to Avoid)\n"]
        for l in learnings:
            lines.append(f"**{l['title']}**: {l['learning']}")

        return "\n".join(lines)

    # ========================================================================
    # Layer 6: Runtime Schema Introspection
    # ========================================================================

    def _introspect_table(self, table_name: str) -> Optional[Dict]:
        """Get runtime schema information for a table."""
        try:
            conn = self._get_pg_connection()
            with conn.cursor() as cur:
                # Get column information
                cur.execute(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (table_name,),
                )
                columns = [
                    {"name": row[0], "type": row[1], "nullable": row[2]}
                    for row in cur.fetchall()
                ]

                # Get row count
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cur.fetchone()[0]

            conn.close()
            return {"table_name": table_name, "columns": columns, "row_count": count}
        except Exception as e:
            logger.warning(f"Failed to introspect {table_name}: {e}")
            return None

    # ========================================================================
    # SQL Generation
    # ========================================================================

    def generate(
        self,
        question: str,
        expanded_query: Optional[str] = None,
        include_explanation: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate SQL from natural language question.

        Args:
            question: The user's question
            expanded_query: Pre-expanded query (with synonyms resolved)
            include_explanation: Include explanation in result

        Returns:
            Dict with sql, valid, tables_used, context_used, etc.
        """
        query = expanded_query or question

        # Build 6-layer context
        context = self._build_context(query)

        # Generate SQL using LLM
        sql, explanation = self._generate_sql_with_llm(question, context)

        # Validate SQL
        is_valid, error = self._validate_sql(sql)

        # Extract tables used
        tables_used = self._extract_tables(sql)

        result = {
            "sql": sql if is_valid else None,
            "valid": is_valid,
            "error": error if not is_valid else None,
            "tables_used": tables_used,
            "context_used": list(context.keys()),
        }

        if include_explanation:
            result["explanation"] = explanation

        return result

    def _build_context(self, query: str) -> Dict[str, str]:
        """Build 6-layer context for SQL generation."""
        context = {}

        # Layer 1: Table schemas
        context["table_schemas"] = self._format_table_schemas()

        # Layer 2: Business rules
        context["business_rules"] = self._format_business_rules()

        # Layer 3: Similar validated queries
        similar = self._format_similar_queries(query)
        if similar:
            context["similar_queries"] = similar

        # Layer 4: Synonym mappings
        synonyms = self._format_synonym_mappings(query)
        if synonyms:
            context["synonyms"] = synonyms

        # Layer 5: Learnings
        learnings = self._format_learnings(query)
        if learnings:
            context["learnings"] = learnings

        # Layer 6: Runtime schema (only if needed)
        # Introspection is expensive, skip for now unless needed

        return context

    def _generate_sql_with_llm(
        self, question: str, context: Dict[str, str]
    ) -> Tuple[str, str]:
        """Generate SQL using LLM with context."""
        # Build prompt
        context_str = "\n\n".join(context.values())

        prompt = f"""你是一个SQL专家，专门为故障排除数据库生成查询。

{context_str}

## SQL 规则
- 只生成 SELECT 查询，禁止 DROP/DELETE/UPDATE/INSERT
- 使用 LIMIT 50 防止返回过多结果
- 对于数组字段（如 defect_types），使用 @> 操作符
- 结果状态判断用 result_t1 = 'OK' OR result_t2 = 'OK'
- 中文字符串使用单引号

## 用户问题
{question}

请生成SQL查询。只返回JSON格式:
{{"sql": "SELECT ...", "explanation": "简短解释查询逻辑"}}"""

        try:
            response = requests.post(
                f"{self.llm_url}/v1/chat/completions",
                json={
                    "model": "qwen3",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 500,
                },
                timeout=30,
            )

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # Extract JSON
            json_start = content.find("{")
            json_end = content.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(content[json_start:json_end])
                return parsed.get("sql", ""), parsed.get("explanation", "")

            # Fallback: try to extract SQL directly
            sql_match = re.search(r"SELECT\s+.+?(?:;|$)", content, re.IGNORECASE | re.DOTALL)
            if sql_match:
                return sql_match.group(0).rstrip(";"), ""

        except Exception as e:
            logger.error(f"LLM SQL generation failed: {e}")

        return "", "Failed to generate SQL"

    def _validate_sql(self, sql: str) -> Tuple[bool, Optional[str]]:
        """
        Validate SQL for safety and syntax.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not sql or not sql.strip():
            return False, "Empty SQL"

        sql_upper = sql.upper()

        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, sql_upper, re.IGNORECASE):
                return False, f"Dangerous SQL pattern detected: {pattern}"

        # Must be SELECT
        if not sql_upper.strip().startswith("SELECT"):
            return False, "Only SELECT queries are allowed"

        # Try to parse with PostgreSQL
        try:
            conn = self._get_pg_connection()
            with conn.cursor() as cur:
                # Use EXPLAIN to validate without executing
                cur.execute(f"EXPLAIN {sql}")
            conn.close()
            return True, None
        except Exception as e:
            return False, str(e)

    def _extract_tables(self, sql: str) -> List[str]:
        """Extract table names from SQL query."""
        tables = []
        # Simple pattern matching for FROM and JOIN clauses
        patterns = [
            r"\bFROM\s+(\w+)",
            r"\bJOIN\s+(\w+)",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            tables.extend(matches)

        return list(set(tables))

    # ========================================================================
    # Execution
    # ========================================================================

    def execute(self, sql: str, limit: int = 50) -> Dict[str, Any]:
        """
        Execute SQL query and return results.

        Args:
            sql: SQL query to execute
            limit: Maximum rows to return

        Returns:
            Dict with columns, rows, row_count
        """
        # Strip trailing semicolons and whitespace
        sql = sql.strip().rstrip(";").strip()

        # Validate first
        is_valid, error = self._validate_sql(sql)
        if not is_valid:
            return {"error": error, "rows": [], "row_count": 0}

        try:
            conn = self._get_pg_connection()
            with conn.cursor() as cur:
                cur.execute(sql)
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchmany(limit)

                # Get total count
                cur.execute(f"SELECT COUNT(*) FROM ({sql}) AS subq")
                total_count = cur.fetchone()[0]

            conn.close()

            return {
                "columns": columns,
                "rows": [list(row) for row in rows],
                "row_count": len(rows),
                "total_count": total_count,
            }
        except Exception as e:
            return {"error": str(e), "rows": [], "row_count": 0}

    # ========================================================================
    # Learning
    # ========================================================================

    def save_validated_query(
        self,
        name: str,
        question: str,
        sql: str,
        tables_used: Optional[List[str]] = None,
        summary: Optional[str] = None,
    ):
        """
        Save a validated query to the knowledge base.

        Args:
            name: Short name for the query
            question: Original question
            sql: The SQL query
            tables_used: Tables used in the query
            summary: Summary of what the query does
        """
        try:
            conn = self._get_pg_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ts_knowledge_queries
                    (name, question, sql_query, tables_used, summary)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (name, question, sql, tables_used or [], summary),
                )
            conn.commit()
            conn.close()
            logger.info(f"Saved validated query: {name}")
        except Exception as e:
            logger.error(f"Failed to save query: {e}")

    def save_learning(
        self,
        title: str,
        learning: str,
        learning_type: str = "error_pattern",
        tables_affected: Optional[List[str]] = None,
    ):
        """
        Save a learning (error pattern, gotcha, etc.).

        Args:
            title: Short title
            learning: The learning content
            learning_type: Type of learning
            tables_affected: Tables affected
        """
        try:
            conn = self._get_pg_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ts_learnings
                    (title, learning, learning_type, tables_affected)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (title, learning, learning_type, tables_affected or []),
                )
            conn.commit()
            conn.close()
            logger.info(f"Saved learning: {title}")
        except Exception as e:
            logger.error(f"Failed to save learning: {e}")


if __name__ == "__main__":
    # Test text-to-SQL generation
    print("Testing Text-to-SQL Generator")
    print("=" * 70)
    print()

    generator = TextToSQLGenerator()

    test_questions = [
        "有多少个披锋问题",
        "T1成功的案例有哪些",
        "HIPS材料的问题数量",
        "按缺陷类型统计问题数",
    ]

    for question in test_questions:
        print(f"Question: \"{question}\"")
        print("-" * 70)

        result = generator.generate(question, include_explanation=True)

        if result["valid"]:
            print(f"  SQL: {result['sql']}")
            print(f"  Tables: {result['tables_used']}")
            if result.get("explanation"):
                print(f"  Explanation: {result['explanation']}")
        else:
            print(f"  Error: {result['error']}")

        print()
