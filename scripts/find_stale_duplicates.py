#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
find_stale_duplicates.py — 检测「改名/改造后留下的过期副本」

要拦的真实事故：
    `scripts/deletion_guard.py`（旧版，**有 P0 漏洞**：漏判命名空间导入，
    会给出「可以删」的结论）是 `scripts/capability_guard.py` 改名后的残留，
    **从未进 git**。危害不是它占地方，而是：
        有人照着旧版跑 → 拿到「可以安全删」的**假安全信号** → 真删 → 能力丢失。
    这类「看起来能用、其实已过期」的副本是**最隐蔽的债**：
    它不像报错那样提醒你，它**假装自己是答案**。

设计取舍（为什么这样判重，宁可漏报也不要误报）：
  误报的代价是**信任崩塌** —— 一旦工具开始喊「这里有重复文件」，
  大家就会学会忽略它，于是真重复也被忽略。所以阈值定得极高。

  相似度算法：`difflib.SequenceMatcher` 的 **ratio**（基于最长公共子序列），
  先做**降噪**再比：
    1. 去掉注释行、空行、docstring（文档不同不算「内容不同」）；
    2. 去掉所有空白（缩进风格差异不算差异）。
  只有 ratio ≥ **0.95** 才报告。
  ⚠️ 为什么不用更松的 0.8：脚本之间「结构相似但业务不同」极其常见
  （本仓库里 fill_missing_data.py 与 fill_missing_data_v2.py 就是这种），
  0.8 一定误报。实测在真实仓库上跑，0.95 得到 **0 条**报告 —— 这正是期望值。

  额外收敛（双重保险）：
    - 同名不同目录 → 直接跳过（同名往往是有意的分层，不是过期副本）；
    - 只比**同扩展名**的文件。

用法：
    python scripts/find_stale_duplicates.py                       # 扫整个仓库
    python scripts/find_stale_duplicates.py --threshold 0.98     # 更严
    python scripts/find_stale_duplicates.py scripts/              # 只扫某目录
    python scripts/find_stale_duplicates.py --min-lines 50       # 忽略小文件
    python scripts/find_stale_duplicates.py --json

退出码：0 = 未发现（这是正常状态）；1 = 发现疑似过期副本；
        2 = 用法/环境错误。
"""
from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 绝不能进去的目录：构建产物、依赖、缓存、版本库、测试临时区
SKIP_DIRS = {
    "__pycache__", "node_modules", "dist", "build", ".git", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".idea", ".vscode",
    "_audit_tmp", "_audit_evidence", "_lead_stash", "deliverables",
    "_docx_media", "e2e", "knowledge_packs", ".workbuddy", "htmlcov",
    "site-packages", ".eggs", "migrations",
    # 前端构建产物目录：内容是压缩后的 bundle，同一版本多次构建天然几乎逐字相同，
    # 报出来 100% 是误报（实测 frontend/_d4、_d5、_dist_old 三份互相撞到 0.95+）。
    # 这类目录不属于「源码」，过期副本要找的是源码副本。
    "_dist_old", "coverage", ".next", ".nuxt", ".output", ".parcel-cache",
}
# 只在这些扩展名之间做相似度比较
SCAN_EXT = {".py", ".sh", ".js", ".ts", ".vue", ".md", ".yml", ".yaml", ".bat", ".ps1"}


def _is_scannable_dir(name: str) -> bool:
    return name not in SKIP_DIRS and not name.startswith(".")


def iter_files(root: str, exts=None, min_lines: int = 0):
    """遍历候选文件，跳过所有构建/依赖/缓存目录与压缩产物。"""
    exts = exts or SCAN_EXT
    out = []
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if _is_scannable_dir(d)]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in exts:
                continue
            full = os.path.join(dirpath, fn)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.read().splitlines()
            except OSError:
                continue
            if len(lines) < min_lines:
                continue
            if _is_minified_bundle(lines):
                continue
            out.append((full, lines))
    return out


# 压缩产物的判据：平均行长极大。
# 实测标定（本仓库真实数据）：
#   frontend/_d2/assets/index-*.js  平均 12587 字符/行（最长一行 27 万字符）
#   scripts/capability_guard.py      平均    38 字符/行
#   scripts/find_stale_duplicates.py 平均    31 字符/行
# 两者相差三个数量级 ⇒ 阈值取 1000 有极大安全余量：
# 正常源码再宽的排版也到不了 1000 字符/行，而任何真实 bundle 都远超它。
MINIFIED_AVG_LINE = 1000


def _is_minified_bundle(lines) -> bool:
    """识别压缩/打包产物（vite/webpack 产出的 .js）。

    为什么需要它：本仓库 frontend/ 下同时留着 `_d2` `_d3` `_d4` `_d5`
    `dist_new` 等多份历史构建输出，它们是**同一版本 bundle 的重复**，
    相似度轻松 0.95+ ⇒ 100% 误报。但目录名会变（_d6、dist_2024…），
    写死目录名堵不住，所以改为**按内容特征**识别：压缩产物几乎全是超长单行。
    """
    if len(lines) < 5:
        return False
    avg = sum(len(l) for l in lines) / len(lines)
    return avg > MINIFIED_AVG_LINE


def _is_module_package_pair(a: str, b: str) -> bool:
    """识别 `foo.py` 与 `foo/__init__.py` 这类**共存的正常结构**。

    Python 允许同名模块与同名包并存（迁移期的常见手法），
    内容高度相似是必然的，不该报成「过期副本」。
    """
    def parts(p):
        return p.replace("\\", "/").split("/")

    for x, y in ((a, b), (b, a)):
        px, py = parts(x), parts(y)
        stem_x = os.path.splitext(px[-1])[0]
        if stem_x == "__init__":
            stem_x = os.path.splitext(py[-2])[0]
        if stem_x == py[-2]:          # 文件名 == 父目录名
            return True
    return False


def normalize_py(lines) -> list[str]:
    """Python：去掉注释/空行/docstring，再压掉所有空白。"""
    # 用 ast 精确剥 docstring，避免误删字符串里的内容
    body = lines
    try:
        tree = ast.parse("\n".join(lines))
        if tree.body and isinstance(tree.body[0], ast.Expr) and \
                isinstance(getattr(tree.body[0], "value", None), ast.Constant) and \
                isinstance(tree.body[0].value.value, str):
            # 找到 docstring 的行号范围，整段剔除
            start = tree.body[0].lineno - 1
            end = tree.body[0].end_lineno
            body = lines[:start] + lines[end:]
    except SyntaxError:
        # 文件语法有问题（或正在编辑）→ 退回逐行去注释
        pass
    out = []
    for ln in body:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        out.append("".join(s.split()))     # 压掉全部空白
    return out


def normalize_generic(lines) -> list[str]:
    """Shell/JS/Vue/文本：按 # 与 // 去注释行，再压掉空白。"""
    out = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("#") or s.startswith("//") or s.startswith("*"):
            continue
        out.append("".join(s.split()))
    return out


