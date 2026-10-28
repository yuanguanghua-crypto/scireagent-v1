# -*- coding: utf-8 -*-
"""
Tests for `scripts/check_migrations_safe.py` —— 迁移「破坏性删除」静态闸门。

为什么要给闸门本身写测试（2026-10-28）：
    这个脚本的**失效方式是静默的**：写错一行，它会对 90 个迁移文件全部返回
    "OK"，CI 全绿，谁都不会发现闸门其实没在工作。
    本脚本第一版就正是这样 —— `operations` 只扫了模块级 `ast.Assign`，
    而 Django 迁移把它写在 `class Migration` 类体里 ⇒ 扫了 90 个文件、0 命中。
    是下面的变异用例把它抓出来的，不是人眼。

三层断言：
    ① 每种已知破坏形态都能被拦住（12 个变异用例）
    ② 真实仓库当前是干净的（回归护栏：新增迁移若误删检索对象，这里立刻红）
    ③ 受保护清单与代码里的实际索引名对齐（防"新增索引忘了登记"⇒ 闸门漏保护）
"""
import importlib.util
import re
from pathlib import Path

import pytest

# backend/core/tests/test_migration_guard.py → parents[3] = 仓库根（src_claude）
REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / 'scripts' / 'check_migrations_safe.py'


def _load_guard():
    """按路径加载脚本（它不是包里的模块，不能 import）。"""
    spec = importlib.util.spec_from_file_location('check_migrations_safe', SCRIPT)
    assert spec and spec.loader, f'无法加载 {SCRIPT}'
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: 受保护迁移文件必须存在，否则脚本会报 MISSING-FILE。
#: 这里复制一份是**故意的**：如果谁把清单里的路径改错了，下面第 ② 层会红。
_PROTECTED_FILES = [
    'apps/commerce/migrations/0008_search_vector.py',
    'apps/commerce/migrations/0016_fts_state_align.py',
    'apps/knowledge/migrations/0008_search_vectors.py',
    'apps/knowledge/migrations/0022_search_trgm_indexes.py',
    'apps/knowledge/migrations/0023_fts_state_align.py',
    'apps/knowledge/migrations/0024_search_vector_triggers.py',
]


@pytest.fixture()
def fake_backend(tmp_path):
    """造一个最小的 backend 目录：6 个受保护迁移的占位 + 一个 demo app。"""
    for rel in _PROTECTED_FILES:
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text('# placeholder\n', encoding='utf-8')
    demo = tmp_path / 'apps' / 'demo' / 'migrations'
    demo.mkdir(parents=True, exist_ok=True)
    (demo / '__init__.py').write_text('', encoding='utf-8')
    return tmp_path, demo


def _migration(*ops):
    """拼一个最小可解析的迁移文件内容。"""
    return (
        'from django.db import migrations\n'
        '\n'
        'class Migration(migrations.Migration):\n'
        "    dependencies = []\n"
        '    operations = [\n'
        + ''.join(f'        {op},\n' for op in ops)
        + '    ]\n'
    )


# ── ① 变异用例：每种破坏形态都必须被拦住 ────────────────────────────────
BODY_REMOVE_FIELD = _migration(
    "migrations.RemoveField(model_name='product', name='search_vector')")
BODY_REMOVE_FIELD_POSITIONAL = _migration(
    "migrations.RemoveField('product', 'search_vector')")
BODY_REMOVE_INDEX_GIN = _migration(
    "migrations.RemoveIndex(model_name='product', name='product_search_gin')")
BODY_REMOVE_INDEX_TRGM = _migration(
    "migrations.RemoveIndex(model_name='method', name='method_nsp_trgm')")
BODY_SIDE_DOOR = _migration(
    'migrations.SeparateDatabaseAndState('
    "state_operations=[migrations.RemoveIndex(model_name='method', "
    "name='method_search_gin')], database_operations=[])")
BODY_SQL_DROP_INDEX = _migration(
    'migrations.RunSQL("DROP INDEX IF EXISTS reference_search_gin;")')
