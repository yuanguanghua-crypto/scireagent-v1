# -*- coding: utf-8 -*-
"""给 5 张表建 tsvector 维护 trigger + 回填 `search_vector`（2026-10-22）

## 为什么需要（FAILURE_MODES 10.2 的实测结论）
`/api/v1/search/grouped` **生产实测 4.87 秒**（普通 `/search` 只要 0.126 秒）。
根因不是"数据变多"，而是 `search_grouped_views.py` 在**查询时**用 `SearchVector(...)`
现场计算 tsvector —— 因为 `search_vector` 列虽然**存在**、GIN 索引也**建好了**，
但**列里从来没填过数据**（`0008_*` 迁移只建结构，没有 trigger、没有 backfill）。

⇒ 索引完全用不上，每次查询都要对候选行现场算 tsvector。

## 实测收益（28,600 行 application）
| 方式 | 耗时 | 计划 |
|---|---|---|
| 现场算 `to_tsvector(...)` | **205.8ms** | Seq Scan + 每行算向量 |
| 查 `search_vector` 列（命中全部） | **5.96ms** | Seq Scan（但不需算向量） |
| 查 `search_vector` 列（选择性） | **0.059ms** | **Bitmap Index Scan on `application_search_gin`** |

## 为什么用 trigger 而不是"表达式索引"
表达式索引要求查询表达式与索引表达式**逐字匹配**，而 Django 生成的表达式带
双重 `COALESCE((COALESCE(col,''))::text,'')`，靠手工对齐很脆弱。
`search_vector` **列和索引都已存在** ⇒ 只需填列 + 用 trigger 维护，
查询侧退化成最简单的 `filter(search_vector=...)`，没有匹配风险。

## 为什么回填放在 migration 里（而不是独立命令）
如果只建 trigger 不回填，部署后新查询查的是**空列** ⇒ **搜索直接返回空**
（比慢更糟）。放在同一 migration 里能保证"结构 + 数据"同时到位。
回填成本实测：28,600 行约 **2 秒**，可接受（部署时一次性）。

## 只在 PostgreSQL 下执行
`search_vector` 列在 sqlite 下不存在（`_USE_POSTGRES` 条件定义），
`to_tsvector` 也不是 sqlite 的函数 ⇒ 其它 vendor 直接跳过。
"""
from django.db import migrations

#: (表名, 搜索列, 索引名) —— 与 `search_grouped_views` 里的 `*_SEARCH_COLS` 必须一致。
#: 改这里的列清单，必须同步改视图里的常量，否则"搜索字段"会静默变窄。
TARGETS = [
    ('product', ['name', 'cas', 'catalog_no', 'formula', 'overview']),
    ('application', ['name', 'summary']),
    ('method', ['name', 'summary', 'purpose']),
    ('protocol', ['name', 'objective']),
    ('reference', ['title', 'authors', 'doi']),
]


def _fn_name(table):
    return f'{table}_search_vector_update'


def _trigger_name(table):
    return f'{table}_sv_trg'


def _new_expr(cols):
    """trigger 体内用 NEW.<col>。"""
    return " || ' ' || ".join(f"coalesce(NEW.{c}, '')" for c in cols)


def _row_expr(cols):
    """回填 UPDATE 用裸列名。"""
    return " || ' ' || ".join(f"coalesce({c}, '')" for c in cols)


def apply_forward(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cur:
        for table, cols in TARGETS:
            fn, trg = _fn_name(table), _trigger_name(table)
            cur.execute(f'''
                CREATE OR REPLACE FUNCTION {fn}() RETURNS trigger AS $$
                BEGIN
                  NEW.search_vector := to_tsvector('english',
                    {_new_expr(cols)});
                  RETURN NEW;
                END $$ LANGUAGE plpgsql;
            ''')
            cur.execute(f'DROP TRIGGER IF EXISTS {trg} ON {table};')
            cur.execute(f'''
                CREATE TRIGGER {trg}
                BEFORE INSERT OR UPDATE OF {', '.join(cols)}
                ON {table} FOR EACH ROW
                EXECUTE FUNCTION {fn}();
            ''')
            # ★ 回填：不填的话新查询会查空列 ⇒ 搜索直接返回空（比慢更糟）
            cur.execute(f'''
                UPDATE {table}
                   SET search_vector = to_tsvector('english', {_row_expr(cols)})
                 WHERE search_vector IS NULL;
            ''')
            # 统计信息：不 ANALYZE 的话 planner 可能不用索引
            cur.execute(f'ANALYZE {table};')


def apply_reverse(apps, schema_editor):
    """回滚只摘 trigger + 函数，**不清空 search_vector 列**。

    为什么不清空：清空会让"回滚后仍跑新代码"的中间态搜索变空；
    留着旧值最多是"数据略旧"，无害。
    """
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cur:
        for table, _cols in TARGETS:
            cur.execute(f'DROP TRIGGER IF EXISTS {_trigger_name(table)} ON {table};')
            cur.execute(f'DROP FUNCTION IF EXISTS {_fn_name(table)}();')


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge', '0023_fts_state_align'),
        ('commerce', '0016_fts_state_align'),
    ]

    operations = [
        migrations.RunPython(apply_forward, apply_reverse),
    ]
