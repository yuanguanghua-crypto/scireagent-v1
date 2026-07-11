# SciReagent Design Standards

> **唯一权威设计文档** — 全局设计系统 + 各页面设计指引
> 所有设计规范、组件规则、页面布局标准均以此文档为准。
> 修改或新增设计规范时，必须同时更新此文档。
> 最后更新：2026-07-10

---

# Part I — Global Design System

## 1. Brand & Philosophy

**精确 · 冷峻 · 高效**

| 维度 | 定义 |
|------|------|
| **品牌定位** | 精确冷峻、创新有特色，非传统生物试剂风格。像实验室笔记本：每个元素都有目的，不为装饰而装饰 |
| **目标用户** | 科研人员、实验室管理者——需要快速扫描信息密度高的页面，信任数据透明度 |
| **设计语气** | Professional distance, scientific seriousness. 不是通用电商 |

**设计原则**：
- **Precise** — 结构精确，每像素有意义
- **Efficient** — 信息密度高但有序，视觉权重决定层级
- **Consistent** — 相同内容在不同页面保持一致的视觉语言

---

## 2. Color System

### 2.1 Core Palette

| Token | Hex | oklch | Usage |
|-------|-----|-------|-------|
| `--color-primary` | `#047857` | — | 主色，emerald-700。Primary actions, links, brand（2026-07-11 由 emerald-600 #059669 加深以满足 WCAG AA 4.5:1） |
| `--color-primary-hover` | `#047857` | — | Primary hover |
| `--color-primary-light` | `#D1FAE5` | — | Primary background tint |
| `--color-primary-subtle` | `#ECFDF5` | — | Subtle bg (row hover, etc.) |
| `--color-accent` | `#D97706` | oklch(0.655 0.155 75) | 强调色，amber。CTAs, highlights |
| `--color-accent-hover` | `#B45309` | — | Accent hover |
| `--color-accent-light` | `#FEF3C7` | — | Accent background tint |

### 2.2 Neutral Scale (Cold Gray)

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-text` | `#0F172A` | Headings, primary text |
| `--color-text-secondary` | `#475569` | Body text, labels |
| `--color-text-tertiary` | `#94A3B8` | Placeholder, disabled, meta |
| `--color-border` | `#CBD5E1` | Borders, dividers |
| `--color-border-light` | `#E2E8F0` | Light borders, subtle dividers |
| `--color-bg` | `#F1F5F9` | Surface alt background |
| `--color-surface` | `#FFFFFF` | Card, panel background |

### 2.3 Semantic Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-success` | `#22C55E` | Active, in-stock (status dot) |
| `--color-warning` | `#F59E0B` | Limited, draft, preorder (status dot) |
| `--color-info` | `#3B82F6` | Informational |
| `--color-danger` | `#DC2626` | Error, discontinued |
| `--color-gray` | `#9CA3AF` | Default/unknown status dot |

### 2.4 Knowledge Entity Colors (Desaturated)

用于知识实体卡片图标背景和标签：

| Entity | Hex | Usage |
|--------|-----|-------|
| Research Goal (RG) | `#A78BEF` | Tag, card icon bg |
| Application (App) | `#6BC4A0` | Tag, card icon bg |
| Method (Met) | `#7AAEDB` | Tag, card icon bg |
| Protocol (Pro) | `#C9A34E` | Tag, card icon bg |
| Product (Prd) | `#D47C7C` | Tag, card icon bg |

---

## 3. Typography

### 3.1 Font Stack

```css
--font-sans: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Monaco', monospace;
```

全英文站点，无中文。

### 3.2 Type Scale

