# 知识字段集成到产品编辑系统 — 详细计划

## 一、现状分析

### 现有产品编辑流程
```
前端 ProductEditPage → PUT /api/v1/products/{id} → ProductCreateUpdateSerializer
  ├── 保存 Product 基础字段 (24个)
  ├── 全量替换 SKU (删除旧的 + 创建新的)
  └── 不处理知识关联
```

### 知识关联当前状态
```
知识关联在独立的桥接表中:
  ProductMethod (Product ↔ Method)
  MethodProtocol (Method ↔ Protocol)
  ProductReference (Product ↔ Reference)

当前只能通过 KnowledgeIntake.vue 单独页面逐个填写
无法在产品编辑时一起设置
```

### 需要解决的问题
1. 产品编辑表单没有知识字段
2. 产品 API 不接受知识关联数据
3. 没有批量导入功能
4. SKU 更新是全量替换（风险）

---

## 二、变更范围

### 后端变更

| 文件 | 变更 | 影响 |
|------|------|------|
| `commerce/api/v1/serializers.py` | ProductCreateUpdateSerializer 增加知识字段 | 产品创建/更新 API |
| `commerce/api/v1/views.py` | ProductViewSet 可能需要调整 | 视图层 |
| `commerce/tests/test_product_knowledge.py` | 新建：知识字段 TDD 测试 | 测试覆盖 |
| `knowledge/api/v1/intake_views.py` | 可能废弃（功能合并到产品编辑） | 清理 |

### 前端变更

| 文件 | 变更 | 影响 |
|------|------|------|
| `views/products/ProductEditPage.vue` | 增加 3 个 section | 产品编辑表单 |
| `api/products.js` | 可能需要增加 API 函数 | API 层 |

### 不变的部分
- Product 模型（不加字段，知识在桥接表）
- ResearchGoal/Application/Method/Protocol 模型
- 桥接表模型（ProductMethod 等）
- 前端路由

---

## 三、TDD 实现计划

### Phase 1: 后端 — Serializer 支持知识字段

**测试先行：**

```python
# test_product_knowledge.py

class ProductKnowledgeSerializerTest(TestCase):
    """产品 Serializer 支持知识关联字段"""

    def test_create_product_with_methods(self):
        """创建产品时可以同时指定 methods"""
        # 传入 method_ids=[1, 2]，应该创建 ProductMethod 桥接

    def test_update_product_methods(self):
        """更新产品时可以修改 methods"""
        # 原来有 [1, 2]，更新为 [1, 3]，桥接表应该同步

    def test_create_product_with_protocols(self):
        """创建产品时可以同时指定 protocols"""

    def test_update_product_protocols(self):
        """更新产品时可以修改 protocols"""

    def test_create_product_with_research_goals(self):
        """创建产品时可以同时指定 research_goals"""

    def test_create_product_with_applications(self):
        """创建产品时可以同时指定 applications"""

    def test_knowledge_fields_in_response(self):
        """产品详情 API 返回知识关联数据"""

    def test_empty_knowledge_fields(self):
        """知识字段为空时不报错"""

    def test_invalid_method_id_ignored(self):
        """无效的 method_id 应该被忽略（不报错）"""
```

**实现：**
- ProductCreateUpdateSerializer 增加 `method_ids`, `protocol_ids`, `research_goal_ids`, `application_ids` 字段
- create() 方法中创建桥接记录
- update() 方法中同步桥接记录（增量更新，不是全量替换）

### Phase 2: 后端 — 批量导入 API

**测试先行：**

```python
class ProductBatchImportTest(TestCase):
    """批量导入产品 + 知识关联"""

    def test_import_csv_basic(self):
        """CSV 导入基本产品数据"""

    def test_import_csv_with_knowledge(self):
        """CSV 导入包含知识字段"""

    def test_import_creates_bridge_records(self):
        """导入后自动创建桥接记录"""

    def test_import_duplicate_catalog_no_updates(self):
        """重复 catalog_no 更新而非新建"""

    def test_import_invalid_rows_skipped(self):
        """无效行被跳过，不中断导入"""
```

**实现：**
- POST /api/v1/products/import/ 端点
- 接受 CSV 文件上传
- 解析后逐行创建/更新产品 + 桥接记录

### Phase 3: 前端 — ProductEditPage 增加知识字段

**在现有 ProductEditPage.vue 中增加 3 个 section：**

```
Section 5: Research Knowledge（研究知识）
  - Research Goals: 多选标签
  - Applications: 多选标签
  - Methods: 多选标签
  - Protocols: 多选下拉

Section 6: Content（内容）
  - Overview: textarea
  - Key Advantages: textarea
  - Key Limitations: textarea

Section 7: SEO（已有，保留）
  - SEO Title: input
  - SEO Description: textarea
```

### Phase 4: 前端 — 批量导入页面

**新建 ImportProducts.vue：**
- CSV 文件上传
- 预览导入数据
- 确认导入
- 显示导入结果

---

## 四、关联影响分析

### 风险点

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Serializer 变更影响现有 API | 前端调用可能报错 | 新字段全部 optional |
| 桥接表同步逻辑复杂 | 数据不一致 | 用事务包裹，失败回滚 |
| SKU 全量替换已有风险 | 现有 SKU 丢失 | 保持现有逻辑不变（不在本次修改） |
| 批量导入数据量大 | 超时 | 分批处理，返回进度 |

### 不影响的部分

- 产品列表 API（GET /products/）
- 产品详情 API（GET /products/:id/detail/）
- 搜索 API
- 知识图谱 API
- 首页 API
- 前端其他页面

---

## 五、执行顺序

```
Step 1: 写测试 (test_product_knowledge.py)
Step 2: 修改 ProductCreateUpdateSerializer
Step 3: 运行测试，确认通过
Step 4: 修改 ProductEditPage.vue 增加知识字段
Step 5: 前端构建验证
Step 6: 写批量导入测试
Step 7: 实现批量导入 API
Step 8: 创建 ImportProducts.vue
Step 9: 全量测试
Step 10: 提交
```
