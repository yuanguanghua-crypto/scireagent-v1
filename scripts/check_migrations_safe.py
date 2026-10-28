#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_migrations_safe.py — 迁移文件「破坏性删除」静态闸门

要拦的错误（2026-10-28 实测确认的真实形态）：
    全文检索是生产在用的能力：5 个 `search_vector` 列 + 5 个 GIN 索引
    + 4 个 trgm 相似度索引 + 5 个触发器 + 5 个 plpgsql 函数。
    它们是用 RunSQL / RunPython 原生 SQL 建的（commerce/0008、knowledge/0008、
    0022、0024），后来才用 state-only 迁移（SeparateDatabaseAndState）把
    migration state 补齐。
    ⇒ 一旦有人提交一个 `RemoveField('product','search_vector')` 或
      `RemoveIndex(name='product_search_gin')`，`migrate` 会把它们真删掉，
      商品/方法/协议/文献的全文检索与模糊匹配**当场全塌**，而且报错是
      「搜索返回空」而不是异常 —— 属于最难发现的失效模式。

为什么不能只靠 `makemigrations --check`（这是本脚本存在的核心理由）：
    `--check` 检的是「模型 ↔ 迁移 state 是否漂移」，语义不是「你在删东西」。
    ① 现状实测：在 PostgreSQL 下 `makemigrations --check --dry-run`
       返回 `No changes detected`（2026-10-28 实测），sqlite 下有
       config/settings/base.py 的守卫直接 RuntimeError ⇒ **不会误生成**。
    ② 但如果有人是**有意**重做检索方案（比如决定不用 PG 全文检索了），
       他会同步改模型 + 生成迁移，`--check` 就**绿了**，破坏性迁移被放行。
    ③ 另外 `RemoveIndex` / `DeleteModel` 在模型里本来就不可见，
       `--check` 对「纯 state 层面的删除」也不敏感。
    ⇒ 需要一条**独立于模型状态**的断言：受保护对象清单里的东西，任何迁移
      都不许删。这与本仓库既有的 `capability_guard.py` / `deletion-guard`
      是同一条纪律：删除类操作必须过闸门，不能靠"我记得"。

设计要点：
  1. **AST 解析而不是 grep**：`migrations.RemoveField(model_name='product',
     name='search_vector')` 跨行、参数顺序可变、可用位置参数 —— 正则容易漏。
  2. **递归进 `SeparateDatabaseAndState`**：它的
     `state_operations` / `database_operations` 两个列表里照样能删东西，
     不递归就等于留了一个正门旁边的侧门。
  3. **同时检查 RunSQL / RunPython 的字符串**：`DROP INDEX` / `DROP TRIGGER`
     / `DROP FUNCTION` / `ALTER TABLE … DROP COLUMN search_vector` 都不经过
     `migrations.Remove*`，grep 操作类名抓不到。
  4. **检查受保护的迁移文件本身还在**：删掉
     `knowledge/0024_search_vector_triggers.py` 比删列更隐蔽（migrate 不会报错，
     只是触发器永远不再创建），必须拦。
  5. **留逃生口**：文件内出现注释 `migration-guard: allow-removal <理由>`
     时，该文件的命中降级为 WARN（仍打印），因为这个能力将来可能真的下线；
     但必须由人显式写下理由，不能静默通过。

用法：
    python scripts/check_migrations_safe.py
        人类可读输出。退出码 0 = OK，1 = BLOCK，2 = 用法/环境错误。

    python scripts/check_migrations_safe.py --json
        机器可读（接 CI / pre-commit）。

    python scripts/check_migrations_safe.py --list
        打印受保护对象清单（改清单时对照用）。

    python scripts/check_migrations_safe.py --backend-root backend
        指定后端根目录（默认按脚本位置推断）。

退出码：0 = OK（可能有 WARN），1 = BLOCK，2 = 用法/环境错误。
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover - 极老的 Python / 被重定向
    pass


# ── 受保护对象清单 ────────────────────────────────────────────────────────
# ⚠️ 改这里的任何一条，都等于改了「生产上不许消失的东西」。改动必须在
#    PR 里单独说明，并同步 docs/e2e/MIGRATION_DRILL_LEDGER.md。
PROTECTED_FIELDS = {
    'search_vector',
}

PROTECTED_INDEXES = {
    # 5 个 GIN（全文检索）
    'product_search_gin',
    'application_search_gin',
    'method_search_gin',
    'protocol_search_gin',
    'reference_search_gin',
    # 4 个 trgm（相似度 / 模糊匹配）
    'application_name_summary_trgm',
    'method_nsp_trgm',
    'protocol_name_objective_trgm',
    'reference_tad_trgm',
}

