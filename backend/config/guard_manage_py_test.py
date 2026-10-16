"""`manage.py test` 误用拦截守卫。

背景
----
本项目测试**混用两种风格**：

* unittest 风格 —— 类继承 ``django.test.TestCase``
* pytest 风格—— 模块级 ``def test_xxx()`` + 裸 ``assert`` + ``pytestmark``

``manage.py test`` 走 unittest 发现器，**只收集 TestCase 子类里以 test 开头的方法**
⇒ pytest 风格文件对它不可见（实测 34 个文件含 pytest 风格用例）。

危险不在于"报错"，而在于**假通过**：``manage.py test`` 会跑完它能看见的那 1984 个
用例并返回 exit 0，让人以为"测试都过了"，而那些 pytest 风格用例**从未运行**。

因此本守卫在 ``manage.py`` 最靠前的位置拦截 ``manage.py test``，直接失败并给出
正确命令。

判定方式：静态 AST 扫描（不启动 pytest、不连数据库、不加载 Django）
--------------------------------------------------------------------
备选方案是"实跑 ``pytest --collect-only`` 再与 unittest 收集数比对"。实测开销：

=========================  ==========
方案                耗时
=========================  ==========
本方案（静态 AST）        0.42 s
备选（pytest collect）    3.58 s
参照：``manage.py check``  1.66 s（仅初始化 Django）
=========================  ==========

静态扫描更快，且不依赖 pytest 插件与数据库连接。开销并非零，但守卫只在"真的要跑
``manage.py test``"时触发，而那条命令本身要建测试库 + 跑 1984 个用例（分钟级），
0.42 s 相对可忽略。

静态扫描同样能完成"区分真的 0 个用例 与 因pytest 风格而收集不到"这一要求：
「有 test_ 定义 + unittest 收集不到用例」⇒ 隐形；「完全没有 test_ 定义」⇒ 是误命名
的非测试文件（如 management command），单独归类、不计入隐形统计。

交叉验证：把静态判定与 ``unittest.defaultTestLoader`` 的真实行为逐文件比对，
28 个文件完全一致（unittest 实收 0），另 6 个混风格文件被本守卫列入但 unittest 实收
5~21 个用例 —— 属偏严的假阳性，见"已知局限"第 3 条。

已知局限
--------
1. **对任何形式的 ``manage.py test`` 都拦截**，包括显式传入 unittest 风格目录
   （如 ``manage.py test apps/accounts``）。这是有意的：即使该目录当下全是
   TestCase，也不应让"用错发现器"重新变成静默假通过。代价是想跑单个目录也必须改用
   pytest（``pytest apps/accounts``，功能等价）。

2. **对"两条命令都收集不到"的文件，守卫无法覆盖。**
   若某文件 pytest 也收不到（例如纯 management command 被误命名为
   ``test_*.py``），两条命令的收集数都是 0 ⇒ 一致 ⇒ 守卫**放行**。
   静态扫描把这类文件识别为"无 test_ 定义"并**排除在隐形统计外**，
   但这只是让统计更准，并不能让它被守卫拦住。
   ⇒ 真正的解法是给这类文件改名（去掉 ``test_`` 前缀），而不是指望守卫。
   已知实例：``apps/bridges/management/commands/test_bioz_cache_roundtrip.py``
   实为 ``BaseCommand`` 诊断脚本，两条命令都不收它（**这是正确行为，不是缺陷**）。

3. **偏保守：可能多拦。** 判定依据是"文件里有没有 test_ 开头的定义"，而不是
   "unittest 到底收几个用例"。混风格文件（既有 TestCase 子类，又有模块级 pytest
   函数）会被一并列入，而 unittest 其实能收到其中 TestCase 那部分。
   实测 34 个被列入的文件里有 6 个属此类（unittest 实收 5~21 个用例）。
   后果是可能拦下一次本可运行的 ``manage.py test`` —— 偏严方向，不会造成假通过。
   （若要消除这类假阳性，需改成"实跑 unittest loader 数用例数"，代价是必须 import
   全部测试模块 —— 那会引入 Django/DB 依赖，与守卫"不碰数据库"的初衷冲突。）

4. AST 只认**直接**继承 unittest TestCase 家族的类，且只数**类体内直接定义**的
   test 方法。若测试方法来自自定义间接基类（``class T(BaseTestCase)``），
   静态扫描会漏判成隐形（假阳性）。后果同上：偏严。

5. 扫描按 pytest 的 ``python_files``（``test_*.py`` / ``*_tests.py`` / ``tests.py``）
   匹配文件。若有人新增测试文件却用了别的命名模式，静态扫描看不到它。

逃生阀
------
确需以 unittest 发现器跑测试时（几乎不需要）::

    SCIPREAGENT_ALLOW_MANAGE_TEST=1 python manage.py test ...
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

# 与 pytest.ini 的 python_files 保持一致
TEST_FILE_PATTERNS = ("test_*.py", "*_tests.py", "tests.py")

# unittest 默认加载器（django.test.runner 用 unittest.defaultTestLoader）
# 只收集这些基类的子类 —— 见 unittest/loader.py loadTestsFromTestCase
UNITTEST_BASES = frozenset({
    "TestCase",
    "TransactionTestCase",
    "SimpleTestCase",
    "LiveServerTestCase",
    "StaticLiveServerTestCase",
})

SKIP_DIR_PARTS = frozenset({
    "venv", ".pytest_cache", "__pycache__", "node_modules", ".git", "staticfiles",
})

# 守卫本身的输出，统一前缀便于检索
_BANNER = "=" * 72


def _is_test_file(path: Path) -> bool:
    name = path.name
    return (
        name == "tests.py"
        or name.startswith("test_")
        or name.endswith("_tests.py")
    )


def _analyze(path: Path) -> tuple[bool, bool]:
    """返回 (has_test_def, unittest_visible)。

    has_test_def     —— 文件里存在 test_ 开头的函数/方法定义
    unittest_visible —— 存在「直接继承 unittest TestCase 家族、且类内至少有一个
                        test_ 开头方法」的类。注意只看**类体内直接定义**的方法：
                        TestCase 子类为空壳（真正的用例是模块级 pytest 函数）时
                        收集不到任何用例，不能算作可见。
                        若TestCase 里的test 方法是继承来的，静态分析会漏判
                        （见"已知局限"第 3 条）。
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (SyntaxError, ValueError, OSError):
        # 读不了/语法错误一律当作"有测试且unittest 看不见"，偏保守（宁可误拦）
        return True, False

    has_test_def = False
    unittest_visible = False

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            is_unittest = any(
                (getattr(b, "id", None) or getattr(b, "attr", None)) in UNITTEST_BASES
                for b in node.bases
            )
            if is_unittest and any(
                isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))
                and sub.name.startswith("test")
                for sub in node.body
            ):
                unittest_visible = True
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test"):
                has_test_def = True

    return has_test_def, unittest_visible


