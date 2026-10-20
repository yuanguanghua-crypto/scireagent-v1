# -*- coding: utf-8 -*-
"""比对 FULL_SITE 台账路由 vs router 实际路由，找出不存在的路由。"""
import io
import re

ROOT = "."
LEDGER = "docs/e2e/COVERAGE_LEDGER.md"
ROUTER = "frontend/src/router/index.js"

rt = io.open(ROUTER, encoding="utf-8").read()
real = set(re.findall(r"path:\s*'([^']+)'", rt))

led = io.open(LEDGER, encoding="utf-8").read()
routes = []
for line in led.splitlines():
    if not line.startswith("| ") or "`" not in line:
        continue
    c = [x.strip() for x in line.strip("|").split("|")]
    if len(c) < 11 or not re.match(r"^\d+$", c[0]):
        continue
    routes.append(c[1].strip("`"))

print("台账路由 %d 个，router 实际 %d 条" % (len(routes), len(real)))
print()
missing = [r for r in routes if r not in real]
print("❌ 台账里有、router 里没有的：%d 个" % len(missing))
for m in missing:
    # 尝试猜真实路由：/admin/ -> /ops/
    guess = m.replace("/admin/", "/ops/")
    hint = ""
    if guess in real:
        hint = "  → 实际应是 %s" % guess
    elif m.rstrip("/") in real:
        hint = "  → 实际是 %s（无尾斜杠）" % m.rstrip("/")
    print("   %-30s%s" % (m, hint))

print()
extra = [r for r in sorted(real) if r not in routes and not r.startswith("/:") and r.count("/") >= 1]
print("ℹ️ router 里有、台账没列的：%d 条（前 15）" % len(extra))
for e in extra[:15]:
    print("   %s" % e)
