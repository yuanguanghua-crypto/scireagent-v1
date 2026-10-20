# -*- coding: utf-8 -*-
"""算出 R/V/A 维「缺且可加」的页面（排除 :id 服务端页）。

来源：
- audit_7d_auto.py 的输出 COVERAGE_AUDIT.md（每页每维 ✓/✗）
- PAGE_MAP.md（每页根 class + 是否可加 ✅/❌需fixture）
"""
import io
import re

AUDIT = "docs/e2e/COVERAGE_AUDIT.md"
MAP = "docs/e2e/PAGE_MAP.md"

# PAGE_MAP: route -> (cls, addable)
pmap = {}
for line in io.open(MAP, encoding="utf-8").read().splitlines():
    if not line.startswith("| ") or "`/" not in line:
        continue
    c = [x.strip() for x in line.strip("|").split("|")]
    if len(c) < 7:
        continue
    route = c[1].strip("`")
    cls = c[3]
    addable = "✅" in c[6]
    if cls and cls != "?":
        pmap[route] = (cls, addable)

# AUDIT: route -> {dim: mark}
rows = []
for line in io.open(AUDIT, encoding="utf-8").read().splitlines():
    if not line.startswith("| ") or "`/" not in line:
        continue
    c = [x.strip() for x in line.strip("|").split("|")]
    if len(c) < 12 or not re.match(r"^\d+$", c[0]):
        continue
    route = c[1].strip("`")
    marks = c[4:11]      # I P S R V A B
    rows.append({"route": route, "page": c[2], "marks": dict(zip(["I","P","S","R","V","A","B"], marks))})

for dim in ("R", "V", "A"):
    todo = []
    for r in rows:
        if r["marks"].get(dim) != "✗":
            continue
        cls, addable = pmap.get(r["route"], (None, False))
        if addable:
            todo.append((r["route"], cls, r["page"]))
    print("=" * 64)
    print("%s 维：缺且可加 = %d 页" % (dim, len(todo)))
    print("=" * 64)
    for route, cls, page in todo:
        print("  { name: '%s', path: '%s', sel: '.%s' }," %
              (re.sub(r"[^A-Za-z]", "", page.split("/")[0]) or "Page", route, cls))
    print()