def find_pytest_only_files(root: Path | None = None) -> tuple[list[str], list[str]]:
    """扫描测试文件，返回 (对 unittest 隐形的文件, 无任何 test_ 定义的文件)。

    * pytest_only —— 有 test_ 定义但unittest 收集不到任何用例 ⇒ 对 manage.py test 隐形
    * not_a_test  —— 完全没有 test_ 定义 ⇒ 名字像测试但不是测试（误命名的脚本/命令）
    """
    # 本文件在 backend/config/ 下，测试树的根是 backend/
    base = (root or Path(__file__).resolve().parent.parent)
    pytest_only: list[str] = []
    not_a_test: list[str] = []

    for path in sorted(base.rglob("*.py")):
        if SKIP_DIR_PARTS.intersection(path.parts):
            continue
        if not _is_test_file(path):
            continue
        has_test_def, unittest_visible = _analyze(path)
        rel = path.relative_to(base).as_posix()
        if not has_test_def:
            not_a_test.append(rel)
        elif not unittest_visible:
            pytest_only.append(rel)

    return pytest_only, not_a_test


def _print_blocker(pytest_only: list[str], not_a_test: list[str]) -> None:
    shown = pytest_only[:10]
    remaining = len(pytest_only) - len(shown)

    lines = [
        _BANNER,
        " 拦截：检测到 `manage.py test` —— 本项目请改用 pytest。",
        _BANNER,
        "",
        "原因：",
        "  `manage.py test` 使用 unittest 发现器，只收集 unittest.TestCase 子类。",
        "  本项目存在 pytest 风格测试（模块级 def test_xxx() + 裸 assert），",
        "  对 manage.py test 不可见 —— 它不会报错，而是静悄悄少跑一批用例后",
        "  返回 exit 0，造成\"假通过\"。",
        "",
        f"静态扫描：{len(pytest_only)} 个测试文件含 pytest 风格用例，"
        "manage.py test 无法完整收集，例如：",
    ]
    lines += [f"    - {p}" for p in shown]
    if remaining > 0:
        lines.append(f"    - ...（另有 {remaining} 个）")
    lines += [
        "",
        "正确命令（在 backend/ 目录下执行）：",
        "    venv/Scripts/python.exe -B -m pytest -p no:cacheprovider",
        "",
        "只跑某个文件/目录：",
        "    venv/Scripts/python.exe -B -m pytest <路径> -p no:cacheprovider",
        "",
        "pytest 能同时收集两种风格，因此**无需改动任何测试代码**。",
    ]
    if not_a_test:
        lines += [
            "",
            f"另：{len(not_a_test)} 个文件名字像测试但不含任何 test_ 定义，"
            "两条命令都不会收集（属正常，非缺陷）：",
        ]
        lines += [f"    - {p}" for p in not_a_test]
    lines += [
        "",
        "本守卫的已知局限：",
        "  * 判定基于静态 AST 分析「文件里有没有 test_ 开头的定义」，不数用例数，",
        "    因此偏保守：混风格文件（既有 TestCase 类又有模块级 pytest 函数）会被",
        "    一并列入，而 unittest 其实能收到其中 TestCase 那部分。后果是可能多拦",
        "    一次本可运行的 manage.py test —— 不会造成假通过，只是略严。",
        "  * 若某文件 pytest 也收集不到（如纯 management command 被误命名为",
        "    test_*.py），两条命令收集数都是 0，守卫会放行。",
        "    解法是给该文件改名去掉 test_ 前缀，而不是依赖守卫。",
        "  * 守卫只拦 manage.py test；直接调 `unittest` 模块绕过 manage.py 不在覆盖范围。",
        "",
        "确需以 unittest 发现器运行时，显式设置 SCIPREAGENT_ALLOW_MANAGE_TEST=1 放行。",
        _BANNER,
    ]
    print("\n".join(lines))