| Level | Size | Weight | Line-height | Usage |
|-------|------|--------|-------------|-------|
| Product name | 32px | 800 | 1.15 | Product detail page title |
| h2 / section title | 24px | 700 | 1.3 | Section headings |
| h3 | 20px | 600 | 1.35 | Card titles, subsections |
| Body | 14px | 400 | 1.6 | Default body text |
| Caption | 12px | 500 | 1.5 | Metadata, labels |
| Micro / label | 11px | 600–700 | 1.4 | Uppercase labels, table headers, property labels |
| Mono | 12px | 400 | 1.5 | SMILES, CAS, catalog numbers |
| Mono-sm | 11px | 400 | 1.45 | Small code, SKU codes |

### 3.3 Chemical Typography Rules

- **CAS numbers / SMILES / catalog codes**: `font-family: var(--font-mono); font-size: 12px;`
- **Product codes** (e.g., SC8003): mono font, 600 weight
- **Purity / prices**: `font-variant-numeric: tabular-nums;`

---

## 4. Spacing & Layout

### 4.1 Baseline Grid

**8px baseline grid.** 所有间距值为 8px 的倍数。

| Value | Usage |
|-------|-------|
| 4px | Tight inline, icon gap |
| 8px | Inner padding, small gaps |
| 12px | Between related elements |
| 16px | Card inner padding, button padding |
| 20px | Between sections (tight) |
| 24px | Card gap, section spacing |
| 32px | Between major sections |
| 40px | Page section top/bottom |

### 4.2 Layout Principles

- **最大内容宽度**: 1200px，水平居中
- **两栏布局**: `grid-template-columns: 1fr 1fr; gap: 32px;`，≤768px 折叠为单栏
- **水平间距**: 页面两侧 padding 32px

---

## 5. Motion

| Token | Value | Usage |
|-------|-------|-------|
| Easing | `cubic-bezier(0.22, 1, 0.36, 1)` | ease-out, no bounce |
| Fast | 0.15s | Hover, active states |
| Normal | 0.2s | Color transitions, borders |
| Slow | 0.3s | Page content fade-in |

不使用的动效：弹性缓动 (bounce)、布局属性动画、毛玻璃过度。

---

## 6. Common Components

### 6.1 Buttons

- **Border radius**: 4px（所有尺寸统一）
- **Sizes**: LG 44px / MD 36px / SM 28px
- **Variants**:
  - **Primary**: emerald (`--color-primary`) fill, white text
  - **CTA**: amber (`--color-accent`) fill, white text — 用于关键转化操作
  - **Outline**: transparent bg, `1px solid var(--color-border)`, `var(--color-text)` text
- **Disabled**: `opacity: 0.5; pointer-events: none;`

### 6.2 Cards

| Property | Value |
|----------|-------|
| Border radius | 4px |
| Border | `1px solid var(--color-border)` |
| Background | `var(--color-surface)` |
| Hover | `translateY(-2px)`, border tint to `--color-primary` |
| Transition | 0.15s ease-out |

### 6.3 Status Badges

**不使用**彩色背景。所有状态标签统一为中性灰边框风格：

```css
background: var(--color-bg);
color: var(--color-text-secondary);
border: 1px solid var(--color-border-light);
```

语义通过 6px `::before` 伪元素圆点传达：

| Status | Dot Color |
|--------|-----------|
| active / in_stock | `#22C55E` |
| limited / draft / preorder | `#F59E0B` |
| (other / default) | `#9CA3AF` |

### 6.4 Property List (Label/Value)

用于展示产品属性或实体元数据：
- **布局**: 2-column grid — `100px label | 1fr value`，3px gap rows
- **分组标题**: 11px uppercase, 700 weight, 底部 border 分隔线
- **标签色**: `--color-text-tertiary`
- **值色**: `--color-text`

### 6.5 Icons

- **Library**: Lucide Icons, `stroke-width: 2`, clean consistent
- **Size scale**: 16px (inline/badges), 18px (nav items), 24px (default/cards)

---

## 7. Dark Mode

正式支持，通过 CSS 自定义属性语义映射。Light 和 Dark 共用同一套 token 结构，只换值：

