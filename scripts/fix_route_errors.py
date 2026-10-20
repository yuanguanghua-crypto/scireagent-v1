# -*- coding: utf-8 -*-
"""校正 FULL_SITE_E2E_PLAN.md §2.2 的 8 处路由错误（以 router/index.js 为准）。

依据（逐条核过）：
- router 里没有 /admin/*，实际全部是 /ops/*（平铺路由，非嵌套）
  174 /ops/orders、180 /ops/orders/:id、226 /ops/po/review、232 /ops/po/shipments
  238 /ops/po/invoicing、244 /ops/po/ar、250 /ops/po/organizations
- /references 实际是 /workspace/references（/workspace 的 children）
- 台账漏列 /workspace/verified（children 里存在）

只改路由字符串，不动维度/优先级/其他内容。
"""
import io
import re

P = "docs/e2e/FULL_SITE_E2E_PLAN.md"
s = io.open(P, encoding="utf-8").read()
orig = s

# (旧, 新) —— 按更长的先替换，避免前缀误伤
REPL = [
    ("/admin/po/organizations", "/ops/po/organizations"),
    ("/admin/po/shipments", "/ops/po/shipments"),
    ("/admin/po/invoicing", "/ops/po/invoicing"),
    ("/admin/po/review", "/ops/po/review"),
    ("/admin/po/ar", "/ops/po/ar"),
    ("/admin/orders", "/ops/orders"),
    ("`/references`", "`/workspace/references`"),
]

m = re.search(r"(### 2\.2 .*?\n)(.*?)(\n### 2\.3 )", s, re.S)
if not m:
    raise SystemExit("MISS: 找不到 §2.2")
head, body, tail = m.group(1), m.group(2), m.group(3)

n = 0
for old, new in REPL:
    if old in body:
        cnt = body.count(old)
        body = body.replace(old, new)
        n += cnt
        print("  替换 %-26s -> %-26s ×%d" % (old, new, cnt))

new_s = s[: m.start()] + head + body + tail + s[m.end():]

# 在 §2.2 的修复说明里补一句
note_anchor = "> 依据：§2.0 把 B 定义为全站维度"
if note_anchor in new_s and "2026-10-20 路由校正" not in new_s:
    extra = ("> **2026-10-20 路由校正**：以 `router/index.js` 为准修正 8 处 ——\n"
             "> 7 个 `/admin/*` 实际是 `/ops/*`（router 里没有 /admin 前缀），\n"
             "> `/references` 实际是 `/workspace/references`（`/workspace` 的 children）。\n"
             "> 台账漏列 `/workspace/verified`（children 里存在），已记入差异清单。\n"
             "> ⚠️ 教训：`/workspace/*` 是 **children 嵌套路由**，比对路由时必须拼父路径，\n"
             "> 否则会把存在的路由误判为不存在。\n")
    new_s = new_s.replace(note_anchor, extra + note_anchor, 1)

io.open(P, "w", encoding="utf-8").write(new_s)
print("OK 共替换 %d 处，文件 %d -> %d 行" % (n, len(orig.splitlines()), len(new_s.splitlines())))
