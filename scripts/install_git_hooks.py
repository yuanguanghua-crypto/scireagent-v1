#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install_git_hooks.py — 把闸门 hook 装进 .git/hooks/（纯标准库，只读+一次写）

为什么需要安装脚本，而不是让人手抄：
  `scripts/hooks/pre-commit-capability-guard` 是**入库的模板**，
  但 `.git/hooks/` **不入库**（每个 clone 都是空的）。
  ⇒ 模板必须被"装"一次，闸门才真正生效。

这个脚本刻意处理的几个真实坑：
  1. **core.hooksPath 可能已被设置**。若设了，写 `.git/hooks/` 是**无效的**
     （git 只看 hooksPath 指向的目录）—— 实测本仓库当前**未设置**，
     但别的开发者/CI 可能设了。不检查就装 = 装了个不生效的东西，
     比不装更糟（以为有闸门，实际没有）。
  2. **CRLF 会搞坏 bash hook**。本仓库 `core.autocrlf=true`（实测），
     模板若被检出成 CRLF，Git Bash 执行会报 `$'\r': command not found`。
     ⇒ 安装时**强制转成 LF**，而不是简单 cp。
  3. **可执行位**。Windows 上靠文件关联，Git Bash 下必须 chmod +x。
  4. **不覆盖别人的 hook**。若目标已存在且内容不同，**拒绝覆盖**并说明，
     除非显式 `--force`。闸门被静默覆盖 = 又一次"以为有闸门"。

用法：
    python scripts/install_git_hooks.py            # 安装（幂等）
    python scripts/install_git_hooks.py --status   # 只看状态，不改任何东西
    python scripts/install_git_hooks.py --force    # 覆盖已存在的不同版本
    python scripts/install_git_hooks.py --uninstall

退出码：0 = 成功/已安装；1 = 需要人工介入（hooksPath 被占用且给了不同目录、
        或目标已存在不同内容）；2 = 用法/环境错误。
"""
from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(REPO, "scripts", "hooks", "pre-commit-capability-guard")
HOOK_NAME = "pre-commit"


def git(*args, cwd=None):
    p = subprocess.run(["git", *args], cwd=cwd or REPO,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def hooks_dir() -> tuple[str, str | None, bool]:
    """返回 (实际生效的 hooks 目录, core.hooksPath 原值, 是否被 hooksPath 接管)。"""
    rc, out, _ = git("config", "--get", "core.hooksPath")
    if rc == 0 and out:
        hp = out
        if not os.path.isabs(hp):
            hp = os.path.join(REPO, hp)
        return hp, out, True
    return os.path.join(REPO, ".git", "hooks"), None, False


def to_lf(text: str) -> str:
    """归一化成 LF。CRLF 的 hook 在 Git Bash 下是坏的。"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_lf(path: str) -> str:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return to_lf(f.read())


def make_executable(path: str) -> bool:
    """尽力设置可执行位。返回是否真的设上了。

    ⚠️ 实测的平台事实：**Windows 上的 Python 无法设置可执行位** ——
       `os.chmod(..., S_IXUSR)` 在 NTFS 上是空操作（stat 出来仍是 0o100666）。
       这不是脚本的 bug，是 CPython 在 Windows 上只支持 read-only 标志。
    ⇒ 所以这里返回实际结果，让调用方能如实告诉用户「位没设上」，
       而不是打印一个假的"可执行: True"。
    ⇒ 好消息：Git for Windows 在 Windows 上执行 hook 时不检查可执行位，
       所以照样能跑（已实测通过）。在 Linux/macOS 上则必须靠这个位。
    """
    try:
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        return False
    return bool(os.stat(path).st_mode & stat.S_IXUSR)


def exec_hint() -> str:
    if os.name == "nt":
        return ("（Windows 上无法设置可执行位，属平台限制；"
                "Git for Windows 执行 hook 时不检查该位，已实测可正常运行）")
    return ""


def has_crlf(path: str) -> bool:
    with open(path, "rb") as f:
        return b"\r\n" in f.read(65536)