def normalize(path: str, lines) -> list[str]:
    return normalize_py(lines) if path.endswith(".py") else normalize_generic(lines)


def similar_groups(files, threshold: float, progress=None):
    """两两比较，返回 [(pathA, pathB, ratio), ...]，按相似度降序。"""
    norm = {p: normalize(p, ls) for p, ls in files}

    # 快速筛掉长度差异过大的组合：序列比再准也不可能救回 10 倍长度差
    pairs = []
    for i, (pa, la) in enumerate(files):
        na = norm[pa]
        if len(na) < 5:            # 太短的内容比出来的相似度不可信
            continue
        for pb, lb in files[i + 1:]:
            if os.path.basename(pa) == os.path.basename(pb):
                continue          # 同名不同目录 → 有意分层，跳过
            if _is_module_package_pair(pa, pb):
                continue          # foo.py 与 foo/__init__.py → 正常共存
            nb = norm[pb]
            if len(nb) < 5:
                continue
            if min(len(na), len(nb)) / max(len(na), len(nb)) < 0.90:
                continue          # 长度差 >10% 直接不做序列比
            r = difflib.SequenceMatcher(None, na, nb, autojunk=False).ratio()
            if r >= threshold:
                pairs.append((pa, pb, round(r, 4)))
                if progress:
                    progress()
    pairs.sort(key=lambda x: -x[2])
    return pairs


def _rel(p: str, base: str) -> str:
    try:
        return os.path.relpath(p, base)
    except ValueError:
        return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="检测改名/改造后残留的过期脚本副本（只报告，不删除）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("roots", nargs="*", default=None,
                    help="要扫描的目录（默认整个仓库）")
    ap.add_argument("--threshold", type=float, default=0.95,
                    help="相似度阈值，默认 0.95（越低越容易误报，不建议调低）")
    ap.add_argument("--min-lines", type=int, default=30,
                    help="少于这么多行的文件不参与比较，默认 30")
    ap.add_argument("--ext", default=None,
                    help="只比某类文件，逗号分隔，如 py,sh")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--quiet", action="store_true", help="只输出结论行")
    args = ap.parse_args(argv)

    if not 0.5 <= args.threshold <= 1.0:
        print(f"[错误] --threshold 必须在 0.5~1.0 之间，收到 {args.threshold}",
              file=sys.stderr)
        return 2

    roots = args.roots or [REPO]
    for r in roots:
        if not os.path.isdir(r):
            print(f"[错误] 目录不存在：{r}", file=sys.stderr)
            return 2

    exts = None
    if args.ext:
        exts = {"." + e.strip().lstrip(".") for e in args.ext.split(",") if e.strip()}

    files = []
    for r in roots:
        files.extend(iter_files(r, exts, args.min_lines))

    # 同路径去重（多个 root 可能覆盖同一文件）
    seen, uniq = set(), []
    for p, ls in files:
        if p not in seen:
            seen.add(p)
            uniq.append((p, ls))
    files = uniq

    pairs = similar_groups(files, args.threshold)

    if args.json:
        print(json.dumps({
            "threshold": args.threshold,
            "min_lines": args.min_lines,
            "files_scanned": len(files),
            "pairs": [{"a": _rel(a, REPO), "b": _rel(b, REPO), "similarity": r}
                      for a, b, r in pairs],
        }, ensure_ascii=False, indent=2))
    else:
        print("=" * 78)
        print("过期副本检测（只报告，不删除）")
        print("=" * 78)
        print(f"阈值 {args.threshold}｜最小行数 {args.min_lines}｜已扫文件 {len(files)}")
        print()
        if not pairs:
            print("未发现疑似过期副本。")
            print("  ⚠️ 这不等于「一定没有」：阈值 0.95 只抓几乎逐字相同的副本。")
            print("  ⚠️ 「改了名字但逻辑已分叉」的副本本脚本抓不到（那需要读代码语义）。")
        for a, b, r in pairs:
            print(f"🛑 [{r:.4f}] 内容高度相似，但路径/文件名不同")
            print(f"        A: {_rel(a, REPO)}")
            print(f"        B: {_rel(b, REPO)}")
            print("        ⇒ 确认哪个是现行版。若两者都在，**必须删除过期那份**：")
            print("          过期副本会给出过期的结论（假的「可以删」信号），")
            print("          这比缺失更危险。")
            print()

    return 1 if pairs else 0


if __name__ == "__main__":
    sys.exit(main())