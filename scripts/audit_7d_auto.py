# -*- coding: utf-8 -*-
"""全站 7 维覆盖自动审计 —— 把 44 页 × 7 维的 263 格一次算清。

## 能自动判什么、不能判什么（必须先说清）

| 维 | 能否自动 | 依据 | 局限 |
|---|---|---|---|
| P 权限 | ✅ | `permission-matrix.spec.cjs` 的三个页面数组 | 只证明"该页在权限矩阵里"，不证明 4 角色全覆盖 |
| S 状态 | ✅ | `state-matrix.spec.cjs` + `state-branches-*.spec.cjs` 的 `path:` 注册表 | 后者按页面穷举状态分支 |
| R 响应式 | ✅ | `responsive.spec.cjs` 的 path 数组 | 只证明"加载不崩"，不证明布局真的对 |
| V 视觉 | ✅ | `visual-tokens.spec.cjs` 的 path 数组 | 只证明"断言过令牌"，不证明全站一致 |
| A 可访问 | ✅ | `a11y.spec.cjs` 的 path 数组 | 只证明"扫过 axe"，不证明零 violation |
| B 浏览器 | ✅ | `cross-browser-smoke.spec.cjs` 页面清单 **且** 有 firefox 实测基线 | 2 引擎（Chromium+Firefox）；WebKit 见基线文档 |
| **I 交互** | ❌ | 需逐页比对 FULL_SITE 要求的交互 vs spec 断言 | **必须人工** |

⇒ 本脚本填 P/S/R/V/A/B 六维，**I 维留空 `☐` 交人工**。
⇒ 输出是「**让战场可见**」，不是「证明测好了」。
"""
import io
import json
import os
import re
import glob

E2E = "frontend/e2e"
LEDGER = "docs/e2e/COVERAGE_LEDGER.md"
OUT = "docs/e2e/COVERAGE_AUDIT.md"

# ── 1. 从台账读 44 页 ──
led = io.open(LEDGER, encoding="utf-8").read()
pages = []
for line in led.splitlines():
    if not line.startswith("| ") or "`" not in line:
        continue
    cells = [c.strip() for c in line.strip("|").split("|")]
    if len(cells) < 11:
        continue
    if not re.match(r"^\d+$", cells[0]):
        continue
    route = cells[1].strip("`")
    pages.append({"route": route, "page": cells[2], "prio": cells[10],
                  "dims": cells[3:10]})   # I P S R V A B 的规划：☐ 或 —

# ── 2. 读各矩阵 spec 的页面清单 ──
def paths_in(spec):
    p = os.path.join(E2E, spec)
    if not os.path.isfile(p):
        return set()
    s = io.open(p, encoding="utf-8", errors="replace").read()
    return set(re.findall(r"path:\s*'([^']+)'", s))


R_PAGES = paths_in("responsive.spec.cjs")
A_PAGES = paths_in("a11y.spec.cjs")
V_PAGES = paths_in("visual-tokens.spec.cjs")

# P 维：permission-matrix 的三个 REQUIRES_* 数组 + 「guest 已登录重定向」段
pm = os.path.join(E2E, "permission-matrix.spec.cjs")
P_PAGES = set()
if os.path.isfile(pm):
    s = io.open(pm, encoding="utf-8", errors="replace").read()
    for arr in ("REQUIRES_AUTH", "REQUIRES_ADMIN_STANDALONE", "REQUIRES_ADMIN_WORKSPACE",
                "REQUIRES_SUPERUSER"):
        m = re.search(arr + r"\s*=\s*\[(.*?)\]", s, re.S)
        if m:
            P_PAGES.update(re.findall(r"'([^']+)'", m.group(1)))
    # ★ 修正（2026-10-20）：初版漏了「guest 页已登录重定向」段
    #   那段测的是「已登录访问 /login 应跳走」，属于 P 维，但页面不在 REQUIRES_* 数组里
    for m in re.finditer(r"已登录访问\s+(/[A-Za-z0-9_/-]+)", s):
        P_PAGES.add(m.group(1))

