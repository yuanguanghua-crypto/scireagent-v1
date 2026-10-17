r"""
prod_schema_tables（生产表清单，只读）回归测试。

这个脚本固化的是一次真实事故：
    我按本地 Django 的默认习惯猜表名 `productmethod`，
    实际生产是 **`product_method`**（带下划线、无 app 前缀）
    ⇒ SQL 直接报 `relation "productmethod" does not exist`。
    本脚本把「真表名」从「猜」变成「查」。

★ 本脚本最重要的性质是**绝对只读** —— 它连的是生产库。
   所以测试的重心不是「能不能列出表」，而是「**能不能保证不写**」：
     - `_assert_readonly` 必须拦住所有写关键字；
     - 必须**不误杀**合法查询（`updated_at` 里含 "update" 子串，
       若用朴素子串匹配就会把正常 SELECT 拦下来 —— 那等于工具不可用）；
     - 引号里的 'delete' 不该被当成关键字（误报）；
     - 注释里的 drop 不该被当成关键字（误报）。
   只测「拦得住」不测「不误杀」，得到的工具会因误报而无人敢用。
"""
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

from django.test import SimpleTestCase

REPO = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
)
SCRIPT = os.path.join(REPO, "scripts", "prod_schema_tables.py")


def _load():
    spec = importlib.util.spec_from_file_location("pst_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


pst = _load()


class ReadOnlyGuardTests(SimpleTestCase):
    """★ 核心：写操作必须被拦住，且不能误杀合法 SELECT。"""

    def test_blocks_every_write_keyword(self):
        for sql in ("DELETE FROM x", "DROP TABLE x", "INSERT INTO x VALUES (1)",
                    "UPDATE x SET a=1", "ALTER TABLE x ADD COLUMN y",
                    "CREATE TABLE x (a int)", "TRUNCATE x",
                    "GRANT ALL ON x TO y", "VACUUM"):
            with self.subTest(sql=sql):
                with self.assertRaises(PermissionError):
                    pst._assert_readonly(sql)

    def test_allows_normal_selects(self):
        for sql in ("SELECT tablename FROM pg_tables",
                    "SELECT COUNT(*) FROM product",
                    "SELECT 1"):
            with self.subTest(sql=sql):
                pst._assert_readonly(sql)          # 不该抛异常

    def test_does_not_false_positive_on_updated_at(self):
        """★ `updated_at` 含 'update' 子串 —— 朴素子串匹配会误杀。

        误报的代价：工具对正常查询也报警 ⇒ 没人敢用 ⇒ 守卫形同虚设。
        这里断言必须用**词边界**匹配。
        """
        pst._assert_readonly(
            "SELECT id FROM product WHERE updated_at > NOW()")
        pst._assert_readonly(
            "SELECT n_live_tup FROM pg_stat_user_tables")

    def test_does_not_false_positive_on_quoted_literals(self):
        """字符串字面量里的 'delete' 不该被当成关键字。"""
        pst._assert_readonly("SELECT 'delete me' AS note")

    def test_does_not_false_positive_on_comments(self):
        """注释里的 drop 不该被当成关键字。"""
        pst._assert_readonly("-- this would drop the table\nSELECT 1")
        pst._assert_readonly("/* create index here */ SELECT 1")

    def test_error_message_is_actionable(self):
        with self.assertRaises(PermissionError) as cm:
            pst._assert_readonly("DROP TABLE product")
        self.assertIn("只读", str(cm.exception))


class SqliteFallbackTests(SimpleTestCase):
    """退化模式：没有 docker 的机器上也能验证逻辑。"""

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.addCleanup(os.remove, self.path)
        conn = sqlite3.connect(self.path)
        conn.execute("CREATE TABLE product_method (id integer primary key)")
        conn.execute("CREATE TABLE productmethod (id integer primary key)")
        conn.executemany("INSERT INTO product_method VALUES (?)",
                         [(i,) for i in range(7)])
        conn.commit()
        conn.close()

    def test_lists_tables_and_row_counts(self):
        tables = pst.list_tables_sqlite(self.path)
        names = {t["table"] for t in tables}
        self.assertIn("product_method", names)
        counts = {t["table"]: t["rows"] for t in tables}
        self.assertEqual(counts["product_method"], 7)

    def test_both_spellings_coexist_and_are_distinguishable(self):
        """★ 今天的核心困惑：product_method 与 productmethod 是两张不同的表。

        这个用例把「查表名才能区分」这件事钉成断言。
        """
        counts = {t["table"]: t["rows"] for t in pst.list_tables_sqlite(self.path)}
        self.assertIn("product_method", counts)
        self.assertIn("productmethod", counts)
        self.assertNotEqual(counts["product_method"], counts["productmethod"],
                            "两张表行数相同，测不出区分能力")


class CliTests(SimpleTestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "-B", SCRIPT, *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace")

    def test_missing_sqlite_file_exits_2(self):
        p = self._run("--sqlite", "/nonexistent/definitely_not_here.sqlite3")
        self.assertEqual(p.returncode, 2)
        self.assertIn("sqlite 文件不存在", p.stderr)

    def test_no_docker_exits_2_with_hint(self):
        """没有 docker 时必须明确报错 + 给出退化方案，而不是崩栈。"""
        if _has_docker():
            self.skipTest("本机有 docker，会走生产分支")
        p = self._run()
        self.assertEqual(p.returncode, 2)
        self.assertIn("docker", p.stderr)
        self.assertIn("--sqlite", p.stderr, "报错时必须告诉人怎么退化")

    def test_help_works(self):
        p = self._run("--help")
        self.assertEqual(p.returncode, 0)
        self.assertIn("--sqlite", p.stdout)
        self.assertIn("--grep", p.stdout)

    def test_grep_no_match_exits_1(self):
        p = self._run("--sqlite", ":memory:", "--grep", "zzz_nothing")
        self.assertEqual(p.returncode, 1)
        self.assertIn("没有表名含", p.stdout)

    def test_json_output_on_memory_db(self):
        """空库也要给出结构完整的 JSON（并用 EXIT=1 表达「没查到」）。"""
        p = self._run("--sqlite", ":memory:", "--json")
        self.assertEqual(p.returncode, 1)
        data = json.loads(p.stdout)
        self.assertTrue(data["degraded"], "退化模式必须自我标注")
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["tables"], [])

    def test_empty_db_does_not_crash(self):
        """★ 实测踩到的坑：空表清单曾让 max() 抛 ValueError 而崩栈。

        只读工具崩栈比报错更糟 —— 崩栈会让人以为是环境坏了，而不是「库是空的」。
        """
        p = self._run("--sqlite", ":memory:")
        self.assertNotIn("Traceback", p.stderr, "空库不该崩栈")
        self.assertEqual(p.returncode, 1)
        self.assertIn("空库", p.stdout)

    def test_degraded_banner_warns_about_truth_value(self):
        """★ 退化模式必须在输出里写明「不代表生产真值」。"""
        p = self._run("--sqlite", ":memory:")
        self.assertIn("不代表生产真值", p.stdout)


class RealLocalDbTests(SimpleTestCase):
    """在真实本地 sqlite 库上验证退化模式确实能拿到表名。"""

    def setUp(self):
        self.db = os.path.join(REPO, "backend", "db.sqlite3")
        if not os.path.isfile(self.db):
            self.skipTest("本地没有 backend/db.sqlite3")

    def test_real_db_has_many_tables(self):
        tables = pst.list_tables_sqlite(self.db)
        self.assertGreater(len(tables), 20,
                           "真实库应有几十张表；这么少说明退化模式坏了")

    def test_real_db_table_names_contain_underscore_style(self):
        """★ 今天的教训本体：真实表名用下划线，不靠 app 前缀猜。

        本地 commerce 的 `Product` 落在表 `product`（无 app 前缀），
        `ProductMethod` 落在 `product_method`。
        这个断言记录了「Django 默认表名 = 小写下划线、不加 app 前缀」这一事实。
        """
        names = {t["table"] for t in pst.list_tables_sqlite(self.db)}
        self.assertIn("product", names)
        if "product_method" in names:
            self.assertNotIn("productmethod", names,
                             "若两张表同时存在，'猜表名'就更危险了")


def _has_docker():
    import shutil
    return shutil.which("docker") is not None