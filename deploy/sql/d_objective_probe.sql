-- 只读探针：D 执行前必须报的数（不写任何数据）
\pset pager off
\set ON_ERROR_STOP on

SELECT '1 总协议数' AS k, count(*)::text AS v FROM protocol
UNION ALL
SELECT '2 窄口径 LIKE 1: title:%', count(*)::text FROM protocol WHERE objective LIKE '1: title:%'
UNION ALL
SELECT '3 宽口径 编号开头', count(*)::text FROM protocol WHERE objective ~ '^[0-9]+(\.[0-9]+)*[[:space:]]*:'
UNION ALL
SELECT '4 objective为空(全库)', count(*)::text FROM protocol WHERE objective = ''
UNION ALL
SELECT '5 objective为空(bioprocorpus)', count(*)::text FROM protocol WHERE objective = '' AND source = 'bioprocorpus'
UNION ALL
SELECT '6 bioprocorpus总数', count(*)::text FROM protocol WHERE source = 'bioprocorpus'
UNION ALL
SELECT '7 窄口径∩bioprocorpus', count(*)::text FROM protocol WHERE objective LIKE '1: title:%' AND source = 'bioprocorpus'
UNION ALL
SELECT '8 objective为NULL', count(*)::text FROM protocol WHERE objective IS NULL;

-- 列属性：是否 NOT NULL、类型、默认值
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'protocol' AND column_name IN ('objective','updated_at','name','source');

-- 与已发批次的交集：7520(protocol 6652) 与 11658(protocol 13450)
SELECT id, (objective LIKE '1: title:%') AS is_outline, length(objective) AS len
FROM protocol WHERE id IN (6652, 13450) ORDER BY id;

-- 形态抽检：前 3 条 + 末 3 条
(SELECT id, left(replace(objective, chr(13), '\r'), 90) AS head FROM protocol
  WHERE objective LIKE '1: title:%' ORDER BY id LIMIT 3)
UNION ALL
(SELECT id, left(replace(objective, chr(13), '\r'), 90) FROM protocol
  WHERE objective LIKE '1: title:%' ORDER BY id DESC LIMIT 3);

-- 窄口径里 objective 长度分布（备份容量预估）
SELECT min(length(objective)) AS min_len, round(avg(length(objective))) AS avg_len,
       max(length(objective)) AS max_len, sum(length(objective)) AS total_chars
FROM protocol WHERE objective LIKE '1: title:%';
