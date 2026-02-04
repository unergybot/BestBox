#!/usr/bin/env python3
"""
Troubleshooting Data Sync

Dual-write synchronization between PostgreSQL (structured) and Qdrant (vector).
Ensures data consistency across both storage systems.

Usage:
    from services.troubleshooting.data_sync import TroubleshootingDataSync

    sync = TroubleshootingDataSync()
    sync.sync_case(case_data)  # Writes to both PostgreSQL and Qdrant
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

# Add project root to path when running as script
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

import psycopg2
from psycopg2.extras import execute_values, Json

from services.troubleshooting.indexer import TroubleshootingIndexer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TroubleshootingDataSync:
    """Synchronize troubleshooting data between PostgreSQL and Qdrant."""

    def __init__(
        self,
        pg_host: str = "localhost",
        pg_port: int = 5432,
        pg_database: str = "bestbox",
        pg_user: str = "bestbox",
        pg_password: str = "bestbox",
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        embeddings_url: Optional[str] = None,
    ):
        """
        Initialize data sync with database connections.

        Args:
            pg_host: PostgreSQL host
            pg_port: PostgreSQL port
            pg_database: PostgreSQL database name
            pg_user: PostgreSQL username
            pg_password: PostgreSQL password
            qdrant_host: Qdrant host
            qdrant_port: Qdrant port
            embeddings_url: Embeddings service URL (optional)
        """
        # PostgreSQL connection params
        self.pg_params = {
            "host": os.getenv("POSTGRES_HOST", pg_host),
            "port": int(os.getenv("POSTGRES_PORT", pg_port)),
            "database": os.getenv("POSTGRES_DB", pg_database),
            "user": os.getenv("POSTGRES_USER", pg_user),
            "password": os.getenv("POSTGRES_PASSWORD", pg_password),
        }

        # Initialize Qdrant indexer
        self.indexer = TroubleshootingIndexer(
            qdrant_host=qdrant_host,
            qdrant_port=qdrant_port,
            embeddings_url=embeddings_url
            or os.getenv("EMBEDDINGS_URL", "http://localhost:8004"),
        )

        logger.info(
            f"DataSync initialized: PostgreSQL={pg_host}:{pg_port}/{pg_database}"
        )

    def _get_pg_connection(self):
        """Get PostgreSQL connection."""
        return psycopg2.connect(**self.pg_params)

    def sync_case(
        self, case_data: Dict, force_reindex: bool = True
    ) -> Dict[str, Any]:
        """
        Sync a case to both PostgreSQL and Qdrant.

        Args:
            case_data: Case dictionary with metadata and issues
            force_reindex: If True, delete existing data before re-syncing

        Returns:
            Dict with sync statistics
        """
        case_id = case_data["case_id"]
        logger.info(f"📊 Syncing case {case_id}")

        stats = {
            "case_id": case_id,
            "pg_case": False,
            "pg_issues": 0,
            "qdrant_case": False,
            "qdrant_issues": 0,
            "errors": [],
        }

        # Step 1: Sync to PostgreSQL
        try:
            if force_reindex:
                self._delete_case_pg(case_id)

            self._upsert_case_pg(case_data)
            stats["pg_case"] = True

            issue_count = self._upsert_issues_pg(case_data)
            stats["pg_issues"] = issue_count

        except Exception as e:
            logger.error(f"PostgreSQL sync failed: {e}")
            stats["errors"].append(f"PostgreSQL: {str(e)}")

        # Step 2: Sync to Qdrant
        try:
            qdrant_stats = self.indexer.index_case(case_data, force_reindex=force_reindex)
            stats["qdrant_case"] = qdrant_stats["case_points"] == 1
            stats["qdrant_issues"] = qdrant_stats["issue_points"]

        except Exception as e:
            logger.error(f"Qdrant sync failed: {e}")
            stats["errors"].append(f"Qdrant: {str(e)}")

        # Log summary
        if stats["errors"]:
            logger.warning(f"   ⚠️ Sync completed with errors: {stats['errors']}")
        else:
            logger.info(
                f"   ✅ Synced: PG(1 case, {stats['pg_issues']} issues) "
                f"+ Qdrant({stats['qdrant_issues']} issues)"
            )

        return stats

    def _upsert_case_pg(self, case_data: Dict):
        """Upsert case to PostgreSQL."""
        conn = self._get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO troubleshooting_cases (
                        case_id, part_number, internal_number, mold_type,
                        material, color, total_issues, source_file,
                        vlm_processed, vlm_summary, vlm_confidence,
                        key_insights, tags
                    ) VALUES (
                        %(case_id)s, %(part_number)s, %(internal_number)s, %(mold_type)s,
                        %(material)s, %(color)s, %(total_issues)s, %(source_file)s,
                        %(vlm_processed)s, %(vlm_summary)s, %(vlm_confidence)s,
                        %(key_insights)s, %(tags)s
                    )
                    ON CONFLICT (case_id) DO UPDATE SET
                        part_number = EXCLUDED.part_number,
                        internal_number = EXCLUDED.internal_number,
                        mold_type = EXCLUDED.mold_type,
                        material = EXCLUDED.material,
                        color = EXCLUDED.color,
                        total_issues = EXCLUDED.total_issues,
                        source_file = EXCLUDED.source_file,
                        vlm_processed = EXCLUDED.vlm_processed,
                        vlm_summary = EXCLUDED.vlm_summary,
                        vlm_confidence = EXCLUDED.vlm_confidence,
                        key_insights = EXCLUDED.key_insights,
                        tags = EXCLUDED.tags,
                        updated_at = NOW()
                    """,
                    {
                        "case_id": case_data["case_id"],
                        "part_number": case_data["metadata"].get("part_number"),
                        "internal_number": case_data["metadata"].get("internal_number"),
                        "mold_type": case_data["metadata"].get("mold_type"),
                        "material": case_data["metadata"].get("material_t0"),
                        "color": case_data["metadata"].get("color"),
                        "total_issues": case_data.get("total_issues", 0),
                        "source_file": case_data.get("source_file"),
                        "vlm_processed": case_data.get("vlm_processed", False),
                        "vlm_summary": case_data.get("vlm_summary"),
                        "vlm_confidence": case_data.get("vlm_confidence", 0.0),
                        "key_insights": case_data.get("key_insights", []),
                        "tags": case_data.get("tags", []),
                    },
                )
            conn.commit()
        finally:
            conn.close()

    def _upsert_issues_pg(self, case_data: Dict) -> int:
        """Upsert issues to PostgreSQL."""
        if not case_data.get("issues"):
            return 0

        conn = self._get_pg_connection()
        try:
            with conn.cursor() as cur:
                issues_data = []
                for issue in case_data["issues"]:
                    # Build unique issue_id
                    issue_id = (
                        f"{case_data['case_id']}-{issue['issue_number']}-{issue.get('excel_row', 0)}"
                    )

                    # Extract defect types from images
                    defect_types = [
                        img.get("defect_type", "")
                        for img in issue.get("images", [])
                        if img.get("defect_type")
                    ]

                    # Aggregate VLM data from images
                    max_vlm_confidence = max(
                        (img.get("vlm_confidence", 0.0) for img in issue.get("images", [])),
                        default=0.0,
                    )
                    severity = self._get_max_severity(issue.get("images", []))
                    tags = self._aggregate_tags(issue.get("images", []))
                    key_insights = self._aggregate_insights(issue.get("images", []))
                    suggested_actions = self._aggregate_actions(issue.get("images", []))

                    issues_data.append(
                        (
                            issue_id,
                            case_data["case_id"],
                            issue["issue_number"],
                            issue.get("excel_row"),
                            issue.get("trial_version"),
                            issue.get("category"),
                            issue.get("problem", ""),
                            issue.get("solution"),
                            issue.get("result_t1"),
                            issue.get("result_t2"),
                            issue.get("cause_classification"),
                            defect_types,
                            case_data.get("vlm_processed", False),
                            max_vlm_confidence,
                            severity,
                            tags,
                            key_insights,
                            suggested_actions,
                            len(issue.get("images", [])) > 0,
                            len(issue.get("images", [])),
                        )
                    )

                execute_values(
                    cur,
                    """
                    INSERT INTO troubleshooting_issues (
                        issue_id, case_id, issue_number, excel_row,
                        trial_version, category, problem, solution,
                        result_t1, result_t2, cause_classification, defect_types,
                        vlm_processed, vlm_confidence, severity, tags,
                        key_insights, suggested_actions, has_images, image_count
                    ) VALUES %s
                    ON CONFLICT (issue_id) DO UPDATE SET
                        trial_version = EXCLUDED.trial_version,
                        category = EXCLUDED.category,
                        problem = EXCLUDED.problem,
                        solution = EXCLUDED.solution,
                        result_t1 = EXCLUDED.result_t1,
                        result_t2 = EXCLUDED.result_t2,
                        cause_classification = EXCLUDED.cause_classification,
                        defect_types = EXCLUDED.defect_types,
                        vlm_processed = EXCLUDED.vlm_processed,
                        vlm_confidence = EXCLUDED.vlm_confidence,
                        severity = EXCLUDED.severity,
                        tags = EXCLUDED.tags,
                        key_insights = EXCLUDED.key_insights,
                        suggested_actions = EXCLUDED.suggested_actions,
                        has_images = EXCLUDED.has_images,
                        image_count = EXCLUDED.image_count,
                        updated_at = NOW()
                    """,
                    issues_data,
                )
            conn.commit()
            return len(issues_data)
        finally:
            conn.close()

    def _delete_case_pg(self, case_id: str):
        """Delete case and issues from PostgreSQL."""
        conn = self._get_pg_connection()
        try:
            with conn.cursor() as cur:
                # Issues are deleted via CASCADE
                cur.execute(
                    "DELETE FROM troubleshooting_cases WHERE case_id = %s", (case_id,)
                )
            conn.commit()
            logger.info(f"   Deleted case {case_id} from PostgreSQL")
        finally:
            conn.close()

    def delete_case(self, case_id: str):
        """Delete case from both PostgreSQL and Qdrant."""
        logger.info(f"🗑️ Deleting case {case_id}")

        # Delete from PostgreSQL
        try:
            self._delete_case_pg(case_id)
        except Exception as e:
            logger.error(f"PostgreSQL delete failed: {e}")

        # Delete from Qdrant
        try:
            self.indexer.delete_case(case_id)
        except Exception as e:
            logger.error(f"Qdrant delete failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics from both storage systems."""
        stats = {"postgresql": {}, "qdrant": {}}

        # PostgreSQL stats
        conn = self._get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM troubleshooting_cases")
                stats["postgresql"]["cases"] = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM troubleshooting_issues")
                stats["postgresql"]["issues"] = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM troubleshooting_synonyms")
                stats["postgresql"]["synonyms"] = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM ts_knowledge_queries")
                stats["postgresql"]["knowledge_queries"] = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM ts_learnings")
                stats["postgresql"]["learnings"] = cur.fetchone()[0]
        except Exception as e:
            stats["postgresql"]["error"] = str(e)
        finally:
            conn.close()

        # Qdrant stats
        try:
            stats["qdrant"] = self.indexer.get_collection_stats()
        except Exception as e:
            stats["qdrant"]["error"] = str(e)

        return stats

    def _get_max_severity(self, images: List[Dict]) -> Optional[str]:
        """Get highest severity from images."""
        severity_order = {"high": 3, "medium": 2, "low": 1, "": 0}
        severities = [img.get("severity", "") for img in images]
        if not severities:
            return None
        max_sev = max(severities, key=lambda s: severity_order.get(s.lower(), 0))
        return max_sev if max_sev else None

    def _aggregate_tags(self, images: List[Dict]) -> List[str]:
        """Aggregate unique tags from images."""
        tags = set()
        for img in images:
            for tag in img.get("tags", []):
                if tag:
                    tags.add(tag)
        return list(tags)[:10]

    def _aggregate_insights(self, images: List[Dict]) -> List[str]:
        """Aggregate key insights from images."""
        insights = []
        for img in images:
            for insight in img.get("key_insights", []):
                if insight and insight not in insights:
                    insights.append(insight)
                    if len(insights) >= 5:
                        return insights
        return insights

    def _aggregate_actions(self, images: List[Dict]) -> List[str]:
        """Aggregate suggested actions from images."""
        actions = []
        for img in images:
            for action in img.get("suggested_actions", []):
                if action and action not in actions:
                    actions.append(action)
                    if len(actions) >= 5:
                        return actions
        return actions

    # ========================================================================
    # Backfill Methods
    # ========================================================================

    def backfill_from_qdrant(self, batch_size: int = 100) -> Dict[str, int]:
        """
        Backfill PostgreSQL from existing Qdrant data.

        Args:
            batch_size: Number of records to process per batch

        Returns:
            Dict with backfill statistics
        """
        from qdrant_client import QdrantClient

        logger.info("🔄 Starting backfill from Qdrant to PostgreSQL...")

        stats = {"cases_synced": 0, "issues_synced": 0, "errors": []}

        qdrant = QdrantClient(host="localhost", port=6333)

        # Backfill cases
        logger.info("   Backfilling cases...")
        offset = None
        while True:
            results, offset = qdrant.scroll(
                collection_name="troubleshooting_cases",
                limit=batch_size,
                offset=offset,
                with_payload=True,
            )

            if not results:
                break

            for point in results:
                try:
                    self._backfill_case_pg(point.payload)
                    stats["cases_synced"] += 1
                except Exception as e:
                    stats["errors"].append(f"Case {point.payload.get('case_id')}: {e}")

            if offset is None:
                break

        # Backfill issues
        logger.info("   Backfilling issues...")
        offset = None
        while True:
            results, offset = qdrant.scroll(
                collection_name="troubleshooting_issues",
                limit=batch_size,
                offset=offset,
                with_payload=True,
            )

            if not results:
                break

            for point in results:
                try:
                    self._backfill_issue_pg(point.payload)
                    stats["issues_synced"] += 1
                except Exception as e:
                    stats["errors"].append(f"Issue {point.payload.get('issue_id')}: {e}")

            if offset is None:
                break

        logger.info(
            f"✅ Backfill complete: {stats['cases_synced']} cases, "
            f"{stats['issues_synced']} issues, {len(stats['errors'])} errors"
        )
        return stats

    def _backfill_case_pg(self, payload: Dict):
        """Backfill a single case from Qdrant payload."""
        conn = self._get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO troubleshooting_cases (
                        case_id, part_number, internal_number, mold_type,
                        material, color, total_issues, source_file,
                        vlm_processed, vlm_summary, vlm_confidence,
                        key_insights, tags
                    ) VALUES (
                        %(case_id)s, %(part_number)s, %(internal_number)s, %(mold_type)s,
                        %(material)s, %(color)s, %(total_issues)s, %(source_file)s,
                        %(vlm_processed)s, %(vlm_summary)s, %(vlm_confidence)s,
                        %(key_insights)s, %(tags)s
                    )
                    ON CONFLICT (case_id) DO NOTHING
                    """,
                    {
                        "case_id": payload.get("case_id"),
                        "part_number": payload.get("part_number"),
                        "internal_number": payload.get("internal_number"),
                        "mold_type": payload.get("mold_type"),
                        "material": payload.get("material"),
                        "color": payload.get("color"),
                        "total_issues": payload.get("total_issues", 0),
                        "source_file": payload.get("source_file"),
                        "vlm_processed": payload.get("vlm_processed", False),
                        "vlm_summary": payload.get("vlm_summary"),
                        "vlm_confidence": payload.get("vlm_confidence", 0.0),
                        "key_insights": payload.get("key_insights", []),
                        "tags": payload.get("tags", []),
                    },
                )
            conn.commit()
        finally:
            conn.close()

    def _backfill_issue_pg(self, payload: Dict):
        """Backfill a single issue from Qdrant payload."""
        conn = self._get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO troubleshooting_issues (
                        issue_id, case_id, issue_number, excel_row,
                        trial_version, category, problem, solution,
                        result_t1, result_t2, cause_classification, defect_types,
                        vlm_processed, vlm_confidence, severity, tags,
                        key_insights, suggested_actions, has_images, image_count
                    ) VALUES (
                        %(issue_id)s, %(case_id)s, %(issue_number)s, %(excel_row)s,
                        %(trial_version)s, %(category)s, %(problem)s, %(solution)s,
                        %(result_t1)s, %(result_t2)s, %(cause_classification)s, %(defect_types)s,
                        %(vlm_processed)s, %(vlm_confidence)s, %(severity)s, %(tags)s,
                        %(key_insights)s, %(suggested_actions)s, %(has_images)s, %(image_count)s
                    )
                    ON CONFLICT (issue_id) DO NOTHING
                    """,
                    {
                        "issue_id": payload.get("issue_id"),
                        "case_id": payload.get("case_id"),
                        "issue_number": payload.get("issue_number"),
                        "excel_row": payload.get("excel_row"),
                        "trial_version": payload.get("trial_version"),
                        "category": payload.get("category"),
                        "problem": payload.get("problem", ""),
                        "solution": payload.get("solution"),
                        "result_t1": payload.get("result_t1"),
                        "result_t2": payload.get("result_t2"),
                        "cause_classification": payload.get("cause_classification"),
                        "defect_types": payload.get("defect_types", []),
                        "vlm_processed": payload.get("vlm_processed", False),
                        "vlm_confidence": payload.get("vlm_confidence", 0.0),
                        "severity": payload.get("severity"),
                        "tags": payload.get("tags", []),
                        "key_insights": payload.get("key_insights", []),
                        "suggested_actions": payload.get("suggested_actions", []),
                        "has_images": payload.get("has_images", False),
                        "image_count": payload.get("image_count", 0),
                    },
                )
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    # Test data sync
    print("Testing Troubleshooting Data Sync")
    print("=" * 70)
    print()

    sync = TroubleshootingDataSync()

    # Get stats
    print("📊 Current Statistics:")
    stats = sync.get_stats()
    print(f"\nPostgreSQL:")
    for key, value in stats["postgresql"].items():
        print(f"  {key}: {value}")
    print(f"\nQdrant:")
    for key, value in stats["qdrant"].items():
        print(f"  {key}: {value}")