BODY_SQL_DROP_TRIGGER = _migration(
    'migrations.RunSQL("DROP TRIGGER IF EXISTS product_sv_trg ON product;")')
BODY_SQL_DROP_FUNCTION = _migration(
    'migrations.RunSQL("DROP FUNCTION IF EXISTS product_search_vector_update();")')
BODY_SQL_DROP_COLUMN = _migration(
    'migrations.RunSQL("ALTER TABLE method DROP COLUMN IF EXISTS search_vector;")')
BODY_DELETE_MODEL = _migration("migrations.DeleteModel(name='product')")

#: 不该被拦的（防止闸门退化成"什么都拦"）
BODY_UNRELATED_FIELD = _migration(
    "migrations.RemoveField(model_name='protocol', name='method')")
BODY_UNRELATED_CONSTRAINT = _migration(
    "migrations.RemoveConstraint(model_name='pmr', name='ck_pmr_status')")
BODY_EXEMPT = (
    'from django.db import migrations\n'
    '# migration-guard: allow-removal 计划下线旧检索，改用外部分析引擎\n'
    '\n'
    'class Migration(migrations.Migration):\n'
    '    operations = [\n'
    "        migrations.RemoveField(model_name='product', name='search_vector'),\n"
    '    ]\n'
)


@pytest.mark.parametrize('body,expect', [
    pytest.param(BODY_REMOVE_FIELD, 'BLOCK', id='remove-field-search-vector'),
    pytest.param(BODY_REMOVE_FIELD_POSITIONAL, 'BLOCK', id='remove-field-positional-args'),
    pytest.param(BODY_REMOVE_INDEX_GIN, 'BLOCK', id='remove-index-gin'),
    pytest.param(BODY_REMOVE_INDEX_TRGM, 'BLOCK', id='remove-index-trgm'),
    pytest.param(BODY_SIDE_DOOR, 'BLOCK', id='side-door-separate-database-and-state'),
    pytest.param(BODY_SQL_DROP_INDEX, 'BLOCK', id='raw-sql-drop-index'),
    pytest.param(BODY_SQL_DROP_TRIGGER, 'BLOCK', id='raw-sql-drop-trigger'),
    pytest.param(BODY_SQL_DROP_FUNCTION, 'BLOCK', id='raw-sql-drop-function'),
    pytest.param(BODY_SQL_DROP_COLUMN, 'BLOCK', id='raw-sql-drop-column'),
    pytest.param(BODY_DELETE_MODEL, 'BLOCK', id='delete-model'),
    pytest.param(BODY_UNRELATED_FIELD, 'OK', id='allow-unrelated-remove-field'),
    pytest.param(BODY_UNRELATED_CONSTRAINT, 'OK', id='allow-unrelated-remove-constraint'),
    pytest.param(BODY_EXEMPT, 'WARN', id='explicit-exemption-becomes-warn'),
])
def test_guard_verdict(fake_backend, body, expect, capsys):
    """每种形态 → 期望判定 + 退出码必须一致。"""
    root, demo = fake_backend
    (demo / '0001_bad.py').write_text(body, encoding='utf-8')

    mod = _load_guard()
    rc = mod.main(['--backend-root', str(root)])
    out = capsys.readouterr().out

    got = 'BLOCK' if '[BLOCK]' in out else ('WARN' if '[WARN]' in out else 'OK')
    assert got == expect, f'判定不符：期望 {expect}，实得 {got}\n--- 输出 ---\n{out}'
    assert rc == (1 if expect == 'BLOCK' else 0), f'退出码不符：{rc}\n{out}'


def test_missing_protected_migration_file_is_blocked(fake_backend, capsys):
    """删掉地基迁移文件（比删列更隐蔽）必须 BLOCK。"""
    root, demo = fake_backend
    (demo / '0001_ok.py').write_text(_migration(), encoding='utf-8')
    (root / 'apps/knowledge/migrations/0024_search_vector_triggers.py').unlink()

    mod = _load_guard()
    rc = mod.main(['--backend-root', str(root)])
    out = capsys.readouterr().out

    assert rc == 1
    assert 'MISSING-FILE' in out
    assert '0024_search_vector_triggers.py' in out