#: 触发器 / plpgsql 函数名由 knowledge/0024 的 `_trigger_name` / `_fn_name` 生成。
#: 改命名规则必须同步改这里，否则闸门会静默失效（这是本清单唯一的维护成本）。
PROTECTED_TABLES = ('product', 'application', 'method', 'protocol', 'reference')
PROTECTED_TRIGGERS = {f'{t}_sv_trg' for t in PROTECTED_TABLES}
PROTECTED_FUNCTIONS = {f'{t}_search_vector_update' for t in PROTECTED_TABLES}

#: 全文检索的「地基」迁移。删掉/重命名这些文件 ⇒ migrate 不再创建对应对象。
#: 路径相对 `backend/`（即 `backend_root`），所以带 `apps/` 前缀。
PROTECTED_MIGRATION_FILES = {
    'apps/commerce/migrations/0008_search_vector.py',
    'apps/commerce/migrations/0016_fts_state_align.py',
    'apps/knowledge/migrations/0008_search_vectors.py',
    'apps/knowledge/migrations/0022_search_trgm_indexes.py',
    'apps/knowledge/migrations/0023_fts_state_align.py',
    'apps/knowledge/migrations/0024_search_vector_triggers.py',
}

#: 允许删除的显式豁免标记（必须带理由，写在同文件的注释里）
ALLOW_MARKER = 'migration-guard: allow-removal'

#: RunSQL/RunPython 里可能出现危险 DDL 的正则。全部大小写不敏感。
_DDL_PATTERNS = [
    (re.compile(r'\bDROP\s+INDEX\s+(?:IF\s+EXISTS\s+)?["\']?(\w+)', re.I), 'DROP INDEX'),
    (re.compile(r'\bDROP\s+TRIGGER\s+(?:IF\s+EXISTS\s+)?["\']?(\w+)', re.I), 'DROP TRIGGER'),
    (re.compile(r'\bDROP\s+FUNCTION\s+(?:IF\s+EXISTS\s+)?["\']?(\w+)', re.I), 'DROP FUNCTION'),
    (re.compile(r'\bALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?["\']?(\w+)["\']?\s+DROP\s+COLUMN\s+(?:IF\s+EXISTS\s+)?["\']?(\w+)', re.I),
     'ALTER TABLE … DROP COLUMN'),
    (re.compile(r'\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?["\']?(\w+)', re.I), 'DROP TABLE'),
]


class Hit:
    """一条命中。level = BLOCK / WARN。"""

    __slots__ = ('path', 'line', 'level', 'op', 'target', 'why')

    def __init__(self, path, line, level, op, target, why):
        self.path = path
        self.line = line
        self.level = level
        self.op = op
        self.target = target
        self.why = why

    def as_dict(self):
        return {
            'path': self.path, 'line': self.line, 'level': self.level,
            'op': self.op, 'target': self.target, 'why': self.why,
        }

    def render(self):
        return (f'  [{self.level}] {self.path}:{self.line}\n'
                f'          {self.op} → `{self.target}`\n'
                f'          {self.why}')


def _call_name(node: ast.AST) -> str | None:
    """`migrations.RemoveField(...)` → 'RemoveField'；`RemoveField(...)` → 'RemoveField'。"""
    if not isinstance(node, ast.Call):
        return None
    f = node.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return None


