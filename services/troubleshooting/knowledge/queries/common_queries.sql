-- Common Validated Queries for Troubleshooting Text-to-SQL
-- These queries serve as patterns for similar question matching

-- ============================================================================
-- Counting & Statistics
-- ============================================================================

-- Q: 有多少个披锋问题？/ How many flash/burr issues?
-- Name: count_defect_by_type
SELECT COUNT(*) as count
FROM troubleshooting_issues
WHERE defect_types @> ARRAY['披锋'];

-- Q: 各种缺陷类型的数量？/ Count by defect type
-- Name: defect_type_distribution
SELECT unnest(defect_types) as defect_type, COUNT(*) as count
FROM troubleshooting_issues
GROUP BY defect_type
ORDER BY count DESC;

-- Q: 有多少个案例？/ Total case count
-- Name: total_cases
SELECT COUNT(*) as total_cases FROM troubleshooting_cases;

-- Q: 有多少个问题？/ Total issue count
-- Name: total_issues
SELECT COUNT(*) as total_issues FROM troubleshooting_issues;

-- ============================================================================
-- Success/Failure Analysis
-- ============================================================================

-- Q: T1成功的案例有哪些？/ Cases successful at T1
-- Name: t1_successful_issues
SELECT i.issue_id, i.case_id, c.part_number, i.problem, i.solution
FROM troubleshooting_issues i
JOIN troubleshooting_cases c ON i.case_id = c.case_id
WHERE i.result_t1 = 'OK'
ORDER BY i.created_at DESC
LIMIT 50;

-- Q: 成功解决的问题数量？/ Count of successfully resolved issues
-- Name: success_count
SELECT
    COUNT(*) as total,
    COUNT(CASE WHEN result_t1 = 'OK' OR result_t2 = 'OK' THEN 1 END) as resolved,
    ROUND(COUNT(CASE WHEN result_t1 = 'OK' OR result_t2 = 'OK' THEN 1 END) * 100.0 / COUNT(*), 1) as success_rate
FROM troubleshooting_issues;

-- Q: T1成功率是多少？/ T1 success rate
-- Name: t1_success_rate
SELECT
    COUNT(CASE WHEN result_t1 = 'OK' THEN 1 END) as t1_ok,
    COUNT(result_t1) as t1_total,
    ROUND(COUNT(CASE WHEN result_t1 = 'OK' THEN 1 END) * 100.0 / NULLIF(COUNT(result_t1), 0), 1) as t1_success_rate
FROM troubleshooting_issues;

-- ============================================================================
-- Material-based Queries
-- ============================================================================

-- Q: HIPS材料的问题有哪些？/ Issues with HIPS material
-- Name: issues_by_material
SELECT i.issue_id, i.problem, i.solution, i.defect_types
FROM troubleshooting_issues i
JOIN troubleshooting_cases c ON i.case_id = c.case_id
WHERE c.material ILIKE '%HIPS%'
ORDER BY i.created_at DESC
LIMIT 50;

-- Q: 各材料的问题数量？/ Issue count by material
-- Name: material_issue_distribution
SELECT c.material, COUNT(i.id) as issue_count
FROM troubleshooting_cases c
JOIN troubleshooting_issues i ON c.case_id = i.case_id
WHERE c.material IS NOT NULL
GROUP BY c.material
ORDER BY issue_count DESC;

-- ============================================================================
-- Part Number Queries
-- ============================================================================

-- Q: 零件1947688的所有问题？/ All issues for part 1947688
-- Name: issues_by_part_number
SELECT i.issue_id, i.issue_number, i.problem, i.solution, i.result_t1, i.result_t2
FROM troubleshooting_issues i
JOIN troubleshooting_cases c ON i.case_id = c.case_id
WHERE c.part_number = '1947688'
ORDER BY i.issue_number;

-- ============================================================================
-- Severity-based Queries
-- ============================================================================

-- Q: 高严重度的问题有哪些？/ High severity issues
-- Name: high_severity_issues
SELECT issue_id, case_id, problem, solution, severity
FROM troubleshooting_issues
WHERE severity = 'high'
ORDER BY created_at DESC
LIMIT 50;

-- Q: 按严重程度统计问题数？/ Issue count by severity
-- Name: severity_distribution
SELECT severity, COUNT(*) as count
FROM troubleshooting_issues
WHERE severity IS NOT NULL
GROUP BY severity
ORDER BY
    CASE severity
        WHEN 'high' THEN 1
        WHEN 'medium' THEN 2
        WHEN 'low' THEN 3
    END;

-- ============================================================================
-- Combined Filters
-- ============================================================================

-- Q: HIPS材料的披锋问题？/ Flash issues with HIPS material
-- Name: defect_by_material
SELECT i.issue_id, i.problem, i.solution
FROM troubleshooting_issues i
JOIN troubleshooting_cases c ON i.case_id = c.case_id
WHERE c.material ILIKE '%HIPS%'
  AND i.defect_types @> ARRAY['披锋']
LIMIT 50;

-- Q: T1成功解决的披锋问题？/ Flash issues resolved at T1
-- Name: successful_defect_solutions
SELECT issue_id, problem, solution
FROM troubleshooting_issues
WHERE defect_types @> ARRAY['披锋']
  AND result_t1 = 'OK'
LIMIT 50;

-- ============================================================================
-- Synonym-expanded Queries
-- ============================================================================

-- Q: 查找术语的标准名称 (for query expansion)
-- Name: get_canonical_term
SELECT canonical_term
FROM troubleshooting_synonyms
WHERE synonym = '毛边'
ORDER BY confidence DESC
LIMIT 1;

-- Q: 获取标准术语的所有同义词 (for display)
-- Name: get_all_synonyms
SELECT synonym
FROM troubleshooting_synonyms
WHERE canonical_term = '披锋';
