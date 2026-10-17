#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
test_result_summary.py — pytest 输出的可靠判读（汇总行不可信时的唯一出路）

要解决的真实事故（两个都实测过）：
  1. **汇总行会整个消失**。部分 app 全量跑时因
     `ValueError: I/O operation on closed file` 丢掉 pytest 末尾的
     `=== 613 passed, 5 failed, 1 skipped in 12.3s ===` 汇总行。
     此时**只剩 EXIT 码 + `^FAILED` 行可信**，任何从别处抠出来的数字都是编的。
  2. **`grep -oE '[.FEsxX]'` 会被路径字母污染**。它对**整行**做字符提取，
     于是 `apps/knowledge/tests/test_expert_skill.py` 里的每个 `s`、`e`、`x`
     都变成一个「跳过的测试」。
     实测：在同一份输出上，正确做法数出 `s=1`，
     `grep -oE '[.FEsxX]'` 数出 **`s=194`**（虚高 193），还凭空多出
     `E=16 / x=4 / X=1`。⇒ 绝不能按「整行 grep 字符」计数。

本脚本的判定纪律（为什么这样写）：
  - 进度点图**只认行首**：`^[.FEsxX]+ +\[`。
    pytest 的进度行形如 `.........F.s..   [ 45%]`，
    进度点图后面跟的是空格 + `[NN%]`。
    只有**从行首开始**连续的点图才算数 ⇒ 路径里的字母永远进不来。
  - **不解析 `X` 为 failed**：pytest 里 `x` = xfail(通过)，
    `X` = xpass(意外通过)。它们既不是 failed 也不是 passed，
    单列为 `xpassed/xfailed`，避免混进任何一边造成数字对不上。
  - **汇总行缺失时不编数字**：改用进度点图反推，并显式标注
    「汇总行不可用（可能是 ValueError: I/O operation on closed file）」，
    同时说明这个数字是**反推值**而非 pytest 自己说的。
  - **反推值与汇总行都在时**：两者都打印，并标出是否一致；
    不一致本身就是信号（通常意味着进度点图被截断），给出警告。

用法：
    python scripts/test_result_summary.py _fb_after_commerce.txt
    python scripts/test_result_summary.py out.txt --json
    python scripts/test_result_summary.py out.txt --expect-failed 5     # 与基线比对
    cat out.txt | python scripts/test_result_summary.py -

退出码：
    0 = 解析成功，且（未指定 --expect-failed 或与基线一致）
    1 = 有测试失败（failed > 0），或与 --expect-failed 基线不符
    2 = 用法/输入错误（文件不存在、没有任何可判读的行等）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── 判读正则 ──────────────────────────────────────────────────────────
# 进度点图行：行首连续的点图字符 + 空白 + '['。
# 行首锚点 ^ 是全部关键：它保证路径中的字母不会被误当成进度符号。
PROGRESS_RE = re.compile(r"^([.FEsxX]+)[ \t]*\[")
# 进度点图字符 → 语义
GLYPH = {
    ".": "passed",
    "F": "failed",
    "E": "error",     # 用例内异常（fixture 挂了等），pytest 打成 E
    "s": "skipped",
    "x": "xfailed",
    "X": "xpassed",
}
# pytest 末尾汇总行，例如：
#   === 613 passed, 5 failed, 1 skipped, 2 xfailed, 1 xpassed in 12.34s ===
SUMMARY_RE = re.compile(r"^=+ *(.+?) in [\d.]+s(?: \(\d+\.\d+.*\))? =+\s*$")
# 汇总行里的分项：'613 passed' / '5 failed' / '1 skipped' / '2 xfailed'
COUNT_RE = re.compile(r"(\d+)\s+(passed|failed|skipped|error|errors|xfailed|xpassed|deselected|warning|warnings)")
# ^FAILED 行：pytest 的 short test summary 段
FAILED_RE = re.compile(r"^FAILED\s+(\S+?)(?:\s+-\s+(.*))?$")
# 汇总行丢失的典型原因
LOST_SUMMARY_HINTS = (
    "ValueError: I/O operation on closed file",
    "OSError: [Errno 9]",
)


def _norm_kind(word: str) -> str:
    """把 pytest 的复数/单数措辞统一成我们的语义键。"""
    w = word.rstrip("s") if word in ("errors", "warnings") else word
    return {"error": "error", "warning": "warning"}.get(w, w)