def test_json_output_shape(fake_backend, capsys):
    """--json 是 CI 消费的口径，字段不能漂。"""
    import json as _json

    root, demo = fake_backend
    (demo / '0001_bad.py').write_text(BODY_REMOVE_FIELD, encoding='utf-8')

    mod = _load_guard()
    rc = mod.main(['--backend-root', str(root), '--json'])
    payload = _json.loads(capsys.readouterr().out)

    assert rc == 1
    assert payload['ok'] is False
    assert payload['block'] == 1 and payload['warn'] == 0
    assert payload['scanned_files'] >= 1
    assert payload['hits'][0]['op'] == 'RemoveField'
    assert payload['hits'][0]['target'].endswith('search_vector')


def test_usage_error_when_backend_root_invalid(tmp_path, capsys):
    """指错目录时必须 exit 2，不能"扫 0 个文件 → OK"假绿。"""
    mod = _load_guard()
    rc = mod.main(['--backend-root', str(tmp_path / 'nope')])
    err = capsys.readouterr().err
    assert rc == 2
    assert '找不到后端目录' in err


# ── ② 回归护栏：真实仓库当前必须干净 ──────────────────────────────────
def test_real_repo_migrations_are_clean(capsys):
    """真实仓库 90 个迁移文件里不得有任何受保护对象的删除。

    这条是**长期价值最高**的一条：以后谁提交删检索对象的迁移，这里立刻红，
    不依赖有没有人记得跑脚本。
    """
    assert BACKEND_ROOT.joinpath('apps').is_dir(), f'后端目录不存在：{BACKEND_ROOT}'

    mod = _load_guard()
    rc = mod.main(['--backend-root', str(BACKEND_ROOT)])
    out = capsys.readouterr().out

    assert rc == 0, f'仓库迁移里出现受保护对象的删除：\n{out}'


# ── ③ 清单完整性：代码里真实存在的检索索引必须都登记了 ─────────────────
def _protected_index_names_in_repo() -> set:
    """从所有迁移文件里抽出 GinIndex(... name='xxx') 的 name。

    这是"清单是否漏登记"的判据：新增一个检索索引但忘了加进
    `PROTECTED_INDEXES` ⇒ 闸门对它视而不见 ⇒ 这个测试红。
    """
    pat = re.compile(r"GinIndex\((?:[^)]*?)name=['\"]([a-z0-9_]+)['\"]", re.S)
    names = set()
    for f in sorted((BACKEND_ROOT / 'apps').glob('*/migrations/*.py')):
        names |= set(pat.findall(f.read_text(encoding='utf-8')))
    return names


def test_all_gin_indexes_are_registered():
    """迁移里出现的每个 GinIndex 都必须登记进 PROTECTED_INDEXES。"""
    mod = _load_guard()
    found = _protected_index_names_in_repo()
    assert found, '没从迁移里解析出任何 GinIndex —— 正则或目录结构变了，护栏已失效'
    missing = found - set(mod.PROTECTED_INDEXES)
    assert not missing, (
        f'这些 GinIndex 没登记进 PROTECTED_INDEXES，闸门不会保护它们：{sorted(missing)}\n'
        f'（在 scripts/check_migrations_safe.py 的 PROTECTED_INDEXES 里补上）')


def test_trigger_targets_match_protected_tables():
    """knowledge/0024 的 TARGETS 表清单必须与 PROTECTED_TABLES 一致。"""
    mod = _load_guard()
    src = (BACKEND_ROOT / 'apps/knowledge/migrations/0024_search_vector_triggers.py'
           ).read_text(encoding='utf-8')
    # TARGETS = [ ('product', [...]), ... ]
    tables = set(re.findall(r"^\s*\('([a-z_]+)',\s*\[", src, re.M))
    assert tables, '没解析出 0024 的 TARGETS —— 迁移文件结构变了，护栏已失效'
    assert tables == set(mod.PROTECTED_TABLES), (
        f'触发器目标表清单不一致：迁移={sorted(tables)} '
        f'vs 闸门={sorted(mod.PROTECTED_TABLES)}')
