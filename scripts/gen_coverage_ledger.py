# -*- coding: utf-8 -*-
"""全站覆盖台账生成器 —— 只出「骨架」，不判「覆盖」。

## 为什么只出骨架（2026-10-20 实测结论）

初版试图用「关键词匹配 spec」反推覆盖，实测两次都失败：
- 太严（只匹配页面名）→ /login 判成"无 spec"的假空洞
- 太松（+ 路由片段）→ a11y.spec / permission-matrix 这类**全站扫描 spec**
  让 44 个页面全部"有 spec" → 假 100% 覆盖

**根本原因**：本项目 56 个 spec 是「点菜单进入」的（符合拟人化铁律，`goto` 只有 2 个），
所以**覆盖度无法从代码静态反推** —— 必须看断言、看点击路径。

⇒ 所以本脚本只做两件确定的事：
  1. 从 FULL_SITE_E2E_PLAN §2.2 **程序化提取** 页面清单与七维规划（不手抄）
  2. 输出**空白骨架**，覆盖状态由人逐格填（附关键词提及的 spec 仅作检索入口）

用法：python scripts/gen_coverage_ledger.py  → 生成 docs/e2e/COVERAGE_LEDGER.md
重跑即刷新骨架；**人工填写的内容会丢**（所以要改骨架外的东西请改本脚本）。
"""
import io
import os
import re
import glob

PLAN = "docs/e2e/FULL_SITE_E2E_PLAN.md"
OUT = "docs/e2e/COVERAGE_LEDGER.md"

# ── 1. 截取 §2.2 ──
text = io.open(PLAN, encoding="utf-8").read()
m = re.search(r"### 2\.2 .*?\n(.*?)\n### 2\.3 ", text, re.S)
if not m:
    raise SystemExit("MISS: 找不到 §2.2")
seg = m.group(1)

# ── 2. 解析表格 ──
rows, group = [], ""
for line in seg.splitlines():
    s = line.strip()
    g = re.match(r"\*\*(.+?)\*\*", s)
    if g:
        group = g.group(1)
        continue
    if not s.startswith("|"):
        continue
    cells = [c.strip() for c in s.strip("|").split("|")]
    if len(cells) < 9 or "/" not in cells[0]:
        continue
    rows.append({
        "group": group,
        "route": cells[0],                    # 保留反引号，下面要靠它切分
        "page": cells[1],
        "dims": cells[2:9],                   # I P S R V A B
        "prio": cells[9] if len(cells) > 9 else "",
    })


def parse_routes(cell):
    """一行可能含多页：
    `/login` `/register`                    → 2 页
    `/products`+`:id`                       → 列表 + 详情
    `/workspace/goals` `/applications` …    → 5 页
    `/workspace/products/new`+`:id/edit`    → new + :id/edit（拼到父路径）
    """
    parts = re.findall(r"`([^`]+)`", cell)
    if not parts:
        return [cell.strip("`").strip()]
    out, last = [], None
    for p in parts:
        if p.startswith(":"):
            base = (last or "").rstrip("/")
            parent = "/".join(base.split("/")[:-1]) or base
            out.append((parent + "/" + p) if parent else p)
        else:
            out.append(p)
            last = p
    return out


pages = []
for r in rows:
    for route in parse_routes(r["route"]):
        pages.append({**r, "route": route})

# ── 3. spec 关键词索引（仅作检索入口，不作为覆盖证据）──
specs = sorted(glob.glob("frontend/e2e/*.spec.cjs"))
spec_text = {}
for f in specs:
    try:
        spec_text[os.path.basename(f)] = io.open(f, encoding="utf-8", errors="replace").read()
    except Exception:
        pass


def find_specs(page, route=""):
    keys = set()
    for k in re.split(r"[/（）()\s]+", page):
        if len(k.strip()) >= 4:
            keys.add(k.strip().lower())
    for s2 in route.split("/"):
        s2 = s2.strip()
        if len(s2) >= 4 and not s2.startswith(":") and "`" not in s2:
            keys.add(s2.lower())
    if not keys:
        return []
    return [n for n, t in spec_text.items() if any(k in t.lower() for k in keys)]


