# Chapter 12 Design System

## Document Authority

This chapter defines the design system for LabPro Global.
It provides the visual, typographic, layout, and interaction language that the frontend must use when rendering the scientific graph and commerce flows.

If a later UI or styling note conflicts with this chapter on tokens, component styling, hierarchy, or interaction language, this chapter wins on design-system intent and the later note must be adjusted.

This chapter is intentionally concrete:

- It defines the visual direction.
- It defines the core tokens and layout rules.
- It defines the reusable component language.
- It defines tables, cards, tabs, and protocol presentation rules.
- It defines states, responsiveness, and content hierarchy.

## 1. Design System Mission

The design system must make the LabPro Global platform feel like a scientific capability platform rather than a generic storefront.

It must support:

- Scientific credibility
- Clear product evaluation
- Efficient commerce workflows
- Dense but readable technical content
- Mobile and desktop usability
- Consistent rendering across applications, methods, protocols, products, and resources

## 2. Design Principles

### 2.1 Scientific Clarity

- The UI should feel precise, structured, and technical.
- Scientific content should be legible at a glance.

### 2.2 Commercial Confidence

- Product and quote surfaces should feel trustworthy and operationally clear.
- Inventory and lead-time information should be easy to find.

### 2.3 Hierarchical Readability

- The user should be able to understand what is primary, secondary, and supporting content.
- Scientific hierarchy should be obvious in layout and typography.

### 2.4 Reusable Language

- The same visual language should apply across related pages and components.
- Similar content should look similar wherever it appears.

### 2.5 Controlled Density

- Scientific pages are allowed to be information-dense.
- Density must be structured, not chaotic.

### 2.6 Consistency Over Novelty

- The design system should prioritize predictability and usability over decorative variety.

## 3. Visual Direction

The visual language should communicate:

- Precision
- Trust
- Scientific seriousness
- Modern product capability

The interface should avoid looking like a generic blog, a generic SaaS dashboard, or a generic ecommerce catalog.

### 3.1 Overall Feel

- Clean
- Technical
- Calm
- Structured
- High-trust

### 3.2 Visual Tone

- Subtle but confident
- Dense but readable
- Research-oriented rather than marketing-heavy

## 4. Color System

### 4.1 Color Philosophy

- Use a restrained palette with strong semantic contrast.
- Color should support hierarchy and status, not overwhelm the content.

### 4.2 Core Color Roles

- Primary: brand/action emphasis
- Secondary: supporting accents
- Background: page and surface separation
- Surface: cards, panels, and content regions
- Border: structural separation
- Text primary: main content
- Text secondary: supporting metadata
- Success: confirmed or positive states
- Warning: caution states
- Danger: errors or blocking states
- Info: informational states

### 4.3 Semantic Usage

- Use status colors sparingly and consistently.
- Avoid using color as the only way to communicate meaning.
- Keep scientific hierarchy more important than decorative color.

### 4.4 Product and Scientific Context Colors

- Product, method, protocol, reference, and compatibility states should have recognizable but restrained semantic treatment.
- A consistent badge or tag system should be used rather than inventing a different color meaning on each page.

### 4.5 Color Tokens

以下为可实施的具体颜色值，基于 Tailwind CSS 4 默认调色板 + Element Plus 主题基线：

| Token Role | CSS Variable | Hex Value | Usage |
|---|---|---|---|
| Primary | `--color-primary` | `#1E40AF` | 品牌按钮、链接、主强调色 |
| Primary Hover | `--color-primary-hover` | `#1E3A8A` | 主按钮悬停态 |
| Secondary | `--color-secondary` | `#0F766E` | 辅助按钮、次要强调 |
| Background | `--color-bg` | `#F8FAFC` | 页面底色（slate-50） |
| Surface | `--color-surface` | `#FFFFFF` | 卡片、面板、表格背景 |
| Border | `--color-border` | `#E2E8F0` | 卡片边线、表格分割线（slate-200） |
| Text Primary | `--color-text` | `#0F172A` | 正文、标题（slate-900） |
| Text Secondary | `--color-text-secondary` | `#64748B` | 辅助说明、元数据（slate-500） |
| Success | `--color-success` | `#16A34A` | 现货、已发布、兼容 |
| Warning | `--color-warning` | `#D97706` | 少量库存、条件兼容、注意 |
| Danger | `--color-danger` | `#DC2626` | 缺货、不兼容、已停产 |
| Info | `--color-info` | `#2563EB` | 信息提示、中性状态 |