| Light Token → | Dark Value |
|---------------|-----------|
| `--color-surface` (white) | `#1E293B` |
| `--color-bg` (`#F1F5F9`) | `#0F172A` |
| `--color-border` (`#CBD5E1`) | `#334155` |
| `--color-text` (`#0F172A`) | `#F1F5F9` |
| `--color-text-secondary` (`#475569`) | `#94A3B8` |
| `--color-primary` (`#047857`) | `#34D399` (lighter emerald) |

Toggle 方式：`prefers-color-scheme` media query + 用户手动切换。

---

# Part II — Page Design Guides

> 每个页面的具体布局、组件规范、交互模式和响应式规则见对应章节。
> 页面设计中的通用组件（按钮/卡片/标签/属性列表等）以 Part I 为准。

## Product Detail Page

页面路径：`/products/:id` | 组件：`ProductDetail.vue`

### Layout Architecture

```
Full-width Header
├── Breadcrumb (Products / {product_class_path})
├── Product Name (32px, 800 weight)
└── Tags (Catalog No | CAS) — mono font chips

Two-Column Grid (1fr 1fr, gap 32px)
├── Left Column
│   ├── Structure Row (flex: 280px fixed + description)
│   │   ├── Structure Box (280x220px, border, rounded)
│   │   └── Description Column
│   │       ├── Category tag
│   │       ├── Status + RUO badges
│   │       ├── Overview paragraph
│   │       └── "Also known as" synonyms
│   └── Property List
│       ├── Chemical Identity group
│       └── Specifications group
│
└── Right Column
    ├── SKU Table (6 columns grid)
    ├── SKU Bottom Bar (SDS + Request Quote)
    └── Related Products (auto-fill grid)

Second Screen: Knowledge Tabs
├── Tab Bar (underline active style)
└── Tab Content (card-style items per entity type)

Bottom Section
├── Handling Notes
└── Unified CTA
```

### Component Specifications

#### SKU Table

Grid columns（header 和 rows 必须严格一致）：

| Column | Width | Align | Content |
|--------|-------|-------|---------|
| SKU | 120px | left | `sku_code` in mono font |
| Pack Size | 80px | left | `pack_size` text |
| Price | 75px | left | `formatCurrency()` — 700 weight, tabular-nums |
| Status | 65px | left | Badge with semantic dot (§6.3) |
| COA | 55px | **center** | Icon button or `—` placeholder |
| Actions | `1fr` | right | Qty selector + "Add to Cart" |

- Table: border, border-radius, overflow hidden
- Row hover: `var(--color-primary-subtle)` background
- COA header: `.pd-coa-header { text-align: center }`
- COA cell: 28x28px icon button, centered flex
- COA "—" placeholder when no document exists for SKU

#### Property List

- Groups: **Chemical Identity** (SMILES, InChI, CAS, Formula, MW) + **Specifications** (Purity, Conc., Storage, Shipping, Lead Time)
- InChI truncation at 100 chars, "Show full" / "Collapse" toggle button

#### Structure Box

- Fixed: 280×220px, flex centering
- Fallback chain: RDKit client-side SVG → server `structure_svg` → SMILES text → "No structure"

#### Document Display (COA / SDS)

**COA (SKU-level)**: Icon button in SKU table COA column, opens preview via `openPreview('coa', coa)`

**SDS (Product-level)**: Two-button group in SKU table bottom bar:
```
[SDS | High] [ ↓ ]   Request Quote
```
- Preview button with confidence badge inside (`.pd-sds-conf`: 10px pill, border)
- Download icon button (separate, calls `downloadSds()`)
- Bottom bar: flex row, 12px gap, top border separator from SKU table

#### Related Products Grid

- **CSS**: `grid-template-columns: repeat(auto-fill, minmax(150px, 1fr))`
- **Adaptive count** (前端计算，非后端硬编码):
  - ResizeObserver 测量容器宽度
  - `cols = floor((width + 8) / 158)`
  - `displayCount = floor(pool / cols) * cols` — 取列数整数倍，避免不完整最后一行
  - Pool: `min(10, available)`. Fallback: `min(items.length, 6)`.
