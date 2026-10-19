"""守卫提示文案与代码实际读取的环境变量名必须一致。

★ 为什么单独有这个测试文件
--------------------------------------------------------------------------
2026-10-19 发现的真实 bug：
    ``config/guard_manage_py_test.py`` 的**提示文案**里写的是
        SCIPREAGENT_ALLOW_MANAGE_TEST=1        ← 多了一个 P
    而**代码实际读取**的是
        SCIREAGENT_ALLOW_MANAGE_TEST           ← 正确拼写
    ⇒ 用户照着提示设置环境变量，**会发现逃生阀完全不生效**。

这类缺陷最隐蔽的地方：代码是对的、文案是"看起来很正经"的，
两者都写在同一个文件里，测试也只测代码行为不看文案 ⇒ 谁都不会发现。

⇒ 所以本测试不看行为，只看**源码里的一致性**：
   源码中出现的每一个 ``*_ALLOW_MANAGE_TEST`` 字面量，
   都必须等于 ``os.environ.get(...)`` 真正读取的那个名字。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# backend/config/guard_manage_py_test.py
# __file__ = backend/apps/core/tests/test_manage_test_guard_banner.py
GUARD_SOURCE = Path(__file__).resolve().parents[3] / "config" / "guard_manage_py_test.py"

# 形如 SCIREAGENT_ALLOW_MANAGE_TEST / SCIPREAGENT_ALLOW_MANAGE_TEST
# ⚠️ 故意用宽松前缀 [A-Z]+，这样"拼错前缀"也能被匹配到 —— 否则正是漏掉它的原因
_ANY_ESCAPE_HATCH_NAME = re.compile(r"\b([A-Z]+_ALLOW_MANAGE_TEST)\b")
_CODE_READS = re.compile(r"os\.environ\.get\(\s*['\"]([A-Z_]+)['\"]")


@pytest.fixture(scope="module")
def guard_text() -> str:
    assert GUARD_SOURCE.is_file(), f"守卫源文件不存在：{GUARD_SOURCE}"
    return GUARD_SOURCE.read_text(encoding="utf-8")


def test_guard_source_exists(guard_text: str) -> None:
    """前置：源文件确实存在且非空（避免测试因路径错而空转通过）。"""
    assert len(guard_text) > 1000


def test_all_escape_hatch_mentions_match_code(guard_text: str) -> None:
    """★ 核心：源码里提到的逃生阀变量名，必须与代码读取的一致。

    覆盖 docstring、print 语句、注释里的所有出现 —— 因为它们都是"给人看的"，
    给人看的那份错了，比代码错更难发现。
    """
    read_names = set(_CODE_READS.findall(guard_text))
    assert read_names, "未能在守卫源码中找到 os.environ.get(...) 读取语句"

    mentioned_names = set(_ANY_ESCAPE_HATCH_NAME.findall(guard_text))
    assert mentioned_names, "未能在守卫源码中找到任何 *_ALLOW_MANAGE_TEST 字面量"

    wrong = mentioned_names - read_names
    assert not wrong, (
        "守卫源码中的变量名与代码实际读取的不一致，照着文案设置会不生效：\n"
        f"  代码实际读取: {sorted(read_names)}\n"
        f"  源码中被提及: {sorted(mentioned_names)}\n"
        f"  ★ 不一致的:   {sorted(wrong)}"
    )


def test_no_misspelled_reagent_prefix(guard_text: str) -> None:
    """★ 防复发：项目名是 SciReAgent，不是 SciPReAgent。

    2026-10-19 之前的文案写成 ``SCIPREAGENT_...``（多一个 P）。
    本断言直接钉死这个拼写，任何人再敲错都会在 CI 里红。
    """
    assert "SCIPREAGENT" not in guard_text, (
        "发现拼写错误 SCIPREAGENT（应为 SCIREAGENT，多了一个 P）"
    )


def test_banner_prints_correct_variable_name(guard_text: str) -> None:
    """提示横幅里出现的必须是正确变量名（而非只是"没有错的那个"）。

    上一条断言"没有错的"，这条断言"有对的" —— 两者合起来才完整：
    只断言"没有错的"，将来若把提示删掉也能通过。
    """
    correct = set(_CODE_READS.findall(guard_text))
    assert correct, "未找到代码读取的变量名"

    for name in correct:
        assert name in guard_text, f"源码中未出现正确变量名 {name}"

    # 至少有一处出现在"提示性文本"里（含 =1 的用法示例或 print 的字符串）
    assert f"{sorted(correct)[0]}=1" in guard_text