def parse(text: str) -> dict:
    """从 pytest 输出文本中抽取可判读的全部信息。"""
    result = {
        "summary_line_found": False,
        "summary_raw": None,
        "summary_counts": {},        # pytest 自报（权威）
        "progress_counts": {},       # 进度点图反推（兜底）
        "progress_total": 0,
        "progress_lines": 0,
        "failed_tests": [],          # [(test_id, reason)]
        "summary_lost_suspected": False,
        "lost_summary_hints": [],
        "has_failure_marker": False,
    }
    prog = {k: 0 for k in GLYPH.values()}
    total = 0
    plines = 0

    for line in text.splitlines():
        # 1) 进度点图（行首锚定）
        m = PROGRESS_RE.match(line)
        if m:
            plines += 1
            for ch in m.group(1):
                total += 1
                prog[GLYPH[ch]] += 1

        # 2) 汇总行
        ms = SUMMARY_RE.match(line)
        if ms and " in " in line:
            result["summary_line_found"] = True
            result["summary_raw"] = line
            counts = {}
            for num, word in COUNT_RE.findall(ms.group(1)):
                counts[_norm_kind(word)] = counts.get(_norm_kind(word), 0) + int(num)
            result["summary_counts"] = counts
            # 汇总行自带 failed ⇒ 明确知道有失败
            if counts.get("failed"):
                result["has_failure_marker"] = True

        # 3) ^FAILED 行
        mf = FAILED_RE.match(line)
        if mf:
            result["has_failure_marker"] = True
            result["failed_tests"].append([mf.group(1), mf.group(2) or ""])

        # 4) 汇总行丢失的线索
        for h in LOST_SUMMARY_HINTS:
            if h in line and h not in result["lost_summary_hints"]:
                result["lost_summary_hints"].append(h)

    result["progress_counts"] = prog
    result["progress_total"] = total
    result["progress_lines"] = plines

    # 汇总行没出现，但输出里出现了「关闭文件」类错误 ⇒ 高度疑似被打断
    if not result["summary_line_found"] and result["lost_summary_hints"]:
        result["summary_lost_suspected"] = True

    return result


def choose_counts(r: dict) -> tuple[dict, str, list[str]]:
    """决定用哪份数字，并返回 (counts, 来源标签, 警告列表)。"""
    warns: list[str] = []
    s, p = r["summary_counts"], r["progress_counts"]

    if r["summary_line_found"] and r["progress_total"] > 0:
        # 两份都有：交叉核对
        s_total = sum(v for k, v in s.items()
                      if k in ("passed", "failed", "error", "skipped", "xfailed", "xpassed"))
        if s_total != r["progress_total"]:
            warns.append(
                f"汇总行自报 {s_total} 项，进度点图数出 {r['progress_total']} 项，"
                f"相差 {abs(s_total - r['progress_total'])}。"
                f"通常意味着输出被截断或进度行被覆盖 —— 两个数字都要打问号。")
        return s, "pytest 汇总行（权威）", warns

    if r["summary_line_found"]:
        return s, "pytest 汇总行（权威）", warns

    if r["progress_total"] > 0:
        reason = ""
        if r["summary_lost_suspected"]:
            reason = ("（检测到 " + " / ".join(r["lost_summary_hints"])
                      + " ⇒ 几乎可以确认汇总行是被这个错误吃掉了）")
        warns.append(
            f"⚠️ 汇总行不可用{reason}。以下数字是从进度点图（行首锚定 ^[.FEsxX]+ +\\[）"
            f"反推的**反推值**，不是 pytest 自己说的。")
        return p, "进度点图反推（汇总行不可用）", warns

    return {}, "无", ["❌ 输出里既没有汇总行也没有任何进度点图行，无法判读。"]