def _kw(call: ast.Call, name: str):
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def _const_str(node) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _all_strings(node: ast.AST):
    """递归收集子树里的所有字符串常量（用于扫 RunSQL / RunPython 的代码文本）。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            yield sub.lineno, sub.value


def _arg_strings(call: ast.Call) -> set[str]:
    """该调用里出现的所有字符串常量（位置参数 + 关键字参数）。

    为什么不只读 `name=`：迁移操作既支持关键字写法，也支持位置写法，
    而且**各操作的位置参数顺序不一致**（`RemoveField(model_name, name)` vs
    `RemoveIndex(model_name, name)` vs `DeleteModel(name)`）。按位置索引取值
    等于把 Django 的签名硬编码进来，升级时静默失效。
    一个迁移操作里平白出现 `'search_vector'` / `'product_search_gin'` 这种
    字符串，本身就已经是强信号 ⇒ 全收集再求交，既不漏也不误。
    """
    out: set[str] = set()
    for a in call.args:
        s = _const_str(a)
        if s:
            out.add(s)
    for k in call.keywords:
        s = _const_str(k.value)
        if s:
            out.add(s)
    return out


def _name_only(call: ast.Call) -> str | None:
    """只取「名字」这一个参数（DeleteModel / RemoveConstraint 需要）。"""
    v = _kw(call, 'name')
    s = _const_str(v)
    if s:
        return s
    if call.args:
        return _const_str(call.args[0])
    return None


def _scan_operations(nodes, rel_path: str, hits: list[Hit]):
    """递归扫 operations 里的 Call 节点（含 SeparateDatabaseAndState 的子列表）。"""
    for node in nodes:
        if isinstance(node, (ast.List, ast.Tuple)):
            _scan_operations(node.elts, rel_path, hits)
            continue
        if not isinstance(node, ast.Call):
            continue

        name = _call_name(node)
        if name is None:
            continue

        # ── SeparateDatabaseAndState：递归两个子列表 ──────────────────
        if name == 'SeparateDatabaseAndState':
            for kw in ('state_operations', 'database_operations'):
                sub = _kw(node, kw)
                if isinstance(sub, (ast.List, ast.Tuple)):
                    _scan_operations(sub.elts, rel_path, hits)
            continue

        # ── RemoveField ────────────────────────────────────────────────
        if name == 'RemoveField':
            strs = _arg_strings(node)
            hit = strs & PROTECTED_FIELDS
            model = (_const_str(_kw(node, 'model_name'))
                     or (_const_str(node.args[0]) if node.args else None)
                     or '?')
            for fname in sorted(hit):
                hits.append(Hit(
                    rel_path, node.lineno, 'BLOCK', 'RemoveField',
                    f'{model}.{fname}',
                    f'`{fname}` 是 PostgreSQL 全文检索列（{model} 表），'
                    f'删掉后该表搜索直接返回空、且不会抛异常。'))
            continue

        # ── RemoveIndex ────────────────────────────────────────────────
        if name == 'RemoveIndex':
            strs = _arg_strings(node)
            hit = strs & PROTECTED_INDEXES
            model = (_const_str(_kw(node, 'model_name'))
                     or (_const_str(node.args[0]) if node.args else None)
                     or '?')
            for iname in sorted(hit):
                kind = 'GIN 全文检索索引' if iname.endswith('_gin') else 'trgm 相似度索引'
                hits.append(Hit(
                    rel_path, node.lineno, 'BLOCK', 'RemoveIndex',
                    f'{model}.{iname}',
                    f'`{iname}` 是 {kind}，删掉后搜索退化为全表扫描'
                    f'（数据量 10 万级时接口会超时）。'))
            continue

        # ── DeleteModel ────────────────────────────────────────────────
        if name == 'DeleteModel':
            mname = _name_only(node)
            if mname in PROTECTED_TABLES:
                hits.append(Hit(
                    rel_path, node.lineno, 'BLOCK', 'DeleteModel', mname,
                    f'`{mname}` 是被全文检索保护的模型，整表删除会连带'
                    f' search_vector 列 / GIN / trgm / 触发器全部消失。'))
            continue

        # ── RemoveConstraint（保守：名字里带检索特征就拦）─────────────
        if name == 'RemoveConstraint':
            cname = _name_only(node) or ''
            if any(t in cname for t in ('search', 'trgm', 'gin')):
                hits.append(Hit(
                    rel_path, node.lineno, 'BLOCK', 'RemoveConstraint',
                    cname, '约束名带检索特征，疑似与全文检索相关，需人工确认。'))
            continue

        # ── RunSQL / RunPython / RunCode：扫字符串里的危险 DDL ─────────
        if name in ('RunSQL', 'RunPython', 'RunCode'):
            for lineno, text in _all_strings(node):
                _scan_ddl(rel_path, lineno, text, hits)
            continue


def _scan_ddl(rel_path: str, lineno: int, text: str, hits: list[Hit]):
    """在一段 SQL / Python 源码文本里找危险 DDL。"""
    for pat, op in _DDL_PATTERNS:
        for m in pat.finditer(text):
            groups = [g for g in m.groups() if g]
            if op == 'ALTER TABLE … DROP COLUMN':
                table, col = m.group(1), m.group(2)
                if col in PROTECTED_FIELDS:
                    hits.append(Hit(
                        rel_path, lineno, 'BLOCK', 'RunSQL/RunPython',
                        f'{table}.{col}',
                        '原生 SQL 删除 search_vector 列（不经过 migrations.RemoveField，'
                        '操作类名 grep 抓不到）。'))
                continue
            ident = groups[-1] if groups else ''
            protected = (ident in PROTECTED_INDEXES
                         or ident in PROTECTED_TRIGGERS
                         or ident in PROTECTED_FUNCTIONS
                         or (op == 'DROP TABLE' and ident in PROTECTED_TABLES))
            if protected:
                hits.append(Hit(
                    rel_path, lineno, 'BLOCK', f'RunSQL/RunPython ({op})', ident,
                    '原生 SQL 删除受保护的检索对象（触发器/函数/索引/表）。'))


def check_file(path: Path, backend_root: Path) -> list[Hit]:
    rel = path.relative_to(backend_root).as_posix()
    # 只认 apps/<app>/migrations/*.py
    if not rel.startswith('apps/') or '/migrations/' not in rel:
        return []
    if path.name == '__init__.py':
        return []

    try:
        src = path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return [Hit(rel, 0, 'BLOCK', 'READ', path.name, '文件不是 UTF-8，无法静态校验。')]

    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as e:
        return [Hit(rel, e.lineno or 0, 'BLOCK', 'PARSE', path.name,
                    f'语法错误，无法静态校验：{e.msg}')]

    hits: list[Hit] = []
    # ⚠️ 必须用 ast.walk 而不是 tree.body：Django 迁移的 `operations = [...]`
    #    写在 `class Migration(migrations.Migration):` 类体里，模块级 body 里
    #    只有 Import / ClassDef。只扫 tree.body 会「扫了 90 个文件、永远 0 命中」
    #    —— 这正是本脚本第一版的 bug，靠变异验证抓到的。
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name) and tgt.id == 'operations':
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    _scan_operations(node.value.elts, rel, hits)

    # 豁免：文件里显式写了理由 ⇒ 降级 WARN
    if hits and ALLOW_MARKER in src:
        for h in hits:
            h.level = 'WARN'
            h.why += f'（已被 `{ALLOW_MARKER}` 豁免，请确认理由成立）'
    return hits


def find_migration_files(backend_root: Path) -> list[Path]:
    apps = backend_root / 'apps'
    if not apps.is_dir():
        return []
    return sorted(apps.glob('*/migrations/*.py'))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description='迁移文件「破坏性删除」静态闸门（全文检索对象保护）')
    ap.add_argument('--backend-root', default=None,
                    help='后端根目录（默认 = 脚本所在目录的 ../backend）')
    ap.add_argument('--json', action='store_true', help='机器可读输出')
    ap.add_argument('--list', action='store_true', help='打印受保护对象清单')
    args = ap.parse_args(argv)

    if args.list:
        print('受保护字段：', ', '.join(sorted(PROTECTED_FIELDS)))
        print('受保护索引：')
        for i in sorted(PROTECTED_INDEXES):
            print('  -', i)
        print('受保护触发器：', ', '.join(sorted(PROTECTED_TRIGGERS)))
        print('受保护函数：', ', '.join(sorted(PROTECTED_FUNCTIONS)))
        print('受保护迁移文件：')
        for f in sorted(PROTECTED_MIGRATION_FILES):
            print('  -', f)
        return 0

    if args.backend_root:
        backend_root = Path(args.backend_root).resolve()
    else:
        backend_root = (Path(__file__).resolve().parent.parent / 'backend')

    if not (backend_root / 'apps').is_dir():
        msg = f'找不到后端目录：{backend_root}/apps'
        print(f'[ERROR] {msg}', file=sys.stderr)
        return 2

    files = find_migration_files(backend_root)
    if not files:
        print(f'[ERROR] {backend_root}/apps/*/migrations/ 下没有迁移文件',
              file=sys.stderr)
        return 2

    hits: list[Hit] = []
    for f in files:
        hits.extend(check_file(f, backend_root))

    # ── 受保护的迁移文件本身必须还在 ────────────────────────────────
    for rel in sorted(PROTECTED_MIGRATION_FILES):
        if not (backend_root / rel).is_file():
            hits.append(Hit(
                rel, 0, 'BLOCK', 'MISSING-FILE', rel,
                '全文检索的地基迁移文件不见了。删掉它 migrate 不会报错，'
                '只是触发器/索引永远不再创建 —— 最隐蔽的失效方式。'))

    blocks = [h for h in hits if h.level == 'BLOCK']
    warns = [h for h in hits if h.level == 'WARN']

    if args.json:
        print(json.dumps({
            'ok': not blocks,
            'scanned_files': len(files),
            'block': len(blocks),
            'warn': len(warns),
            'hits': [h.as_dict() for h in hits],
        }, ensure_ascii=False, indent=2))
    else:
        print(f'[migration-guard] 扫描 {len(files)} 个迁移文件'
              f'（{backend_root}/apps/*/migrations/）')
        if not hits:
            print('[migration-guard] OK —— 未发现对受保护检索对象的删除操作。')
        for h in blocks + warns:
            print(h.render())
        if blocks:
            print(f'\n[migration-guard] BLOCK × {len(blocks)}'
                  f' —— 提交被拒。这些对象是生产在用的全文检索能力，'
                  f'删除会让搜索静默返回空。')
            print('  若确实要下线该能力：在**同一个迁移文件**里加注释 '
                  f'`# {ALLOW_MARKER} <理由>`，并同步更新 '
                  'docs/e2e/MIGRATION_DRILL_LEDGER.md。')
        elif warns:
            print(f'\n[migration-guard] WARN × {len(warns)} —— 已豁免，放行。')

    return 1 if blocks else 0


if __name__ == '__main__':
    sys.exit(main())
