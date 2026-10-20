# -*- coding: utf-8 -*-
"""解析 router/index.js（含 children 嵌套），建立 完整路由 -> 组件 映射。"""
import io
import json
import re

ROUTER = "frontend/src/router/index.js"
src = io.open(ROUTER, encoding="utf-8").read()

# 按 `path: '...'` 分块，每块向后看 400 字符找 component
mapping = {}
# 先找顶层路由
for m in re.finditer(r"path:\s*'([^']*)'\s*,", src):
    path = m.group(1)
    tail = src[m.end(): m.end() + 500]
    cm = re.search(r"component:\s*\(\)\s*=>\s*import\('@/views/([^']+)'\)", tail)
    if cm:
        mapping[path] = cm.group(1)
    else:
        cm2 = re.search(r"component:\s*([A-Za-z_][A-Za-z0-9_]*)", tail)
        if cm2:
            mapping[path] = "VAR:" + cm2.group(1)

# 处理 /workspace 的 children：找到 children 块
wm = re.search(r"path:\s*'/workspace'.*?children:\s*\[(.*?)\n\s*\],", src, re.S)
child_map = {}
if wm:
    block = wm.group(1)
    for cm in re.finditer(r"path:\s*'([^']*)'.*?component:\s*\(\)\s*=>\s*import\('@/views/([^']+)'\)", block, re.S):
        p, comp = cm.group(1), cm.group(2)
        full = "/workspace" + ("/" + p if p else "")
        child_map[full] = comp
        mapping[full] = comp

io.open("docs/e2e/ROUTE_MAP.json", "w", encoding="utf-8").write(
    json.dumps({"flat": mapping, "workspace_children": child_map}, ensure_ascii=False, indent=1))

print("顶层/平铺路由: %d 条" % len(mapping) if False else "解析完成")
print("  /workspace children: %d 条" % len(child_map))
for k, v in sorted(child_map.items()):
    print("    %-34s %s" % (k, v))
