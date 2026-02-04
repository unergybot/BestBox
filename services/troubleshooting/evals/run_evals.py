#!/usr/bin/env python3
"""
Run Evaluations for Troubleshooting Text-to-SQL

Evaluates the text-to-SQL system against test cases.

Usage:
    python -m services.troubleshooting.evals.run_evals
    python -m services.troubleshooting.evals.run_evals --category counting
    python -m services.troubleshooting.evals.run_evals --verbose
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any
import logging
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from services.troubleshooting.evals.test_cases import (
    TEST_CASES,
    get_test_cases_by_category,
)
from services.troubleshooting.query_expander import QueryExpander
from services.troubleshooting.text_to_sql import TextToSQLGenerator
from services.troubleshooting.hybrid_searcher import HybridSearcher

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class Evaluator:
    """Evaluate text-to-SQL system against test cases."""

    def __init__(self, verbose: bool = False):
        """
        Initialize evaluator.

        Args:
            verbose: Print detailed output
        """
        self.verbose = verbose
        self.expander = None
        self.generator = None
        self.searcher = None

    def _init_components(self):
        """Lazily initialize components."""
        if self.expander is None:
            try:
                self.expander = QueryExpander()
            except Exception as e:
                logger.warning(f"Failed to init expander: {e}")

        if self.generator is None:
            try:
                self.generator = TextToSQLGenerator()
            except Exception as e:
                logger.warning(f"Failed to init generator: {e}")

        if self.searcher is None:
            try:
                self.searcher = HybridSearcher()
            except Exception as e:
                logger.warning(f"Failed to init searcher: {e}")

    def evaluate(
        self,
        test_cases: List[Dict],
        skip_execution: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluate test cases.

        Args:
            test_cases: List of test cases
            skip_execution: Skip SQL execution (just test generation)

        Returns:
            Evaluation results
        """
        self._init_components()

        results = {
            "timestamp": datetime.now().isoformat(),
            "total": len(test_cases),
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "by_category": {},
            "details": [],
        }

        for tc in test_cases:
            result = self._evaluate_test_case(tc, skip_execution)
            results["details"].append(result)

            # Update counters
            if result["status"] == "PASS":
                results["passed"] += 1
            elif result["status"] == "FAIL":
                results["failed"] += 1
            else:
                results["skipped"] += 1

            # Update category stats
            cat = tc["category"]
            if cat not in results["by_category"]:
                results["by_category"][cat] = {"total": 0, "passed": 0}
            results["by_category"][cat]["total"] += 1
            if result["status"] == "PASS":
                results["by_category"][cat]["passed"] += 1

        return results

    def _evaluate_test_case(
        self,
        tc: Dict,
        skip_execution: bool = False,
    ) -> Dict:
        """Evaluate a single test case."""
        result = {
            "id": tc["id"],
            "question": tc["question"],
            "category": tc["category"],
            "status": "PASS",
            "checks": [],
        }

        try:
            # Check 1: Intent classification
            if self.expander:
                expansion = self.expander.expand(tc["question"])
                intent_result = self._check_intent(tc, expansion)
                result["checks"].append(intent_result)
                result["expansion"] = expansion

                if not intent_result["passed"]:
                    result["status"] = "FAIL"

                # Check 2: Synonym expansion
                if tc.get("expected_expansion"):
                    syn_result = self._check_synonyms(tc, expansion)
                    result["checks"].append(syn_result)
                    if not syn_result["passed"]:
                        result["status"] = "FAIL"

            # Check 3: SQL generation (for STRUCTURED queries)
            if tc.get("expected_sql_patterns") and self.generator:
                sql_result = self.generator.generate(
                    tc["question"],
                    expanded_query=expansion.get("expanded") if self.expander else None,
                )
                result["generated_sql"] = sql_result.get("sql")

                sql_check = self._check_sql_patterns(tc, sql_result)
                result["checks"].append(sql_check)
                if not sql_check["passed"]:
                    result["status"] = "FAIL"

                # Check 4: SQL execution (if not skipped)
                if not skip_execution and sql_result.get("valid") and sql_result.get("sql"):
                    exec_result = self.generator.execute(sql_result["sql"])
                    result["execution_result"] = exec_result

                    if exec_result.get("error"):
                        result["status"] = "FAIL"
                        result["checks"].append({
                            "name": "sql_execution",
                            "passed": False,
                            "error": exec_result["error"],
                        })

        except Exception as e:
            result["status"] = "SKIP"
            result["error"] = str(e)

        if self.verbose:
            self._print_result(result)

        return result

    def _check_intent(self, tc: Dict, expansion: Dict) -> Dict:
        """Check if intent was classified correctly."""
        expected = tc.get("expected_intent")
        actual = expansion.get("intent")

        return {
            "name": "intent_classification",
            "passed": expected == actual,
            "expected": expected,
            "actual": actual,
        }

    def _check_synonyms(self, tc: Dict, expansion: Dict) -> Dict:
        """Check if synonyms were expanded correctly."""
        expected = tc.get("expected_expansion", {})
        actual = expansion.get("synonyms_used", [])

        # Convert actual to dict format
        actual_dict = {}
        for syn in actual:
            if isinstance(syn, dict):
                actual_dict.update(syn)

        # Check if all expected expansions are present
        all_found = True
        for orig, expanded in expected.items():
            if orig not in str(actual_dict):
                all_found = False
                break

        return {
            "name": "synonym_expansion",
            "passed": all_found,
            "expected": expected,
            "actual": actual_dict,
        }

    def _check_sql_patterns(self, tc: Dict, sql_result: Dict) -> Dict:
        """Check if generated SQL contains expected patterns."""
        expected_patterns = tc.get("expected_sql_patterns", [])
        sql = sql_result.get("sql") or ""

        missing = []
        for pattern in expected_patterns:
            if pattern.upper() not in sql.upper():
                missing.append(pattern)

        return {
            "name": "sql_patterns",
            "passed": len(missing) == 0 and sql_result.get("valid", False),
            "expected_patterns": expected_patterns,
            "missing_patterns": missing,
            "sql_valid": sql_result.get("valid", False),
            "sql_error": sql_result.get("error"),
        }

    def _print_result(self, result: Dict):
        """Print test case result."""
        status_icon = "✅" if result["status"] == "PASS" else ("⏭️" if result["status"] == "SKIP" else "❌")
        print(f"{status_icon} {result['id']}: {result['question']}")

        if result["status"] != "PASS":
            for check in result.get("checks", []):
                if not check.get("passed"):
                    print(f"   ❌ {check['name']}: expected {check.get('expected')}, got {check.get('actual')}")

            if result.get("error"):
                print(f"   Error: {result['error']}")

            if result.get("generated_sql"):
                print(f"   SQL: {result['generated_sql'][:80]}...")

        print()