- Card: 8px padding, surface bg, border, hover primary border color

#### Knowledge Tabs

| Tab | Card Icon Color | Icon |
|-----|----------------|------|
| Applications | `#6BC4A0` | Clock SVG |
| Methods | `#7AAEDB` | Wrench SVG |
| Protocols | `#C9A34E` | Document SVG |
| References | — | Title + Journal/Year + DOI link |
| FAQ | `#A78BEF` | Question mark SVG, click-to-expand |

- Tab active style: **underline** (NOT filled bg)
- Tab hover: subtle bg change

#### Breadcrumb

- Inline flex, `Products / {class_path}` format
- Root link: primary color. Separator `/`: tertiary color
- Uses `product.product_class_path` array

#### CTA (UnifiedCTA)

- Title: "Request this Product" (NOT "Need this product?")
- Outline style: `1px solid var(--color-border)`, surface background
- Positioned at page bottom, after all content

### Responsive Behavior

| Viewport | Layout |
|----------|--------|
| > 768px | Two columns (1fr 1fr) |
| ≤ 768px | Single column; structure row stacks vertically; SKU grid → flex wrap |

### Data Dependencies

| API Field | Where Used |
|-----------|-----------|
| `product.name` | Page title (h1, 32px) |
| `product.catalog_no` / `product.cas` | Header tags |
| `product.product_class_path` | Breadcrumb |
| `product.smiles` / `product.structure_svg` | Structure box |
| `product.overview` | Description |
| `product.synonyms` | "Also known as" |
| `product.purity/concentration/storage/shipping/lead_time` | Specifications group |
| `product.skus` | SKU table |
| `detail.related_products` (limit=10) | Related Products grid |
| `detail.applications/methods/protocols/references/faq` | Knowledge Tabs |
| `documentsApi.getSdsList(productId)` | SDS preview + download |
| `documentsApi.getCoaList({ product_id, status:'published' })` | COA per SKU |

---

# Part III — Design Changelog

| Date | Change | Section |
|------|--------|---------|
| 2026-07-09 | 品牌定位确认 (精确冷峻) | §1 |
| 2026-07-09 | 主色 teal → emerald; 强调色 amber; 冷灰中性色 | §2 |
| 2026-07-11 | 主色 emerald-600(#059669) → emerald-700(#047857) 以满足 WCAG AA 4.5:1；text-tertiary gray-400→gray-500；success emerald-600→emerald-700 | §2 |
| 2026-07-09 | 字体 Inter + JetBrains Mono; 字号表 11/12/14/20/24/32px | §3 |
| 2026-07-09 | 间距 8px 基线网格; 两栏布局 | §4 |
| 2026-07-09 | 动效 ease-out(0.22,1,0.36,1); 0.15s/0.2s/0.3s | §5 |
| 2026-07-09 | 按钮 4px 圆角, Primary/CTA/Outline; 卡片 4px + hover 上移 | §6 |
| 2026-07-09 | 状态标签 → 中性 border + 语义色圆点 (非彩色背景) | §6.3 |
| 2026-07-09 | 知识实体降饱和色: RG#A78BEF/App#6BC4A0/Met#7AAEDB/Pro#C9A34E/Prd#D47C7C | §2.4 |
| 2026-07-09 | 暗色模式正式支持 | §7 |
| 2026-07-09 | 产品详情页左-右两栏布局 + Knowledge Tabs | Part II |
| 2026-07-10 | Related Products 自适应网格 (视口驱动, 非后端硬编码) | Part II |
| 2026-07-10 | COA 列居中对齐; SDS 预览+下载双按钮 | Part II |
| 2026-07-10 | 设计规范合并为本文档 | — |

---

*本文档取代以下历史文件: `docs/design/DESIGN_SYSTEM.md`, `docs/13_PRODUCT_DETAIL_DESIGN.md`*
