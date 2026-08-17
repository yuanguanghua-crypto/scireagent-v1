# S6 ②+④ 测试手册（四轴子结构标签 · 前端展示 + 数据治理门）

> 适用对象：S6「SMARTS 四轴子结构判定」的「②前端展示标签」与「④数据治理门 `--write`」两件事。
> 范围：纯本地 dev（SQLite + 前端 dev server），**开发测试态 + 种子数据**，不可表述为"已交付/已上架"。
> 关联文档：`s6_substructure_display_and_governance.md`（设计/操作说明）

---

## 0. 测试目标（一句话）

确认三件事跑通且闭环：
1. 后端把 `substructure_tags`（四轴标签）从 DB 经 API 真实吐给前端；
2. 前端卡片 / 详情页真实渲染四轴 chips（不报错、不漏渲染、不误渲染空值）；
3. 数据治理门 `detect_substructures --write` 能（重）写标签、告警非阻断、幂等。

---

## 1. 前置条件（每次测试前确认）

| 项 | 命令 / 检查 | 期望 |
|---|---|---|
| 后端服务 | `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/v1/products/?page_size=1` | `200` |
| 前端服务 | `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5173/` | `200` |
| 标签已填充 | `python manage.py shell` 查 `Product.objects.exclude(substructure_tags__isnull=True).count()` | `>= 107` |
| 商品可见 | 列表 `meta.pagination.count` | `>= 67`（active 且未归档） |

### 若服务没起（冷启动步骤）

```bash
# 终端1：后端（SQLite）
cd src_claude/backend
DB_ENGINE=sqlite venv/Scripts/python.exe -B manage.py runserver 127.0.0.1:8000

# 终端2：前端
cd src_claude/frontend
NODE_OPTIONS="" npx vite --port 5173 --host

# 若标签未填充，先跑治理门（RDKit venv 路径按本机调整）
cd src_claude/backend
DB_ENGINE=sqlite S6_RDKIT_VENV=D:/s6_rdkit_venv venv/Scripts/python.exe -B manage.py detect_substructures --write
```

---

## 2. 测试分层

### ▸ T1 后端列表接口（卡片数据源）

**操作**
```bash
curl -s "http://127.0.0.1:8000/api/v1/products/?page_size=3" \
  | python -c "import sys,json;d=json.load(sys.stdin);rows=d['data'];print('count=',d['meta']['pagination']['count']);[print(' ',r['catalog_no'],'->',json.dumps(r.get('substructure_tags'),ensure_ascii=False)[:90]) for r in rows[:3]];print('field_present=',all('substructure_tags' in r for r in rows))"
```

**通过判据**
- [ ] `count >= 67`
- [ ] 每条 item 都有 `substructure_tags` 字段
- [ ] 字段结构为 `{ "parsed": true, "labels": [...], "axes": { "base":..., "base_mod":..., "sugar_sub":..., "sugar_type":... } }`
- [ ] `labels` 为非空前端可读字符串数组（如 `["U","2'-F","deoxy"]`）

### ▸ T2 后端详情接口（详情页数据源，按 pk）

**操作**（SC8035 的 pk 通常为 54，以实际为准）
```bash
curl -s "http://127.0.0.1:8000/api/v1/products/54/" \
  | python -c "import sys,json;d=json.load(sys.stdin);print('success=',d['success']);data=d['data'];print('catalog_no=',data['catalog_no']);print('substructure_tags=',json.dumps(data.get('substructure_tags'),ensure_ascii=False));print('present=', 'substructure_tags' in data)"
```

**通过判据**
- [ ] `success == true`
- [ ] `substructure_tags.present == True`
- [ ] `axes` 四键齐全（base/base_mod/sugar_sub/sugar_type），缺失轴为 `null` 而非报错
- [ ] SC8035 预期 `labels` 含 `U`、`2'-F`、`deoxy`、`NTP`

### ▸ T3 前端卡片 chips（目视，浏览器）

**操作**：浏览器打开 `http://localhost:5173/`
**观察点**：
- [ ] 每张商品卡在化学标识（chem-id）下方出现一行彩色 chips
- [ ] 四轴标签按轴着色：碱基(base)/碱基修饰(base_mod)/糖环取代(sugar_sub)/糖型(sugar_type)，派生标签（Biotin / NTP / Propargyl）另色
- [ ] 无 SMILES 的商品：chips 区域被正确隐藏（不显示空框、不报错）
- [ ] 滚动/翻页后 chips 持续正常，无 console 报错（F12 看 Console）

