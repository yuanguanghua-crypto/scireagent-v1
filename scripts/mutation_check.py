#!/usr/bin/env python
"""mutation_check.py — 自动变异检测：证明测试不是摆设

## 为什么需要它

2026-10-19 一天里，我手工做了 4 次变异测试来证明新写的测试真的有效
（IDOR 跨用户隔离、`--verify-map` 的耗时归一化、URL 常量展开、`@action` 尾斜杠）。
每一次都是"改一行代码 → 跑测试 → 必须变红 → 改回来"。

问题：**这靠的是"当时记得"**。换个人、或者隔两周，就会退化成
"跑绿了就算过" —— 而那正是本项目反复吃亏的地方
（签收式 QA、假绿、以及 `266333c` 那次 76 天 185 次提交 0 次文档更新）。

⇒ 把「质疑」变成一条命令，不再靠自觉。

## 判据

对每个守卫注入一个**已知会破坏行为**的变异，然后跑它的测试：

| 结果 | 含义 |
|---|---|
| 测试**变红**（failed ≥ expect_failed_min） | ✅ 测试真的在测这件事 |
| 测试**还绿** | ❌ 测试是摆设（退出码 1） |

## 安全

- 每个变异前把原文读进内存，`finally` **无条件还原**并校验（sha256 比对）
- 不 commit、不 stash、不碰 git 索引、不删文件
- 任何一个变异失败，都会先还原再退出，工作区不会停在变异状态

## 用法

    python scripts/mutation_check.py              # 跑全部
    python scripts/mutation_check.py --list       # 只列出变异，不执行
    python scripts/mutation_check.py --only idor  # 只跑名字含 idor 的那个
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO, "backend")
PY = os.path.join(BACKEND, "venv", "Scripts", "python.exe")
if not os.path.isfile(PY):
    PY = sys.executable


class Mutation:
    """一个变异定义。

    `old` 必须在目标文件里**唯一且原样**出现 —— 脚本会先校验，
    匹配不到就拒绝执行（避免"以为注入了、其实没注入"的假阳性）。
    """

    def __init__(self, name, file, old, new, tests, expect_failed_min, why):
        self.name = name
        self.file = file
        self.old = old
        self.new = new
        self.tests = tests
        self.expect_failed_min = expect_failed_min
        self.why = why


MUTATIONS: list[Mutation] = [
    Mutation(
        name="idor-去掉用户过滤",
        file="backend/apps/transactions/api/v1/views.py",
        old="""            return Wishlist.objects.filter(
                user=self.request.user
            ).prefetch_related('products').order_by('-created_at')""",
        new="""            return Wishlist.objects.all().prefetch_related('products')  # ★MUTATION""",
        tests="apps/transactions/tests/test_wishlist_products.py",
        expect_failed_min=3,
        why="去掉 queryset 的 user 过滤后，跨用户 get/patch/delete 应该全部穿掉 —— "
            "3 个 IDOR 用例必须变红，否则它们根本没在验隔离",
    ),
    Mutation(
        name="verifymap-不归一化耗时",
        file="scripts/capability_guard.py",
        old='    return _VOLATILE_LINE.sub("[耗时] <不参与对比>", text)',
        new="    return text  # ★MUTATION",
        tests="apps/core/tests/test_capability_guard.py",
        expect_failed_min=2,
        why="生成物里有每次运行都变的 [耗时] 行。不归一化 ⇒ "
            "内容相同的两份也会被判不一致（检测永远假红）",
    ),
    Mutation(
        name="expandconst-不展开",
        file="scripts/capability_guard.py",
        old="    return _FSTRING_PURE_VAR.sub(_sub, text)",
        new="    return text  # ★MUTATION",
        tests="apps/core/tests/test_capability_guard.py",
        expect_failed_min=2,
        why="不展开 URL 常量 ⇒ f-string 拼的测试全部漏判（wishlist detail 曾因此被标无测试）",
    ),
    Mutation(
        name="actionurl-去尾斜杠",
        file="scripts/capability_guard.py",
        old='    return base + ("/{X}/" if detail else "/") + up + "/"',
        new='    return base + ("/{X}/" if detail else "/") + up  # ★MUTATION',
        tests="apps/core/tests/test_capability_guard.py",
        expect_failed_min=4,
        why="DRF DefaultRouter 默认 trailing_slash='/'，去掉尾斜杠后 URL 与真实路由不符 ⇒ "
            "13 个 @action 端点会被误标为无测试",
    ),
]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _count_failed(out: str) -> int:
    """数失败用例数。

    ⚠️ 不用 pytest 的汇总行（`N failed`）—— 本项目实测该行在有 warnings 时
       会整个消失。`-q` 模式下每个失败都会打印 `FAILED <nodeid>`，用这个更稳。
    """
    return sum(1 for ln in out.splitlines() if ln.startswith("FAILED"))


