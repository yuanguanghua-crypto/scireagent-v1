-- ============================================================================
-- T3 · 执行脚本：把 ProtocolStep.title 里字面字符串 'null' 置为 ''（空串）
--
-- ⚠️ 本脚本会写生产库。执行前必须满足 work/T3_证据包_20261102.md §6 的放行条件。
-- ⚠️ 必须在"发盲测包之前"或"κ 全部做完之后"执行，不得在标注进行中改底层数据。
-- ⚠️ 绝对不能把 WHERE title = 'null' 改成 ILIKE 'null%' / LIKE 'null%'
--    —— 会误杀 2 条真标题 "Null Model"（step 68583 / 68584，协议 2145）。
-- ⚠️ title 列是 NOT NULL，只能置 ''，不能置 NULL。
--
-- 执行：docker exec -i -e PGPASSWORD=*** scireagent-db-1 \
--         psql -U scireagent -d scireagent -v ON_ERROR_STOP=1 < t3_null_title_apply.sql
-- ============================================================================
\pset pager off
\set ON_ERROR_STOP on

-- ---------------------------------------------------------------------------
-- 【重跑规程】本脚本可安全重跑，不需要先手工清备份表
--
--   ① 备份表是独立提交的；UPDATE 事务回滚后，备份表那 1,056 行会留着。
--   ② 但重跑时 INSERT 带 `ON CONFLICT (id) DO NOTHING`（见下方 INSERT 语句），
--      且 id 是 PRIMARY KEY ⇒ 第二次插入命中 1,056 个冲突，插入 0 行，总数仍是 1,056。
--      **不会变成 2,112，备份行数闸门（DO $bk$）也不会误拦。**
--   ③ 已用 TEMP 表实测（会话级、事务结束即消失、零持久写入）：
--        第 1 次 INSERT 0 1056 → count 1056
--        第 2 次 INSERT 0 0    → count 1056
--        第 3 次 INSERT 0 0    → count 1056
--      对照组（故意去掉 ON CONFLICT）：直接
--        ERROR: duplicate key value violates unique constraint "bak_test_pkey"
--      ⇒ 没有 ON CONFLICT 时也**不会**变成 2,112，而是立刻报错。
--        两种情况下都不可能出现 2,112。
--   ④ 首次已 COMMIT 成功后再重跑：`WHERE title='null'` 返回 0 行 → UPDATE 影响 0 行
--      → 断言 A–E 仍全部成立 → COMMIT 成功。**是一次无害的空操作。**
--
--   唯一需要人工做的事：若曾用非本脚本的方式改过备份表内容，先
--       TRUNCATE protocol_step_nulltitle_bak_20261102;
--   再跑本脚本。否则 ON CONFLICT 会沿用旧值（本场景下旧值仍是正确的 'null'）。
-- ---------------------------------------------------------------------------
-- STEP 1｜建独立备份表（自动提交，脱离后面的 UPDATE 事务，保证回滚有据）
--        只备份被改动的 1,056 行，不动其他数据。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS protocol_step_nulltitle_bak_20261102 (
    id        bigint PRIMARY KEY,
    old_title varchar(255) NOT NULL,
    backed_up_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO protocol_step_nulltitle_bak_20261102 (id, old_title)
SELECT id, title FROM protocol_step WHERE title = 'null'
ON CONFLICT (id) DO NOTHING;

-- 断言：备份必须正好 1,056 行，否则中止
DO $bk$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM protocol_step_nulltitle_bak_20261102;
    IF n <> 1056 THEN
        RAISE EXCEPTION '备份行数 % <> 1056，已中止，未做任何修改', n;
    END IF;
END
$bk$;

-- ---------------------------------------------------------------------------
-- STEP 2｜一个事务内完成：更新 + 五道断言；任一断言失败 → 整体回滚
-- ---------------------------------------------------------------------------
-- 【updated_at 影响面】显式写 updated_at = now()，会让这 1,056 行的时间戳全部变化。
--   已全仓排查，**没有任何流程依赖 ProtocolStep.updated_at**：
--     · `updated_at__gt` / `updated_at__gte` / `last_synced` / `since=` —— 全仓 0 命中
--     · `order_by('-updated_at')` —— 0 命中
--     · `ProtocolStepSerializer.fields` 里**没有** updated_at（不暴露给 API/前端）
--     · `backfill_protocol_steps` 选取条件是"该协议没有任何步骤"（exclude id__in=with_steps），
--       **不看 title、也不看 updated_at** ⇒ 置空标题不会触发它重跑
--   ⚠️ 限度：以上是**静态检索**结论，不能证明仓库之外（手工运维脚本、外部 BI）没有读它。
BEGIN;

UPDATE protocol_step
   SET title = '', updated_at = now()
 WHERE title = 'null'
   AND id IN (SELECT id FROM protocol_step_nulltitle_bak_20261102);

-- 断言 A：改动行数必须正好 1,056
DO $a$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM protocol_step
     WHERE id IN (SELECT id FROM protocol_step_nulltitle_bak_20261102)
       AND title = '';
    IF n <> 1056 THEN
        RAISE EXCEPTION '断言A失败：置空后应为 1056 行，实际 %，已回滚', n;
    END IF;
END
$a$;

-- 断言 B：全库不得再存在 title = 'null'
DO $b$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM protocol_step WHERE title = 'null';
    IF n <> 0 THEN
        RAISE EXCEPTION '断言B失败：仍有 % 行 title=''null''，已回滚', n;
    END IF;
END
$b$;

-- 断言 C：2 条真标题 "Null Model" 必须原样保留（防误伤闸门）
DO $c$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM protocol_step WHERE title = 'Null Model';
    IF n <> 2 THEN
        RAISE EXCEPTION '断言C失败：Null Model 应为 2 行，实际 % —— 说明用错了宽匹配，已回滚', n;
    END IF;
END
$c$;

-- 断言 D：总行数不变、body 一个字节都没动（只改 title）
--   ⚠️ D1（总步数 = 381001）对**并发写入**敏感：若执行窗口内有人新增/删除步骤，
--      总数会变，D1 会误拦。**误拦的结果是整体回滚，是安全的一侧**，只是白跑一次。
--      ⇒ 执行窗口要选安静的时段，**不要在有人批量导入协议/步骤的时段跑**。
--      （本项目当前为开发测试态，正常没有并发导入；仍按此选窗口。）
DO $d$
DECLARE
    total int;
    body_changed int;
BEGIN
    SELECT count(*) INTO total FROM protocol_step;
    IF total <> 381001 THEN
        RAISE EXCEPTION '断言D1失败：总步数 % <> 381001，已回滚', total;
    END IF;
    SELECT count(*) INTO body_changed FROM protocol_step s
     JOIN protocol_step_nulltitle_bak_20261102 b ON b.id = s.id
     WHERE s.body IS NULL;
    IF body_changed <> 0 THEN
        RAISE EXCEPTION '断言D2失败：有 % 行 body 变成 NULL，已回滚', body_changed;
    END IF;
END
$d$;

-- 断言 E：空标题总数必须正好 1,105（= 既有 49 + 本次 1,056）
--         两个谓词互斥（title='' 与 title='null' 无交集，已验证 overlap_rows=0），所以可直接相加。
DO $e$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM protocol_step WHERE title = '';
    IF n <> 1105 THEN
        RAISE EXCEPTION '断言E失败：空标题总数 % <> 1105（应为 49 既有 + 1056 本次），已回滚', n;
    END IF;
END
$e$;

COMMIT;

-- ---------------------------------------------------------------------------
-- STEP 3｜提交后复核（只读）—— 与断言 A–E 一一对应，独立再验一遍
--   期望：still_null=0 / null_model_kept=2 / now_empty=1105 / backup_rows=1056
-- ---------------------------------------------------------------------------
SELECT count(*) AS still_null FROM protocol_step WHERE title = 'null';
SELECT count(*) AS null_model_kept FROM protocol_step WHERE title = 'Null Model';
SELECT count(*) AS now_empty, count(DISTINCT protocol_id) AS empty_protocols
FROM protocol_step WHERE title = '';
SELECT count(*) AS backup_rows FROM protocol_step_nulltitle_bak_20261102;

-- 备份表保留 30 天，确认稳定后再人工删除：
--   DROP TABLE protocol_step_nulltitle_bak_20261102;
