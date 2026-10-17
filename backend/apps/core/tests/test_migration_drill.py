r"""
migration_drill（migration 演练）回归测试。

这个脚本固化的是一次真实事故：
  部署前在独立 sqlite 实例上跑 migration 全链路，**第一步就抓到**
  `documents/0006` 漏了 commerce 的跨 app 依赖
  ⇒ 回填抛 `FieldError: Cannot resolve keyword 'current_sds_id'`。
  ⚠️ 生产 commerce 已在 0015，所以**没在生产触发** ——
     但新环境 / 回滚 / 分库就会炸。
  ⚠️ `manage.py check` **查不出这个**：它只查 model 层，不查迁移图。

⚠️ 测试纪律（决定这个测试有没有价值）：
  1. **不能只测「跑通」**。跑通是最低要求，不是目的。
     真正要证明的是「**能抓到问题**」⇒ 必须做变异验证：
     把 documents/0006 的 commerce 依赖删掉（复现今天的真 bug），
     断言脚本**报出 FieldError 且退出码非 0**。
     这条变异是本文件的核心价值。
  2. 变异用的是**临时副本**，绝不动真仓库的迁移文件。
  3. 必须证明「不污染项目 DB」—— 否则这个工具本身就成了新风险源。
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

from django.test import SimpleTestCase

REPO = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
)
SCRIPT = os.path.join(REPO, "scripts", "migration_drill.py")
BACKEND = os.path.join(REPO, "backend")
MIG_0006 = os.path.join(BACKEND, "apps", "documents", "migrations",
                        "0006_sdsrevision_status.py")
DEP_LINE = "        ('commerce', '0006_product_current_sds'),\n"
PROJ_DB = os.path.join(BACKEND, "db.sqlite3")


def _load():
    spec = importlib.util.spec_from_file_location("drill_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


drill = _load()


def _run(*args, timeout=900):
    return subprocess.run(
        [sys.executable, "-B", SCRIPT, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout)


class StaticAuditTests(SimpleTestCase):
    """静态依赖审计：不需要跑迁移，最快，`manage.py check` 覆盖不到。"""

    def setUp(self):
        d = drill.Drill("documents", "0006", keep_db=False)
        d.settings_mod = None          # 只调静态方法，不建隔离环境
        self.problems = d.audit_dependencies()

    def test_real_repo_has_no_missing_dependency(self):
        """当前代码已修好（有 commerce 依赖）⇒ 审计必须报干净。"""
        self.assertEqual(self.problems, [],
                         f"静态审计报了假阳性：{self.problems}")

    def test_detects_missing_cross_app_dependency(self):
        """★ mutation：删掉 commerce 依赖后，审计必须报出来。"""
        with open(MIG_0006, "r", encoding="utf-8") as f:
            src = f.read()
        mutated = src.replace(DEP_LINE, "")
        self.assertNotEqual(mutated, src, "未能构造变异（依赖行没找到）")

        tmp = tempfile.mkdtemp(prefix="drill_mut_")
        self.addCleanup(shutil.rmtree, tmp, True)
        # 目录结构必须与真仓库一致：<root>/apps/documents/migrations/
        mig_dir = os.path.join(tmp, "apps", "documents", "migrations")
        os.makedirs(mig_dir)
        # 把整个 documents 迁移目录复制过去，只改 0006
        src_dir = os.path.join(BACKEND, "apps", "documents", "migrations")
        for fn in os.listdir(src_dir):
            if fn.endswith(".py"):
                shutil.copy(os.path.join(src_dir, fn), os.path.join(mig_dir, fn))
        with open(os.path.join(mig_dir, "0006_sdsrevision_status.py"), "w",
                  encoding="utf-8") as f:
            f.write(mutated)

        d = drill.Drill("documents", "0006", keep_db=False)
        d.settings_mod = None
        probs = d.audit_dependencies(backend_root=tmp)
        self.assertTrue(probs, "删掉 commerce 依赖后审计竟然没报 —— 这是致命漏报")
        joined = " ".join(probs)
        self.assertIn("commerce", joined)
        self.assertIn("0006", joined)


class ClassifyFailureTests(SimpleTestCase):
    """★ 核心：必须把「依赖缺失」与「其它迁移错误」区分开。"""

    def test_classifies_field_error_as_dependency_missing(self):
        out = ("Applying documents.0006...\n"
               "django.core.exceptions.FieldError: Cannot resolve keyword "
               "'current_sds_id' into field. Choices are: id, name, ...")
        d = drill.Drill("documents", "0006", keep_db=False)
        msg = d.classify_failure(out)
        self.assertIn("跨 app 依赖缺失", msg)
        self.assertIn("current_sds_id", msg,
                      "报告里必须点名是哪个字段，人才知道去看哪")
        self.assertIn("新环境", msg, "必须说明为什么生产没炸")

    def test_classifies_missing_table(self):
        out = "django.db.utils.OperationalError: no such table: product_method"
        d = drill.Drill("commerce", None, keep_db=False)
        self.assertIn("依赖", d.classify_failure(out))

    def test_classifies_missing_column(self):
        out = ("django.db.utils.ProgrammingError: "
               "no such column: product.search_vector")
        d = drill.Drill("commerce", None, keep_db=False)
        self.assertIn("no such column", d.classify_failure(out))

    def test_generic_failure_still_reports_output(self):
        out = "ValueError: something else went wrong"
        d = drill.Drill("documents", None, keep_db=False)
        msg = d.classify_failure(out)
        self.assertIn("something else went wrong", msg,
                      "未知错误也必须把原始输出带出来，否则无从排查")


class TargetResolutionTests(SimpleTestCase):
    def test_target_prefix_matches(self):
        self.assertTrue(drill.FIELD_ERROR_RE.search(
            "FieldError: Cannot resolve keyword 'x' into field."))
        self.assertTrue(drill.CHOICES_RE.search(
            "Cannot resolve keyword 'y' into field. Choices are: a, b"))
        self.assertIsNone(drill.FIELD_ERROR_RE.search("ValueError: nope"))


class CliContractTests(SimpleTestCase):
    def test_missing_app_exits_2(self):
        p = _run("--app", "no_such_app_xyz")
        self.assertEqual(p.returncode, 2)
        self.assertIn("找不到 app", p.stderr)

    def test_help_works(self):
        p = _run("--help")
        self.assertEqual(p.returncode, 0)
        self.assertIn("--target", p.stdout)
        self.assertIn("--audit-only", p.stdout)

    def test_bad_target_reports_existing_ones(self):
        """目标找不到时必须**列出可选项**，而不是只说"没找到"。"""
        p = _run("--app", "documents", "--target", "9999")
        self.assertIn("0006", p.stdout + p.stderr,
                      "找不到目标时应列出该 app 现有的迁移名")


class RealDrillTests(SimpleTestCase):
    """★ 真实跑一遍全链路（较慢，但这是这个脚本的存在意义）。"""

    @classmethod
    def setUpClass(cls):
        cls.db_before = (os.path.getsize(PROJ_DB)
                         if os.path.isfile(PROJ_DB) else None)

    def test_full_drill_passes_on_healthy_code(self):
        p = _run("--app", "documents", "--target", "0006")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        for step in ("① 正向迁移", "② 造贴近生产形态", "③ 应用目标迁移",
                     "④ 幂等重跑", "⑤ 反向回滚"):
            self.assertIn(step, p.stdout, f"缺少步骤：{step}")
        self.assertIn("全链路通过", p.stdout)

    def test_drill_never_touches_project_db(self):
        """★ 不污染项目 DB —— 否则这个工具本身就成了新风险源。"""
        _run("--app", "documents", "--target", "0006")
        self.assertEqual(os.path.getsize(PROJ_DB) if os.path.isfile(PROJ_DB)
                         else None, self.db_before,
                         "项目 db.sqlite3 的大小变了 ⇒ 演练污染了它")

    def test_cleanup_removes_temp_db_and_settings(self):
        """结束必须清理干净（含临时 settings 模块）。"""
        _run("--app", "documents", "--target", "0006")
        leftovers = [f for f in os.listdir(os.path.dirname(BACKEND))
                     if f.startswith("migration_drill_")]
        self.assertEqual(leftovers, [], f"临时库残留：{leftovers}")
        stale = os.path.join(BACKEND, "_migration_drill_settings.py")
        self.assertFalse(os.path.isfile(stale),
                         "临时 settings 模块没清理 —— 它会留在 backend/ 里被误 import")

    def test_audit_only_mode_is_fast_and_readonly(self):
        p = _run("--app", "documents", "--audit-only")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("静态依赖审计", p.stdout)