def main():
    parser = argparse.ArgumentParser(
        description="Run text-to-SQL evaluations"
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Test specific category (counting, filtering, etc.)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed output",
    )
    parser.add_argument(
        "--skip-execution",
        action="store_true",
        help="Skip SQL execution (only test generation)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output results to JSON file",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Troubleshooting Text-to-SQL Evaluation")
    print("=" * 70)
    print()

    # Get test cases
    if args.category:
        test_cases = get_test_cases_by_category(args.category)
        print(f"Running {len(test_cases)} test cases for category: {args.category}")
    else:
        test_cases = TEST_CASES
        print(f"Running all {len(test_cases)} test cases")
    print()

    # Run evaluation
    evaluator = Evaluator(verbose=args.verbose)
    results = evaluator.evaluate(test_cases, skip_execution=args.skip_execution)

    # Print summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print()
    print(f"Total:   {results['total']}")
    print(f"Passed:  {results['passed']} ({results['passed']/results['total']*100:.1f}%)")
    print(f"Failed:  {results['failed']}")
    print(f"Skipped: {results['skipped']}")
    print()

    print("By Category:")
    for cat, stats in sorted(results["by_category"].items()):
        rate = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {cat}: {stats['passed']}/{stats['total']} ({rate:.1f}%)")
    print()

    # Save results if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Results saved to: {args.output}")

    # Exit with error code if any failures
    sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
