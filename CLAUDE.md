# CLAUDE.md — SciReAgent

> AI 原生科学知识图谱平台（核苷酸/点击化学）。**唯一入口文件**，AI 编码前必须先读此文件。
> 核心链路不可变：`ResearchGoal → Application → Method → Protocol → Product → SKU`

---

## 技术栈（锁定）

| 层 | 技术 | 备注 |
|---|------|------|
| 后端 | Django 5.1 + DRF | 分层架构 View→Service→Model |
| 数据库 | PostgreSQL(生产) / SQLite(开发测试) | ArrayField/JSONField SQLite 不可用 |
| 前端 | Vue 3 + Vite + Pinia + Vue Router | JS，不是 TS |
| 图谱 | Cytoscape.js | 懒加载 |
| API 文档 | drf-spectacular | `/api/schema/` |
| 部署 | Docker + Nginx + Gunicorn | |

**引入新依赖前必须讨论。** 当前已否决：FastAPI/Next.js/Nuxt/GraphQL/ElasticSearch/Neo4j/Microservices/Celery。

---

## 目录结构（关键路径）

```
backend/
├── apps/
│   ├── accounts/     # User, Organization
│   ├── knowledge/    # ResearchGoal, Application, Method, Protocol, Reference, Compatibility
│   ├── commerce/     # Product, SKU, ProductClass, ProductDocument + AI/SEO/Word 服务
│   ├── bridges/      # ProductMethod, MethodProtocol, ProductReference, ProductCompatibility
│   ├── transactions/ # Order, Invoice, Quote, Basket, Wishlist
│   ├── quotes/       # QuoteRequest
│   └── assets/       # PdfFile
├── config/settings/  # base.py / development.py / production.py
├── core/             # EnvelopeRenderer, IsAdminOrReadOnly, IsStaffUser, svg_sanitizer
└── venv/

frontend/src/
├── api/              # 19 个模块，含 workspace/ 子目录
├── components/       # cards/ common/ graph/ home/ layout/ navigation/
├── composables/      # useApi, useGraph, useJsonLd, usePagination, useRdkit
├── stores/           # 10 个 Pinia store
├── views/            # 39 个页面组件
│   ├── admin/        # 旧管理后台（仍在使用）
│   └── workspace/    # 研究员工作台（AdminLayout + 10+ 页面）
└── router/index.js
```

---

## 架构铁律

1. **View 薄 → Service 厚 → Serializer 纯验证。** View 只做路由和响应。跨模型写入在 Service 中。Serializer 不编排多模型工作流。
2. **所有 API 响应走信封格式** `{success, data, meta}`，由 `EnvelopeRenderer` 全局强制。
3. **Serializer 字段必须显式声明**，禁止 `fields = '__all__'`。
4. **两个管理员角色：** `IsAdminUser`（Django admin/superuser，管理订单/发票）= 系统管理员；`IsStaffUser`（`is_staff=True`）= 研究员，访问 `/workspace/`。**研究员不能处理订单。**
5. **研究员是最终权威。** 发布检查是告知模式，不是硬阻断。

**代码味道速查（看到即拒绝）：**
`is_featured` BooleanField → 用 `display_priority`；跨模型 serializer 复用；裸数组/对象 API 响应；View 中直接写数据库。

---

## 权限速查

| 资源 | 读 | 写 |
|------|----|-----|
| 知识实体 (RG/App/Method/Protocol/Ref/Compat) | 公开 | Admin 仅 |
| Product, SKU, Category | 公开 | Admin 仅 |
| Order, Quote, Wishlist | 认证用户(自己的) | 认证用户(自己的) |
| QuoteRequest 创建 | 匿名 OK | — |
| `/workspace/` 研究员工作台 | — | StaffUser |
| `/admin/` 订单管理 | — | AdminUser(Superuser) |

---

## API 端点

全部 `/api/v1/` 前缀。**不要在此文件中枚举端点 — 端点清单以 url 路由文件为准：**

- `backend/apps/knowledge/api/v1/urls.py` — 知识实体 + Graph + Search + 首页 + Dashboard + Knowledge Intake
- `backend/apps/commerce/api/v1/urls.py` — Product/SKU/Category/Document + AI工具 + Word解析 + FAQ + Related
- `backend/apps/transactions/api/v1/urls.py` — Basket/Order/Quote/Wishlist + Admin Order 操作
- `backend/apps/accounts/api/v1/urls.py` — 认证 + 组织
- `backend/apps/quotes/api/v1/urls.py` — QuoteRequest
- `backend/apps/assets/api/v1/urls.py` — PdfFile

### 本次迭代新增端点（截至 2026-06-21）

| 端点 | 用途 |
|------|------|
| `POST /products/parse-word/` | Word .docx 解析 → 预填字段 |
| `POST /products/<id>/validate/` | AI 产品校验 |
| `POST /products/<id>/recommend-protocols/` | AI 协议推荐 |
| `POST /products/<id>/recommend-literature/` | AI 文献推荐 |
| `POST /products/batch-validate/` | 批量 AI 校验 |
| `POST /products/batch-recommend-literature/` | 批量文献推荐 |
| `GET /admin/dashboard-stats/` | 工作台 12 项统计指标 |
| `POST /products/<id>/generate-seo/` | SEO 自动生成 |
| `POST /knowledge-intake` | 增强：JSON 校验预览 → 按依赖顺序写入 |

