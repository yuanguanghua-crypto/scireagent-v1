-- ============================================================================
-- D · 回滚脚本：把 443 条 objective 从 '' 还原为备份表里的原大纲
--
-- 用途：D 执行后发现需要撤回时使用。
--
-- ⚠️ 加固点（比 T3 的回滚更严）：**只还原仍然为空的行**。
--    如果执行后有人工/其他流程给某些行填了真实 objective，本脚本**不覆盖**它。
--    ⇒ 还原行数 = 执行时刻"备份集合 ∩ objective=''" 的行数，可能 < 443。
--    因此断言不写死 443，而是与"实际还原集合"比对（见断言 C）。
--
-- ⚠️ 还原后 §4.3 过渡规则**恢复生效**（v3 §4.3 状态更新段）。
-- ============================================================================
\pset pager off
\set ON_ERROR_STOP on

DO $pre$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM protocol_objective_outline_bak_20261102;
    IF n <> 443 THEN
        RAISE EXCEPTION '前置检查失败：备份表 % 行 <> 443，无据可还原，已中止', n;
    END IF;
END
$pre$;

BEGIN;

-- 目标集合先落 TEMP 表（事务内，结束即消失）：备份集合 ∖ 已有非空 objective 的行
CREATE TEMP TABLE _d_restore_target ON COMMIT DROP AS
SELECT p.id
  FROM protocol p
  JOIN protocol_objective_outline_bak_20261102 b ON b.id = p.id
 WHERE p.objective = '';

-- 断言 A：目标集合不得超过备份总量
DO $a$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM _d_restore_target;
    IF n > 443 THEN
        RAISE EXCEPTION '断言A失败：待还原 % 行 > 443，说明备份表有重复/异常，已回滚', n;
    END IF;
    RAISE NOTICE '待还原行数 = %（=443 表示无人工改动；小于 443 表示有 % 行已被填真实值，将被保留）',
                 n, 443 - n;
END
$a$;

UPDATE protocol p
   SET objective = b.old_objective,
       updated_at = now()
  FROM protocol_objective_outline_bak_20261102 b
  JOIN _d_restore_target t ON t.id = b.id
 WHERE p.id = b.id;

-- 断言 B：还原后，目标集合里每一行都必须等于备份原文
DO $b$
DECLARE bad int;
BEGIN
    SELECT count(*) INTO bad
      FROM protocol p
      JOIN protocol_objective_outline_bak_20261102 b ON b.id = p.id
      JOIN _d_restore_target t ON t.id = p.id
     WHERE p.objective IS DISTINCT FROM b.old_objective;
    IF bad <> 0 THEN
        RAISE EXCEPTION '断言B失败：% 行还原值与备份不一致，已回滚', bad;
    END IF;
END
$b$;

-- 断言 C：全库窄口径行数必须正好等于"实际还原集合大小"
DO $c$
DECLARE
    n int;
    m int;
BEGIN
    SELECT count(*) INTO n FROM protocol WHERE objective LIKE '1: title:%';
    SELECT count(*) INTO m FROM _d_restore_target;
    IF n <> m THEN
        RAISE EXCEPTION '断言C失败：还原后大纲型 % 行 <> 待还原集合 % 行，已回滚', n, m;
    END IF;
END
$c$;

-- 断言 D：总协议数不变
DO $d$
DECLARE total int;
BEGIN
    SELECT count(*) INTO total FROM protocol;
    IF total <> 13895 THEN
        RAISE EXCEPTION '断言D失败：总协议数 % <> 13895，已回滚', total;
    END IF;
END
$d$;

COMMIT;

-- 提交后复核（只读）
SELECT count(*) AS outline_restored FROM protocol WHERE objective LIKE '1: title:%';
SELECT count(*) AS now_empty FROM protocol WHERE objective = '';
SELECT count(*) AS total_protocol FROM protocol;

-- ⚠️ 回滚**不要**删备份表 —— 保留 90 天，留待再次确认。