def render(r: dict, counts: dict, source: str, warns: list[str],
           path: str) -> str:
    out: list[str] = []
    out.append("=" * 78)
    out.append("pytest 输出判读")
    out.append("=" * 78)
    out.append(f"文件: {path}")
    out.append(f"数字来源: {source}")
    out.append("")

    if r["summary_line_found"]:
        out.append(f"[pytest 自报汇总行] {r['summary_raw']}")
    else:
        out.append("[pytest 自报汇总行] —— 缺失")
        if r["summary_lost_suspected"]:
            out.append(f"                  疑似原因: {' / '.join(r['lost_summary_hints'])}")
            out.append("                  （该错误会吞掉 pytest 收尾阶段的输出，"
                       "这是本项目多次踩到的形态）")
    out.append(f"[进度点图行数] {r['progress_lines']} 行，共 {r['progress_total']} 个符号")
    out.append("")

    order = ["passed", "failed", "error", "skipped", "xfailed", "xpassed", "deselected"]
    out.append("[反推/自报明细]")
    for k in order:
        if k in counts:
            out.append(f"  {k:<11} {counts[k]}")
    unknown = set(counts) - set(order)
    for k in sorted(unknown):
        out.append(f"  {k:<11} {counts[k]}")
    if not counts:
        out.append("  （无）")

    if r["progress_counts"] and r["summary_line_found"]:
        out.append("")
        out.append("[进度点图独立计数（用于交叉核对）] "
                   + " ".join(f"{k}={v}" for k, v in r["progress_counts"].items() if v))

    out.append("")
    if warns:
        out.append("[⚠️ 警告]")
        for w in warns:
            out.append(f"  - {w}")
        out.append("")

    out.append(f"[判读结论] failed+error = {counts.get('failed', 0) + counts.get('error', 0)}"
               f"｜passed = {counts.get('passed', 0)}")
    if r["failed_tests"]:
        out.append(f"           判定: **有测试失败**（{len(r['failed_tests'])} 条 ^FAILED）")
    elif counts.get("failed", 0) or counts.get("error", 0):
        out.append("           判定: **有测试失败**（汇总计数非零，但没有 ^FAILED 行 —— "
                   "很可能是 collection 阶段就炸了）")
    else:
        out.append("           判定: 无失败")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="可靠判读 pytest 输出（汇总行丢失时的兜底）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("path", help="pytest 输出文件；'-' 表示从 stdin 读")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--expect-failed", type=int, metavar="N", default=None,
                    help="已知基线失败数；实际超过它判为回归")
    args = ap.parse_args(argv)

    if args.path == "-":
        text = sys.stdin.read()
        disp = "<stdin>"
    else:
        if not os.path.isfile(args.path):
            print(f"[错误] 文件不存在：{args.path}", file=sys.stderr)
            return 2
        with open(args.path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        disp = args.path

    if not text.strip():
        print(f"[错误] 文件是空的：{args.path}", file=sys.stderr)
        return 2

    r = parse(text)
    counts, source, warns = choose_counts(r)

    if args.json:
        print(json.dumps({
            "file": disp,
            "source": source,
            "counts": counts,
            "summary_line_found": r["summary_line_found"],
            "summary_raw": r["summary_raw"],
            "progress_counts": r["progress_counts"],
            "progress_total": r["progress_total"],
            "summary_lost_suspected": r["summary_lost_suspected"],
            "failed_tests": r["failed_tests"],
            "warnings": warns,
        }, ensure_ascii=False, indent=2))
    else:
        print(render(r, counts, source, warns, disp))
        if r["failed_tests"]:
            print()
            print(f"[^FAILED 清单] 共 {len(r['failed_tests'])} 条")
            for tid, reason in r["failed_tests"]:
                print(f"  FAILED {tid}" + (f"  — {reason}" if reason else ""))

    # ── 退出码 ──
    if not counts:
        print("[错误] 无法从该文件判读任何 pytest 结果", file=sys.stderr)
        return 2

    failed = counts.get("failed", 0) + counts.get("error", 0)
    if args.expect_failed is not None:
        # 给了基线 ⇒ 以「是否超基线」为唯一判据。
        # 失败数正好等于基线（本项目 commerce 那 5 条外网失败）是**预期状态**，
        # 此时必须退出 0，否则基线比对功能反而天天误报。
        if failed > args.expect_failed:
            print(f"[回归] 失败数 {failed} 超过已知基线 {args.expect_failed}"
                  f" ⇒ 有回归", file=sys.stderr)
            return 1
        if not args.json:
            print(f"[基线] 失败数 {failed} ≤ 已知基线 {args.expect_failed} ⇒ 无回归")
        return 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())