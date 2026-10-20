# -*- coding: utf-8 -*-
"""从 PAGE_MAP.md 生成三个 spec 的新 PUBLIC / STAFF 数组文本。

只输出文本，由人贴进 spec —— 不直接改文件（避免生成错代码破坏绿测）。
"""
import io
import re

MAP = "docs/e2e/PAGE_MAP.md"
pages = []
for line in io.open(MAP, encoding="utf-8").read().splitlines():
    if not line.startswith("| ") or "✅" not in line:
        continue
    c = [x.strip() for x in line.strip("|").split("|")]
    if len(c) < 7:
        continue
    route, comp, cls, grp, prio = c[1].strip("`"), c[2], c[3], c[4], c[5]
    if not cls or cls in ("?", ""):
        continue
    pages.append({"route": route, "cls": cls, "grp": grp, "prio": prio, "comp": comp})

def jsname(route, comp):
    # 用组件名去掉 .vue 和目录层级，保证唯一
    base = comp.split("/")[-1].replace(".vue", "")
    if route == "/":
        return "Home"
    return base

def emit(grp_list, indent="  "):
    out = []
    for p in grp_list:
        out.append("%s{ name: '%s', path: '%s', sel: '.%s' },"
                   % (indent, jsname(p["route"], p["comp"]), p["route"], p["cls"]))
    return "\n".join(out)

PUB = [p for p in pages if p["grp"] == "PUBLIC"]
AUTH = [p for p in pages if p["grp"] == "AUTH"]
ADM = [p for p in pages if p["grp"] == "ADMIN"]

print("=" * 70)
print("PUBLIC（%d 页）" % len(PUB))
print("=" * 70)
print(emit(PUB))
print()
print("=" * 70)
print("STAFF / AUTH（%d 页）" % len(AUTH))
print("=" * 70)
print(emit(AUTH))
print()
print("=" * 70)
print("ADMIN（%d 页）—— 需要 loginAsAdmin，现有 spec 可能没这个 helper" % len(ADM))
print("=" * 70)
print(emit(ADM))
print()
print("合计可加: %d 页（PUBLIC %d + AUTH %d + ADMIN %d）" % (len(pages), len(PUB), len(AUTH), len(ADM)))
print()
print("⚠️ 检查有无重名（同名会导致 test 标题重复）：")
from collections import Counter
for g, lst in (("PUBLIC", PUB), ("AUTH", AUTH), ("ADMIN", ADM)):
    names = [jsname(p["route"], p["comp"]) for p in lst]
    dup = [n for n, c in Counter(names).items() if c > 1]
    print("  %s: %s" % (g, ("重复 " + str(dup)) if dup else "无重复"))
