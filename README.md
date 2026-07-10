# 试剂网站AI化腾讯版 (SciReagent Tencent)

> LabPro Global — AI-Native Scientific Reagent Platform for Nucleotides & Click Chemistry

## 项目概述

基于 12 章升级文档重新构建的科学试剂电商平台，核心链路：

```
Research Goal → Application → Method → Protocol → Product → SKU → Order
```

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Composition API + Vite + Element Plus + Tailwind CSS |
| 后端 | Django 5.1 + Django REST Framework 3.15 |
| 数据库 | PostgreSQL |
| 缓存 | Redis (可选) |
| 部署 | Docker Compose |

## 项目结构

```
scireagent-tencent/
├── backend/                 # Django 后端
│   ├── config/              # Django 项目配置 (settings, urls, wsgi)
│   ├── apps/
│   │   ├── knowledge/       # 知识层 (ResearchGoal, Application, Method, Protocol, Reference, Compatibility)
│   │   ├── commerce/        # 商务层 (Product, SKU, Order, Quote, Basket, Wishlist)
│   │   ├── assets/          # 资产层 (PdfFile, Image)
│   │   └── accounts/        # 账户层 (User, Customer)
│   ├── services/            # 跨 app Service Layer
│   ├── serializers/         # 公共序列化器
│   ├── tests/               # 测试
│   └── manage.py
├── frontend/                # Vue 3 前端
├── docs/                    # 12 章升级文档
├── docker/                  # Docker 配置
├── scripts/                 # 脚本工具
└── README.md
```

## 开发阶段

| Phase | 内容 | 状态 |
|---|---|---|
| Phase 1 | 数据库 & 知识层基础 | 🚧 进行中 |
| Phase 2 | 前端升级 & Application Center | ⏳ 待开始 |
| Phase 3 | Method Center | ⏳ 待开始 |
| Phase 4 | Protocol Center | ⏳ 待开始 |
| Phase 5 | Agent Layer (JSON-LD/MCP) | ⏳ 待开始 |

## 快速开始

### 后端

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
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

## 文档

详细的设计文档位于 `docs/` 目录，共 12 章：

1. Product Vision
2. System Architecture
3. Domain Model
4. Database Architecture
5. Frontend PRD
6. Backend API Spec
7. Research Knowledge Graph
8. Application / Method / Protocol Spec
9. AI Agent Integration Spec
10. Roadmap
11. Codex Rules
12. Design System

## 许可证

Private — 仅限内部使用
