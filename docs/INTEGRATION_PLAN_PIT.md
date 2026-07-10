# Product Intake Tool 集成实施计划

## 目标
将 product-intake-tool 的产品管理功能完整集成到 SciReagent，采用 TDD 方式（测试先行）。

## 技术决策
- 方案：字段合并（PIT 字段合并到 SciReagent 模型）
- 化学结构渲染：RDKit.js（前端 WASM，CDN 加载）
- 国际化：保留中英双语
- 认证：统一使用 Django Token Auth

---

## Phase 0: 模型扩展（后端基础）

### 0.1 Product 模型扩展

需要新增的字段（从 PIT 合并）：

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `catalog_no` | CharField(64), unique, nullable | null | 产品目录号 SC8111 |
| `formula` | CharField(256) | '' | 分子式 |
| `molecular_weight` | FloatField, nullable | null | 分子量 (g/mol) |
| `inchi` | TextField | '' | InChI 标识符 |
| `concentration` | CharField(64) | '' | 产品级浓度 |
| `overview` | TextField | '' | 产品概述（纯文本） |
| `structure_svg` | TextField | '' | SMILES 渲染 SVG |
| `research_use_only` | BooleanField | True | 仅供研究使用 |
| `seo_title` | CharField(256) | '' | SEO 标题 |
| `seo_description` | TextField | '' | SEO 描述 |
| `category_l1` | CharField(128) | '' | 一级分类 |
| `category_l2` | CharField(128) | '' | 二级分类 |
| `handling_notes` | TextField | '' | 操作注意事项 |
| `shelf_life` | CharField(128) | '' | 保质期 |

需要修改的字段：
| 字段名 | 当前类型 | 新类型 | 原因 |
|--------|---------|--------|------|
| `molecular_weight` | CharField | FloatField | 数值类型更合理 |

### 0.2 SKU 模型扩展

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `concentration` | CharField(64) | '' | SKU 级浓度 |
| `stock_status` | CharField(20) | 'IN_STOCK' | 统一枚举：IN_STOCK/LIMITED/PREORDER/OUT_OF_STOCK |
| `lead_time` | CharField(64) | '' | 交货时间文本 |
| `is_default` | BooleanField | False | 默认 SKU |

### 0.3 ProductDocument 模型（新建）

```
ProductDocument
├── product → Product (FK)
├── document_type: Datasheet / MSDS / COA / ApplicationNote
├── language: CharField(16), default='en'
├── version: CharField(16), default='1.0'
├── file: FileField
├── original_filename: CharField(256)
├── created_at: DateTimeField
```

---

## Phase 1: 后端测试用例（先写）

### 1.1 模型测试 (`tests/test_product_extended.py`)

```
TC-P-001: Product 创建时 catalog_no 可以为 null
TC-P-002: Product catalog_no 设置后必须唯一
TC-P-003: Product formula 字段可存储分子式如 "C11H12N2O5"
TC-P-004: Product molecular_weight 存储浮点数（如 283.24）
TC-P-005: Product inchi 可存储完整 InChI 字符串
TC-P-006: Product research_use_only 默认为 True
TC-P-007: Product category_l1 存储一级分类标识
TC-P-008: Product category_l2 存储二级分类（可含 L3 拼接）
TC-P-009: Product overview 可存储 5000 字符文本
TC-P-010: Product structure_svg 可存储 SVG XML
TC-P-011: Product seo_title 自动生成逻辑
TC-P-012: Product seo_description 自动生成逻辑
```

### 1.2 SKU 测试 (`tests/test_sku_extended.py`)

```
TC-S-001: SKU stock_status 枚举值 IN_STOCK 有效
TC-S-002: SKU stock_status 枚举值 LIMITED 有效
TC-S-003: SKU stock_status 枚举值 PREORDER 有效
TC-S-004: SKU stock_status 枚举值 OUT_OF_STOCK 有效
TC-S-005: SKU stock_status 非法值拒绝
TC-S-006: SKU is_default 同一 Product 下只能有一个 default
TC-S-007: SKU concentration 字段存储如 "100 mM"
TC-S-008: SKU lead_time 字段存储如 "1-3 business days"
```

### 1.3 ProductDocument 测试 (`tests/test_product_document.py`)

```
TC-D-001: ProductDocument 创建关联 Product
TC-D-002: ProductDocument type 为 DATASHEET
TC-D-003: ProductDocument type 为 MSDS
TC-D-004: ProductDocument type 为 COA
TC-D-005: ProductDocument type 为 ApplicationNote
TC-D-006: ProductDocument language 默认 'en'
TC-D-007: ProductDocument version 默认 '1.0'
TC-D-008: ProductDocument file 上传 PDF
TC-D-009: ProductDocument 删除不影响 Product
```

