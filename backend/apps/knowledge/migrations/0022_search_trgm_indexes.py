from django.db import migrations

# pg_trgm 索引：让 search_views.py 的 icontains（ILIKE '%q%'）走索引。
#
# 背景（生产实测，非推断）：
#   EXPLAIN ANALYZE SELECT id,name FROM application
#   WHERE name ILIKE '%zzzq%' OR summary ILIKE '%zzzq%' LIMIT 10;
#   → Seq Scan on application, Rows Removed by Filter: 28570, Execution Time: 183.247 ms
#
# 加上 gin_trgm_ops 后同一条查询 → Bitmap Index Scan, Execution Time: 0.130 ms（约 1400×）。
#
# ⚠️ 为什么不用 model Meta.indexes 自动生成：
#   ① 这些索引只对 PostgreSQL 有意义，SQLite 上 GinIndex/gin_trgm_ops 不可用；
#   ② 更关键：真正需要的是 UPPER(col) 上的**表达式**索引，而 Django 的
#      GinIndex(fields=[...]) 只能索引原列，无法表达 UPPER()。
#   本项目既有模式（见 0008_search_vectors.py）是「model Meta 里用 _USE_POSTGRES 条件
#   声明 + migration 里用 RunPython 手工执行」，此处沿用同一模式，不发明新机制。
#
# ⚠️ 为什么不碰 search_vector / 不用全文检索：
#   search_vector 字段在生产所有表的填充率都是 0（application 28570/0、method 47935/0、
#   protocol 14128/0、reference 437/0），且没有任何代码写入它。改用全文检索需要回填
#   9 万+ 行并会改变搜索语义（分词后子串匹配行为改变）。本次只加索引，
#   保持 icontains 子串匹配语义完全不变。
#
# 字段清单逐字对照 apps/knowledge/api/v1/search_views.py：
#   Application  name, summary
#   Method      name, summary, purpose
#   Protocol    name, objective
#   Reference   title, authors, doi
# Product 只有 125 行、EXPLAIN 实测 1.2 ms，非瓶颈，刻意不加索引。

_TRGM_INDEXES = [
    ('application', 'application_name_summary_trgm', ['name', 'summary']),
    ('method', 'method_name_summary_purpose_trgm', ['name', 'summary', 'purpose']),
    ('protocol', 'protocol_name_objective_trgm', ['name', 'objective']),
    ('reference', 'reference_title_authors_doi_trgm', ['title', 'authors', 'doi']),
]


def _upper_trgm_ddl(table, idx_name, columns):
    """生成 UPPER(表达式) 上的 GIN trigram 索引。

    ⚠️ 必须索引 UPPER(col) 表达式本身，不能索引原列：
    Django 的 `__icontains` 生成的是 `UPPER(col::text) LIKE UPPER('%q%')`
    （实测见下方说明），字段上套了函数，普通 col 上的 trigram 索引用不上。
    实测对照（production，同一条 application 查询）：
      索引建在原列→ Seq Scan，Execution Time 131ms
      索引建在 UPPER(col) → Bitmap Index Scan，Execution Time 0.332ms
    """
    exprs = ', '.join(f"(UPPER({c}::text)) gin_trgm_ops" for c in columns)
    return f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table} USING gin ({exprs});'


def enable_pg_trgm(apps, schema_editor):
    """PostgreSQL-only: 启用 pg_trgm 扩展 + 建 UPPER() 表达式 trigram GIN 索引。

    CREATE INDEX（非 CONCURRENTLY）会锁表写入；生产实测建索引耗时：
    application 4.0s、protocol 6.0s、method 0.3s、reference 0.1s，
    且索引总量约 18MB/表级，部署窗口内可接受。
    如需零停机，改为 CREATE INDEX CONCURRENTLY 并在事务外执行。
    """
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm;')
        for table, idx_name, columns in _TRGM_INDEXES:
            cursor.execute(_upper_trgm_ddl(table, idx_name, columns))


def disable_pg_trgm(apps, schema_editor):
    """回滚：删索引。注意不 DROP EXTENSION pg_trgm —— 它是库级共享对象，
    可能被其他迁移或人工创建的索引依赖。留扩展、删索引是可安全回滚的粒度。"""
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        for _table, idx_name, _columns in _TRGM_INDEXES:
            cursor.execute(f'DROP INDEX IF EXISTS {idx_name};')


class Migration(migrations.Migration):
    dependencies = [
        ('knowledge', '0021_add_origin_fields'),
    ]

    operations = [
        migrations.RunPython(enable_pg_trgm, disable_pg_trgm),
    ]