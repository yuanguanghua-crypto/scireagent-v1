# -*- coding: utf-8 -*-
"""I 维判定：把 FULL_SITE 的交互项做「中英同义词扩展」后重新匹配，给出每页 ✓/✗。

## 为什么要同义词扩展
初版 `audit_interaction.py` 只用原始中文词 grep，实测出假空白：
  "分页"（中文）命中 0 个 spec，但 "pagination"（英文）命中 3 个。
⇒ 直接按中文词下"没测"的结论是错的。

## 本脚本的判定规则（**保守/乐观要明确**）
- 该页**所有**交互项都命中 ⇒ `✓`
- 有**任一**交互项未命中 ⇒ `✗`
⚠️ `✓` 只表示「关键词全覆盖」，**不表示断言充分**。
   要确认断言强度仍需打开 spec 看 `expect(...)`。本脚本的产出是"消除 ☐"，
   让每格都有判定，而不是证明测试质量。
"""
import io
import os
import re
import glob

PLAN = "docs/e2e/FULL_SITE_E2E_PLAN.md"
E2E = "frontend/e2e"
OUT = "docs/e2e/INTERACTION_VERDICT.md"

# 中英同义词表：中文词 -> 追加搜索的关键词
SYN = {
    "分页": ["pagination", "page=", "pageSize", "currentPage", "next page", "nextPage"],
    "提交": ["submit", "confirm"],
    "跳转": ["toHaveURL", "waitForURL", "navigate", "redirect"],
    "搜索": ["search", "query", "keyword"],
    "删除": ["remove", "delete"],
    "保存": ["save"],
    "发布": ["publish"],
    "审批": ["approval", "approve", "review"],
    "结算": ["checkout"],
    "详情": ["detail"],
    "列表": ["list", "table"],
    "筛选": ["filter", "select"],
    "排序": ["sort", "order"],
    "上传": ["upload"],
    "下载": ["download"],
    "弹层": ["dialog", "modal", "drawer", "popup"],
    "表单": ["form", "input"],
    "状态": ["status", "state"],
    "数量": ["quantity", "qty"],
    "输入校验": ["validation", "invalid", "required", "error"],
    "成功横幅": ["success", "banner", "toast"],
    "快捷入口": ["shortcut", "quick"],
    "概览卡片": ["overview", "card", "stat"],
    "地址": ["address"],
    "附件": ["attachment", "file"],
    "重订": ["reorder"],
    "复制": ["duplicate", "copy"],
    "增删改": ["create", "update", "delete", "crud"],
}

# ★ 逐项同义词（2026-10-21 补）：只对**下面这几个原子项**生效，**不进通用 SYN 表**。
#
# 为什么需要：通用 SYN 是按「子串包含」命中的（`if cn in kw`），而这几项的**文字措辞**
# 与 spec 里的实现用词毫无交集（"3步注册" vs `.step-item`），故一律 0 命中 ⇒ 假阴性。
#
# ⚠️ 为什么不用通用词（如 "product"/"select"/"step"）：本脚本是**全局 grep 所有 spec**，
#   一旦用这种词，任何提到 product 的 spec 都会让该项变绿 ⇒ 变成"用同义词把判定刷绿"，
#   比假阴性更危险。所以这里每条都必须是**该 spec 独有的类名/文案**，并且附证据。
ATOM_SYN = {
    # 证据：frontend/e2e/register-wizard.spec.cjs（5 passed，独立复跑已验证）
    #   「步骤 1 → 2 → 3 推进；第 3 步指标出现；Back 回退保留已填值」
    #   → :92 `.step-item` count == 2、:153 count == 3
    "3步注册": ["step-item", "Complete Registration"],
    # 证据：frontend/e2e/checkout-progressive-sections.spec.cjs（2 passed）
    #   「四段齐全且顺序正确 Shipping→Payment→Notes→Summary」→ :89 `.checkout-section .section-title`
    #   「支付分段推进/回退」→ :106-124 `.payment-option--active` / `.po-fields`
    "多步": ["checkout-section", "payment-option--active"],
    # 证据：frontend/e2e/workspace-entry-intake.spec.cjs（1 passed）
    #   「产品列表可筛选 → 选中 → 右侧回显」→ `.ki-product-item` / `.ki-active` / `.ki-form-area`
    "产品下拉": ["ki-product-item", "ki-form-area"],
}


def load_specs():
    d = {}
    for f in sorted(glob.glob(os.path.join(E2E, "*.spec.cjs"))):
        d[os.path.basename(f)] = io.open(f, encoding="utf-8", errors="replace").read()
    return d

SPECS = load_specs()

def strip_comments(txt):
    return "\n".join(ln for ln in txt.splitlines()
                     if not ln.lstrip().startswith("//") and not ln.lstrip().startswith("*"))

def body_of(name):
    return strip_comments(SPECS[name])

def hit(kw, body):
    if len(kw) <= 4 and re.fullmatch(r"[A-Za-z0-9_=]+", kw):
        return re.search(r"\b" + re.escape(kw) + r"\b", body, re.I) is not None
    return kw.lower() in body.lower()

