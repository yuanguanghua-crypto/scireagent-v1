-- ============================================================================
-- T3 · 回滚脚本：把 title 从 '' 还原为字面 'null'
-- 触发条件：STEP 2 提交后复核发现异常，或事后发现下游被影响
-- 前提：备份表 protocol_step_nulltitle_bak_20261102 仍在（30 天内）
-- ============================================================================
\pset pager off
\set ON_ERROR_STOP on

-- 前置检查：备份表必须存在且正好 1,056 行
DO $pre$
DECLARE n int;
BEGIN
    IF to_regclass('public.protocol_step_nulltitle_bak_20261102') IS NULL THEN
        RAISE EXCEPTION '备份表不存在，无法回滚';
    END IF;
    SELECT count(*) INTO n FROM protocol_step_nulltitle_bak_20261102;
    IF n <> 1056 THEN
        RAISE EXCEPTION '备份表行数 % <> 1056，拒绝回滚（先查清原因）', n;
    END IF;
END
$pre$;

BEGIN;

-- ★ 只还原"当前仍为空标题"的行（加 AND s.title = ''）。
--   原因：若执行过一次 apply 之后，有人**合法改过**备份表里某行的标题（比如人工补了真标题），
--   无条件的 UPDATE 会把他的人工编辑静默覆盖掉。加这个条件后：
--     · 仍是 '' 的行 → 还原为 'null'（回滚正常生效）
--     · 已被人工改成别的 → **不动它**，由下面的断言 R1/R2 报错，提醒人工确认
--   这样回滚变成"可安全重跑、且绝不静默覆盖他人改动"。
UPDATE protocol_step s
   SET title = b.old_title, updated_at = now()
  FROM protocol_step_nulltitle_bak_20261102 b
 WHERE s.id = b.id
   AND s.title = '';

DO $chk$
DECLARE
    n int;
    m int;
    restored int;
    touched int;
BEGIN
    -- 断言 R1：备份表内、当前 title='null' 的必须正好 1056（即全部还原成功）
    SELECT count(*) INTO restored FROM protocol_step s
      JOIN protocol_step_nulltitle_bak_20261102 b ON b.id = s.id
     WHERE s.title = 'null';
    -- 断言 R2：备份表内、当前仍是 '' 的必须为 0（没有漏还原的行）
    SELECT count(*) INTO touched FROM protocol_step s
      JOIN protocol_step_nulltitle_bak_20261102 b ON b.id = s.id
     WHERE s.title = '';
    IF restored <> 1056 OR touched <> 0 THEN
        RAISE EXCEPTION
            '回滚不完整：已还原 % / 应为 1056，仍为空的 % 行。'
            '很可能是备份表内有人工改过标题的行——脚本不覆盖人工编辑，'
            '请人工确认这些行后决定是否手动处理。已回滚本次操作。',
            restored, touched;
    END IF;

    -- 断言 R3：全库 title='null' 必须正好 1056
    SELECT count(*) INTO n FROM protocol_step WHERE title = 'null';
    IF n <> 1056 THEN
        RAISE EXCEPTION '回滚后 title=''null'' 应为 1056 行，实际 %，已回滚', n;
    END IF;

    -- 断言 R4：Null Model 必须仍是 2（回滚也不能误伤真标题）
    SELECT count(*) INTO m FROM protocol_step WHERE title = 'Null Model';
    IF m <> 2 THEN
        RAISE EXCEPTION '回滚后 Null Model 应为 2 行，实际 %，已回滚', m;
    END IF;
END
$chk$;

COMMIT;

-- 复核
SELECT count(*) AS restored_null FROM protocol_step WHERE title = 'null';
SELECT count(*) AS null_model FROM protocol_step WHERE title = 'Null Model';