def guard_manage_py_test(argv: list[str] | None = None,
                        root: Path | None = None) -> None:
    """若 argv 是 manage.py test，则在真正执行前拦截；被拦截时直接 sys.exit(1)。

    放在 manage.py 中 Django 初始化**之前**调用 —— 误用要立刻失败，
    不值得为它先建测试库。
    """
    args = list(sys.argv if argv is None else argv)

    # 只拦 `test` 这个子命令本身。`test --keepdb`、`test apps/x` 等都拦。
    if len(args) < 2 or args[1] != "test":
        return

    if os.environ.get("SCIREAGENT_ALLOW_MANAGE_TEST") == "1":
        return

    pytest_only, not_a_test = find_pytest_only_files(root)

    # 没有隐形文件 ⇒ 本次 test 调用不存在"静默少跑"的风险，放行
    if not pytest_only:
        return

    _print_blocker(pytest_only, not_a_test)
    raise SystemExit(1)


if __name__ == "__main__":
    # 自检：python config/guard_manage_py_test.py
    _only, _not = find_pytest_only_files()
    print(f"pytest-only（对 manage.py test 隐形）: {len(_only)} 个文件")
    for p in _only:
        print(f"  - {p}")
    print(f"非测试（名字像测试但无 test_ 定义）: {len(_not)} 个文件")
    for p in _not:
        print(f"  - {p}")