### 1.4 API 测试 (`tests/test_product_crud_api.py`)

```
TC-API-001: POST /api/v1/products 创建产品（含新字段）
TC-API-002: POST /api/v1/products 创建产品（不含 catalog_no，自动生成）
TC-API-003: POST /api/v1/products catalog_no 重复返回 400
TC-API-004: PUT /api/v1/products/{id} 更新产品所有新字段
TC-API-005: GET /api/v1/products/{id} 返回新字段
TC-API-006: GET /api/v1/products 列表包含新字段摘要
TC-API-007: POST /api/v1/products 带 SKU 数组创建
TC-API-008: PUT /api/v1/products/{id} 替换 SKU 数组
TC-API-009: POST /api/v1/products/{id}/documents 上传文档
TC-API-010: GET /api/v1/products/{id}/documents 获取文档列表
TC-API-011: DELETE /api/v1/products/{id}/documents/{doc_id} 删除文档
TC-API-012: POST /api/v1/products 带 category_l1/l2 创建
TC-API-013: GET /api/v1/products?category_l1=nucleotides 筛选
TC-API-014: POST /api/v1/products research_use_only 默认 True
TC-API-015: PUT /api/v1/products/{id} 更新 structure_svg
```

### 1.5 产品编辑权限测试 (`tests/test_product_editor_permissions.py`)

```
TC-PERM-001: Editor 角色可以创建产品
TC-PERM-002: Editor 角色可以编辑产品
TC-PERM-003: Editor 角色不能访问订单
TC-PERM-004: Researcher 角色不能创建产品
TC-PERM-005: Admin 角色可以执行所有产品操作
TC-PERM-006: 未认证用户不能创建产品
TC-PERM-007: 未认证用户可以查看已发布产品
```

### 1.6 SEO 自动生成测试 (`tests/test_seo_generation.py`)

```
TC-SEO-001: 产品名 + 纯度 → 自动生成 seo_title
TC-SEO-002: 产品名 + 分类 → 自动生成 seo_description
TC-SEO-003: 产品名 → 自动生成 slug（英文小写+连字符）
TC-SEO-004: catalog_no + 产品名 → slug 格式正确
TC-SEO-005: 中文产品名 → slug 使用拼音或 catalog_no
TC-SEO-006: slug 唯一性（重复 slug 自动加后缀）
```

### 1.7 分类体系测试 (`tests/test_categories.py`)

```
TC-CAT-001: category_l1 有效值（9 大类）
TC-CAT-002: category_l1 无效值拒绝
TC-CAT-003: category_l2 属于对应 l1 的子类
TC-CAT-004: category_l2 可包含 L3 拼接（如 "click_chemistry | 5-Formyl"）
TC-CAT-005: 按 category_l1 筛选产品列表
TC-CAT-006: 按 category_l2 筛选产品列表
```

---

## Phase 2: 后端实现

### 2.1 迁移文件
- `0004_product_extended_fields.py` — Product 新增字段
- `0005_sku_extended_fields.py` — SKU 新增字段
- `0006_productdocument.py` — 新建 ProductDocument 模型

### 2.2 Serializer 更新
- ProductSerializer：添加所有新字段
- ProductCreateSerializer：支持嵌套 SKU 创建
- ProductDocumentSerializer：文档 CRUD
- CategorySerializer：分类体系数据

### 2.3 View 更新
- ProductViewSet：扩展 CRUD 支持新字段
- ProductDocumentViewSet：文档上传/列表/删除
- CategoryView：返回分类树

### 2.4 SEO Service
- `seo_service.py`：从 PIT 移植，适配 Django

---

## Phase 3: 前端产品编辑页面

### 3.1 前端测试用例

