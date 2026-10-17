r"""
find_stale_duplicates（过期副本检测）回归测试。

这个脚本固化的是一次真实事故：
  `scripts/deletion_guard.py`（旧版，有 P0 漏洞）曾是
  `scripts/capability_guard.py` 的前身，改名后**旧文件还留在磁盘上**，
  且从未进 git。危害在于它会输出「可以删」的**假安全信号**。

⚠️ 本脚本的设计目标是**宁可漏报也不能误报**。
   误报的代价是信任崩塌：工具一旦开始喊狼来了，大家就会学会忽略它，
   于是真重复也被忽略。所以测试里有一半的用例是在**钉住「不许报」**：
     - 压缩 bundle（frontend/_d2、_d3…）必须被跳过；
     - `services.py` 与 `services/__init__.py` 必须被跳过；
     - 同名不同目录必须被跳过；
     - 版本号不同但逻辑已分叉（fill_missing_data vs _v2）必须被跳过。
   另一半钉住「该报要报」：造两份几乎逐字相同的副本，必须被抓出来。
"""
import importlib.util
import json
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
SCRIPT = os.path.join(REPO, "scripts", "find_stale_duplicates.py")


def _load():
    spec = importlib.util.spec_from_file_location("fsd_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


fsd = _load()


def _body(n=40, marker="x"):
    """造一段有 n 行的正常源码。"""
    return "\n".join(
        f"def fn_{i}(value_{i}):\n    result_{i} = value_{i} + {i}\n    return result_{i}\n"
        for i in range(n))


class TempTreeMixin:
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fsd_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, rel, text):
        full = os.path.join(self.tmp, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(text)
        return full


class TruePositiveTests(TempTreeMixin, SimpleTestCase):
    """该报要报：几乎逐字相同的副本必须被抓出来。"""

    def test_detects_near_identical_renamed_copy(self):
        """今天的真事故形态：`capability_guard.py` 改名后旧文件残留。"""
        a = self.write("scripts/capability_guard.py", _body(50))
        b = self.write("scripts/deletion_guard.py", _body(50))
        files = fsd.iter_files(self.tmp)
        pairs = fsd.similar_groups(files, 0.95)
        self.assertEqual(len(pairs), 1, "改名残留的逐字副本必须被抓出")
        names = {os.path.basename(p[0]) for p in pairs}
        names |= {os.path.basename(p[1]) for p in pairs}
        self.assertEqual(names, {"capability_guard.py", "deletion_guard.py"})
        self.assertGreaterEqual(pairs[0][2], 0.95)

    def test_detects_copy_with_only_comments_changed(self):
        """注释不同不算内容不同 —— 降噪后仍应判定为重复。

        ⚠️ 这个用例必须塞**大量互不相同的注释行**，否则杀不掉「关掉注释降噪」
        那个变异：只差 1~2 行注释时，即使完全不降噪声度也还在 0.97 以上，
        测试照样绿 ⇒ 根本测不出降噪是否生效。这里用 40 行完全不同的注释。
        """
        a_body = _body(40)
        b_body = _body(40)
        a_comments = "\n".join(f"# 现行版第 {i} 行说明：{i} " + "详述" * 20
                               for i in range(40))
        b_comments = "\n".join(f"# 旧版残留第 {i} 行注释：{i} " + "作废" * 20
                               for i in range(40))
        self.write("a/guard_new.py", a_comments + "\n" + a_body)
        self.write("b/guard_old.py", b_comments + "\n" + b_body)
        files = fsd.iter_files(self.tmp)
        pairs = fsd.similar_groups(files, 0.95)
        self.assertEqual(len(pairs), 1,
                         "只差注释的两个文件仍应判为重复（注释已降噪）")

    def test_detects_copy_with_whitespace_only_differences(self):
        """缩进风格不同不该掩盖重复。"""
        body = "\n".join(f"def f{i}(): return {i}" for i in range(40))
        a = self.write("x/mod_a.py", body)
        b = self.write("y/mod_b.py", body.replace("def f", "def  f"))
        pairs = fsd.similar_groups(fsd.iter_files(self.tmp), 0.95)
        self.assertEqual(len(pairs), 1, "纯空白差异应被归一化后判为重复")

    def test_ignores_docstring_only_differences(self):
        """模块 docstring 不同（改了说明文字）仍判为重复。"""
        body = _body(40)
        a = self.write("p/old_tool.py", '"""旧版说明"""\n' + body)
        b = self.write("q/new_tool.py", '"""新版说明，内容完全一样"""\n' + body)
        pairs = fsd.similar_groups(fsd.iter_files(self.tmp), 0.95)
        self.assertEqual(len(pairs), 1, "docstring 差异应被剥掉后再比")


class FalsePositiveTests(TempTreeMixin, SimpleTestCase):
    """不许报：误报是这类工具的头号死因。"""

    def test_minified_bundle_pairs_are_skipped(self):
        """★ 多份历史构建输出（frontend/_d2、_d3…）天然几乎逐字相同。

        真实 bundle 的形态：平均 12587 字符/行（实测 frontend/_d2）。
        这里按同样形态造，确保压缩产物识别规则真的生效。
        """
        # 30 行 × 每行 ~5000 字符 ⇒ 平均行长远超 1000 的阈值
        chunk = "".join(f"var a{i}={i};function f{i}(x){{return x*%d}}" % i
                        for i in range(60)) + " " * 4000
        minified = "\n".join(chunk for _ in range(30))
        self.assertGreater(len(chunk), 1000)
        self.write("frontend/_d2/assets/index-aaa.js", minified)
        self.write("frontend/_d3/assets/index-bbb.js", minified)
        self.write("frontend/_d4/assets/index-ccc.js", minified)
        files = fsd.iter_files(self.tmp)
        self.assertEqual(files, [], "压缩产物必须被排除在候选之外")
        self.assertEqual(fsd.similar_groups(files, 0.95), [])

    def test_normal_wide_source_is_not_treated_as_minified(self):
        """★ 反向保护：超长但正常的源码（长 SQL / 长注释行）不能被误杀。"""
        wide = "\n".join(
            "# " + "说明文字" * 40 + str(i) for i in range(40))   # 每行约 165 字符
        self.write("scripts/wide_source.py", wide)
        files = fsd.iter_files(self.tmp)
        self.assertEqual(len(files), 1,
                         "正常的长行源码被误判成压缩产物了 ⇒ 阈值 1000 需下调或规则需修正")

    def test_module_and_package_init_are_not_duplicates(self):
        """`services.py` 与 `services/__init__.py` 共存是正常结构。"""
        body = _body(40)
        self.write("apps/knowledge/services.py", body)
        self.write("apps/knowledge/services/__init__.py", body)
        pairs = fsd.similar_groups(fsd.iter_files(self.tmp), 0.95)
        self.assertEqual(pairs, [], "模块与同名包共存不该报成过期副本")

    def test_same_basename_different_dir_is_skipped(self):
        """同名不同目录是有意分层，不是过期副本。"""
        body = _body(40)
        self.write("backend/services/util.py", body)
        self.write("scripts/util.py", body)
        pairs = fsd.similar_groups(fsd.iter_files(self.tmp), 0.95)
        self.assertEqual(pairs, [])

    def test_versioned_scripts_with_real_divergence_not_flagged(self):
        """fill_missing_data.py vs _v2：同源但已分叉，真实仓库里不该报。

        实测真实相似度是 **0.357**（远低于 0.95 阈值）⇒ 阈值对
        「同源但已分叉」这一形态是安全的。这里用相近量级的分叉来复现。
        """
        base = _body(60)
        # 造出实质分叉：追加一整段不同实现（而非只加几行）
        diverged = _body(20) + "\n" + "\n".join(
            f"def changed_{i}(v):\n    return v * {i} - 1\n" for i in range(60))
        self.write("scripts/fill_missing_data.py", base)
        self.write("scripts/fill_missing_data_v2.py", diverged)
        pairs = fsd.similar_groups(fsd.iter_files(self.tmp), 0.95)
        self.assertEqual(pairs, [], "已实质分叉的版本化脚本不该报")

    def test_skip_directories_are_not_walked(self):
        """__pycache__ / node_modules / dist 等绝不能进去。"""
        body = _body(40)
        for d in ("__pycache__", "node_modules", "dist", "_audit_tmp", ".git"):
            self.write(f"{d}/junk.py", body)
        self.assertEqual(fsd.iter_files(self.tmp), [],
                         "跳过目录规则失效了")

    def test_underscore_prefixed_dir_not_scanned(self):
        self.write("_lead_stash/old.py", _body(40))
        self.assertEqual(fsd.iter_files(self.tmp), [])

    def test_short_files_are_ignored(self):
        """太短的文件比出来的相似度不可信（小文件撞车概率极高）。"""
        self.write("a/tiny.py", "x = 1\n")
        self.write("b/tiny.py", "x = 2\n")
        self.assertEqual(fsd.iter_files(self.tmp, min_lines=30), [])

    def test_real_repo_has_zero_false_positives(self):
        """★ 在真实仓库上跑，0.95 阈值必须给出 0 条报告。

        这条是本脚本的**核心质量门**：一旦有人调松阈值或改坏归一化，
        这里会立刻爆出一堆构建产物路径。
        """
        files = fsd.iter_files(REPO, min_lines=30)
        self.assertGreater(len(files), 200, "扫描范围异常小，规则可能写坏了")
        pairs = fsd.similar_groups(files, 0.95)
        offenders = [p for p in pairs
                     if "_d2" in p[0] or "_d3" in p[0] or "node_modules" in p[0]
                     or "__pycache__" in p[0] or "services.py" in p[0]
                     and "services/__init__.py" in p[1]]
        self.assertEqual(offenders, [], "真实仓库上出现了已知误报模式")
        self.assertEqual(pairs, [],
                         f"真实仓库上有 {len(pairs)} 条报告，需人工确认是否误报")


class CliTests(TempTreeMixin, SimpleTestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "-B", SCRIPT, *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace")

    def test_missing_dir_exits_2(self):
        p = self._run(os.path.join(self.tmp, "__nope__"))
        self.assertEqual(p.returncode, 2)
        self.assertIn("目录不存在", p.stderr)

    def test_bad_threshold_exits_2(self):
        p = self._run(self.tmp, "--threshold", "0.3")
        self.assertEqual(p.returncode, 2)
        self.assertIn("threshold", p.stderr)

    def test_clean_tree_exits_0(self):
        self.write("only/one.py", _body(40))
        p = self._run(self.tmp, "--json")
        self.assertEqual(p.returncode, 0)
        data = json.loads(p.stdout)
        self.assertEqual(data["pairs"], [])

    def test_finds_duplicate_exits_1(self):
        self.write("a/guard_new.py", _body(50))
        self.write("b/guard_old.py", _body(50))
        p = self._run(self.tmp, "--json")
        self.assertEqual(p.returncode, 1)
        data = json.loads(p.stdout)
        self.assertEqual(len(data["pairs"]), 1)

    def test_never_deletes_anything(self):
        """★ 只报告不删除：跑完之后文件必须还在。"""
        self.write("a/guard_new.py", _body(50))
        self.write("b/guard_old.py", _body(50))
        before = sorted(os.listdir(os.path.join(self.tmp, "a")))
        self._run(self.tmp)
        self.assertEqual(sorted(os.listdir(os.path.join(self.tmp, "a"))), before)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "b", "guard_old.py")),
                        "过期副本被删了！本脚本只允许报告")

    def test_help_works(self):
        p = self._run("--help")
        self.assertEqual(p.returncode, 0)
        self.assertIn("--threshold", p.stdout)