# S 维：状态分支测试覆盖的页面。
# 数据源有两个（2026-10-21 补）：
#   ① state-matrix.spec.cjs —— **按 PO 的 8/9 个状态**组织，全部落在 /ops/orders/:id 一页；
#   ② state-branches-*.spec.cjs —— **按页面**组织的状态分支穷举（commerce / po 两个域），
#      每页在 `PAGES` 注册表里写 `path: '/xxx'` 字面量（同时作为 goto 依据）。
# 初版只读 ①，于是「按页面」的状态测试写了也不算数 ⇒ 14 页恒判 ✗（这正是当时的缺口根因）。
S_SPECS = ["state-matrix.spec.cjs",
           "state-branches-commerce.spec.cjs",
           "state-branches-po.spec.cjs"]
S_PAGES = set()
for _spec in S_SPECS:
    _p = os.path.join(E2E, _spec)
    if os.path.isfile(_p):
        _s = io.open(_p, encoding="utf-8", errors="replace").read()
        S_PAGES.update(re.findall(r"path:\s*'([^']+)'", _s))

# B 维：跨浏览器冒烟。
#
# ★ 2026-10-21 重写判据。旧判据是「`package.json` 里有没有不带 `--project=` 的
#   `test:e2e*` script」—— 那是**纸面判据**（写个 script 就能判绿，跑没跑过完全不管），
#   而且当时它恒为假，把 44 格全判 ✗ 并写进文档说"基础设施阻塞、不可补"。
#   实测该结论是**误判**：真因是本机系统代理把 `/@vite/client` 接走返回 404（见
#   `playwright.config.cjs` firefox project 的注释），关掉代理后 Firefox 45 例全绿。
#
# 新判据 = 两件事同时成立（缺一不可）：
#   ① 该页出现在 `cross-browser-smoke.spec.cjs` 的页面清单里（**真被覆盖**）；
#   ② `docs/e2e/CROSS_BROWSER_BASELINE.md` 存在，且记录了 **firefox 的 passed>0**
#      （**真跑过**，不是只有 spec 文件）。
xb = os.path.join(E2E, "cross-browser-smoke.spec.cjs")
B_PAGES = set()
if os.path.isfile(xb):
    s = io.open(xb, encoding="utf-8", errors="replace").read()
    B_PAGES.update(re.findall(r"path:\s*'([^']+)'", s))

B_BASELINE_DOC = "docs/e2e/CROSS_BROWSER_BASELINE.md"
b_firefox_passed = 0
if os.path.isfile(B_BASELINE_DOC):
    _bt = io.open(B_BASELINE_DOC, encoding="utf-8").read()
    # 基线表里固定写一行：| firefox | <passed> | <failed> | ... |
    _m = re.search(r"\|\s*\**firefox\**\s*\|\s*\**(\d+)\**\s*\|", _bt, re.I)
    if _m:
        b_firefox_passed = int(_m.group(1))
b_ok = bool(B_PAGES) and b_firefox_passed > 0


# I 维：读 judge_interaction.py 的判定（不再返回 ☐）
VERDICT = "docs/e2e/INTERACTION_VERDICT.md"
I_MARKS = {}
if os.path.isfile(VERDICT):
    vt = io.open(VERDICT, encoding="utf-8").read()
    for m in re.finditer(r"^## `([^`]+)` .*?\*\*(✓|✗)\*\*", vt, re.M):
        I_MARKS[m.group(1)] = m.group(2)

def has(route_set, route):
    """宽松匹配：台账写 /products/:id，spec 里写 /products/66 也算覆盖"""
    if route in route_set:
        return True
    base = re.sub(r"/:[A-Za-z_]+.*$", "", route)
    if base != route:
        return any(p.startswith(base + "/") or p == base for p in route_set)
    return False

# ── 3. 判定 ──
def verdict(route, dim, planned):
    if planned.strip() in ("—", "-", ""):
        return "—", "不适用"
    if dim == "I":
        v = I_MARKS.get(route)
        if v in ("✓", "✗"):
            return v, "I 维判定（见 INTERACTION_VERDICT）"
        return "☐", "需人工"
    if dim == "P":
        return ("✓", "在 permission-matrix") if has(P_PAGES, route) else ("✗", "不在矩阵")
    if dim == "S":
        return ("✓", "在 state-matrix") if has(S_PAGES, route) else ("✗", "无状态测试")
    if dim == "R":
        return ("✓", "在 responsive") if has(R_PAGES, route) else ("✗", "不在 responsive")
    if dim == "V":
        return ("✓", "在 visual-tokens") if has(V_PAGES, route) else ("✗", "不在 visual-tokens")
    if dim == "A":
        return ("✓", "在 a11y") if has(A_PAGES, route) else ("✗", "不在 a11y")
    if dim == "B":
        if has(B_PAGES, route) and b_ok:
            return "✓", "跨浏览器冒烟（chromium+firefox 实测）"
        if has(B_PAGES, route):
            return "✗", "有 spec 但无实测基线"
        return "✗", "不在 cross-browser-smoke"
    return "☐", ""