def status() -> int:
    tpl_ok = os.path.isfile(TEMPLATE)
    hd, hp_raw, managed = hooks_dir()
    target = os.path.join(hd, HOOK_NAME)
    installed = os.path.isfile(target)

    print("=" * 74)
    print("capability-guard hook 安装状态")
    print("=" * 74)
    print(f"模板: {TEMPLATE}")
    print(f"      {'✅ 存在' if tpl_ok else '❌ 缺失（hook 无法安装）'}")
    print(f"生效的 hooks 目录: {hd}")
    if managed:
        print(f"⚠️  core.hooksPath = {hp_raw}")
        print("    git 只看这个目录，写 .git/hooks/ **不生效**。")
    else:
        print("      core.hooksPath 未设置 ⇒ .git/hooks/ 就是生效目录。")

    print(f"目标: {target}")
    if installed:
        print(f"      ✅ 已安装｜可执行={_is_exec(target)}｜CRLF={has_crlf(target)}")
        if tpl_ok:
            same = read_lf(target) == read_lf(TEMPLATE)
            print(f"      与模板一致: {'是' if same else '否（模板有更新，可重跑安装）'}")
    else:
        print("      ❌ 未安装 ⇒ 删除文件时不会触发闸门")
    print()
    if not installed:
        print("安装: python scripts/install_git_hooks.py")
    return 0


def _is_exec(path: str) -> bool:
    try:
        return bool(os.stat(path).st_mode & stat.S_IXUSR)
    except OSError:
        return False


def uninstall() -> int:
    hd, hp_raw, managed = hooks_dir()
    target = os.path.join(hd, HOOK_NAME)
    if not os.path.isfile(target):
        print("未安装，无需卸载。")
        return 0
    with open(target, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    if "capability-guard" not in content:
        print(f"拒绝删除：{target} 不是本项目的 hook（内容不含 capability-guard）。")
        print("        请人工确认后手动处理。")
        return 1
    os.remove(target)
    print(f"已卸载：{target}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="安装删除前置闸门的 pre-commit hook",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("--status", action="store_true", help="只看状态，不改动")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的不同版本")
    ap.add_argument("--uninstall", action="store_true", help="卸载 hook")
    args = ap.parse_args(argv)

    rc, _, err = git("rev-parse", "--git-dir")
    if rc != 0:
        print(f"[错误] 不在 git 仓库内：{err}", file=sys.stderr)
        return 2

    if args.status:
        return status()
    if args.uninstall:
        return uninstall()

    if not os.path.isfile(TEMPLATE):
        print(f"[错误] 模板缺失：{TEMPLATE}", file=sys.stderr)
        return 2

    hd, hp_raw, managed = hooks_dir()

    if managed and not os.path.isdir(hd):
        print(f"[需要人工介入] core.hooksPath = {hp_raw} 指向的目录不存在：{hd}")
        print(f"  两种选择：")
        print(f"    A. 在该目录下安装（保持 hooksPath 语义一致）：")
        print(f"         mkdir -p \"{hd}\" && cp scripts/hooks/pre-commit-capability-guard \\")
        print(f"              \"{hd}/{HOOK_NAME}\"")
        print(f"    B. 取消 hooksPath，改用 .git/hooks/：")
        print(f"         git config --unset core.hooksPath")
        print(f"         python scripts/install_git_hooks.py")
        return 1

    os.makedirs(hd, exist_ok=True)
    target = os.path.join(hd, HOOK_NAME)
    desired = read_lf(TEMPLATE)

    if os.path.isfile(target):
        current = read_lf(target)
        if current == desired:
            exec_ok = make_executable(target)
            if has_crlf(target):
                _rewrite_lf(target, desired)
            print(f"✅ 已是最新，无需改动：{target}")
            print(f"   （已确认 LF 行尾；可执行位已设置: {exec_ok}"
                  + (f" {exec_hint()}" if not exec_ok else "") + "）")
            return 0
        if not args.force:
            print(f"[拒绝覆盖] 目标已存在且内容不同：{target}")
            print("  那可能是你自己写的 hook。本项目不会静默覆盖它。")
            print("  确认要用本项目的版本替换：")
            print(f"    python scripts/install_git_hooks.py --force")
            return 1
        print("⚠️  --force：正在覆盖既有 hook")

    _rewrite_lf(target, desired)
    exec_ok = make_executable(target)
    print(f"✅ 已安装：{target}")
    print(f"   LF 行尾: {not has_crlf(target)}｜可执行位已设置: {exec_ok}"
          + (f" {exec_hint()}" if not exec_ok else ""))
    if managed:
        print(f"   注意：core.hooksPath = {hp_raw}，装在这里是对的。")
    print()
    print("验证：暂存一个删除后 git commit，闸门会启动。")
    print("绕过：git commit --no-verify | SKIP_CAPABILITY_GUARD=1 git commit")
    return 0


def _rewrite_lf(path: str, content: str) -> None:
    """用 LF 写出（newline='' 防止平台默认把 \n 又转成 \r\n）。"""
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)


if __name__ == "__main__":
    sys.exit(main())