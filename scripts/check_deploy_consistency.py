#!/usr/bin/env python
"""check_deploy_consistency.py — C7 / C8 的可复现判据

## 它判什么

对应 `docs/CLAIMS.md` 的两条结论：

- **C7** 生产代码 = GitHub = 本地 HEAD
- **C8** 生产前端产物与 HEAD 源码一致

在此之前这两条**没有任何自动化判据**（只能靠人每次部署后手工 ssh 敲命令核对）。
本脚本把那些命令固化下来，让「四地一致」这件事变成一条可重跑的命令。

## 为什么不做成 CI job

C7/C8 需要 ssh 到生产机。把生产 SSH key 放进 GitHub Secrets，
等于给"能 push 的人"开了一个读生产凭据的口子（本仓库是 public）。
⇒ 权衡后做成**本地可跑的命令**，属 CLAIMS 第 4 问允许的「可复现命令」形态。

## 用法

    python scripts/check_deploy_consistency.py
    python scripts/check_deploy_consistency.py --host admin@1.2.3.4 --key ~/.ssh/deploy
    SCIREAGENT_HOST=server-alias SCIREAGENT_SSH_KEY=~/.ssh/k python scripts/check_deploy_consistency.py --json

环境变量（都可选，命令行优先）：
    SCIREAGENT_HOST      生产 ssh 目标，默认 admin@47.82.156.48
    SCIREAGENT_SSH_KEY   ssh 私钥路径（不设则用默认 key / ~/.ssh/config）
    SCIREAGENT_REMOTE    生产仓库目录，默认 /home/admin/scireagent

退出码：0 = C7 与 C8 都成立；1 = 有不一致；2 = 环境问题（连不上等）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_HOST = os.environ.get("SCIREAGENT_HOST", "admin@47.82.156.48")
DEFAULT_KEY = os.environ.get("SCIREAGENT_SSH_KEY", "")
DEFAULT_REMOTE = os.environ.get("SCIREAGENT_REMOTE", "/home/admin/scireagent")


def _run(cmd: list[str], cwd: str | None = None, timeout: int = 60) -> tuple[int, str]:
    """跑命令，返回 (exit, stdout+stderr)。

    ⚠️ 用 list 形式而不是 shell 字符串：本项目踩过「ssh 多层引号把 $var 吞掉」
       导致 URL 变成 // 从而假报 401 的坑。列表形式完全避开 shell 解析。
    """
    try:
        p = subprocess.run(cmd, cwd=cwd or REPO, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except FileNotFoundError:
        return 127, f"命令不存在: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"超时（{timeout}s）: {' '.join(cmd[:3])}"


def _md5(path: str) -> str | None:
    if not os.path.isfile(path):
        return None
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ssh_base(host: str, key: str) -> list[str]:
    cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=15"]
    if key:
        # ⚠️ Windows 上 ssh 要求正斜杠路径
        cmd += ["-i", key.replace("\\", "/")]
    cmd += [host]
    return cmd


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="校验 C7（四地 HEAD 一致）与 C8（生产 dist 与源码一致）",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--host", default=DEFAULT_HOST, help=f"生产 ssh 目标（默认 {DEFAULT_HOST}）")
    ap.add_argument("--key", default=DEFAULT_KEY, help="ssh 私钥路径（默认用 ssh 自身配置）")
    ap.add_argument("--remote", default=DEFAULT_REMOTE, help="生产仓库目录")
    ap.add_argument("--skip-remote", action="store_true", help="只查本地/GitHub，不连生产（离线自检）")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args(argv)

    res: dict = {"checks": {}, "ok": True, "notes": []}

    def record(name: str, value, ok: bool | None = None, detail: str = ""):
        res["checks"][name] = {"value": value, "ok": ok, "detail": detail}
        if ok is False:
            res["ok"] = False

    # ── 本地 HEAD ──
    rc, out = _run(["git", "rev-parse", "HEAD"])
    local_head = out if rc == 0 else None
    record("本地 HEAD", local_head, rc == 0)

    # ── origin/master（本地视角）──
    rc, out = _run(["git", "ls-remote", "origin", "master"])
    origin_head = out.split()[0] if rc == 0 and out else None
    record("origin/master", origin_head, rc == 0)

    c7_ok = bool(local_head and origin_head and local_head == origin_head)

    # ── 生产侧 ──
    remote_head = None
    remote_origin_head = None
    remote_dist_md5 = None
    remote_dist_mtime = None

    if not args.skip_remote:
        ssh = _ssh_base(args.host, args.key)
        rc, out = _run(ssh + [f"cd {args.remote} && git rev-parse HEAD"], timeout=45)
        if rc == 0 and len(out.split()) == 1:
            remote_head = out.strip()
            record("生产 worktree HEAD", remote_head, remote_head == local_head)
        else:
            record("生产 worktree HEAD", None, False, f"ssh 失败: {out[:160]}")
            res["notes"].append("连不上生产 ⇒ 本脚本**只验证了本地↔GitHub**，C7 仍未证实")

        if remote_head:
            rc, out = _run(ssh + [f"cd {args.remote} && git ls-remote origin master"], timeout=60)
            if rc == 0 and out:
                remote_origin_head = out.split()[0]
                record("生产视角 origin/master", remote_origin_head,
                       remote_origin_head == local_head)

            # ⚠️ 这里不再取 dist 的 md5/mtime —— C8 已改为「生产机上 rebuild 幂等性」，
            #    比对本地/线上 md5 属于循环论证（见下方 C8 段的说明）。

        c7_ok = c7_ok and remote_head == local_head and remote_origin_head == local_head

    # ★ --skip-remote 时**绝不能**报 C7 成立：它只验证了"本地 ↔ GitHub"两地，
    #   而 C7 是"四地"（本地 / GitHub / 生产 worktree / 生产视角的 origin）。
    #   把"两地一致"写成"四地一致"就是假阳性 —— 与"跑绿≠有效"是同一类错误。
    if args.skip_remote:
        res["checks"]["C7 四地一致"] = {
            "value": "未验证生产（--skip-remote）",
            "ok": None,
            "detail": "只查了本地↔GitHub，C7 不成立（不能说「一致」）",
        }
        res["notes"].append("--skip-remote：C7 只验证了两地，生产侧未查 ⇒ C7 未证实")
    else:
        res["checks"]["C7 四地一致"] = {
            "value": c7_ok,
            "ok": c7_ok,
            "detail": "" if c7_ok else "四值未全等（见上面各项）",
        }
        if not c7_ok:
            res["ok"] = False

    # ── C8：生产产物是不是「当前 HEAD 构建出来的」 ──
    #
    # ★★ 2026-10-20 重写判据 —— 原判据有**循环论证**漏洞：
    #   旧逻辑比的是「本地 dist md5 == 生产 dist md5」。
    #   但本地 dist 完全可能是从生产下载/拷贝的，那两边必然相同，
    #   **什么都证明不了**（就像"我抄了答案，所以我的答案和标准答案一样"）。
    #
    # 正确判据（rebuild 幂等性）：
    #   在**生产机上**用当前 HEAD 源码重新构建到临时目录，
    #   与线上 dist 逐文件比对 —— 一致才说明线上产物确实是 HEAD 构建的。
    #   这是唯一能真正证伪的形态：如果线上 dist 是旧代码的产物，
    #   rebuild 出来的文件 hash 会不同。
    # ★★★ 第三版（本版，2026-10-20 12:00）：构建时把 commit 写进产物
    #   前面两版都错了：
    #     第一版「本地 dist md5 == 生产 md5」→ 本地可能是从生产拷的，循环论证
    #     第二版「生产机 rebuild 后逐文件 diff」→ **假设构建可复现，实测不成立**
    #       （同源码连两次构建：Tailwind v4 的 CSS 差 685 字节 421115 vs 420430，
    #         CSS hash 变 → 入口 JS hash 变 → 167 个文件全改名）
    #   本版：frontend/vite.config.js 的 injectBuildCommit() 把 commit 写进
    #     dist/index.html 的 <meta name="build-commit">，判据 = 取出来与 HEAD 比对。
    #   ⇒ 直接回答「这份产物是哪个 commit 构建的」，不受构建不确定性影响。
    c8_ok = None
    if not args.skip_remote and remote_head:
        ssh = _ssh_base(args.host, args.key)
        html = f"{args.remote}/frontend/dist/index.html"
        # 用 sed 而不是 grep -P（部分环境没有 -P）
        rc, out = _run(
            ssh + [f"sed -n 's/.*build-commit\" content=\"\\([^\"]*\\)\".*/\\1/p' {html}"],
            timeout=45,
        )
        deployed = out.strip().splitlines()[0].strip() if rc == 0 and out.strip() else None

        if deployed and deployed != "unknown":
            expect = (local_head or "")[:7]
            same = deployed.startswith(expect) or expect.startswith(deployed)
            c8_ok = same
            record("产物标注的 commit（生产 dist）", deployed, same,
                   "" if same else f"期望 HEAD 前缀 {expect}")
            if not same:
                res["notes"].append(
                    f"生产产物标注 {deployed}，HEAD 是 {expect} ⇒ "
                    "线上跑的不是当前源码的产物（需重新构建并部署）")
        elif deployed == "unknown":
            record("产物标注的 commit", "unknown", False,
                   "构建时取不到 git 信息")
            res["notes"].append("产物标注 unknown ⇒ C8 无法证实")
        else:
            record("产物标注的 commit", None, None,
                   "dist/index.html 里没有 build-commit meta（这是加注入之前的旧产物）")
            res["notes"].append(
                "旧产物缺 build-commit 标记 ⇒ C8 未判定（不是不一致，是没法判）；"
                "重新构建部署一次即可支持")

    # 本地 dist 只作参考，**不参与 C8 判定**（避免上面说的循环论证）
    local_dist = os.path.join(REPO, "frontend", "dist", "index.html")
    local_dist_md5 = _md5(local_dist)
    if local_dist_md5:
        res["checks"]["本地 dist（仅参考，不参与判定）"] = {
            "value": local_dist_md5[:16], "ok": None,
            "detail": "本地产物仅用于本地预览；C8 只认产物里标注的 build-commit",
        }

    res["checks"]["C8 生产产物一致"] = {
        "value": c8_ok,
        "ok": c8_ok,
        "detail": "" if c8_ok else ("未查生产（--skip-remote）" if c8_ok is None else "未证实（见上面各项）"),
    }
    if c8_ok is not True:
        res["ok"] = False

    res["c7_short"] = (local_head or "?")[:7]
    res["c8_local_dist_md5"] = local_dist_md5

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res["ok"] else 1

    # ── 人类可读输出 ──
    print("=" * 72)
    print("部署一致性校验（CLAIMS C7 / C8 的可复现判据）")
    print("=" * 72)
    for k, v in res["checks"].items():
        mark = "✅" if v["ok"] is True else ("❌" if v["ok"] is False else "·")
        val = v["value"]
        if isinstance(val, str) and len(val) > 46:
            val = val[:46] + "…"
        print(f"  {mark} {k:<34} {val}")
        if v["detail"]:
            print(f"       {v['detail']}")
    if res["notes"]:
        print("\n  ⚠️ 注意：")
        for n in res["notes"]:
            print(f"    · {n}")
    print("\n" + "=" * 72)
    if res["ok"]:
        print("✅ C7 与 C8 均成立")
    else:
        print("❌ 未成立 —— 见上面 ❌ 项与注意")
    print("=" * 72)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