# ── 4. 输出 ──
DIMS = ["I", "P", "S", "R", "V", "A", "B"]
L = []
L.append("# 全站测试覆盖台账（骨架 V1）")
L.append("")
L.append("> **本文件由 `scripts/gen_coverage_ledger.py` 生成 —— 重跑会覆盖人工填写内容。**")
L.append("> **人工判定结果请写进 `docs/e2e/COVERAGE_FINDINGS.md`**（带证据，不会被覆盖）。")
L.append("> 来源：`docs/e2e/FULL_SITE_E2E_PLAN.md` §2.2（程序化提取 %d 页，不手抄）" % len(pages))
L.append("")
L.append("## ⚠️ 先说清楚：为什么这里没有「覆盖率」")
L.append("")
L.append("我试过用「关键词匹配 spec」自动算覆盖率，**两次都失败**：")
L.append("")
L.append("| 尝试 | 结果 |")
L.append("|---|---|")
L.append("| 只匹配页面名 | `/login` 判成「无 spec」= **假空洞** |")
L.append("| 再加路由片段 | `a11y.spec` / `permission-matrix` 这类**全站扫描**让 44 页全部「有 spec」= **假 100%** |")
L.append("")
L.append("**根本原因**：本项目 %d 个 spec 是**点菜单进入**的（符合「不许 goto 直达」铁律，全仓 `goto` 只有 2 处），" % len(specs))
L.append("所以覆盖度**无法从代码静态反推** —— 必须看断言、看点击路径。")
L.append("")
L.append("⇒ 本台账**只给骨架**：格子由人填。这比给一个假的 100% 有用。")
L.append("")
L.append("## ✅ 源表缺陷已修复（2026-10-20）")
L.append("")
L.append("生成台账时曾查出 `FULL_SITE_E2E_PLAN.md` §2.2 表格**列数不齐**：")
L.append("表头声明 10 列，但 **30 行里有 29 行只有 9 列**（整列 B 维未填，末格直接是优先级）。")
L.append("")
L.append("**已逐行核过**（30 行模式一致、0 异常）后补齐：给 29 行插入了 B 列并标 `☐`（待评估，非「不适用」）。")
L.append("复核结果：**30 行全部 10 列**。")
L.append("")
L.append("⇒ 所以本台账的**维度分区现在是可信的**（此前不可信）。")
L.append("")
L.append("## 判读规则")
L.append("")
L.append("| 符号 | 含义 |")
L.append("|---|---|")
L.append("| `☐` | **待评估** —— 需要有人确认这一维测没测 |")
L.append("| `—` | **不适用** —— FULL_SITE 规划如此，不是缺失 |")
L.append("| `✓` | 已覆盖（**你填的**，附 spec 名或说明） |")
L.append("| `✗` | 确认未覆盖（**你填的**） |")
L.append("")
L.append("## 七维含义（摘自 FULL_SITE §2.0）")
L.append("")
L.append("| 维 | 含义 |")
L.append("|---|---|")
L.append("| **I 交互** | 每个按钮/输入/选择/弹窗/下拉/Tab/上传/分页/排序/Toast/加载态都被触发 |")
L.append("| **P 权限** | 4 角色（匿名 / customer / staff / admin）× 受限页的预期行为 |")
L.append("| **S 状态** | 业务状态分支（PO 8 态 / 订单旧态 / 产品 active·draft·discontinued）的 UI 差异 |")
L.append("| **R 响应式** | 桌面 / 笔记本 / 平板 / 移动 4 视口，布局不崩、关键交互可用 |")
L.append("| **V 视觉** | 设计令牌一致（主色 / 圆角 / badge+点 / 字体） |")
L.append("| **A 可访问性** | WCAG：label 关联 / 对比度 / 焦点顺序 / aria |")
L.append("| **B 浏览器** | chromium / firefox / webkit 行为一致 |")
L.append("")

total_apply = total_na = 0
cur = None
for i, p in enumerate(pages, 1):
    if p["group"] != cur:
        cur = p["group"]
        L.append("")
        L.append("### %s" % cur)
        L.append("")
        L.append("| # | 路由 | 页面 | I | P | S | R | V | A | B | 优先级 | 相关 spec（仅检索线索，非覆盖证据） |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    cells = []
    for d in p["dims"]:
        if d.strip() in ("—", "-", ""):
            cells.append("—")
            total_na += 1
        else:
            cells.append("☐")
            total_apply += 1
    hits = find_specs(p["page"], p["route"])
    hint = ("、".join(h[:24] for h in hits[:2]) + ("…" if len(hits) > 2 else "")) if hits else "—"
    L.append("| %d | `%s` | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"
             % (i, p["route"], p["page"], *cells, p["prio"] or "—", hint))

L.append("")
L.append("## 骨架规模")
L.append("")
L.append("| 指标 | 数值 |")
L.append("|---|---|")
L.append("| 页面数 | **%d** |" % len(pages))
L.append("| 待评估格子 `☐` | **%d** |" % total_apply)
L.append("| 不适用 `—` | %d |" % total_na)
L.append("")
L.append("> ⚠️ 上面**不写完成率**，因为没人填过。要算完成率，先把 `☐` 填成 `✓`/`✗`。")
L.append("")
L.append("## 怎么填（建议顺序）")
L.append("")
L.append("1. **先填 P0 页面**（下表），一页一页来，别摊大饼")
L.append("2. 打开该页对应的 spec（看最后一列的线索），**逐维确认「这一维真的断言了吗」**")
L.append("   - 有断言 → 填 `✓` + spec 名")
L.append("   - 没断言 → 填 `✗`（这就是要补的）")
L.append("   - 不确定 → 保持 `☐`，别猜")
L.append("3. **填完一页再填下一页** —— 半填的台账比空台账更危险（会让人以为看过了）")
L.append("")
L.append("### P0 页面清单（先填这些）")
L.append("")
L.append("| 路由 | 页面 | 待评估格数 |")
L.append("|---|---|---|")
for p in pages:
    if p["prio"].strip() == "P0":
        n = sum(1 for d in p["dims"] if d.strip() not in ("—", "-", ""))
        L.append("| `%s` | %s | %d |" % (p["route"], p["page"], n))

L.append("")
L.append("## 更新方式")
L.append("")
L.append("```bash")
L.append("python scripts/gen_coverage_ledger.py   # 重跑刷新骨架")
L.append("```")
L.append("")
L.append("⚠️ 重跑会覆盖人工填写的 `✓`/`✗`。**填完后请把台账另存为 `COVERAGE_LEDGER_FILLED.md`**，")
L.append("或直接把填写结果落到 spec 文件的注释里（更持久）。")
L.append("")

io.open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("OK 页面=%d 待评估格=%d 不适用=%d -> %s" % (len(pages), total_apply, total_na, OUT))
