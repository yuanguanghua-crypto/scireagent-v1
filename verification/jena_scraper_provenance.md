# 验证：桌面 `jena_scraper` 文件夹 = `jena_products_v2.jsonl` 的**真正源头**

**日期**：2026-07-16（接续此前对 `jenabioscience_scraper` 的排除性验证）
**方法**：只读比对 + 正则复现，未修改任何数据/脚本
**候选脚本**：`C:/Users/yuankaifeng/Desktop/jena_scraper/`（scraper.py / scraper_v2.py / **scraper_v3.py** / 多份 DB 与报告）

---

## 结论：**是同一程序——这就是 v2 的产出源头**（与上一文件夹 `jenabioscience_scraper` 结论相反）

### 三重实证

| # | 证据 | 结果 |
|---|------|------|
| 1 | 自述文档 `jena_scraper_report.md` | 明确写"程序版本 `scraper_v3.py`、最终产物 `jena_products_v2.jsonl`（2,098 条、33 字段）"，字段清单逐字等于 v2（含 `jena_catalog_no`/`systematic_name`/`form`/`storage_condition`/`shipping_condition`/`shelf_life`/`category_path`） |
| 2 | 两份 jsonl 逐条比对 | 桌面 `jena_products_v2.jsonl` 与项目 `backend/data/jena/jena_products_v2.jsonl`：**记录数都是 2098、catalog_no 100% 重合、字段集合完全相同**；CO-501 的 concentration/form/storage/shipping/systematic_name 逐字一致。项目 v2 = 此导出版去掉 2 个超重字段 `applications`/`application_methods` |
| 3 | 源码 INSERT 语句 | `scraper_v3.py` 第 691–711 行 `INSERT OR REPLACE INTO products (...)` 正是写出这 31 个字段；`_parse_product` 第 729 行起构建同名字典 |

> 时间线吻合：v2 `crawled_at` ∈ 2026-06-25~27；此文件夹 `jena_products_v2.jsonl` 文件日期 2026-06-28（是爬取后 CAS 回填脚本 `_fix_cas_v3.py` 打的补丁，非新爬）。

---

## 路径 B 打通：变形具体代码行已指认

此前因"真实爬虫代码不在本机"而走不通的路径 B，现在可执行。读完 `scraper_v3.py` 的 `_parse_product`（第 729 行起），**所有变形都来自同一类设计缺陷**：字段提取 regex **允许标签冒号可选 + 不做词尾边界**，于是页面正文/导航/面包屑里任何含该词的字符串都会被捕获；且提取后**没有任何"值是否像合法规格"的校验闸门**。

### 具体变形行（scraper_v3.py）

| 变形（来自 Step1~2b-A） | 根因行 | 机制 |
|------|------|------|
| **form = "ation"**（33 条，5 字符截断） | 第 877 行 `form: r'\bForm\s*[:#]?\s*(.+?)(?:\n|$)'` | `\bForm` 缺词尾边界，命中 "**Form**ation" 等词，吞掉 "ation" |
| **shipping = "Accessories"**（11 条，导航串） | 第 882 行 `shipping_condition: r'\bShipping\s*[:#]?\s*(.+?)(?:\n|$)'` | `\bShipping` 命中面包屑 "Crystal Storage and **Shipping**"，`[:#]?` 让冒号可选，抓到后续 "Accessories" |
| **concentration 散文**（151 条，如 CO-501 "the concentration is slowly increased…"） | 第 879 行 `concentration: r'\bConcentration\s*[:#]?\s*(.+?)(?:\n|$)'` | 页面无 "Concentration:" 标签、但描述段有 "concentration"，冒号可选 → 把散文整段抓进字段 |
| **storage 通用模板覆盖**（RNT-018/008、HEL-299、PCR-353 写 `-20/-80°C`） | 第 881 行 `storage_condition` 同族正则 + 第 832–868 行 BS4 `<b>` 提取 | 首匹配优先 + 无校验闸门，套到通用存储标语而非真实 "avoid freeze/thaw" |
| **（化学属性自洽矛盾 12 条）** | 第 898–904 行 formula 清洗 + 第 873–896 行 MW/float 解析 | formula 去空格、MW 取首个浮点，二者形态未对齐 → 专有染料内部不自洽 |
| **（价格欧式格式）** | 第 795–798 行 `float(...replace(',','.'))` | `1.191,00`→`1.19`（千位分隔符误判小数点），报告 §7 记为 P0 |

### 正则复现（自验证，证明机制成立）

```
[form] 输入='Formation of a supersaturated solution occurs at 4°C.'
      -> 捕获='ation of a supersaturated solution occurs at 4°C.'   # 正是 form="ation" 来源
[shipping_condition] 输入='Crystal Storage and Shipping\nAccessories\n> Product'
      -> 捕获='Accessories'                                          # 正是 shipping="Accessories"
[concentration] 输入='In this assay the concentration is slowly increased until a point of supersaturation is reached. Using the phase diagram,'
      -> 捕获='is slowly increased until a point of supersaturation is reached. Using the phase diagram,'  # 正是 CO-501 散文
[form] 输入='Form: Solution' -> 捕获='Solution'                     # 正常样本也能抓，说明问题不是"抓不到"而是"不区分 label 与散文"
```

**元根因一句话**：`scraper_v3.py` 第 873–884 行的 fallback 正则把 `[:#]?`（冒号设为可选）且未加词尾边界，使字段关键词在导航/面包屑/描述散文中任意命中；第 853–868 行提取后直接 `data[key]=val`、`_parse_product` 全程**无任何"值是否像合法规格"的校验闸门** → 搬运即变形。这正好印证了之前 Step1~2b-A 推断的"宽松选择器 + 无校验闸门"，现在落到具体行。

### 作者的自检不充分（重要）

`jena_scraper_report.md` §6.1 声称"字段映射验证 100% 匹配、无交叉污染"，但 §7 自己记录了 concentration 混入 Bradford 描述（20 条）、PDF 污染空名行（319 条）。我们独立查出的 shipping=Accessories(11)/concentration 散文(151)/form="ation"(33) 等**未被作者自检覆盖**——说明当时的验证脚本（`verify_jena_products.py`）只查了空名行、重复 catalog、价格格式、浓度混入 Bradford 文本，**没查"字段关键词在散文/导航中被误命中"这一类污染**。

---

## 对调查的含义

- 之前 Step1~2b-A 锁定的所有变形**已 100% 归因到 `scraper_v3.py` 的具体行**，无需再假设"丢失的旧脚本"。
- 下一步只剩 **(C) 根因修复设计**：建议优先修 `scraper_v3.py` 第 873–884 行（标签强制 `:`/`#`、加词尾边界、首匹配改"标签区优先"），并在 `_parse_product` 提取后加**校验闸门**（如 shipping 值必须含 `°C/ship/ambient`、form 值长度与形态过滤）。该修复是**重新爬取/重清洗**层面的，不依赖项目后端改动；项目后端的消费闸门（jena_index 匹配期校验）应另做一层防御。
- 若决定重跑爬虫，此文件夹已具备完整可复跑工具链（scraper_v3.py + jena_crawl.db 断点续传 + 报告），但需注意：`jena_products_v2.jsonl` 已含 6/27–28 的 CAS 回填补丁，重跑会覆盖——应先备份当前 jsonl 与 `jena_v2.db`。
