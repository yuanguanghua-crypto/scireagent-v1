-- ============================================================================
-- D · 执行脚本：把 Protocol.objective 里"文档大纲"型污染置为 ''（空串）
--
-- 背景：443 条 source='bioprocorpus' 的协议，objective 被写成了文档大纲
--       （形态 `1: title: \r1.1: …\r1.2: …`）。根因是 backfill_protocol_objective
--       把结构字段 hierarchical_protocol 当作最后兜底写进了 objective。
--       源头（bioprocorpus 语料）目标类字段全空，没有正确 objective 可取 ⇒
--       正确处理是留空（"这条没有目标证据"），不是塞大纲。
--
-- 决定：2026-11-02 16:52 用户「就按 1–4 步收尾，选 DD + 同时修导入映射，90 天」
-- 报告：work/objective污染_只读调查报告_20261102.md
-- 规范：docs/方法定义规范_v3.md §4.2 / §4.3 / §4.4
--
-- ⚠️ 本脚本会写生产库。执行前必须已完成：
--    ① 导入映射已修（backfill_protocol_objective 不再写 hierarchical_protocol）
--       —— 否则下次重导会再污染，属"治标不治本"
--    ② 已把末尾 COMMIT 换成 ROLLBACK 完整演练过一遍，断言全绿
--
-- ⚠️ 绝对不能把 WHERE objective LIKE '1: title:%' 放宽成
--    objective ~ '^[0-9]+(\.[0-9]+)*[[:space:]]*:'
--    —— 宽口径 542 条里另有 99 条性质未确认（可能是合法编号列表），**不许一起动**。
--    断言 F 就是守这条：改完宽口径必须正好剩 99。
--
-- ⚠️ objective 列是 NOT NULL（实测 is_nullable=NO）⇒ 只能置 ''，不能置 NULL。
--
-- 执行：
--   ssh admin@47.82.156.48 'docker exec -i scireagent-db-1 \
--     psql -U scireagent -d scireagent -v ON_ERROR_STOP=1' < d_objective_apply.sql
-- ============================================================================
\pset pager off
\set ON_ERROR_STOP on

-- ---------------------------------------------------------------------------
-- 基线（2026-11-02 16:54 实测，执行前必须与此一致，否则断言会拦）
--   总协议数                       13,895
--   窄口径 LIKE '1: title:%'          443
--   宽口径 编号开头                    542
--   objective='' 全库                  88   （全部是 source='curated'）
--   objective='' 其中 bioprocorpus       0
--   objective IS NULL                   0
--   窄口径的最小/平均/最大长度  17 / 3,310 / 65,180，合计 1,466,413 字符
-- ---------------------------------------------------------------------------
-- 【重跑规程】本脚本可安全重跑，不需要先手工清备份表
--   ① 备份表独立提交；UPDATE 事务回滚后，备份表那 443 行会留着。
--   ② INSERT 带 `ON CONFLICT (id) DO NOTHING`，id 是 PRIMARY KEY
--      ⇒ 第二次插入命中 443 个冲突，插入 0 行，总数仍是 443（断言 A 不会误拦）。
--   ③ 但首次已 COMMIT 之后再跑：WHERE 命中 0 行 ⇒ **断言 B 会失败并中止**。
--      这是**有意为之**：D 只应执行一次，二次执行必须被拦下而不是静默"成功"。
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- STEP 1｜独立备份表（自动提交，脱离后面的 UPDATE 事务，保证回滚有据）
--        保留期 90 天（用户 2026-11-02 定）。
--        置空后表里就没了，只剩本备份与源头大纲 ⇒ 备份是唯一原值来源。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS protocol_objective_outline_bak_20261102 (
    id            bigint PRIMARY KEY,
    old_objective text   NOT NULL,
    old_len       int    NOT NULL,
    backed_up_at  timestamptz NOT NULL DEFAULT now(),
    keep_until    date   NOT NULL DEFAULT (now() + interval '90 days')::date
);

COMMENT ON TABLE protocol_objective_outline_bak_20261102 IS
  'D 处置备份：objective 为文档大纲的 443 条协议原值。保留 90 天。'
  '导出件与核验包同待遇，绝不发给标注员（含 7520/protocol 6652 与 11658/protocol 13450 原文）。';

INSERT INTO protocol_objective_outline_bak_20261102 (id, old_objective, old_len)
SELECT id, objective, length(objective)
  FROM protocol
 WHERE objective LIKE '1: title:%'
ON CONFLICT (id) DO NOTHING;

-- 断言 A：备份必须正好 443 行
DO $bk_count$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM protocol_objective_outline_bak_20261102;
    IF n <> 443 THEN
        RAISE EXCEPTION '断言A失败：备份行数 % <> 443，已中止，未做任何修改', n;
    END IF;
END
$bk_count$;

-- 断言 A2：备份内容必须是"完整大纲原文"，不许截断、不许空
DO $bk_intact$
DECLARE bad int;
BEGIN
    SELECT count(*) INTO bad
      FROM protocol_objective_outline_bak_20261102
     WHERE old_objective NOT LIKE '1: title:%'
        OR old_len <> length(old_objective)
        OR old_len < 17;
    IF bad <> 0 THEN
        RAISE EXCEPTION '断言A2失败：备份内容异常 % 行（非大纲原文/长度不符/短于17），已中止', bad;
    END IF;
