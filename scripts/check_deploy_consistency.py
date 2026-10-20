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


# 前端「构建输入」—— 只有这些变了，产物才必须重建
BUILD_INPUTS = (
    "frontend/src/", "frontend/public/", "frontend/index.html",
    "frontend/vite.config.js", "frontend/package.json",
    "frontend/package-lock.json",
)


def _c8_verdict(deployed: str | None, local_head: str | None) -> tuple[bool | None, str]:
    """C8 判定核心：产物里标注的 commit 与 HEAD 是否"对得上"。

    返回 (结果, 说明)：
      True  —— 产物确实是当前 HEAD 的前端源码构建的
      False —— 不是（或无法确认）
      None  —— 没法判（旧产物没有 build-commit 标记）

    ★ 抽成独立函数是为了让 `--self-check` 能测**真实逻辑**，
      而不是复制一份判定规则来测副本（那样测的是副本，不是这条代码）。
    """
    if not deployed:
        return None, "产物里没有 build-commit meta（这是加注入之前的旧产物）"
    if deployed == "unknown":
        return False, "构建时取不到 git 信息（可能在没有 .git 的环境里打包）"

    expect = (local_head or "")[:7]
    if deployed.startswith(expect) or expect.startswith(deployed):
        return True, ""

    # meta ≠ HEAD 时不能直接判红：可能只改了文档/脚本，前端源码没动。
    rc, out = _run(["git", "diff", "--name-only", f"{deployed}..HEAD"])
    if rc != 0:
        return False, f"期望 HEAD 前缀 {expect}；且本地没有 {deployed} 这个提交，无法判断差异范围"

    touched = [ln.strip() for ln in out.splitlines()
               if ln.strip().startswith(BUILD_INPUTS)]
    if touched:
        return False, (f"期望 HEAD 前缀 {expect}；且之后改过 {len(touched)} 个前端构建输入"
                       f"（如 {touched[0]}）⇒ 线上产物落后于源码")
    return True, f"产物 {deployed}，HEAD 是 {expect}，但两者之间未改动任何前端构建输入"


def _self_check(local_head: str | None) -> int:
    """**验判据本身**：故意喂错误输入，断言它必须判红。

    这是 mutation_check.py 对测试做的事，用在部署校验上：
    一个"永远绿"的判据比没有判据更危险 —— 它给人安全感。
    今天的 C8 假绿（读宿主机而非容器）就是"判据错了但没人知道"。

    返回 0 = 自检通过；1 = 判据失效
    """
    head7 = (local_head or "")[:7]
    cases = [
        # (输入 deployed, 期望结果, 说明)
        ("0000000", False, "明显错误的 commit（本地不存在）"),
        ("deadbee", False, "另一个不存在的 commit"),
        (None, None, "产物缺 meta（旧产物）"),
        ("unknown", False, "构建时取不到 git"),
        (head7, True, "等于 HEAD —— 正确时必须放行，不能误报"),
    ]

    print("=" * 72)
    print("判据自检（验 C8 判据本身，不查生产）")
    print("=" * 72)
    bad = 0
    for deployed, want, desc in cases:
        got, detail = _c8_verdict(deployed, local_head)
        ok = (got == want)
        mark = "✓" if ok else "✗"
        shown = "(None)" if deployed is None else deployed
        print(f"  {mark} {desc:<34} 输入={shown:<10} 期望={want} 实得={got}")
        if not ok:
            bad += 1
            print(f"      说明: {detail}")
    print("=" * 72)
    if bad:
        print(f"❌ 自检失败：{bad} 个用例不符合预期 ⇒ C8 判据已失效，"
              f"它给出的绿不可信")
        return 1
    print(f"✅ 自检通过：{len(cases)} 个用例全部符合预期"
          f"（错必红 / 对必绿）")
    return 0


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
    ap.add_argument("--self-check", action="store_true",
                    help="★ 验判据本身：喂错误输入，断言 C8 必须判红（不查生产）")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args(argv)

    # ★ 先验判据，再验生产 —— 判据坏了的话，后面查什么都不可信
    if args.self_check:
        rc0, out0 = _run(["git", "rev-parse", "HEAD"])
        head = out0.strip() if rc0 == 0 else None
        return _self_check(head)

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
        # ★★★ 必须读**容器内**的文件，不能读宿主机路径：
        #   Docker bind mount 在容器启动时锁定 **inode**。
        #   实测 2026-10-20：容器挂载源写着 `frontend/dist`，但实际 inode=524269
        #   属于 `dist_prev_20261020` —— 因为部署时用了 `mv dist -> dist_prev && mv new -> dist`，
        #   `dist` 这个**路径名**指向了新 inode，而容器还挂在旧 inode 上。
        #   ⇒ 只查宿主机 `dist/index.html` 会**假绿**（读到新产物，但服务的是旧产物）。
        html = "/usr/share/nginx/html/index.html"
        rc, out = _run(
            ssh + [f"docker exec scireagent-nginx-1 sed -n "
                   f"'s/.*build-commit\" content=\"\\([^\"]*\\)\".*/\\1/p' {html}"],
            timeout=60,
        )
        deployed = out.strip().splitlines()[0].strip() if rc == 0 and out.strip() else None

        # ★ 新增（2026-10-20）：宿主机 vs 容器 —— inode 断开的直接检测器。
        #   今天的事故就是这两个值不同：宿主机 `dist` 有新产物，容器服务旧的。
        #   这条检查能当场发现"部署到 dist 但容器看不到"。
        rc_h, out_h = _run(
            ssh + [f"sed -n 's/.*build-commit\" content=\"\\([^\"]*\\)\".*/\\1/p' "
                   f"{args.remote}/frontend/dist/index.html"],
            timeout=45,
        )
        host_meta = (out_h.strip().splitlines()[0].strip()
                     if rc_h == 0 and out_h.strip() else None)
        if host_meta and deployed and host_meta != deployed:
            record("宿主机 vs 容器（inode 是否断开）",
                   f"宿主机 {host_meta} ≠ 容器 {deployed}", False,
                   "两者不一致 ⇒ dist 的 inode 与容器挂载点不同，部署不会生效")
            res["notes"].append(
                "★ 宿主机 dist 与容器内文件不一致 —— 改用 rsync 写入（不要 mv 换目录），"
                "或用 scripts/deploy_frontend.sh")
        elif host_meta:
            record("宿主机 vs 容器（inode 是否断开）", "一致", True)

        # 判定：真实逻辑在模块级 _c8_verdict 里，--self-check 测的也是它
        verdict, why = _c8_verdict(deployed, local_head)
        c8_ok = verdict
        if verdict is True:
            record("产物标注的 commit（容器内）",
                   (f"{deployed}（HEAD={(local_head or '')[:7]}）" if why else deployed),
                   True)
            if why:
                res["notes"].append(why + " ⇒ 产物仍对应 HEAD 的前端源码")
        elif verdict is False:
            record("产物标注的 commit（容器内）", deployed, False, why)
            res["notes"].append(why)
        else:
            record("产物标注的 commit（容器内）", deployed, None, why)
            res["notes"].append(why + "；重新构建部署一次即可支持")

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
