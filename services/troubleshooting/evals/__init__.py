"""Evaluation suite for troubleshooting text-to-SQL."""

from .test_cases import TEST_CASES, get_test_cases_by_category, get_all_test_cases
from .run_evals import Evaluator

__all__ = [
    "TEST_CASES",
    "get_test_cases_by_category",
    "get_all_test_cases",
    "Evaluator",
]
