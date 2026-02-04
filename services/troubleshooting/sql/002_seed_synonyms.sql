-- Seed data for troubleshooting synonyms
-- ASR term mappings for Chinese defect terminology

-- Clear existing data (for re-seeding)
TRUNCATE troubleshooting_synonyms RESTART IDENTITY;

-- ============================================================================
-- Defect Type Synonyms (披锋/毛边 family)
-- ============================================================================

INSERT INTO troubleshooting_synonyms (canonical_term, synonym, term_type, confidence, source) VALUES
-- 披锋 (flash/burr) - most common defect term variations
('披锋', '毛边', 'defect', 1.0, 'manual'),
('披锋', '毛刺', 'defect', 1.0, 'manual'),
('披锋', '飞边', 'defect', 1.0, 'manual'),
('披锋', '溢料', 'defect', 0.9, 'manual'),
('披锋', '批锋', 'defect', 1.0, 'manual'),  -- Common typo/variant
('披锋', '产品披锋', 'defect', 1.0, 'manual'),

-- 拉白 (whitening/stress marks)
('拉白', '白化', 'defect', 1.0, 'manual'),
('拉白', '发白', 'defect', 1.0, 'manual'),
('拉白', '应力白', 'defect', 0.9, 'manual'),
('拉白', '白痕', 'defect', 0.9, 'manual'),

-- 火花纹 (spark/EDM marks)
('火花纹残留', '火花纹', 'defect', 1.0, 'manual'),
('火花纹残留', '电火花纹', 'defect', 1.0, 'manual'),
('火花纹残留', 'EDM纹', 'defect', 0.9, 'manual'),
('火花纹残留', '放电纹', 'defect', 0.9, 'manual'),

-- 污染/脏污
('模具表面污染', '脏污', 'defect', 1.0, 'manual'),
('模具表面污染', '污染', 'defect', 1.0, 'manual'),
('模具表面污染', '表面脏', 'defect', 0.9, 'manual'),
('模具表面污染', '模污', 'defect', 0.9, 'manual'),
('模具表面污染', '油污', 'defect', 0.8, 'manual'),

-- 缩水 (sink marks)
('缩水', '缩痕', 'defect', 1.0, 'manual'),
('缩水', '凹陷', 'defect', 0.9, 'manual'),
('缩水', '缩印', 'defect', 0.9, 'manual'),

-- 顶白 (ejector marks)
('顶白', '顶针印', 'defect', 1.0, 'manual'),
('顶白', '顶出印', 'defect', 1.0, 'manual'),
('顶白', '顶针白', 'defect', 1.0, 'manual'),
('顶白', '顶痕', 'defect', 0.9, 'manual'),

-- 气纹 (flow marks/gas marks)
('气纹', '流痕', 'defect', 0.8, 'manual'),
('气纹', '气痕', 'defect', 1.0, 'manual'),
('气纹', '困气', 'defect', 0.7, 'manual'),

-- 熔接线 (weld lines)
('熔接线', '结合线', 'defect', 1.0, 'manual'),
('熔接线', '熔接痕', 'defect', 1.0, 'manual'),
('熔接线', '夹水线', 'defect', 0.9, 'manual'),

-- 变形 (warpage/deformation)
('变形', '翘曲', 'defect', 1.0, 'manual'),
('变形', '弯曲', 'defect', 0.9, 'manual'),
('变形', '扭曲', 'defect', 0.9, 'manual'),

-- 刮花 (scratches)
('刮花', '刮伤', 'defect', 1.0, 'manual'),
('刮花', '划伤', 'defect', 1.0, 'manual'),
('刮花', '拉伤', 'defect', 0.9, 'manual'),

-- 缺料 (short shot)
('缺料', '欠注', 'defect', 1.0, 'manual'),
('缺料', '填充不足', 'defect', 1.0, 'manual'),
('缺料', '短射', 'defect', 0.9, 'manual');

-- ============================================================================
-- Material Synonyms
-- ============================================================================

INSERT INTO troubleshooting_synonyms (canonical_term, synonym, term_type, confidence, source) VALUES
-- Common plastics
('ABS', 'ABS树脂', 'material', 1.0, 'manual'),
('HIPS', '高抗冲聚苯乙烯', 'material', 1.0, 'manual'),
('HIPS', 'HI-PS', 'material', 0.9, 'manual'),
('PP', '聚丙烯', 'material', 1.0, 'manual'),
('PC', '聚碳酸酯', 'material', 1.0, 'manual'),
('PA', '尼龙', 'material', 1.0, 'manual'),
('PA', '聚酰胺', 'material', 1.0, 'manual'),
('POM', '聚甲醛', 'material', 1.0, 'manual'),
('PBT', '聚对苯二甲酸丁二醇酯', 'material', 1.0, 'manual');

-- ============================================================================
-- Trial Version Synonyms
-- ============================================================================

INSERT INTO troubleshooting_synonyms (canonical_term, synonym, term_type, confidence, source) VALUES
('T0', '首次试模', 'trial', 1.0, 'manual'),
('T0', '第一次试模', 'trial', 1.0, 'manual'),
('T1', '第二次试模', 'trial', 1.0, 'manual'),
('T1', '二次试模', 'trial', 0.9, 'manual'),
('T2', '第三次试模', 'trial', 1.0, 'manual'),
('T2', '三次试模', 'trial', 0.9, 'manual');

-- ============================================================================
-- Result Status Synonyms
-- ============================================================================

INSERT INTO troubleshooting_synonyms (canonical_term, synonym, term_type, confidence, source) VALUES
('OK', '成功', 'result', 1.0, 'manual'),
('OK', '通过', 'result', 1.0, 'manual'),
('OK', '合格', 'result', 1.0, 'manual'),
('OK', '解决', 'result', 0.9, 'manual'),
('NG', '失败', 'result', 1.0, 'manual'),
('NG', '不通过', 'result', 1.0, 'manual'),
('NG', '不合格', 'result', 1.0, 'manual'),
('NG', '未解决', 'result', 0.9, 'manual');

-- ============================================================================
-- Process Synonyms
-- ============================================================================

INSERT INTO troubleshooting_synonyms (canonical_term, synonym, term_type, confidence, source) VALUES
('注塑', '射出', 'process', 1.0, 'manual'),
('注塑', '注射成型', 'process', 1.0, 'manual'),
('模具', '模子', 'process', 0.8, 'manual'),
('模具', '模仁', 'process', 0.7, 'manual'),
('浇口', '进胶口', 'process', 1.0, 'manual'),
('浇口', '入胶位', 'process', 0.9, 'manual'),
('流道', '跑胶道', 'process', 0.9, 'manual');

-- Verify seed data
SELECT term_type, COUNT(*) as count FROM troubleshooting_synonyms GROUP BY term_type ORDER BY term_type;
