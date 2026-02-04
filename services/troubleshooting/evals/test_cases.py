#!/usr/bin/env python3
"""
Evaluation Test Cases for Troubleshooting Text-to-SQL

Test cases organized by category:
- Counting queries
- Filtering queries
- Aggregation queries
- Synonym handling
- Hybrid queries
"""

from typing import Dict, List, Literal

TestCategory = Literal[
    "counting", "filtering", "aggregation", "synonym", "hybrid", "semantic"
]


TEST_CASES: List[Dict] = [
    # ========================================================================
    # Counting Queries - Should use STRUCTURED mode
    # ========================================================================
    {
        "id": "count_001",
        "question": "有多少个披锋问题",
        "category": "counting",
        "expected_intent": "STRUCTURED",
        "expected_sql_patterns": ["COUNT", "defect_types", "披锋"],
        "expected_result_type": "number",
        "notes": "Basic defect count",
    },
    {
        "id": "count_002",
        "question": "T1成功的案例有几个",
        "category": "counting",
        "expected_intent": "STRUCTURED",
        "expected_sql_patterns": ["COUNT", "result_t1", "OK"],
        "expected_result_type": "number",
        "notes": "Count by trial result",
    },
    {
        "id": "count_003",
        "question": "总共有多少个问题",
        "category": "counting",
        "expected_intent": "STRUCTURED",
        "expected_sql_patterns": ["COUNT", "troubleshooting_issues"],
        "expected_result_type": "number",
        "notes": "Total issue count",
    },
    {
        "id": "count_004",
        "question": "HIPS材料的问题数量",
        "category": "counting",
        "expected_intent": "STRUCTURED",
        "expected_sql_patterns": ["COUNT", "material", "HIPS"],
        "expected_result_type": "number",
        "notes": "Count by material filter",
    },

    # ========================================================================
    # Filtering Queries - Should use STRUCTURED mode
    # ========================================================================
    {
        "id": "filter_001",
        "question": "T1成功的案例有哪些",
        "category": "filtering",
        "expected_intent": "STRUCTURED",
        "expected_sql_patterns": ["result_t1", "OK"],
        "expected_result_type": "list",
        "notes": "Filter by success",
    },
    {
        "id": "filter_002",
        "question": "零件1947688的所有问题",
        "category": "filtering",
        "expected_intent": "STRUCTURED",
        "expected_sql_patterns": ["part_number", "1947688"],
        "expected_result_type": "list",
        "notes": "Filter by part number",
    },
    {
        "id": "filter_003",
        "question": "高严重度的问题",
        "category": "filtering",
        "expected_intent": "STRUCTURED",
        "expected_sql_patterns": ["severity", "high"],
        "expected_result_type": "list",
        "notes": "Filter by severity",
    },

    # ========================================================================
    # Aggregation Queries - Should use STRUCTURED mode
    # ========================================================================
    {
        "id": "agg_001",
        "question": "按缺陷类型统计问题数",
        "category": "aggregation",
        "expected_intent": "STRUCTURED",
        "expected_sql_patterns": ["GROUP BY", "COUNT", "defect_types"],
        "expected_result_type": "table",
        "notes": "Group by defect type",
    },
    {
        "id": "agg_002",
        "question": "各材料的问题分布",
        "category": "aggregation",
        "expected_intent": "STRUCTURED",
        "expected_sql_patterns": ["GROUP BY", "material"],
        "expected_result_type": "table",
        "notes": "Group by material",
    },
    {
        "id": "agg_003",
        "question": "T1成功率是多少",
        "category": "aggregation",
        "expected_intent": "STRUCTURED",
        "expected_sql_patterns": ["COUNT", "result_t1", "OK"],
        "expected_result_type": "number",
        "notes": "Success rate calculation",
    },

    # ========================================================================
    # Synonym Queries - Should expand synonyms
    # ========================================================================
    {
        "id": "syn_001",
        "question": "毛边问题有多少个",
        "category": "synonym",
        "expected_intent": "STRUCTURED",
        "expected_expansion": {"毛边": "披锋"},
        "expected_sql_patterns": ["披锋"],  # Should use canonical term
        "notes": "Synonym: 毛边 → 披锋",
    },
    {
        "id": "syn_002",
        "question": "毛刺怎么解决",
        "category": "synonym",
        "expected_intent": "SEMANTIC",
        "expected_expansion": {"毛刺": "披锋"},
        "notes": "Synonym: 毛刺 → 披锋",
    },
    {
        "id": "syn_003",
        "question": "脏污问题的案例",
        "category": "synonym",
        "expected_intent": "HYBRID",
        "expected_expansion": {"脏污": "模具表面污染"},
        "notes": "Synonym: 脏污 → 模具表面污染",
    },

    # ========================================================================
    # Hybrid Queries - Should use HYBRID mode
    # ========================================================================
    {
        "id": "hybrid_001",
        "question": "HIPS材料的披锋解决方案",
        "category": "hybrid",
        "expected_intent": "HYBRID",
        "expected_sql_patterns": ["material", "HIPS"],
        "notes": "Filter + semantic search",
    },
    {
        "id": "hybrid_002",
        "question": "T1失败的问题怎么改善",
        "category": "hybrid",
        "expected_intent": "HYBRID",
        "expected_sql_patterns": ["result_t1", "NG"],
        "notes": "Filter + solution search",
    },
    {
        "id": "hybrid_003",
        "question": "成功解决的披锋案例",
        "category": "hybrid",
        "expected_intent": "HYBRID",
        "expected_sql_patterns": ["result_t1", "OK", "defect_types"],
        "notes": "Success filter + defect filter",
    },

    # ========================================================================
    # Semantic Queries - Should use SEMANTIC mode
    # ========================================================================
    {
        "id": "sem_001",
        "question": "披锋怎么解决",
        "category": "semantic",
        "expected_intent": "SEMANTIC",
        "expected_result_type": "list",
        "notes": "Solution search",
    },
    {
        "id": "sem_002",
        "question": "拉白的原因是什么",
        "category": "semantic",
        "expected_intent": "SEMANTIC",
        "expected_result_type": "list",
        "notes": "Cause search",
    },
    {
        "id": "sem_003",
        "question": "类似的问题有哪些",
        "category": "semantic",
        "expected_intent": "SEMANTIC",
        "expected_result_type": "list",
        "notes": "Similarity search",
    },
    {
        "id": "sem_004",
        "question": "推荐的解决方法",
        "category": "semantic",
        "expected_intent": "SEMANTIC",
        "expected_result_type": "list",
        "notes": "Recommendation search",
    },
]


def get_test_cases_by_category(category: TestCategory) -> List[Dict]:
    """Get test cases filtered by category."""
    return [tc for tc in TEST_CASES if tc["category"] == category]


def get_all_test_cases() -> List[Dict]:
    """Get all test cases."""
    return TEST_CASES


if __name__ == "__main__":
    # Print test case summary
    print("Test Cases Summary")
    print("=" * 70)
    print()

    categories = {}
    for tc in TEST_CASES:
        cat = tc["category"]
        categories[cat] = categories.get(cat, 0) + 1

    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count} cases")

    print()
    print(f"Total: {len(TEST_CASES)} test cases")
