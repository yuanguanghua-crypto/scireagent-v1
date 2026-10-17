#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prod_schema_tables.py — 生产库真实表名清单（**绝对只读**）

要解决的真实事故：
    查产品方法表时，我按本地 Django 的默认约定猜表名 `productmethod`，
    实际生产是 **`product_method`**（带下划线、无 app 前缀）
    ⇒ SQL 直接报 `relation "productmethod" does not exist`。
    真名要去 `pg_tables` 查，而查表名这件事本身完全不需要写权限。

本脚本的**唯一职责**：把「真表名是什么」这件事从「猜」变成「查」。
所以它有三个不可让步的性质：
  1. **只读**：全程只发 SELECT。脚本里硬编码了一条 SQL 白名单式守卫 ——
     任何被送进 psql 的 SQL 都要先过 `_assert_readonly()`，
     出现 INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/GRANT 等
     关键字就**在本地就拒绝**，根本不会发到生产。
     （仅靠"我不写写操作"的自觉是不够的：脚本会被别人改。）
  2. **可退化**：不在生产 / 没有 docker 时，用本地 sqlite 跑同一套逻辑，
     保证这个工具在任何机器上都能验证表名，不会因为环境差异而废掉。
  3. **能直接查**：支持子串过滤（`--grep method`），
     这是为「我只知道大概叫 method」这个真实场景准备的。

用法：
    # 生产（docker exec 进 postgres 容器）
    python scripts/prod_schema_tables.py
    python scripts/prod_schema_tables.py --grep method      # 只看含 method 的表
    python scripts/prod_schema_tables.py --rows             # 带上每表行数
    python scripts/prod_schema_tables.py --container scireagent-db-1

    # 本地退化（sqlite，不需要 docker）
    python scripts/prod_schema_tables.py --sqlite backend/db.sqlite3
    python scripts/prod_schema_tables.py --sqlite :memory: --grep product

退出码：0 = 成功（查到表）；1 = 没查到（grep 无命中，或库是空的）；
        2 = 环境/用法错误。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 与 scripts/ops/prod_monitor.py 保持一致的生产连接参数
DEFAULT_CONTAINER = "scireagent-db-1"
DEFAULT_DB_USER = "scireagent"
DEFAULT_DB_NAME = "scireagent"

# ★ 只读守卫：这些词一旦出现在 SQL 里就拒绝发送。
# 注意 `pg_tables` 这类**元数据**查询是安全的，不在禁词表里。
FORBIDDEN = (
    "insert", "update", "delete", "drop", "alter", "create", "truncate",
    "grant", "revoke", "replace", "merge", "copy", "vacuum", "reindex",
    "comment", "call", "do", "execute", "set", "begin", "commit", "lock",
)


def _assert_readonly(sql: str) -> None:
    """发送前硬校验：SQL 必须是纯 SELECT。

    为什么需要它：只读脚本最大的风险不是"写错了"，而是"某天有人加了个功能"。
    把约束写进代码里（而不是写进注释里），才拦得住。
    """
    low = sql.lower()
    # 去掉注释与字符串字面量，避免注释/字符串里出现关键字造成误判
    stripped = re.sub(r"--[^\n]*", " ", low)
    stripped = re.sub(r"/\*.*?\*/", " ", stripped, flags=re.S)
    stripped = re.sub(r"'[^']*'", "''", stripped)

    for w in FORBIDDEN:
        # 用词边界匹配，避免 `updated_at` 里的 `update` 被误判
        if re.search(r"\b" + w + r"\b", stripped):
            raise PermissionError(
                f"拒绝发送：SQL 含被禁关键字 '{w}'。本脚本只允许只读查询。\n"
                f"  SQL: {sql[:200]}")


def psql_query(sql: str, container: str, user: str, dbname: str,
                timeout: int = 30) -> str:
    """通过 docker exec 跑一条只读 SQL，返回 stdout。"""
    _assert_readonly(sql)
    if not shutil.which("docker"):
        raise RuntimeError(
            "找不到 docker 可执行文件。\n"
            "  · 在本机请加 --sqlite <db路径> 走退化模式；\n"
            "  · 生产请在有 docker 的机器上运行。")
    cmd = ["docker", "exec", container,
           "psql", "-U", user, "-d", dbname, "-tAF", "|", "-c", sql]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"docker exec 超时（{timeout}s）")
    if p.returncode != 0:
        raise RuntimeError(
            f"psql 返回非 0（{p.returncode}）：\n"
            f"{(p.stderr or p.stdout or '').strip()[:500]}")
    return p.stdout