END
$bk_intact$;

-- ---------------------------------------------------------------------------
-- STEP 2｜一个事务内完成：置空 + 六道断言；任一断言失败 → 整体回滚
-- ---------------------------------------------------------------------------
-- 【updated_at 影响面】显式写 updated_at = now()，会让这 443 行时间戳变化。
--   已全仓排查（2026-11-02）：
--     · ProtocolListSerializer.fields = id/name/slug/version/status/methods/created_at
--       —— **不含 updated_at**（不暴露给列表 API）
--     · `order_by(…updated_at)` / `updated_at__gt|gte|lt|lte` 对 Protocol —— 0 命中
--       （仅 bridges 的 ProductProtocol 测试里读，与本表无关）
--     · 列定义 auto_now=True ⇒ 任何 ORM 写入本来就会改它，raw SQL 保持同语义
--   ⚠️ 限度：以上是**静态检索**结论，不能证明仓库之外（手工运维脚本、外部 BI）没读它。
BEGIN;

UPDATE protocol
   SET objective = '', updated_at = now()
 WHERE objective LIKE '1: title:%'
   AND id IN (SELECT id FROM protocol_objective_outline_bak_20261102);

-- 断言 B：备份集合里，置空后必须正好 443 行 objective=''
DO $b$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM protocol
     WHERE id IN (SELECT id FROM protocol_objective_outline_bak_20261102)
       AND objective = '';
    IF n <> 443 THEN
        RAISE EXCEPTION '断言B失败：置空后应为 443 行，实际 %（若为 0 说明本脚本已执行过），已回滚', n;
    END IF;
END
$b$;

-- 断言 C：全库不得再存在窄口径大纲型 objective
DO $c$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM protocol WHERE objective LIKE '1: title:%';
    IF n <> 0 THEN
        RAISE EXCEPTION '断言C失败：仍有 % 行 objective 是大纲，已回滚', n;
    END IF;
END
$c$;

-- 断言 D：总协议数不变（只改 objective，一行不删）
--   ⚠️ 对**并发写入**敏感：若执行窗口内有人新增/删除协议，总数会变、D 会误拦。
--      **误拦的结果是整体回滚，是安全的一侧**，只是白跑一次。
--      ⇒ 选安静时段执行，不要在批量导入协议的时段跑。
DO $d$
DECLARE total int;
BEGIN
    SELECT count(*) INTO total FROM protocol;
    IF total <> 13895 THEN
        RAISE EXCEPTION '断言D失败：总协议数 % <> 13895，已回滚', total;
    END IF;
END
$d$;

-- 断言 E：空 objective 总数必须正好 531（= 既有 88 + 本次 443）
--   两个集合互斥（既有 88 全是 curated，本次 443 全是 bioprocorpus），可直接相加。
DO $e$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM protocol WHERE objective = '';
    IF n <> 531 THEN
        RAISE EXCEPTION '断言E失败：空 objective 总数 % <> 531（应为 88 既有 + 443 本次），已回滚', n;
    END IF;
END
$e$;

-- 断言 F：宽口径必须正好剩 99（542 − 443）—— 证明没有扩大打击面
DO $f$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM protocol
     WHERE objective ~ '^[0-9]+(\.[0-9]+)*[[:space:]]*:';
    IF n <> 99 THEN
        RAISE EXCEPTION '断言F失败：宽口径剩 % <> 99 —— 打击面超了，已回滚', n;
    END IF;
END
$f$;

-- 断言 G：备份表 443 行内容一个字节都没被 UPDATE 波及
DO $g$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM protocol_objective_outline_bak_20261102
     WHERE old_objective LIKE '1: title:%' AND old_len = length(old_objective);
    IF n <> 443 THEN
        RAISE EXCEPTION '断言G失败：备份内容完好行数 % <> 443，已回滚', n;
    END IF;
END
$g$;

COMMIT;

-- ---------------------------------------------------------------------------
-- STEP 3｜提交后复核（只读）—— 与断言 B–F 一一对应，独立再验一遍
--   期望：still_outline=0 / now_empty=531 / wide=99 / total=13895 / backup_rows=443
-- ---------------------------------------------------------------------------
SELECT count(*) AS still_outline FROM protocol WHERE objective LIKE '1: title:%';
SELECT count(*) AS now_empty FROM protocol WHERE objective = '';
SELECT count(*) AS wide_remaining FROM protocol
 WHERE objective ~ '^[0-9]+(\.[0-9]+)*[[:space:]]*:';
SELECT count(*) AS total_protocol FROM protocol;
SELECT count(*) AS backup_rows,
       min(keep_until) AS keep_until,
       sum(old_len)    AS backup_chars
  FROM protocol_objective_outline_bak_20261102;

-- 备份表保留 90 天（至 2027-01-31），到期并确认稳定后再人工删除：
--   DROP TABLE protocol_objective_outline_bak_20261102;
-- ⚠️ 删除前必须先完成导出双保险（dist/_released_*），否则原值将不可恢复。
