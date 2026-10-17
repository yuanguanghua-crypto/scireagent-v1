r"""
test_result_summary（pytest 输出判读）回归测试。

这个脚本固化的教训来自两个**实测**事故：

  1. 部分 app 全量跑会因 `ValueError: I/O operation on closed file`
     **丢掉 pytest 末尾的汇总行** ⇒ 只能靠 EXIT 码 + `^FAILED` 行判读。
     本脚本必须在这种情况下**显式标注数字来源**，而不是假装汇总行还在。

  2. `grep -oE '[.FEsxX]'` 对整行做字符提取 ⇒ **路径里的字母被当成进度符号**。
     实测同一份输出：正确做法 `s=1`，错误做法 `s=194`（虚高 193），
     还凭空多出 `E=16 / x=4 / X=1`。
     ⇒ 本脚本必须用**行首锚定**的正则 `^[.FEsxX]+[ \t]*\[` 才能把路径排除掉。

⚠️ 断言纪律：
  - 关键断言是**具体数字**，不是「非空」/「大于 0」。
    「非空」在污染与正确两种实现下都成立，测不出 P0。
  - `test_detects_injected_path_letter_pollution` 是**变异验证**的常驻版本：
    它构造一个路径里塞满 `s`/`e`/`x`/`X` 的输出，要求脚本
    仍然只数出进度点图里的那 1 个 `s`。
"""
import importlib.util
import json
import os
import subprocess
import sys

from django.test import SimpleTestCase

REPO = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
)
SCRIPT = os.path.join(REPO, "scripts", "test_result_summary.py")
FIXTURES = os.path.join(REPO, "backend", "apps", "core", "tests", "fixtures")


