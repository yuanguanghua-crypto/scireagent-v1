# -*- coding: utf-8 -*-
"""I 维（交互）半自动审计：把 FULL_SITE 的「要测哪些交互」拆成原子项，逐个在 spec 里找。

## 为什么只能"半"自动
FULL_SITE 的 I 列是自由文本，如：
  `/`        → 搜索/导航/分类 pills/CTA
  `/products`→ 分类 pills / Tab 切换 / Add to Cart / 数量± / SKU 行 / 文档链接

拆成原子项是可靠的（按 / 和 + 分），但"某个交互项有没有被测"**不能只看关键词命中**：
  - spec 里出现 "pills" 可能是注释、可能是 `expect` → 也可能只是点了一下没断言
⇒ 脚本只给「命中线索」，**判定必须人看**。

## 输出
每页一个块：交互项 | 命中 spec 数 | 命中的文件（前 3）
"""
import io
import os
import re
import glob

PLAN = "docs/e2e/FULL_SITE_E2E_PLAN.md"
E2E = "frontend/e2e"
OUT = "docs/e2e/INTERACTION_AUDIT.md"

# ── 1. 读 §2.2 ──
src = io.open(PLAN, encoding="utf-8").read()
m = re.search(r"### 2\.2 .*?\n(.*?)\n### 2\.3 ", src, re.S)
seg = m.group(1)

rows = []
for line in seg.splitlines():
    s = line.strip()
    if not s.startswith("|") or "/" not in s:
        continue
    c = [x.strip() for x in s.strip("|").split("|")]
    if len(c) < 4:
        continue
    route_raw, page, inter = c[0], c[1], c[2]
    if not re.search(r"`/[^`]*`", route_raw):
        continue
    rows.append({"route": route_raw.replace("`", ""), "page": page, "inter": inter})

# ── 2. 读所有 spec ──
specs = {}
for f in sorted(glob.glob(os.path.join(E2E, "*.spec.cjs"))):
    specs[os.path.basename(f)] = io.open(f, encoding="utf-8", errors="replace").read()

# ── 3. 拆原子交互项 ──
STOP = {"详情", "列表", "页面", "交互", "行为", "功能"}

def atoms(text):
    # 按 / + 、，, 拆
    parts = re.split(r"[/+、，,]", text)
    out = []
    for p in parts:
        p = re.sub(r"[（(][^)）]*[)）]", "", p).strip()
        p = re.sub(r"^\d+\s*", "", p)          # 去前缀数字（"14列可排序表" → "列可排序表"）
        p = p.strip()
        if len(p) >= 2 and p not in STOP:
            out.append(p)
    return out

def keywords(atom):
    """从中文/混合描述里抽可用于 grep 的关键词：
    - 英文/数字词（pills / CTA / Tab / SKU / toast）
    - 中文核心词（搜索 / 分页 / 筛选 / 提交 / 跳转 …）
    """
    kws = set()
    for w in re.findall(r"[A-Za-z][A-Za-z0-9_]{1,}", atom):
        kws.add(w.lower())
    # 中文：取 2~4 字的片段，交给 grep（会偏宽，人工判读）
    for w in re.findall(r"[\u4e00-\u9fa5]{2,4}", atom):
        kws.add(w)
    return sorted(kws)

# ── 4. 逐页逐项 ──
def hit_count(kws, txt):
    """短词（≤4 字符）必须词边界匹配，否则 'cta' 会命中 'react'、'pills' 会命中 'spills'。
    同时排除注释行（// 开头），注释里出现关键词不算测试。"""
    body = "\n".join(ln for ln in txt.splitlines()
                     if not ln.lstrip().startswith("//") and not ln.lstrip().startswith("*"))
    for k in kws:
        if len(k) <= 4 and re.fullmatch(r"[A-Za-z0-9_]+", k):
            if re.search(r"\b" + re.escape(k) + r"\b", body, re.I):
                return True
        else:
            if k.lower() in body.lower():
                return True
    return False

L = ["# I 维（交互）半自动审计", "",
     "> 由 `scripts/audit_interaction.py` 生成。",
     "> ⚠️ **命中 ≠ 测了**：spec 里出现关键词，可能只是变量名/选择器，未必有断言。",
     "> ⇒ 本表用来**缩小人工范围**，最终判定必须打开 spec 看 `expect(...)`。",
     "> 已做的降噪：短词（≤4 字符）走词边界；**排除注释行**。", ""]

total_items = hit_items = 0
for r in rows:
    its = atoms(r["inter"])
    if not its:
        continue
    L.append("## `%s` — %s" % (r["route"], r["page"]))
    L.append("")
    L.append("| 交互项 | 命中 spec 数 | 命中的文件（前 3） |")
    L.append("|---|---|---|")
    for it in its:
        kws = keywords(it)
        hits = [n for n, t in specs.items() if hit_count(kws, t)]
        total_items += 1
        if hits:
            hit_items += 1
        shown = "、".join(h[:30] for h in hits[:3]) + ("…" if len(hits) > 3 else "") if hits else "**无**"
        L.append("| %s | %d | %s |" % (it, len(hits), shown))
    L.append("")

L.append("---")
L.append("")
L.append("## 汇总")
L.append("")
L.append("| 指标 | 数值 |")
L.append("|---|---|")
L.append("| 交互项总数 | **%d** |" % total_items)
L.append("| 有关键词命中的 | %d（%.0f%%） |" % (hit_items, hit_items * 100.0 / total_items if total_items else 0))
L.append("| **完全没命中（重点排查）** | **%d** |" % (total_items - hit_items))
L.append("")
L.append("> ⚠️ 再强调：命中率只说明「关键词在代码里出现过」，**不代表断言存在**。")
L.append("> 真正判定要看：打开 spec → 找到那个交互 → 确认有 `expect(...)` 断言它。")

io.open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("页面 %d ｜ 交互项 %d ｜ 有命中 %d ｜ 无命中 %d" %
      (len(rows), total_items, hit_items, total_items - hit_items))