---

## 数据模型（最小摘要）

**核心链：** `ResearchGoal → Application → Method → Protocol → Product → SKU`
**桥接表：** ProductMethod, MethodProtocol, ProductReference, ProductCompatibility, ProductProduct
**关键字段：** Product.status (active/draft/discontinued), Product.display_priority (int, 越高越靠前), Product.structure_svg (必须经 sanitize_svg()), SKU.inventory_status, Protocol.ProtocolStep (FK 子步骤)

---

## 测试

```bash
cd backend
# 全量（996 passed, 10 skipped）
DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 venv/Scripts/python.exe -B -m pytest -p no:cacheprovider

# 单文件
DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 venv/Scripts/python.exe -B -m pytest apps/commerce/tests/test_word_parser.py -p no:cacheprovider
```

**必须加的环境变量：** `DB_ENGINE=sqlite`（避免 PostgreSQL 依赖）、`PYTHONDONTWRITEBYTECODE=1` + `-B`（避免 `__pycache__` 权限错误）、`-p no:cacheprovider`（避免 `.pytest_cache` 权限错误）。

**10 个 skipped 是 PostgreSQL 专用功能**（ArrayField, FTS），SQLite 下正常。

**throttle 在 development.py 中已禁用** — 测试中不会出现 "Request was throttled"。

---

## 开发启动

```bash
# 后端（Git Bash）
cd backend
DB_ENGINE=sqlite venv/Scripts/python.exe manage.py runserver
# → http://localhost:8000

# 前端（另一个终端）
cd frontend
npm run dev
# → http://localhost:5173（代理到 localhost:8000）
```

**不要用 `Start-Process` 或 `cmd.exe /c` 启动服务器** — 子进程无法可靠传递环境变量，Django 失败时无错误输出。在当前终端中直接运行。

---

## 坑（从实际错误中提炼）

1. **不要基于假设设计方案。** 先读取实际数据（Word 文档、数据库记录），再设计。这次 Word 导入踩过坑：110 个文档格式高度统一，正则即可，不需要置信度分档。
2. **研究员不是管理员。** 订单/发票/发货/客户联系 = 管理员；知识编辑/产品维护/发布 = 研究员。不要给研究员分配订单相关任务。
3. **产品编辑页是完整单元。** 不要拆成 Word 导入、AI 面板、知识关联三个 Phase 分次交付 — 拆分会产出"残疾的编辑页"。
4. **不要过度设计状态机。** 产品完整度只有完整/不完整两档，研究员需要知道的是"能不能发布"，不是 5 种中间状态。
5. **发布流程不要硬阻断。** 研究员是最终权威，系统只有建议权。不完整产品的发布按钮不禁用，只显示警告。
6. **SVG 输出必须走 `sanitize_svg()`。** 新 serializer 包含 `structure_svg` 时用 `SerializerMethodField` + `sanitize_svg()`。
7. **用户作用域查询集。** Quote/Wishlist/Order ViewSet 按 `request.user` 过滤 — staff 看全部，普通用户看自己，匿名看空。测试时必须 `force_authenticate()`。
8. **文件上传验证。** 用 `ALLOWED_UPLOAD_EXTENSIONS` 白名单 + `MAX_UPLOAD_SIZE_MB=10`，保存前调用 `_validate_uploaded_file()`。
9. **前端代理目标。** Dev proxy 是 `localhost:8001`，不是 8000。后端跑在 8000 时检查 `vite.config.js`。
10. **永远不要在项目目录创建含密码/密钥的文件。** 创建用户用 `manage.py createsuperuser`（交互式）。

---

## 新增内容操作指南

### 新 API 端点
1. 在 `apps/<app>/api/v1/views.py` 加 thin view
2. 业务逻辑放 `apps/<app>/services/`
3. Serializer 显式字段（禁止 `__all__`）
4. 在 `apps/<app>/api/v1/urls.py` 注册
5. 先写测试，再实现
6. 跑全量测试确认不破坏已有功能

### 新前端页面
1. `src/views/` 下创建（workspace 页面放 `views/workspace/`）
2. 在 `src/router/index.js` 加路由
3. API 调用放 `src/api/`（workspace 专属 API 放 `api/workspace/`）
4. 需要全局状态才加 Pinia store

### 新模型
1. 查 `docs/11_CODEX_RULES.md` — schema 变更需审批
2. 模型加在对应 `apps/<app>/models.py`
3. `makemigrations` + `migrate`
4. Serializer + ViewSet + 测试
5. **如果改了公开 API 面，更新此文件**

---

*最后更新: 2026-06-22 | 测试: 996 passed, 10 skipped, 0 failed | ~30个文件待提交*