def _load():
    spec = importlib.util.spec_from_file_location("trs_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


trs = _load()


def _parse(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return trs.parse(f.read())


class ParseCoreTests(SimpleTestCase):
    """进度点图解析：行首锚定是全部要害。"""

    def test_counts_exact_numbers_from_progress_graph(self):
        """夹具：2 行进度点图，共 8 passed / 1 failed / 1 skipped / 1 xfailed / 1 xpassed。"""
        r = _parse("pytest_consistent.txt")
        self.assertTrue(r["summary_line_found"])
        # 进度点图逐符号累加，不允许任何近似
        self.assertEqual(r["progress_counts"]["passed"], 16)
        self.assertEqual(r["progress_counts"]["failed"], 1)
        self.assertEqual(r["progress_counts"]["skipped"], 1)
        self.assertEqual(r["progress_total"], 18)

    def test_path_letters_do_not_pollute_counts(self):
        """★ P0 回归：路径里的字母绝不能被当成进度符号。

        夹具里进度点图一共只有 **1 个 `s`**（第二行第 2 位）。
        而 `tests/knowledge/tests/test_skill_export_service.py` 等路径里有几十个 s/e/x。
        实测对照：对同一份输出用 `re.findall(r'[.FEsxX]', 整行)`（等价于
        `grep -oE '[.FEsxX]'`）数出 `s=30 / x=6 / E=3`，
        而本脚本只数出 `s=1 / x=1`（后者来自进度点图里真实的 xfail/xpass）。
        ⇒ 断言必须是具体数字，否则这类污染测不出来。
        """
        r = _parse("pytest_lost_summary.txt")
        self.assertEqual(r["progress_counts"]["skipped"], 1)
        self.assertEqual(r["progress_counts"]["passed"], 8)
        self.assertEqual(r["progress_counts"]["xfailed"], 1)
        self.assertEqual(r["progress_counts"]["xpassed"], 1)
        self.assertEqual(r["progress_counts"]["failed"], 1)
        self.assertEqual(r["progress_total"], 12)

    def test_whole_line_char_extraction_would_be_wrong(self):
        """把「错误做法」本身也钉成断言，让污染量级有据可查。

        这不是测脚本，而是测**教训**：如果哪天有人改用整行字符提取，
        这个数字会从 30 掉到 1，review 时立刻能看出判读方式变了。
        """
        import re as _re
        with open(os.path.join(FIXTURES, "pytest_lost_summary.txt"),
                  encoding="utf-8") as f:
            text = f.read()
        naive = _re.findall(r"[.FEsxX]", text)
        self.assertEqual(naive.count("s"), 30,
                         "夹具的污染量变了 ⇒ 更新断言并重新评估")
        self.assertEqual(len(naive), 53)

    def test_detects_injected_path_letter_pollution(self):
        """★ 常驻变异验证：路径行里有 200+ 个 s/e/x，脚本仍只数 1 个。

        这一行是**专门造来区分 `^` 锚定是否还在**的：
        它自身不含 `[`，但路径里塞满了 `s`/`e`/`x`。
        若有人把正则的 `^` 去掉、或把 `.match()` 换成 `.search()`，
        这行会被误当成「6 个点 + 1 个 s」的进度行 ⇒ 断言立刻变红。
        """
        polluted = (
            "tests/knowledge/tests/test_skill_export_service.py::test_export_x "
            "ssssseeeeeexxxxx  [  1%]\n"
            ".....s...                                                 [100%]\n"
        )
        r = trs.parse(polluted)
        self.assertEqual(
            r["progress_counts"]["skipped"], 1,
            "路径行被误当成进度点图了 ⇒ 正则的行首锚定丢了")
        self.assertEqual(r["progress_counts"]["passed"], 8)
        self.assertEqual(r["progress_total"], 9)

    def test_progress_line_must_start_at_column_zero(self):
        """进度点图必须从第 0 列开始—— 这是排除路径污染的唯一机制。"""
        r = trs.parse("  ....F...   [100%]\n")
        self.assertEqual(r["progress_total"], 0,
                         "带前导空白的行被当成了进度行")

    def test_failed_lines_extracted_with_reason(self):
        """`^FAILED` 行必须连原因一起抠出来（人工定位回归用得上）。"""
        r = _parse("pytest_consistent.txt")
        self.assertEqual(len(r["failed_tests"]), 1)
        tid, reason = r["failed_tests"][0]
        self.assertEqual(tid, "apps/x/tests/test_a.py::test_one")
        self.assertEqual(reason, "AssertionError")

    def test_error_glyph_separated_from_failed(self):
        """`E`（用例内异常）单列，不混进 failed —— 但两者都算失败。"""
        r = trs.parse("E.          [100%]\n")
        self.assertEqual(r["progress_counts"]["error"], 1)
        self.assertEqual(r["progress_counts"]["failed"], 0)
        self.assertEqual(r["progress_total"], 2)


class SummaryLostTests(SimpleTestCase):
    """汇总行丢失时的行为：必须标注来源，不能假装一切正常。"""

    def test_detects_lost_summary_and_closed_file_hint(self):
        r = _parse("pytest_lost_summary.txt")
        self.assertFalse(r["summary_line_found"])
        self.assertTrue(
            r["summary_lost_suspected"],
            "输出里有 ValueError: I/O operation on closed file 却没识别为汇总行丢失")

    def test_choose_counts_marks_source_as_backward_inferred(self):
        r = _parse("pytest_lost_summary.txt")
        counts, source, warns = trs.choose_counts(r)
        self.assertIn("反推", source)
        self.assertTrue(any("汇总行不可用" in w for w in warns),
                        "丢失汇总行时必须显式警告")
        self.assertTrue(any("closed file" in w for w in warns),
                        "警告里应指出疑似原因")
        self.assertEqual(counts["failed"], 1)

    def test_consistent_case_prefers_pytest_summary(self):
        """汇总行与进度图一致时，以 pytest 自报为准。"""
        r = _parse("pytest_consistent.txt")
        counts, source, warns = trs.choose_counts(r)
        self.assertIn("权威", source)
        self.assertEqual(counts["passed"], 16)   # 汇总行口径
        self.assertEqual(counts["failed"], 1)
        self.assertEqual([w for w in warns if "相差" in w], [])

    def test_mismatch_between_summary_and_progress_is_flagged(self):
        """两个来源打架本身就是信号，必须报警而不是二选一。"""
        r = _parse("pytest_with_summary.txt")   # 汇总 16 项 vs 进度图 19 项
        counts, source, warns = trs.choose_counts(r)
        self.assertIn("权威", source)
        self.assertTrue(any("相差" in w for w in warns),
                        "汇总行与进度点图不一致时必须告警")


class NoSignalTests(SimpleTestCase):
    """完全无法判读时必须给出明确失败，而不是返回 0 个数字。"""

    def test_empty_input_reports_no_signal(self):
        r = trs.parse("this is not pytest output at all\n")
        counts, _source, warns = trs.choose_counts(r)
        self.assertEqual(counts, {})
        self.assertTrue(any("无法判读" in w for w in warns))


class CliExitCodeTests(SimpleTestCase):
    """退出码契约：能用就非 0，坏输入必须非 0。"""

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "-B", SCRIPT, *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace")

    def test_missing_file_exits_2(self):
        p = self._run(os.path.join(FIXTURES, "__no_such_file__.txt"))
        self.assertEqual(p.returncode, 2)
        self.assertIn("文件不存在", p.stderr)

    def test_empty_file_exits_2(self):
        empty = os.path.join(FIXTURES, "_tmp_empty.txt")
        with open(empty, "w", encoding="utf-8"):
            pass
        try:
            p = self._run(empty)
            self.assertEqual(p.returncode, 2)
            self.assertIn("空的", p.stderr)
        finally:
            os.remove(empty)

    def test_unparseable_file_exits_2(self):
        junk = os.path.join(FIXTURES, "_tmp_junk.txt")
        with open(junk, "w", encoding="utf-8") as f:
            f.write("hello world\n")
        try:
            p = self._run(junk)
            self.assertEqual(p.returncode, 2)
        finally:
            os.remove(junk)

    def test_failures_exit_1(self):
        p = self._run(os.path.join(FIXTURES, "pytest_consistent.txt"))
        self.assertEqual(p.returncode, 1)

    def test_clean_run_exits_0(self):
        p = self._run(os.path.join(FIXTURES, "pytest_all_pass.txt"))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_expect_failed_detects_regression(self):
        """★ 基线比对：超基线判回归，这是判读脚本的主要用途。"""
        f = os.path.join(FIXTURES, "pytest_consistent.txt")   # 1 failed
        ok = self._run(f, "--expect-failed", "1")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        bad = self._run(f, "--expect-failed", "0")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("回归", bad.stderr)

    def test_json_output_shape(self):
        p = self._run(os.path.join(FIXTURES, "pytest_lost_summary.txt"), "--json")
        data = json.loads(p.stdout)
        self.assertFalse(data["summary_line_found"])
        self.assertEqual(data["counts"]["skipped"], 1)
        self.assertEqual(len(data["failed_tests"]), 1)
        self.assertTrue(data["warnings"])

    def test_help_works(self):
        p = self._run("--help")
        self.assertEqual(p.returncode, 0)
        self.assertIn("--expect-failed", p.stdout)