def _changed_files() -> set[str]:
    """取本次提交/工作区里改动的文件（相对仓库根，正斜杠）。"""
    out = set()
    for args in (
        ["git", "diff", "--cached", "--name-only"],   # 已暂存
        ["git", "diff", "--name-only"],               # 工作区
    ):
        try:
            r = subprocess.run(args, cwd=REPO, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
        except OSError:
            continue
        if r.returncode == 0:
            out.update(ln.strip().replace("\\", "/") for ln in r.stdout.splitlines() if ln.strip())
    return out


def _run_tests(tests: str) -> tuple[int, str]:
    env = dict(os.environ)
    env.update({
        "DB_ENGINE": "sqlite",
        "SECRET_KEY": "mutation-check",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    # ⚠️ 残留的 test_db.sqlite3 会让 SQLite 报 "database is locked"（实测）
    stale = os.path.join(BACKEND, "test_db.sqlite3")
    if os.path.isfile(stale):
        try:
            os.remove(stale)
        except OSError:
            pass
    proc = subprocess.run(
        [PY, "-B", "-m", "pytest", tests, "-q", "--tb=no", "-p", "no:cacheprovider"],
        cwd=BACKEND, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _git_leftovers(files: list[str]) -> list[str]:
    """跑完自检：这些文件相对 HEAD 是否还有**内容**差异。

    ⚠️ 不能用 `git status` 判断 —— 本项目文件在工作区是 CRLF、仓库内是 LF，
       写入一次就会让 stat 缓存失效，`git status` 显示 M 但 `git diff` 为空
       （实测：内容一字未改却显示"有改动"，极易被误认为脚本留了残留）。
       所以用 `git diff --quiet`，它比较的是**规范化后的内容**。
    """
    dirty = []
    for f in files:
        try:
            rc = subprocess.run(
                ["git", "diff", "--quiet", "--", f],
                cwd=REPO, capture_output=True,
            ).returncode
        except OSError:
            return []          # 没有 git 就跳过自检，不误报
        if rc != 0:
            dirty.append(f)
    return dirty


def run_one(m: Mutation, verbose: bool) -> str:
    """执行一个变异。返回 'ok' / 'weak' / 'error'。"""
    path = os.path.join(REPO, m.file)
    if not os.path.isfile(path):
        print(f"  ✗ [{m.name}] 文件不存在：{m.file}")
        return "error"
    original = _read(path)
    before_sha = _sha(original)

    if original.count(m.old) != 1:
        print(f"  ✗ [{m.name}] 变异锚点在文件中出现 {original.count(m.old)} 次（要求恰好 1 次）")
        print(f"     锚点：{m.old[:70]!r}")
        return "error"

    print(f"\n  [{m.name}] 注入变异…")
    st = os.stat(path)          # ★ 记录原始 atime/mtime，还原时一并恢复
    mutated = original.replace(m.old, m.new, 1)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(mutated)
        rc, out = _run_tests(m.tests)
        failed = _count_failed(out)
        verdict_ok = failed >= m.expect_failed_min
        if verdict_ok:
            print(f"    ✅ 变红：{failed} 个用例失败（要求 ≥{m.expect_failed_min}）⇒ 测试有效")
            print(f"       验证的是：{m.why}")
        else:
            print(f"    ❌ 仍绿：只有 {failed} 个失败（要求 ≥{m.expect_failed_min}）")
            print(f"       ⇒ 测试是摆设！这个守卫改坏了测试也发现不了。")
            print(f"       本应拦住：{m.why}")
            if verbose:
                tail = [ln for ln in out.splitlines() if ln.strip()][-12:]
                for ln in tail:
                    print(f"       | {ln[:110]}")
        return "ok" if verdict_ok else "weak"
    finally:
        # ★ 无条件还原，并校验还原真的成功（不能只信写入结果）
        with open(path, "w", encoding="utf-8") as f:
            f.write(original)
        # ★ 恢复 mtime：否则 git 的 stat 缓存失效，`git status` 会显示 M
        #   而实际 `git diff` 为空（内容一字未改）—— 容易被误认为"脚本留了残留"。
        try:
            os.utime(path, (st.st_atime, st.st_mtime))
        except OSError:
            pass
        after_sha = _sha(_read(path))
        if after_sha != before_sha:
            print(f"    ⚠️⚠️ 还原校验失败！{m.file} 的 sha256 已变化 —— 请立即 git checkout -- {m.file}")
        else:
            print(f"    ↩ 已还原（sha256 一致，mtime 已恢复）")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="自动变异检测：验证测试是否真的能发现问题",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--list", action="store_true", help="只列出变异，不执行")
    ap.add_argument("--only", metavar="SUBSTR", help="只跑名字包含该子串的变异")
    ap.add_argument("--changed", action="store_true",
                    help="只跑「本次改动涉及的文件」相关的变异（供 hook 用，零改动时秒退）")
    ap.add_argument("--verbose", action="store_true", help="失败时打印测试输出尾部")
    args = ap.parse_args(argv)

    selected = MUTATIONS
    if args.only:
        selected = [m for m in MUTATIONS if args.only.lower() in m.name.lower()]
        if not selected:
            print(f"[错误] 没有名字包含 {args.only!r} 的变异。可用：")
            for m in MUTATIONS:
                print(f"  - {m.name}")
            return 2
    if args.changed:
        changed = _changed_files()
        if not changed:
            print("[跳过] 工作区无改动，无需做变异检测。")
            return 0
        # 只保留「被测文件本身或其测试文件被改动」的变异
        picked = []
        for m in selected:
            watch = {m.file, "backend/" + m.tests, m.tests}
            if any(c in watch for c in changed):
                picked.append(m)
        if not picked:
            print("[跳过] 本次改动不涉及被守卫的文件（"
                  + "、".join(sorted({m.file for m in MUTATIONS})) + "）")
            return 0
        print(f"[--changed] 本次改动命中 {len(picked)}/{len(selected)} 个变异，只跑这些。")
        selected = picked

    if args.list:
        print(f"共 {len(selected)} 个变异：\n")
        for m in selected:
            print(f"  {m.name}")
            print(f"    文件：{m.file}")
            print(f"    测试：{m.tests}（要求 ≥{m.expect_failed_min} 个失败）")
            print(f"    理由：{m.why}\n")
        return 0

    print("=" * 74)
    print("变异检测：注入已知缺陷，测试必须变红")
    print("=" * 74)

    results = []
    for m in selected:
        results.append((m.name, run_one(m, args.verbose)))

    print("\n" + "=" * 74)
    ok = sum(1 for _, r in results if r == "ok")
    weak = [n for n, r in results if r == "weak"]
    err = [n for n, r in results if r == "error"]
    print(f"结果：有效 {ok}/{len(results)}｜测试是摆设 {len(weak)}｜执行出错 {len(err)}")
    if weak:
        print(f"  ❌ 无效测试：{', '.join(weak)}")
    if err:
        print(f"  ⚠️ 无法执行：{', '.join(err)}")
    print("=" * 74)

    if weak or err:
        return 1

    # ★ 收尾自检：确认没有把变异残留在工作区（用内容比较，不用 git status）
    touched = sorted({m.file for m in selected})
    leftovers = _git_leftovers(touched)
    if leftovers:
        print("\n⚠️⚠️ 以下文件相对 HEAD 仍有**内容**差异，可能残留了变异：")
        for f in leftovers:
            print(f"   {f}")
        print("  请执行：git checkout -- " + " ".join(leftovers))
        return 1
    print("  （自检：涉及的文件相对 HEAD 无内容差异，未留残留）")

    print("✅ 全部变异都被测试抓到 —— 这些守卫的测试不是摆设。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