### ▸ T4 前端详情页 Modification Signature（目视，浏览器）

**操作**：浏览器打开 `http://localhost:5173/products/54`（SC8035）
**观察点**：
- [ ] 「Modification Signature (SMARTS)」分组出现在 Chemical Identity 之后
- [ ] 渲染 Base / Sugar 两行 + Labels 行
- [ ] SC8035 应显示：Base=`U`，Sugar=`2'-F / deoxy`，Labels 含 `NTP`
- [ ] SC8016 应显示：Labels 含 `Biotin`
- [ ] Console 无报错

### ▸ T5 数据治理门 `--write`（幂等 + 非阻断）

**操作**
```bash
# 5.1 记录写入前计数
# 5.2 跑治理门（带 --write 真写）
cd src_claude/backend
DB_ENGINE=sqlite S6_RDKIT_VENV=D:/s6_rdkit_venv venv/Scripts/python.exe -B manage.py detect_substructures --write
# 5.3 再跑一次，确认幂等（计数不变）
# 5.4 跑只读模式（不带 --write）
DB_ENGINE=sqlite S6_RDKIT_VENV=D:/s6_rdkit_venv venv/Scripts/python.exe -B manage.py detect_substructures
```

**通过判据**
- [ ] 5.2 输出 `written=N`，`unparsed=0`（脏 SMILES 已被上一轮替换/排除）
- [ ] 5.3 二次运行 `written` 计数与 5.2 一致（幂等，非重复追加）
- [ ] 5.4 只读模式**不修改 DB**，仅打印统计 + 数据质量告警
- [ ] 数据质量告警（SC8053/SC8015/SC8007 名称 vs SMARTS 不一致）打印但**不阻断**（退出码 0，继续写库）

### ▸ T6 自动化单测（回归闸门）

**操作**
```bash
cd src_claude/backend
DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 venv/Scripts/python.exe -B -m pytest \
  apps/bridges/tests/test_s6_substructure.py \
  apps/commerce/tests/test_s6_substructure_tags_exposed.py \
  apps/commerce/tests/test_s5_ordering.py -p no:cacheprovider -q
```

**通过判据**
- [ ] 全部 PASS（含 `test_s6_four_axis_100pct` 70/70、`test_s6_payload_labels_and_axes`、`test_s6_substructure_tags_exposed`）
- [ ] 无 ERROR / 无 FAILED

---

## 3. 通过 / 失败 汇总表（每次测试后勾填）

| 编号 | 测试项 | 结果 | 备注 |
|---|---|---|---|
| T1 | 列表接口返回 substructure_tags | ☐ | |
| T2 | 详情接口返回 substructure_tags | ☐ | |
| T3 | 卡片四轴 chips 渲染 | ☐ | 需人工目视 |
| T4 | 详情页 Modification Signature 渲染 | ☐ | 需人工目视 |
| T5 | --write 幂等 + 非阻断 | ☐ | |
| T6 | 自动化单测全绿 | ☐ | |

**结论门槛**：T1/T2/T5/T6 全绿 + T3/T4 人工目视无异常 = 通过。任一 FAIL 即阻断，需先修后重测。

---

## 4. 已知限制 / 坑（测试时心里有数）

1. **像素级截图无自动化工具**：T3/T4 需人工开浏览器确认（本环境无浏览器自动化）。
2. **公开列表 `status` 过滤已修**：`views.py` 用 `Product.Status.ACTIVE.value`；若日后列表又变 0，先查此行是否被回退。
3. **种子数据被归档会致列表 0 条**：dev 库商品默认 `archived=True` 则不显示。可见商品需 `archived=False & status='active'`。
4. **③接入 relevance 打分未做**：本手册只覆盖 ②+④，不含打分链路。

## 5. 清理 / 还原（可选）

测试完毕若想恢复"干净种子态"（重新归档测试时解档的商品）：
```bash
cd src_claude/backend
DB_ENGINE=sqlite venv/Scripts/python.exe -B manage.py shell -c \
  "from apps.commerce.models import Product; print(Product.objects.filter(archived=False,status='active').update(archived=True))"
```
> 仅软归档（archived=True），不删除任何实体，可随时重新解档。
