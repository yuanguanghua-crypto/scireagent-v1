# deploy/sql · 生产数据操作脚本（入仓版）

> 这些是从 `work/` **复制**过来的正式版本（**不是移动** —— 旧报告里 `work/xxx.sql` 的引用要保持可用）。
> `work/` 已于 2026-11-02 整目录加入 `.gitignore`（里面有 κ 判定 / 盲测批 / 样本原文，绝不能误提交）。

## 文件

| 文件 | 作用 | 是否写数据 |
|---|---|---|
| `d_objective_apply.sql` | D 处置：443 条大纲型 `objective` 置 `''`，8 道断言 + 独立备份表 | ✅ 写（一次性，二次执行会被断言 B 拦下） |
| `d_objective_rollback.sql` | D 回滚：从备份表还原，**只还原仍为空的行**，不覆盖人工填写 | ✅ 写 |
| `d_objective_probe.sql` | D 执行前的只读基线探针 | ❌ 全 SELECT |
| `t3_null_title_apply.sql` | T3：`ProtocolStep.title` 字面 `'null'` → `''`（1,056 行） | ✅ 写 |
| `t3_null_title_rollback.sql` | T3 回滚 | ✅ 写 |

## 执行方式（生产）

```bash
ssh admin@47.82.156.48 'docker exec -i scireagent-db-1 \
  psql -U scireagent -d scireagent -v ON_ERROR_STOP=1' < deploy/sql/<file>.sql
```

## 硬规

1. **每个 apply 都必须先 ROLLBACK 演练**（把末尾 `COMMIT;` 换成 `ROLLBACK;` 跑一遍），断言全绿再真跑。
2. **备份表独立提交**，脱离 UPDATE 事务，保证回滚有据。
3. **导出件校验不能只看"文件存在"** —— 必须核「行数 + 长度合计」（2026-11-02 踩过：SSH 限速把 1.28MB CSV 传断，只落 370/443 行）。
4. **回滚只还原仍为空的行**，不覆盖期间的人工编辑；断言按"实际还原集合"比对，不写死行数。
5. 备份保留期见各脚本头注释（T3 30 天 / D **90 天**，至 2027-01-31）。

## 与 `work/` 的关系

`work/` 里的同名文件是**同一份内容的源**（md5 一致，2026-11-02 核对）。
**改脚本时两边都要更新**，否则会漂移；判断"哪份是真的"以 md5 相同为准，不同则以本目录为准并回写 `work/`。
