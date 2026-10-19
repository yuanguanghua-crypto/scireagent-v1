# SciReAgent（原 LabPro Global）

> AI-Native Scientific Reagent Platform — 核酸与点击化学试剂

---

## 这是什么

面向科研试剂的 B2B 电商 + 知识图谱平台。核心链路：

```
ResearchGoal → Application → Method → Protocol → Product → SKU
```

链路上每层都是可独立检索的知识实体；商品是知识的一个出口，不是终点的全部。

---

## ⚠️ 先读这三份，再动手

| 文件 | 作用 |
|---|---|
| **`CLAUDE.md`** | **唯一入口**：架构铁律、技术栈、权限、测试命令、踩过的坑。**最高优先级** |
| **`docs/CLAIMS.md`** | **改动前必读**：我们相信什么 + 依据 + **什么时候会失效**。涉及资金/库存/权限/数据可见性的改动，必须先看这里 |
| **`docs/DECISIONS.md`** | **为什么这样做**（轻量 ADR）。这是唯一无法从代码反推的信息 |

> 「是什么」请直接读代码（`models.py` / `urls.py` / `vite.config.js`）；
> 「为什么」读 `DECISIONS.md`；「还能不能信」读 `CLAIMS.md`。

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Composition API + Vite + Element Plus + Tailwind CSS + Pinia |
| 后端 | Django 5.1 + Django REST Framework（版本以 `backend/requirements.txt` 为准） |
| 数据库 | PostgreSQL（生产）/ SQLite（开发与测试） |
| 部署 | Docker Compose + nginx（含 Basic Auth） |

---

## 目录结构

> ⚠️ **本段只写目录的组织方式，不写数量** —— 数量会漂移，请以 `ls` 为准。

```
src_claude/
├── backend/
│   ├── config/          # Django 配置（settings 分 development/production）
│   ├── core/            # 跨 app 基础设施（权限、渲染器、Mixin）
│   ├── apps/            # 业务 app（见下）
│   ├── scripts/         # 运维/审计脚本（capability_guard、migration_drill 等）
│   └── manage.py
├── frontend/
│   ├── src/api/         # 按后端端点分模块
│   ├── src/stores/      # Pinia
│   ├── src/views/       # 页面（admin/ 旧后台、workspace/ 研究员工作台）
│   └── e2e/             # Playwright
├── deploy/              # nginx.conf、compose 相关部署配置
├── docs/                # 文档（⚠️ 混杂，见下方「文档诚实声明」）
├── scripts/             # 仓库级脚本
└── CLAUDE.md            # 唯一入口
```

`backend/apps/` 下的 app（用途看各自的 `models.py`，不在此枚举职责）：

`accounts` `assets` `bridges` `commerce` `core` `documents` `inventory` `knowledge` `notifications` `quotes` `transactions`

> ⚠️ **易错点**：`Order` / `Quote` / `Basket` / `Wishlist` 在 **`transactions`**，不在 `commerce`。
> `commerce` 只有 `Product` / `SKU` / 分类与目录相关模型。

---

## 快速开始

### 后端

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

> ⚠️ **dev server 的端口与 proxy target 一律以 `frontend/vite.config.js` 为准。**
> 历史上文档曾把 proxy 写成 8001（实际 8000），照着改会把能用的配置改坏。
>
> ⚠️ **本仓库目录可能是 `C:` 上的 junction**。若 `vite` 从 junction 路径启动后整站白屏
> （表现是 `main.js` 依赖未被重写），改用物理路径启动。物理路径可用
> `git rev-parse --show-toplevel` 确认。

### 测试

**不要用 `manage.py test`**（项目加了守卫，会直接 exit 1 并提示）。
pytest 命令见 **`CLAUDE.md` 的「测试」章节** —— 本文件不重复，避免两处漂移。

---

## 文档诚实声明（重要）

`docs/` 目录**不是**一份统一维护的文档集。它的实际构成：

| 类别 | 可信度 | 说明 |
|---|---|---|
| **被代码引用的规范** | ✅ **可信** | 如 `DATASOURCE_RELIABILITY.md`、`COA_SDS_PRD.md`。它们被代码注释按 §/行号引用，甚至被用作测试判据 ⇒ 相对最准 |
| `docs/po-portal/` | ✅ **较新** | 覆盖 PO 采购门户 + 库存台，2026-10 产出 |
| `docs/CLAIMS.md` / `DECISIONS.md` | ✅ **维护中** | 见上方说明 |
| `docs/00_MASTER_INDEX.md` ~ `12_*.md` | ❌ **已废弃** | 2026-06-27 的设计草案，文件内已标 DEPRECATED。**仅作历史参考**，不要照它写代码 |
| `docs/specifications/` 等其余 | ❌ **已冻结** | 长期未更新，内容可能过期 |

> **判断方法（比记忆更可靠）**：搜代码里有没有引用它 ——
> `grep -rn "docs/<文件名>" backend/ frontend/src/`
> 被引用的才是「活文档」；没被引用的，大概率已经和代码脱节。

⚠️ 特别提醒：**数字类声明（计数、端口、测试数、行号）最容易腐烂**。
看到文档里的具体数字，先怀疑，再验证。

---

## 许可证

Private — 仅限内部使用