# ── 4. 输出 ──
DIMS = ["I", "P", "S", "R", "V", "A", "B"]
L = []
L.append("# 全站 7 维覆盖审计（自动 · V1）")
L.append("")
L.append("> 由 `scripts/audit_7d_auto.py` 生成。**跑一次就算清 263 格**，不用逐页人工。")
L.append("> ⚠️ 自动判定 = 「该页在该矩阵 spec 的清单里」，**不证明断言充分**。")
L.append("> **I 维（交互）无法自动判**，留 `☐` 交人工 —— 那才是真正要一页页看的。")
L.append("")
L.append("## 数据源")
L.append("")
L.append("| 维 | 依据文件 | 覆盖页面数 |")
L.append("|---|---|---|")
L.append("| P 权限 | `permission-matrix.spec.cjs`（3 数组） | **%d** |" % len(P_PAGES))
L.append("| S 状态 | `state-matrix` + `state-branches-*` | %d |" % len(S_PAGES))
L.append("| R 响应式 | `responsive.spec.cjs` | **%d** |" % len(R_PAGES))
L.append("| V 视觉 | `visual-tokens.spec.cjs` | %d |" % len(V_PAGES))
L.append("| A 可访问 | `a11y.spec.cjs` | %d |" % len(A_PAGES))
L.append("| B 浏览器 | `cross-browser-smoke.spec.cjs`（firefox 实测 %d passed） | %d |" % (b_firefox_passed, len(B_PAGES)))
L.append("| I 交互 | — | **不可自动判** |")
L.append("")

stat = {d: {"✓": 0, "✗": 0, "☐": 0, "—": 0} for d in DIMS}
L.append("## 逐页审计")
L.append("")
L.append("| # | 路由 | 页面 | 优先级 | I | P | S | R | V | A | B | 已覆盖 |")
L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
for i, p in enumerate(pages, 1):
    row, done = [], 0
    for j, d in enumerate(DIMS):
        planned = p["dims"][j] if j < len(p["dims"]) else ""
        v, _ = verdict(p["route"], d, planned)
        row.append(v)
        stat[d][v] = stat[d].get(v, 0) + 1
        if v == "✓":
            done += 1
    L.append("| %d | `%s` | %s | %s | %s | %s | %s | %s | %s | %s | %s | **%d/7** |"
             % (i, p["route"], p["page"], p["prio"] or "—", *row, done))

L.append("")
L.append("## 汇总（按维）")
L.append("")
L.append("| 维 | ✓ 覆盖 | ✗ 缺 | ☐ 待人工 | 覆盖率 |")
L.append("|---|---|---|---|---|")
for d in DIMS:
    s = stat[d]
    tot = s["✓"] + s["✗"]
    pct = ("%.0f%%" % (s["✓"] * 100.0 / tot)) if tot else "—"
    L.append("| %s | %d | %d | %d | **%s** |" % (d, s["✓"], s["✗"], s["☐"], pct))

allv = sum(stat[d]["✓"] for d in DIMS)
allx = sum(stat[d]["✗"] for d in DIMS)
allq = sum(stat[d]["☐"] for d in DIMS)
L.append("")
L.append("**总计**：✓ %d 格 / ✗ %d 格 / 待人工 %d 格（共 %d 格）"
         % (allv, allx, allq, allv + allx + allq))
L.append("")
L.append("## 怎么读这份审计")
L.append("")
L.append("1. **先看汇总表的覆盖率** —— 哪一维最空，先补哪一维")
L.append("2. **再看逐页表的 `已覆盖 n/7`** —— 从 0/7 的页面开始")
L.append("3. **I 维（☐）必须人工判** —— 打开 FULL_SITE §2.2 看该页要求哪些交互，逐个 grep spec")
L.append("")

io.open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("OK 页面=%d" % len(pages))
for d in DIMS:
    s = stat[d]
    print("  %s: ✓%-3d ✗%-3d ☐%-3d" % (d, s["✓"], s["✗"], s["☐"]))
print("  总计: ✓%d / ✗%d / ☐%d" % (allv, allx, allq))
