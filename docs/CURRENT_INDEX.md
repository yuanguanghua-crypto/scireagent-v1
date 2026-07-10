# 当前文档导航（Current Documentation Index）

> 此文件替代 `00_MASTER_INDEX.md` 作为项目开发、编码决策和 AI 助手的文档入口。
> 仅包含基于当前代码库实际实现的权威文档，已过时的初始设计文档不再列入。
>
> 更新日期：2026-06-27

---

## 阅读优先级

| 优先级 | 文档 | 用途 | 权威性 |
|:------:|------|------|:------:|
| ⭐⭐⭐ | [`../CLAUDE.md`](../CLAUDE.md) | **唯一入口** — 技术栈锁定、目录结构、架构铁律、权限速查、测试命令、坑记录 | 最高 |
| ⭐⭐⭐ | [`KNOWLEDGE_ASSETS.md`](KNOWLEDGE_ASSETS.md) | 知识图谱体系：实体分类、关联关系、生成机制、校验机制 | 高 |
| ⭐⭐⭐ | [`AI_AUTO_MATCH.md`](AI_AUTO_MATCH.md) | AI AUTO MATCH 功能技术文档：四数据源 + 降级策略 + 前端交互 | 高 |
| ⭐⭐⭐ | [`COA_SDS.md`](COA_SDS.md) | COA/SDS 文档自动生成：数据依赖、工作流、SDS 三级降级链 | 高 |
| ⭐⭐ | [`KNOWLEDGE_ROADMAP.md`](KNOWLEDGE_ROADMAP.md) | 优化待办清单（P0/P1/P2 分级），完成后条目移入 KNOWLEDGE_ASSETS.md | 中 |

> **关于 AI 编码**：每次新会话开始时，必须先读 `CLAUDE.md`，再根据具体任务读相关功能文档。不要读 01-12 号初始设计文档做决策。

---

## 文档关系图

```
CLAUDE.md (唯一入口 · 架构铁律)
    │
    ├──► AI_AUTO_MATCH.md (预填引擎)
    │       │
    │       └──► COA_SDS.md (下游交付 · SDS 依赖 AI 数据源)
    │
    ├──► KNOWLEDGE_ASSETS.md (知识资产基座)
    │       │
    │       └──► KNOWLEDGE_ROADMAP.md (演进待办)
    │
    └──► 代码库 (models · services · views · serializers · tests)
```

---

## 过时文档说明

以下文件是项目初始设计阶段的思路草案（2026-06-11），已废弃：

| 文件 | 说明 |
|------|------|
| `00_MASTER_INDEX.md` | 本文件就是旧导航总纲，已被 CURRENT_INDEX.md 替代 |
| `01_PRODUCT_VISION.md` ~ `12_DESIGN_SYSTEM.md` | 初始设计思路草案 |
| `specifications/` 目录 | 初始规格文档 |
| `design/DESIGN_SYSTEM.md` | 早期设计系统草案 |

**这些文档仅供历史参考，不应作为编码决策的依据。** 如果其中的内容与当前代码库或权威文档（上表）冲突，以权威文档为准。

---

## 按任务类型的快速导航

| 任务类型 | 入口文档 | 关键文件 |
|----------|----------|----------|
| 新增 API 端点 | `AI_AUTO_MATCH.md` §5 | `apps/<app>/api/v1/views.py` |
| 修改数据模型 | `KNOWLEDGE_ASSETS.md` §2-4 | `apps/<app>/models.py` |
| 知识图谱相关 | `KNOWLEDGE_ASSETS.md` §3-5 | `apps/knowledge/models.py` |
| COA/SDS 功能 | `COA_SDS.md` | `apps/documents/services/workflow.py` |
| AI 工具开发 | `AI_AUTO_MATCH.md` §5 | `apps/commerce/services/validators/` |
| 前端页面 | `AI_AUTO_MATCH.md` §6 | `frontend/src/views/workspace/` |
| 桥接表/关联 | `KNOWLEDGE_ASSETS.md` §3.2 | `apps/bridges/models.py` |
| 测试 | `CLAUDE.md` 测试章节 | `apps/<app>/tests/` |
| 架构决策 | `CLAUDE.md` 架构铁律 | 所有 `core/` 和 `config/` 文件 |

---

*CURRENT_INDEX.md 日期：2026-06-27 | 替代 00_MASTER_INDEX.md 作为编码决策入口*