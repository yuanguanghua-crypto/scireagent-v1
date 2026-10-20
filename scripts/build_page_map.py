# -*- coding: utf-8 -*-
"""为 44 页生成「路由 / 组件 / 根class / 权限组」清单，供批量扩容 R/A/V 用。

只输出清单，**不自动改 spec** —— 生成结果要人 review 后再落。
理由：自动写测试代码出错会破坏现有绿测，代价高于手工。

数据来源：
- 台账 `COVERAGE_LEDGER.md`（44 页 + 优先级）
- `frontend/src/router/index.js`（route -> component）
- `frontend/e2e/permission-matrix.spec.cjs`（三个 REQUIRES_* 数组 -> 权限组）
- 各 Vue 组件的根 class
"""
import io
import os
import re

LEDGER = "docs/e2e/COVERAGE_LEDGER.md"
ROUTER = "frontend/src/router/index.js"
E2E = "frontend/e2e"
VIEWS = "frontend/src/views"
OUT = "docs/e2e/PAGE_MAP.md"

# ── 1. 台账 44 页 ──
pages = []
for line in io.open(LEDGER, encoding="utf-8").read().splitlines():
    if not line.startswith("| ") or "`" not in line:
        continue
    c = [x.strip() for x in line.strip("|").split("|")]
    if len(c) < 11 or not re.match(r"^\d+$", c[0]):
        continue
    pages.append({"route": c[1].strip("`"), "page": c[2], "prio": c[10]})

# ── 2. router: route -> component 文件名 ──
rt = io.open(ROUTER, encoding="utf-8").read()
route2comp = {}
for m in re.finditer(r"path:\s*'([^']+)'[^}]*?component:\s*\(\)\s*=>\s*import\('@/views/([^']+)'\)", rt, re.S):
    route2comp[m.group(1)] = m.group(2)
for m in re.finditer(r"path:\s*'([^']+)'[^}]*?component:\s*([A-Za-z_][A-Za-z0-9_]*)", rt, re.S):
    route2comp.setdefault(m.group(1), None)

# ── 3. 权限组 ──
pm = io.open(os.path.join(E2E, "permission-matrix.spec.cjs"), encoding="utf-8").read()
def arr(name):
    m = re.search(name + r"\s*=\s*\[(.*?)\]", pm, re.S)
    return set(re.findall(r"'([^']+)'", m.group(1))) if m else set()

AUTH = arr("REQUIRES_AUTH")
ADMIN_S = arr("REQUIRES_ADMIN_STANDALONE")
ADMIN_W = arr("REQUIRES_ADMIN_WORKSPACE")

def group_of(route):
    if route in ADMIN_S or route in ADMIN_W:
        return "ADMIN"
    if route in AUTH:
        return "AUTH"
    if re.match(r"^/(ops|admin)/", route):
        return "ADMIN"
    if re.match(r"^/(workspace|po)/", route):
        return "AUTH"
    return "PUBLIC"

# ── 4. 组件根 class ──
def root_class(comp):
    if not comp:
        return None
    p = os.path.join(VIEWS, comp)
    if not os.path.isfile(p):
        return None
    s = io.open(p, encoding="utf-8", errors="replace").read()
    m = re.search(r'<div[^>]*class="([a-z][a-z0-9-]*)', s)
    return m.group(1) if m else None

# ── 5. 汇总 ──
L = ["# 页面映射清单（供批量扩容 R/A/V）", "",
     "| # | 路由 | 组件 | 根class | 组 | 优先级 | 可直接加? |", "|---|---|---|---|---|---|---|"]
addable = dynamic = noroute = 0
for i, p in enumerate(pages, 1):
    r = p["route"]
    comp = route2comp.get(r)
    cls = root_class(comp) if comp else None
    dyn = ":" in r
    if dyn:
        addable_flag, dynamic = "❌ 需 fixture", dynamic + 1
    elif not cls:
        addable_flag, noroute = "⚠️ 无根class", noroute + 1
    else:
        addable_flag, addable = "✅", addable + 1
    L.append("| %d | `%s` | %s | %s | %s | %s | %s |"
             % (i, r, comp or "?", cls or "?", group_of(r), p["prio"] or "—", addable_flag))

L += ["", "## 统计", "",
      "| 项 | 数 |", "|---|---|",
      "| 可直接加 ✅ | **%d** |" % addable,
      "| 需 fixture（:id）❌ | %d |" % dynamic,
      "| 无根 class ⚠️ | %d |" % noroute,
      "", "## 分组分布", ""]
for g in ("PUBLIC", "AUTH", "ADMIN"):
    n = sum(1 for p in pages if group_of(p["route"]) == g and ":" not in p["route"])
    L.append("- **%s**：%d 页可加" % (g, n))

io.open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("可直接加=%d  需fixture=%d  无class=%d" % (addable, dynamic, noroute))