**使用规则**：

- 所有颜色应通过 CSS 变量引用，禁止硬编码 hex 值到组件中
- Status 颜色（Success/Warning/Danger/Info）仅用于状态指示器、Badge、库存标签
- 科学内容层级（Application > Method > Protocol > Product）不使用颜色区分，使用位置和排版层级


## 5. Typography System

### 5.1 Typographic Intent

Typography must support:

- Long scientific titles
- Dense metadata
- Step-by-step procedure content
- Tables and citations
- Commerce labels and statuses

### 5.2 Type Hierarchy

The system should provide clear levels for:

- Page title
- Section title
- Subsection title
- Card title
- Body text
- Metadata text
- Caption / helper text

### 5.3 Typography Rules

- Titles should be compact and authoritative.
- Body text should be highly legible for technical reading.
- Metadata should be visually distinct from primary prose.
- Tables and protocol steps must remain readable at smaller sizes.

### 5.4 Scientific Readability

- Avoid decorative type choices that reduce readability.
- Avoid excessive font variance.
- Keep labels and values clearly separated.

### 5.4 Typography Tokens

以下为具体字号、字重、行高值，基于 Tailwind 4 比例尺：

| Token Role | CSS Variable | Font Size / Weight / Line Height | Tailwind Class |
|---|---|---|---|
| Page Title | `--text-page-title` | 28px / 700 / 1.3 | `text-2xl font-bold` |
| Section Title | `--text-section-title` | 20px / 600 / 1.35 | `text-xl font-semibold` |
| Subsection Title | `--text-subsection-title` | 18px / 600 / 1.4 | `text-lg font-semibold` |
| Card Title | `--text-card-title` | 16px / 600 / 1.4 | `text-base font-semibold` |
| Body | `--text-body` | 15px / 400 / 1.6 | `text-[15px]` (或 `text-base`) |
| Body Small | `--text-body-sm` | 14px / 400 / 1.55 | `text-sm` |
| Metadata | `--text-metadata` | 13px / 400 / 1.5 | `text-xs` |
| Caption | `--text-caption` | 12px / 400 / 1.5 | `text-xs` 细体 |
| Code / Chemical | `--text-mono` | 14px / 400 / 1.5 | `font-mono text-sm` |

**字体栈**：

```css
--font-sans: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Monaco', monospace;
```

**使用规则**：

- 正文使用 Inter / system-ui 字体栈
- CAS号、SMILES、InChI 等化学标识符使用等宽字体（mono）
- 字体大小使用 rem 单位，基准 16px（1rem = 16px）


## 6. Spacing System

### 6.1 Spacing Philosophy

- Use a consistent spacing scale.
- Preserve rhythm across cards, sections, and tables.
- Allow scientific pages to breathe without looking sparse.

### 6.2 Layout Spacing Rules

- Card padding should feel consistent.
- Section spacing should be larger than component spacing.
- Dense technical content should still preserve line separation.

### 6.3 Spacing Scale

基于 4px 基准单位的间距比例尺（与 Tailwind 4 spacing scale 一致）：

| Token | Value | CSS Variable | Usage |
|---|---|---|---|
| `space-1` | 4px | `--space-1` | 内联元素间距、Badge 内边距 |
| `space-2` | 8px | `--space-2` | 卡片内边距（compact）、图标与文字间距 |
| `space-3` | 12px | `--space-3` | 列表项间距、表单元素间距 |
| `space-4` | 16px | `--space-4` | 标准卡片内边距、段落间距 |
| `space-6` | 24px | `--space-6` | 区块间距、Section 内边距 |
| `space-8` | 32px | `--space-8` | Section 间距 |
| `space-12` | 48px | `--space-12` | 大区块间距、Hero 区域 |
| `space-16` | 64px | `--space-16` | 页面级区块分隔 |
| `space-24` | 96px | `--space-24` | 首页大区块分隔 |

**使用规则**：

- Card padding 默认 `space-4`（16px），紧凑模式 `space-2`（8px）
- Section 之间默认 `space-8`（32px）
- 科学内容密集区域（Protocol Steps、Tables）可降低至 `space-2` 以提升信息密度
- 禁止使用非比例尺中的任意像素值


### 6.3 Density Control

- Dense pages should use structured grouping instead of random whitespace.
- Tables, steps, and metadata blocks should align to a shared spacing system.