def list_tables_pg(container: str, user: str, dbname: str,
                   with_rows: bool, schema: str = "public") -> list[dict]:
    """取 pg_tables 全清单（表名 + 大小），可选行数。"""
    sql = (
        "SELECT schemaname, tablename "
        "FROM pg_tables "
        f"WHERE schemaname = '{schema}' "
        "ORDER BY tablename"
    )
    out = []
    for line in psql_query(sql, container, user, dbname).splitlines():
        parts = line.split("|")
        if len(parts) < 2:
            continue
        schema_name, table = parts[0].strip(), parts[1].strip()
        if not table:
            continue
        entry = {"schema": schema_name, "table": table, "rows": None}
        if with_rows:
            # 逐表行数：Postgres 里精确 count 在大表上很慢，
            # 这里用 reltuples 估算（pg_class 的统计值，秒回）。
            # 需要精确值时用 --exact-rows（会明显变慢）。
            entry["rows_estimated"] = True
            out.append(entry)
            continue
        out.append(entry)

    if with_rows:
        # 批量取估算行数，避免 N 次往返
        est_sql = (
            "SELECT schemaname || '.' || relname, n_live_tup "
            "FROM pg_stat_user_tables "
            f"WHERE schemaname = '{schema}'"
        )
        est = {}
        for line in psql_query(est_sql, container, user, dbname).splitlines():
            parts = line.split("|")
            if len(parts) == 2:
                try:
                    est[parts[0].strip()] = int(parts[1].strip())
                except ValueError:
                    pass
        for e in out:
            e["rows"] = est.get(f"{e['schema']}.{e['table']}")
    return out


def list_tables_exact_rows_pg(container, user, dbname, schema="public"):
    """精确行数（慢，仅在 --exact-rows 时用）。"""
    names = psql_query(
        "SELECT tablename FROM pg_tables "
        f"WHERE schemaname = '{schema}' ORDER BY tablename",
        container, user, dbname).splitlines()
    out = []
    for t in names:
        t = t.strip()
        if not t:
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", t):
            continue        # 跳过奇怪表名，绝不拼接未校验的标识符
        sql = f"SELECT COUNT(*) FROM \"{schema}\".\"{t}\""   # noqa: S608 只读
        try:
            v = psql_query(sql, container, user, dbname).strip()
            n = int(v) if v.isdigit() else None
        except Exception:
            n = None
        out.append({"schema": schema, "table": t, "rows": n})
    return out


def list_tables_sqlite(path: str) -> list[dict]:
    """退化模式：从 sqlite 文件读表名 + 精确行数。

    ⚠️ sqlite 的表名是**本地 Django 迁移生成**的，与生产 Postgres 可能不同 ——
    这正是本脚本存在的原因。所以退化模式只用来验证「脚本能跑」和
    「大概有哪些表」，**不能拿它当生产真值的来源**。
    """
    if path != ":memory:" and not os.path.isfile(path):
        raise RuntimeError(f"sqlite 文件不存在：{path}")
    conn = sqlite3.connect(path)
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name").fetchall()]
        out = []
        for t in tables:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", t):
                continue
            try:
                n = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]  # noqa: S608
            except sqlite3.Error:
                n = None
            out.append({"schema": "main", "table": t, "rows": n})
        return out
    finally:
        conn.close()