```
TC-FE-001: 产品编辑页加载，显示所有字段分组
TC-FE-002: 基本信息区：catalog_no, product_name, synonyms, cas_number
TC-FE-003: 化学结构区：SMILES 输入 → RDKit.js 渲染 SVG 预览
TC-FE-004: 化学结构区：InChI 输入
TC-FE-005: 科学参数区：formula, molecular_weight, purity, concentration
TC-FE-006: 科学参数区：storage, shipping_condition, shelf_life, handling_notes
TC-FE-007: 分类区：category_l1 下拉选择 → category_l2 联动
TC-FE-008: 分类区：category_l3 自由文本输入
TC-FE-009: 应用领域区：多选 checkbox（17 个预设）
TC-FE-010: 产品描述区：overview textarea（5000 字符限制 + 字数统计）
TC-FE-011: SKU 表格：动态增删行
TC-FE-012: SKU 表格：package_size → 自动拆分 amount + unit
TC-FE-013: SKU 表格：stock_status 下拉选择
TC-FE-014: SKU 表格：is_default 单选标记
TC-FE-015: 文档上传区：拖拽上传 PDF/PNG/SVG
TC-FE-016: 文档上传区：文档类型选择（Datasheet/MSDS/COA/Note）
TC-FE-017: 实时预览面板：右侧显示产品详情预览
TC-FE-018: 表单验证：必填字段为空显示错误
TC-FE-019: 表单验证：CAS 号格式校验
TC-FE-020: 表单验证：分子量必须为正数
TC-FE-021: 保存成功后跳转到产品详情页
TC-FE-022: 编辑模式：加载已有数据回填
TC-FE-023: 国际化：中英文切换
TC-FE-024: research_use_only 开关
TC-FE-025: SEO 字段自动生成（只读展示）
```

### 3.2 前端组件结构

```
src/views/products/
├── ProductEditPage.vue        # 产品编辑页（新建+编辑）
├── components/
│   ├── BasicInfoSection.vue   # 基本信息
│   ├── StructureSection.vue   # 化学结构（SMILES + RDKit.js 渲染）
│   ├── ScientificParams.vue   # 科学参数
│   ├── CategorySection.vue    # 分类选择（L1/L2/L3 级联）
│   ├── ApplicationsSection.vue # 应用领域多选
│   ├── DescriptionSection.vue # 产品描述
│   ├── SkuTable.vue           # SKU 动态表格
│   ├── DocumentUpload.vue     # 文档上传
│   ├── SeoSection.vue         # SEO 信息（只读）
│   └── ProductPreview.vue     # 实时预览面板
```

### 3.3 RDKit.js 集成
- CDN 加载：`https://unpkg.com/rdkit-js@latest/dist/RDKit_minimal.js`
- 懒加载：只在产品编辑页加载 WASM
- 封装 composable：`src/composables/useRdkit.js`
- 功能：SMILES → SVG 渲染、分子式验证、分子量计算

---

## Phase 4: 数据迁移

### 4.1 PIT 数据导出脚本
- 从 PIT 的 Supabase PostgreSQL 导出产品数据为 JSON
- 字段映射：PIT 字段名 → SciReagent 字段名
- `package_size` 解析：正则 "10 uL" → amount=10, unit="uL"

### 4.2 SciReagent 数据导入脚本
- Django management command：`import_pit_products`
- 逐条导入，跳过已存在的 catalog_no
- JSON applications → M2M Application 关联

---

## Phase 5: E2E 测试

```
TC-E2E-001: Editor 登录 → 进入产品编辑页 → 填写完整表单 → 保存 → 产品详情页显示正确
TC-E2E-002: 输入 SMILES → RDKit.js 渲染 SVG 预览 → 保存后详情页显示结构图
TC-E2E-003: 创建产品含多个 SKU → 产品详情页显示 SKU 列表
TC-E2E-004: 上传文档 → 文档列表显示 → 可下载
TC-E2E-005: 按分类筛选产品 → 结果正确
TC-E2E-006: 中英文切换 → 字段标签语言变化
TC-E2E-007: Researcher 尝试编辑产品 → 403 Forbidden
TC-E2E-008: 产品状态切换（Draft → Published）→ 前台可见
TC-E2E-009: 批量导入 → 所有产品正确创建
TC-E2E-010: 产品搜索（名称/CAS/目录号）→ 结果正确
```

---

## 实施顺序

```
Phase 0 (模型扩展) → Phase 1 (写测试) → Phase 2 (后端实现)
                                          ↓
                                    Phase 3 (前端实现)
                                          ↓
                                    Phase 4 (数据迁移)
                                          ↓
                                    Phase 5 (E2E 测试)
```

## 估算工作量

| Phase | 后端 | 前端 | 测试 | 总计 |
|-------|------|------|------|------|
| 0 模型扩展 | 2h | - | - | 2h |
| 1 测试用例 | 3h | 2h | - | 5h |
| 2 后端实现 | 6h | - | 1h | 7h |
| 3 前端实现 | - | 10h | 2h | 12h |
| 4 数据迁移 | 3h | - | 1h | 4h |
| 5 E2E 测试 | - | 2h | 3h | 5h |
| **总计** | **14h** | **14h** | **7h** | **35h** |