### 6.4 Border Radius

| Token | Value | CSS Variable | Usage |
|---|---|---|---|
| `radius-sm` | 4px | `--radius-sm` | 内联元素圆角（Badge、Tag、小按钮） |
| `radius-md` | 8px | `--radius-md` | 标准卡片圆角（ApplicationCard、MethodCard、ProtocolCard、ProductCard） |
| `radius-lg` | 12px | `--radius-lg` | 大容器圆角（模态框、面板） |
| `radius-full` | 9999px | `--radius-full` | 圆形元素（头像、状态指示点） |

**使用规则**：

- 卡片类组件统一使用 `radius-md`（8px），与 Codex 前端构建约束一致（"Cards are kept at 8px border radius or less"）
- 状态 Badge 使用 `radius-sm`（4px）
- 禁止使用非比例尺中的任意圆角像素值


## 7. Layout System

### 7.1 Page Structure

The platform should support a predictable structure:

- Hero or title area
- Primary summary block
- Main content
- Related content
- Supporting evidence
- Commerce or action area

### 7.2 Content Columns

- Desktop layouts may use two or three columns when it improves scanability.
- Mobile layouts should collapse into a clear vertical stack.

### 7.3 Section Hierarchy

- Primary content should always be visually dominant.
- Supporting metadata should not overpower the main scientific story.

### 7.4 Card and Panel Usage

- Cards should be used for summaries and lists.
- Panels should be used for grouped content and metadata clusters.
- Tables should be used when structured comparison is needed.

## 8. Core Component Families

### 8.1 Card System

The design system must support the reusable card language required by the frontend PRD:

- `ApplicationCard`
- `MethodCard`
- `ProtocolCard`
- `ProductCard`

### 8.2 Required Card Traits

Each canonical card should support:

- Title
- Summary
- Key metadata
- Primary action
- Canonical link
- Optional secondary indicators

### 8.3 Supporting UI Families

The design system should standardize:

- Tabs
- Tables
- Badges
- Chips / tags
- Citation blocks
- Step lists
- Search bar
- Filter panels
- Empty states
- Loading states
- Error states
- Inventory indicators
- Quote item rows
- Product summary rows

## 9. Table System

### 9.1 Table Purpose

Tables should be used when data needs to be compared, scanned, or validated quickly.

### 9.2 Table Use Cases

- Product metadata
- Protocol materials and reagents
- Comparison of methods
- Compatibility summaries
- Inventory or quote line items

### 9.3 Table Rules

- Headers should be unambiguous.
- Tables should remain readable on smaller screens.
- If a table becomes too wide, it should degrade gracefully into cards or stacked rows.

### 9.4 Protocol Tables

Protocol content may require table-like structures for:

- Materials
- Reagents
- Equipment
- Troubleshooting
- Expected results

## 10. Tabs and Section Navigation

### 10.1 Tab System

Tabs should be used for canonical page sections such as:

- Overview
- Applications
- Methods
- Protocols
- Compatibility
- References
- Documents
- Inventory

### 10.2 Tab Rules

- Tabs should map to real content sections.
- Do not use tabs to hide unrelated content arbitrarily.
- Tabs should preserve canonical ordering where applicable.

### 10.3 Section Anchors

Long scientific pages should also support anchors or quick-jump links for:

- Objectives
- Steps
- Troubleshooting
- Evidence

## 11. Protocol Component Language

### 11.1 Protocol Visual Structure

Protocols must feel stepwise and executable.

### 11.2 Protocol Component Set

The protocol UI should support:

- Objective block
- Principle block
- Materials block
- Reagents block
- Equipment block
- Ordered steps
- Troubleshooting block
- Expected results block
- Reference block

### 11.3 Step Rendering Rules

- Steps must be clearly numbered.
- Steps should support sub-details when needed.
- Step order must be visually obvious.

### 11.4 Troubleshooting Presentation

- Troubleshooting should be readable without dominating the protocol.
- Problems and remedies should be easy to scan.

## 12. Product Component Language

### 12.1 Product Visual Priorities

Product surfaces should make the following easy to find:

- Identity
- Scientific context
- CAS / SMILES / InChI
- Purity
- Storage
- Shipping
- Lead time
- Inventory
- Related applications, methods, and protocols

### 12.2 Product Status Indicators

Use a consistent indicator system for:

- In stock
- Out of stock
- Lead time
- Discontinued
- Research use only

### 12.3 Product Purchase Clarity

- The product page should clearly separate evaluation content from purchase actions.
- Inventory and lead time should be prominent enough to support procurement decisions.

## 13. Badge and Metadata System

### 13.1 Badge Purpose

Badges should convey compact metadata such as:

- Status
- Version
- Evidence strength
- Compatibility state
- Inventory state

### 13.2 Badge Rules

- Badges must be consistent across the product.
- Badges should not be overloaded with too much text.
- Badge meaning should be stable and documented.

## 14. States and Feedback

### 14.1 Loading State

Loading states should feel lightweight and predictable.

### 14.2 Empty State

Empty states should explain what is missing and what the user can do next.

### 14.3 Error State

Error states should be clear, non-alarming, and actionable.

### 14.4 Success State

Success states should confirm the action and show the next step.

### 14.5 Caution State

Caution states should be used for compatibility warnings, limited inventory, or incomplete evidence.

## 15. Responsive Rules

### 15.1 Desktop

- Use richer multi-column layouts where they improve scanning.
- Keep navigation and related content visible.

### 15.2 Tablet

- Preserve hierarchy while reducing density.
- Keep tabs and metadata accessible.

### 15.3 Mobile

- Prioritize the main content and primary action.
- Stack sections vertically.
- Avoid hiding critical scientific context.

### 15.4 Touch Targets

- Interactive elements must be large enough for reliable touch interaction.

## 16. Accessibility Rules

### 16.1 General Accessibility

- Use semantic headings.
- Ensure keyboard navigation.
- Keep focus states visible.
- Maintain sufficient contrast.
- Label actions clearly.

### 16.2 Scientific Accessibility

- Technical content should remain understandable when viewed with screen readers.
- Tables and step lists should have clear structure.
- Do not rely on color alone to express scientific or operational meaning.

## 17. Motion and Interaction

### 17.1 Motion Philosophy

- Motion should be subtle and purposeful.
- Motion should help orient the user, not distract from technical content.

### 17.2 Interaction Rules

- Avoid excessive animation.
- Use transitions to clarify state changes.
- Keep interaction feedback quick and readable.

## 18. Iconography and Visual Cues

### 18.1 Icon Use

- Use icons sparingly.
- Icons should reinforce meaning, not replace text.

### 18.2 Visual Cues

- Use structural cues such as borders, spacing, and badges before resorting to decorative effects.

## 19. Content Tone in UI

The UI should feel:

- Professional
- Scientific
- Reliable
- Helpful
- Direct

It should avoid:

- Overly promotional language
- Cute or playful visual language
- Decorative clutter
- Ambiguous labels

## 20. Implementation Constraints

### 20.1 No Visual Drift

- New pages should use the established design language unless a documented exception exists.

### 20.2 No Reinvention

- Do not invent a new visual system for Applications, Methods, Protocols, or Products if the design system already covers them.

### 20.3 No Conflicting Tokens

- Color, spacing, typography, and status semantics must remain consistent across the platform.

### 20.4 No Hidden Hierarchy

- The visual language must reflect the scientific hierarchy instead of flattening it.

## 21. Cross-Chapter Dependencies

This chapter depends on the product vision, frontend PRD, system architecture, domain model, and Codex rules chapters.
It also informs every page and component chapter that follows.

| Chapter | Dependency on This Chapter |
|---|---|
| Chapter 1 Product Vision | Defines the brand and experience intent that this chapter visualizes |
| Chapter 2 System Architecture | Defines the UI layer boundaries that this chapter must respect |
| Chapter 3 Domain Model | Defines the scientific and commerce hierarchy this chapter must express |
| Chapter 4 Database Architecture | Defines the data fields and states this chapter must render |
| Chapter 5 Frontend PRD | Defines the page inventory and component expectations this chapter must support |
| Chapter 11 Codex Rules | Must preserve the component and visual consistency rules in this chapter |

## 22. Acceptance Criteria

This chapter is complete when all of the following are true:

- The visual direction is explicit.
- The color, typography, spacing, and layout systems are defined at a useful level.
- The reusable component language is defined.
- Tables, tabs, protocol steps, and product indicators are defined.
- States, responsiveness, and accessibility are defined.
- The system preserves scientific hierarchy instead of flattening it.
- The frontend can implement consistent page experiences from this chapter without inventing a new visual language.