def render(tables, grep, source, degraded: bool) -> str:
    lines = []
    lines.append("=" * 78)
    lines.append(f"生产表清单｜来源：{source}")
    if degraded:
        lines.append("⚠️ 退化模式（sqlite 本地库）：表名/结构**不代表生产真值**，")
        lines.append("   仅用于验证脚本可运行。生产真值必须走 docker exec psql。")
    lines.append("=" * 78)
    lines.append("")

    if grep:
        matches = [t for t in tables if grep.lower() in t["table"].lower()]
        lines.append(f"过滤：表名含 '{grep}'（共 {len(matches)} / {len(tables)} 张表）")
        lines.append("")
        if not matches:
            lines.append(f"❌ 没有表名含 '{grep}'。")
            lines.append("   ⇒ 别急着改代码：先用不带 --grep 的全量清单看看真实命名规律。")
            return "\n".join(lines)
        tables = matches
    else:
        lines.append(f"共 {len(tables)} 张表")
        lines.append("")

    if not tables:
        # 空库也要给出可读输出（max() 对空序列会抛，是实测踩到的坑）
        lines.append("❌ 这是一个空库（0 张表）。")
        if degraded:
            lines.append("   ⇒ sqlite 空库通常说明文件还没迁移过：")
            lines.append("     cd backend && DB_ENGINE=sqlite SECRET_KEY=x "
                         "venv/Scripts/python.exe manage.py migrate")
        else:
            lines.append("   ⇒ 生产库不该是空的，确认 --dbname / --schema 是否指对了。")
        return "\n".join(lines)

    has_rows = any(t.get("rows") is not None for t in tables)
    if has_rows:
        width = max(len(t["table"]) for t in tables)
        lines.append(f"  {'表名'.ljust(width)}  行数")
        lines.append(f"  {'-' * width}  ----")
        for t in tables:
            r = t["rows"]
            rtxt = "?" if r is None else f"{r:,}"
            mark = "~" if t.get("rows_estimated") and r is not None else " "
            lines.append(f"  {t['table'].ljust(width)}  {mark}{rtxt}")
        if any(t.get("rows_estimated") for t in tables):
            lines.append("")
            lines.append("  （行数带 ~ 前缀 = pg_stat 估算值，秒回但可能不准；"
                         "要精确值加 --exact-rows）")
    else:
        width = max(len(t["table"]) for t in tables)
        for t in tables:
            lines.append(f"  {t['table'].ljust(width)}")

    lines.append("")
    lines.append("提示：这正是今天那个坑的正解 —— 表名可能是 product_method "
                 "而不是 productmethod，也可能带 app 前缀也可能不带。")
    lines.append("       查得到就用查到的，不要按本地习惯猜。")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="列生产库真实表名（绝对只读）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("--container", default=DEFAULT_CONTAINER,
                    help=f"postgres 容器名，默认 {DEFAULT_CONTAINER}")
    ap.add_argument("--user", default=DEFAULT_DB_USER)
    ap.add_argument("--dbname", default=DEFAULT_DB_NAME)
    ap.add_argument("--schema", default="public")
    ap.add_argument("--sqlite", default=None,
                    help="退化模式：改从本地 sqlite 文件读（不需要 docker）")
    ap.add_argument("--grep", default=None,
                    help="只显示表名含该子串的表，如 --grep method")
    ap.add_argument("--rows", action="store_true", help="带上行数（估算，秒回）")
    ap.add_argument("--exact-rows", action="store_true",
                    help="带上精确行数（逐表 COUNT，大表上很慢）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    degraded = bool(args.sqlite)
    try:
        if degraded:
            source = f"本地 sqlite {args.sqlite}"
            tables = list_tables_sqlite(args.sqlite)
        else:
            source = f"生产 postgres（容器 {args.container} / 库 {args.dbname}）"
            if args.exact_rows:
                tables = list_tables_exact_rows_pg(
                    args.container, args.user, args.dbname, args.schema)
            else:
                tables = list_tables_pg(
                    args.container, args.user, args.dbname,
                    with_rows=args.rows, schema=args.schema)
    except PermissionError as e:
        print(f"[安全拦截] {e}", file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(f"[错误] {e}", file=sys.stderr)
        print("        提示：不在生产/无 docker 时可用 --sqlite <db> 退化运行。",
              file=sys.stderr)
        return 2

    if args.grep:
        tables = [t for t in tables if args.grep.lower() in t["table"].lower()]

    if args.json:
        print(json.dumps({
            "source": source, "degraded": degraded,
            "tables": tables, "count": len(tables),
        }, ensure_ascii=False, indent=2))
    else:
        print(render(tables, None if args.json else args.grep, source, degraded))

    if not tables:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())