def expanded(kw):
    out = [kw]
    for cn, ens in SYN.items():
        if cn in kw:
            out += ens
    # 原子项级覆盖（见 ATOM_SYN 的说明：只认该 spec 独有的类名/文案）
    for atom, ens in ATOM_SYN.items():
        if atom == kw:
            out += ens
    # 英文片段
    out += re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", kw)
    return out

def clean(atom):
    # ★ 去掉 markdown 粗体标记（FULL_SITE 里有 `**37 按钮 / 50 输入**` 这类写法，
    #   不剥掉的话 `**37 按钮` 匹配不上数量描述规则 ⇒ 又成假空白）
    a = atom.replace("*", "")
    a = re.sub(r"[（(][^)）]*[)）]", "", a).strip()
    # ★ 2026-10-21 修正两处拆词错误（此前造成假空白）：
    #   ① 原写 `re.sub(r"^\d+\s*", "", a)` 会把「3步注册」变成「步注册」——
    #      那不是词，grep 必然 0 命中 ⇒ 假空白。**数字要保留**。
    #   ② 「37 按钮」「50 输入」「90 展示」是**数量描述**，不是可测的交互项 ⇒ 整条丢弃，
    #      否则会被判成"没测"（其实 FULL_SITE 只是说这页控件多）。
    if re.match(r"^\d+\s*(个)?\s*(按钮|输入|字段|列|项|处|展示|步)$", a):
        return ""
    return a

STOP = {"详情", "列表", "页面", "交互", "行为", "功能", ""}

def atoms(text):
    parts = re.split(r"[/+、，,]", text)
    return [clean(p) for p in parts if clean(p) and clean(p) not in STOP]

def parse_routes(cell):
    """拆分一行里的多路由（与 gen_coverage_ledger.parse_routes 保持一致）：
    `/login` `/register`  → 2 页
    `/products`+`:id`     → 列表 + 详情
    """
    parts = re.findall(r"`([^`]+)`", cell)
    if not parts:
        return [cell.strip("`").strip()]
    out, last = [], None
    for p in parts:
        if p.startswith(":"):
            base = (last or "").rstrip("/")
            out.append((base + "/" + p) if base else p)
        else:
            out.append(p)
            last = p
    return out


# ── 读 §2.2 ──
src = io.open(PLAN, encoding="utf-8").read()
m = re.search(r"### 2\.2 .*?\n(.*?)\n### 2\.3 ", src, re.S)
rows = []
for line in m.group(1).splitlines():
    s = line.strip()
    if not s.startswith("|") or "/" not in s:
        continue
    c = [x.strip() for x in s.strip("|").split("|")]
    if len(c) < 4:
        continue
    if not re.search(r"`/[^`]*`", c[0]):
        continue
    for route in parse_routes(c[0]):
        rows.append({"route": route, "page": c[1], "inter": c[2]})

L = ["# I 维（交互）判定", "",
     "> 由 `scripts/judge_interaction.py` 生成。",
     "> **判定规则**：该页所有交互项都命中 ⇒ `✓`；任一未命中 ⇒ `✗`。",
     "> ⚠️ `✓` 只表示「关键词全覆盖」，**不表示断言充分**；要确认强度须打开 spec 看 `expect`。",
     "> **已做中英同义词扩展**（修正初版的假空白，如「分页」→ pagination）。",
     ""]

stat = {"✓": 0, "✗": 0, "—": 0}
for r in rows:
    its = atoms(r["inter"])
    if not its:
        stat["—"] += 1
        continue
    detail = []
    allhit = True
    for it in its:
        kws = expanded(it)
        who = [n for n in SPECS if any(hit(k, body_of(n)) for k in kws)]
        if not who:
            allhit = False
        detail.append("| %s | %s | %s |" % (
            it, "✓" if who else "**✗**",
            ("、".join(h[:26] for h in who[:2]) + ("…" if len(who) > 2 else "")) if who else "无"))
    verdict = "✓" if allhit else "✗"
    stat[verdict] += 1
    L.append("## `%s` — %s ⇒ **%s**" % (r["route"], r["page"], verdict))
    L.append("")
    L.append("| 交互项 | 命中 | spec |")
    L.append("|---|---|---|")
    L.extend(detail)
    L.append("")

L += ["---", "", "## 汇总", "",
      "| 判定 | 页数 |", "|---|---|",
      "| **✓ 全项命中** | **%d** |" % stat["✓"],
      "| **✗ 有未命中项** | **%d** |" % stat["✗"],
      "| — 无交互描述 | %d |" % stat["—"],
      "",
      "⚠️ 这是 I 维的**首次判定**。`✗` 页里的未命中项 = 明确的测试空白，应优先补。",
      "⚠️ `✓` 页仍需抽查断言强度（关键词命中 ≠ 有 expect）。"]

io.open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("=> %s" % OUT)
print("✓ %d 页 ｜ ✗ %d 页 ｜ — %d 页（共 %d）" % (stat["✓"], stat["✗"], stat["—"], len(rows)))
