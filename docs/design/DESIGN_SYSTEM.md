# SciReagent Design System — Lab Precision

> AI-Native Scientific Reagent Platform | Design Specification v1.0

---

## 1. Design Philosophy

**Three words: Precise. Efficient. Chemical.**

- **Precise** — Like a lab notebook: every element has purpose, no decoration for decoration's sake
- **Efficient** — Data-dense, scan-friendly, information hierarchy by visual weight
- **Chemical** — Colors from the chemistry lab: teal solutions, amber heat, white surfaces

Influences: Vercel, Linear, Notion, Shadcn/ui

---

## 2. Color System

### 2.1 Core Palette

| Token | Hex | oklch | Usage |
|-------|-----|-------|-------|
| `--primary` | `#0F766E` | oklch(0.512 0.095 172.8) | Primary actions, links, brand |
| `--primary-hover` | `#0D9488` | oklch(0.562 0.105 172.8) | Primary hover state |
| `--primary-light` | `#CCFBF1` | oklch(0.965 0.03 172.8) | Primary background tint |
| `--primary-subtle` | `#F0FDFA` | oklch(0.987 0.01 172.8) | Primary subtle background |
| `--accent` | `#D97706` | oklch(0.655 0.155 75) | CTAs, highlights, warnings |
| `--accent-hover` | `#B45309` | oklch(0.575 0.135 75) | Accent hover state |
| `--accent-light` | `#FEF3C7` | oklch(0.962 0.04 95) | Accent background tint |

### 2.2 Neutral Scale

| Token | Hex | Usage |
|-------|-----|-------|
| `--gray-950` | `#020617` | Text primary |
| `--gray-900` | `#0F172A` | Headings |
| `--gray-700` | `#334155` | Body text emphasis |
| `--gray-500` | `#64748B` | Body text, labels |
| `--gray-400` | `#94A3B8` | Placeholder, disabled |
| `--gray-300` | `#CBD5E1` | Borders light |
| `--gray-200` | `#E2E8F0` | Borders, dividers |
| `--gray-100` | `#F1F5F9` | Surface alt |
| `--gray-50` | `#F8FAFC` | Page background |

### 2.3 Semantic Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--success` | `#059669` | Active, in-stock, published |
| `--success-light` | `#D1FAE5` | Success background |
| `--warning` | `#D97706` | Pending, limited stock |
| `--warning-light` | `#FEF3C7` | Warning background |
| `--danger` | `#DC2626` | Error, out-of-stock |
| `--danger-light` | `#FEE2E2` | Danger background |
| `--info` | `#0284C7` | Informational, tips |
| `--info-light` | `#E0F2FE` | Info background |

### 2.4 Domain-Specific Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--chem-nucleotide` | `#7C3AED` | Nucleotide category badge |
| `--chem-click` | `#0F766E` | Click chemistry category badge |
| `--chem-fluor` | `#0EA5E9` | Fluorescent/labeling badge |
| `--chem-bioconjugate` | `#CA8A04` | Bioconjugation badge |
| `--chem-modifier` | `#E11D48` | Modifier/reagent badge |

---

## 3. Typography

### 3.1 Font Stack

```css
--font-sans: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Monaco', monospace;
```

### 3.2 Type Scale

| Level | Size | Weight | Line-height | Letter-spacing | Usage |
|-------|------|--------|-------------|----------------|-------|
| `display` | 36px | 800 | 1.15 | -0.02em | Homepage hero title |
| `h1` | 28px | 700 | 1.25 | -0.01em | Page titles |
| `h2` | 22px | 600 | 1.30 | 0 | Section headings |
| `h3` | 18px | 600 | 1.35 | 0 | Card titles, subsections |
| `h4` | 16px | 600 | 1.40 | 0 | Small headings |
| `body-lg` | 16px | 400 | 1.60 | 0 | Large body text |
| `body` | 15px | 400 | 1.60 | 0 | Default body text |
| `body-sm` | 14px | 400 | 1.55 | 0 | Secondary text |
| `caption` | 13px | 400 | 1.50 | 0.01em | Metadata, timestamps |
| `micro` | 12px | 500 | 1.50 | 0.02em | Badges, labels |
| `mono` | 14px | 400 | 1.50 | 0 | CAS numbers, formulas |
| `mono-sm` | 13px | 400 | 1.45 | 0 | Small code, SMILES |

### 3.3 Chemical Typography Rules

- **CAS numbers**: `font-family: var(--font-mono); font-size: 14px; color: var(--gray-700);`
- **Molecular formulas**: Subscripts via `<sub>`, `font-family: var(--font-mono);`
- **SMILES strings**: `font-family: var(--font-mono); font-size: 13px; color: var(--gray-500); word-break: break-all;`
- **Product codes** (e.g., SC8001): `font-family: var(--font-mono); font-weight: 600; color: var(--primary);`
- **Purity percentages**: `font-variant-numeric: tabular-nums;`

---

## 4. Spacing & Layout

### 4.1 Spacing Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--space-0` | 0 | - |
| `--space-0.5` | 2px | Tight inline |
| `--space-1` | 4px | Icon gap, badge padding |
| `--space-1.5` | 6px | Tight element spacing |
| `--space-2` | 8px | Inner padding, small gaps |
| `--space-3` | 12px | Between related elements |
| `--space-4` | 16px | Card inner padding, form fields |
| `--space-5` | 20px | Section inner spacing |
| `--space-6` | 24px | Card outer padding, section gaps |
| `--space-8` | 32px | Between sections |
| `--space-10` | 40px | Major section breaks |
| `--space-12` | 48px | Page section top/bottom |
| `--space-16` | 64px | Hero vertical padding |
| `--space-24` | 96px | Page-level vertical rhythm |

### 4.2 Grid System

| Breakpoint | Width | Columns | Gutter | Margin |
|------------|-------|---------|--------|--------|
| Mobile | <640px | 4 | 16px | 16px |
| Tablet | 640-1024px | 8 | 20px | 24px |
| Desktop | 1024-1440px | 12 | 24px | 32px |
| Wide | >1440px | 12 | 24px | auto (max-width: 1400px) |

### 4.3 Layout Zones

```
┌─────────────────────────────────────────────────────────────────────┐
│ Header (56px fixed)                                                 │
├──────────┬──────────────────────────────────────────────────────────┤
│ Sidebar  │ Main Content Area                                       │
│ (240px)  │                                                          │
│          │  ┌──────────────────────────────────────────────────┐  │
│ Nav      │  │ Page Header (title + actions)                     │  │
│ Section  │  ├──────────────────────────────────────────────────┤  │
│          │  │ Content                                           │  │
│          │  │ (max-width: 960px for text, 1200px for data)      │  │
│          │  │                                                   │  │
│          │  └──────────────────────────────────────────────────┘  │
├──────────┴──────────────────────────────────────────────────────────┤
│ Footer (64px)                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. Component Specifications

### 5.1 Buttons

**Sizes:**

| Size | Height | Padding H | Font size | Icon gap |
|------|--------|-----------|-----------|----------|
| sm | 32px | 12px | 13px | 4px |
| md | 36px | 16px | 14px | 6px |
| lg | 44px | 24px | 15px | 8px |

**Variants:**

| Variant | Background | Text | Border | Hover |
|---------|-----------|------|--------|-------|
| primary | `--primary` | #fff | none | `--primary-hover` |
| secondary | `--gray-100` | `--gray-900` | `--gray-200` | `--gray-200` bg |
| outline | transparent | `--primary` | `--primary` | `--primary-light` bg |
| ghost | transparent | `--gray-500` | none | `--gray-100` bg |
| danger | `--danger` | #fff | none | `#B91C1C` |

**States:**
- Disabled: `opacity: 0.5; pointer-events: none;`
- Loading: Spinner replaces text, same width
- Focus: `outline: 2px solid var(--primary); outline-offset: 2px;`

**Border radius:** `6px` (sm/md), `8px` (lg)

### 5.2 Cards

**Base card:**
```css
.card {
  background: var(--gray-50);       /* #F8FAFC - off-white, not pure white */
  border: 1px solid var(--gray-200); /* #E2E8F0 */
  border-radius: 8px;
  padding: 16px;
  transition: box-shadow 150ms ease, border-color 150ms ease;
}
.card:hover {
  border-color: var(--gray-300);
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
```

**Card variants:**

| Variant | Left border | Background | Usage |
|---------|-------------|-----------|-------|
| default | none | `--gray-50` | Standard content |
| interactive | none | `--gray-50` → hover shadow | Clickable cards |
| highlighted | 3px solid `--primary` | `--primary-subtle` | Featured items |
| category | 3px domain color | white | Category indicator |

**Card types by content:**

| Card | Image area | Content layout |
|------|-----------|---------------|
| ProductCard | Chemical structure SVG (80x80) | Name, CAS (mono), purity badge, price |
| MethodCard | Icon (48x48) | Name, purpose, protocol count |
| ApplicationCard | Icon (48x48) | Name, category badge, method count |
| ProtocolCard | Step count badge | Name, status badge, last updated |

### 5.3 Badges / Tags

```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  font-family: var(--font-sans);
}
```

| Variant | Background | Text | Dot |
|---------|-----------|------|-----|
| success | `--success-light` | `--success` | 6px green dot |
| warning | `--warning-light` | `--warning` | 6px amber dot |
| danger | `--danger-light` | `--danger` | 6px red dot |
| info | `--info-light` | `--info` | 6px blue dot |
| neutral | `--gray-100` | `--gray-600` | no dot |

**Domain badges** use category colors from Section 2.4.

### 5.4 Input Fields

```css
.input {
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--gray-300);
  border-radius: 6px;
  font-size: 14px;
  color: var(--gray-900);
  background: white;
  transition: border-color 150ms ease;
}
.input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-light);
}
.input::placeholder {
  color: var(--gray-400);
}
```

**Search input special:**
- Height: 44px
- Border-radius: 8px
- Left icon: Search (Lucide `search`, 18px)
- Right slot: keyboard shortcut badge `⌘K`

### 5.5 Tables

```css
.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.table th {
  text-align: left;
  padding: 10px 16px;
  font-weight: 500;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--gray-500);
  border-bottom: 1px solid var(--gray-200);
  background: var(--gray-50);
}
.table td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--gray-100);
  color: var(--gray-700);
}
.table tr:hover td {
  background: var(--primary-subtle);
}
```

### 5.6 Navigation

**Sidebar nav item:**
```css
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 14px;
  color: var(--gray-500);
  transition: all 100ms ease;
  text-decoration: none;
}
.nav-item:hover {
  background: var(--gray-100);
  color: var(--gray-900);
}
.nav-item.active {
  background: var(--primary-light);
  color: var(--primary);
  font-weight: 500;
}
```

**Header nav link:**
- Font: 14px, `--gray-500`
- Hover: `--gray-900`
- Active: `--primary`, `font-weight: 500`
- Underline: 2px bottom, `--primary` on active

### 5.7 Breadcrumbs

```
Home  >  Products  >  SC8001 Cy3-azide
  ^        ^             ^
link      link        current (gray-500, no link)
```

- Font: 13px, `--gray-400`
- Separator: `/` with 4px horizontal gap
- Current: `--gray-700`, no underline

### 5.8 Modals / Dialogs

- Overlay: `rgba(0,0,0,0.4)` with `backdrop-filter: blur(4px)`
- Container: `max-width: 520px`, `border-radius: 12px`, white bg
- Header: `font-size: 18px; font-weight: 600;` with close button top-right
- Footer: Right-aligned actions (Cancel + Primary)
- Animation: `fadeScale` 200ms ease-out

### 5.9 Pagination

- Style: Compact number buttons
- Current: `--primary` bg, white text
- Others: transparent bg, `--gray-500` text, hover `--gray-100`
- Size: 32x32px squares, `border-radius: 6px`
- Show: first, last, ±2 from current, ellipsis

### 5.10 Empty State

- Icon: 48px, `--gray-300` (Lucide `inbox`)
- Title: 16px, `--gray-700`
- Description: 14px, `--gray-400`
- Action: Primary button below

### 5.11 Loading State

- Skeleton: `background: linear-gradient(90deg, var(--gray-100) 25%, var(--gray-50) 50%, var(--gray-100) 75%);`
- Animation: `shimmer 1.5s infinite`
- Shape: Match the content it replaces

---

## 6. Icon System

### 6.1 Library

**Lucide Icons** — clean, consistent, 24x24 default, 2px stroke

### 6.2 Size Scale

| Size | Usage |
|------|-------|
| 16px | Inline icons, badges |
| 18px | Nav items, input adornments |
| 20px | Buttons, list items |
| 24px | Default, cards |
| 32px | Empty states, feature highlights |

### 6.3 Core Icon Map

| Area | Icon name | Usage |
|------|-----------|-------|
| Navigation | `flask-conical` | Applications |
| | `file-text` | Protocols |
| | `beaker` | Methods |
| | `package` | Products |
| | `search` | Search |
| | `home` | Home |
| Status | `check-circle` | Active/Published |
| | `alert-circle` | Warning |
| | `x-circle` | Error/Inactive |
| | `clock` | Pending |
| Actions | `plus` | Create |
| | `pencil` | Edit |
| | `trash-2` | Delete |
| | `download` | Export |
| | `share-2` | Share |
| | `bookmark` | Wishlist |
| Chemistry | `atom` | Molecular structure |
| | `test-tubes` | Reagent |
| | `dna` | Nucleotide |
| | `microscope` | Research |
| | `pipette` | Precision |

---

## 7. Page Layouts

### 7.1 Homepage

```
┌──────────────────────────────────────────────────────┐
│  [Logo]  Home  Products  Methods  ...     [Search]  │  Header 56px
├──────────────────────────────────────────────────────┤
│                                                      │
│         SciReagent                                  │  Hero section
│    AI-Native Scientific Reagent Platform             │  padding: 64px 0
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  🔍  Search molecules, CAS, SMILES...    ⌘K   │  │  Search bar 44px
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐           │  Stats row
│  │  128  │  │   87  │  │   64  │  │  730  │           │  4 cards
│  │ Apps  │  │Methods│  │Protos│  │Prods  │           │
│  └──────┘  └──────┘  └──────┘  └──────┘           │
│                                                      │
│  Featured Applications                    View all → │  Section
│  ┌─────────┐ ┌─────────┐ ┌─────────┐              │
│  │ Click   │ │ Fluores │ │ Nucleot │              │  3-col card grid
│  │ Chem    │ │ cent    │ │ ide     │              │
│  └─────────┘ └─────────┘ └─────────┘              │
│                                                      │
│  Featured Products                       View all → │  Section
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐        │  6-col compact grid
│  │SC01│ │SC02│ │SC03│ │SC04│ │SC05│ │SC06│        │
│  └────┘ └────┘ └────┘ └────┘ └────┘ └────┘        │
│                                                      │
├──────────────────────────────────────────────────────┤
│  Footer                                              │
└──────────────────────────────────────────────────────┘
```

### 7.2 Product List Page

```
┌──────────────────────────────────────────────────────┐
│  Header                                              │
├────────┬─────────────────────────────────────────────┤
│        │  Products  (128)                    [Filter]│  Page header
│        │─────────────────────────────────────────────│
│  Nav   │  ┌─ Filters ────────────────────────────┐ │
│  ─────  │  │ Category  Status  Purity  Sort by   │ │  Filter bar
│  Apps   │  └──────────────────────────────────────┘ │
│  Method │                                             │
│  Proto  │  ┌──────────────────────────────────────┐  │
│  Prod   │  │ [SVG]  SC8001  Cy3-azide            │  │  Product row card
│  ─────  │  │        CAS: ... | ⬤ In stock | 98%  │  │
│  Search │  └──────────────────────────────────────┘  │
│         │  ┌──────────────────────────────────────┐  │
│         │  │ [SVG]  SC8002  ...                    │  │
│         │  └──────────────────────────────────────┘  │
│         │                                             │
│         │         < 1 2 3 ... 10 >                   │  Pagination
├────────┴─────────────────────────────────────────────┤
│  Footer                                              │
└──────────────────────────────────────────────────────┘
```

### 7.3 Product Detail Page

```
┌──────────────────────────────────────────────────────┐
│  Header                                              │
├────────┬─────────────────────────────────────────────┤
│        │  Home > Products > SC8001                   │  Breadcrumb
│        │─────────────────────────────────────────────│
│  Nav   │                                             │
│        │  ┌──────────────┐  SC8001                   │
│        │  │              │  Cy3-azide                 │  Product hero
│        │  │  [Mol SVG]   │  ⬤ In stock               │  2-col: image + info
│        │  │              │  C₂₄H₂₆N₆O₃             │
│        │  └──────────────┘  MW: 462.51               │
│        │                                             │
│        │  ┌─ Properties ──────────────────────────┐ │
│        │  │  CAS:  ...   |  Purity: ≥98%          │ │  Property table
│        │  │  Storage: -20°C  |  Form: Solid       │ │
│        │  │  SMILES: CC(=O)Nc1ccc(...)             │ │
│        │  └───────────────────────────────────────┘ │
│        │                                             │
│        │  ┌─ Specifications ──────────────────────┐ │
│        │  │  SKU      Grade    Price    Stock      │ │  SKU/Variant table
│        │  │  SC8001-1  Standard  ¥XXX    ✓        │ │
│        │  │  SC8001-5  Premium   ¥XXX    ✓        │ │
│        │  └───────────────────────────────────────┘ │
│        │                                             │
│        │  Related Methods                View all →  │  Related content
│        │  ┌────────┐ ┌────────┐ ┌────────┐         │
│        │  │ CuAAC  │ │ Amide  │ │ Label  │         │
│        │  └────────┘ └────────┘ └────────┘         │
│        │                                             │
│        │  Documents & References                     │  References
│        │  1. Smith et al. (2023) J. Org. Chem.      │
├────────┴─────────────────────────────────────────────┤
│  Footer                                              │
└──────────────────────────────────────────────────────┘
```

### 7.4 Search Page

```
┌──────────────────────────────────────────────────────┐
│  Header                                              │
├────────┬─────────────────────────────────────────────┤
│        │  ┌────────────────────────────────────────┐ │
│        │  │  🔍  Cy3                          ✕   │ │  Search bar (large)
│        │  └────────────────────────────────────────┘ │
│        │                                             │
│        │  All(12)  Products(6)  Methods(3)  Protos(3)│  Result tabs
│        │  ────────────────────────────────────────── │
│        │                                             │
│        │  Products                                    │  Result section
│        │  ┌──────────────────────────────────────┐  │
│        │  │ 🔬 SC8001  Cy3-azide  ⬤ In stock     │  │  Result item
│        │  │    CAS: ... | Purity: ≥98% | ¥XXX    │  │
│        │  └──────────────────────────────────────┘  │
│        │  ┌──────────────────────────────────────┐  │
│        │  │ 🔬 SC8002  ...                        │  │
│        │  └──────────────────────────────────────┘  │
│        │                                             │
│        │  Methods                                    │  Cross-type results
│        │  ┌──────────────────────────────────────┐  │
│        │  │ 🧪 CuAAC Click Reaction              │  │
│        │  │    3 protocols | Copper-catalyzed     │  │
│        │  └──────────────────────────────────────┘  │
│        │                                             │
├────────┴─────────────────────────────────────────────┤
│  Footer                                              │
└──────────────────────────────────────────────────────┘
```

---

## 8. Animation & Motion

### 8.1 Motion Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `--duration-fast` | 100ms | Hover, active states |
| `--duration-normal` | 150ms | Color transitions, borders |
| `--duration-slow` | 250ms | Page content fade-in |
| `--duration-modal` | 200ms | Modal enter/exit |
| `--ease-default` | `cubic-bezier(0.4, 0, 0.2, 1)` | Standard ease |
| `--ease-decelerate` | `cubic-bezier(0, 0, 0.2, 1)` | Enter animations |
| `--ease-accelerate` | `cubic-bezier(0.4, 0, 1, 1)` | Exit animations |

### 8.2 Animation Patterns

| Element | Enter | Exit | Hover |
|---------|-------|------|-------|
| Page content | 250ms fade-up (Y+8→0, α0→1) | - | - |
| Modal | 200ms fadeScale (S0.95→1, α0→1) | 150ms fade (α1→0) | - |
| Card | Present (no enter anim) | - | 150ms border-color + shadow |
| Button | Present | - | 100ms background-color |
| Toast | 250ms slide-in (Y-16→0) | 200ms slide-out (Y0→-16) | - |
| Dropdown | 150ms fade + slide (Y-4→0) | 100ms fade | - |
| Skeleton shimmer | 1.5s infinite linear | - | - |

### 8.3 Transition Classes

```css
.fade-enter-active, .fade-leave-active {
  transition: opacity 250ms var(--ease-default);
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

.slide-up-enter-active {
  transition: all 250ms var(--ease-decelerate);
}
.slide-up-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
```

---

## 9. Dark Mode (Future)

Dark mode follows the same token structure with swapped values:

| Light Token | Dark Value |
|-------------|-----------|
| `--gray-50` (bg) | `#0F172A` |
| `--gray-100` (surface) | `#1E293B` |
| `--gray-200` (border) | `#334155` |
| `--gray-900` (text) | `#F1F5F9` |
| `--gray-500` (body) | `#94A3B8` |
| `--primary` | `#2DD4BF` (lighter teal) |
| `--accent` | `#FBBF24` (lighter amber) |

Toggle via `prefers-color-scheme` media query + manual switch in header.

---

## 10. Accessibility

- **Color contrast**: All text meets WCAG AA (4.5:1 for body, 3:1 for large text)
- **Focus visible**: 2px solid `--primary` outline, 2px offset
- **Skip link**: Hidden skip-to-content link at page top
- **Semantic HTML**: `<nav>`, `<main>`, `<article>`, `<aside>`, `<footer>`
- **ARIA**: Live regions for search results, `aria-label` on icon buttons
- **Keyboard**: Full tab navigation, Enter/Space activation, Escape to close modals
- **Reduced motion**: `@media (prefers-reduced-motion: reduce)` disables all animations

---

## 11. Responsive Behavior

| Element | Desktop | Tablet | Mobile |
|---------|---------|--------|--------|
| Sidebar | 240px fixed | 240px overlay | Hidden (hamburger) |
| Card grid | 3-col | 2-col | 1-col |
| Product grid | 6-col compact | 3-col | 2-col |
| Hero search | 640px centered | Full width - 48px | Full width - 32px |
| Table | Full columns | Scroll horizontal | Card view |
| Nav | Horizontal links | Hamburger menu | Bottom tab bar |

---

*SciReagent Design System v1.0 — Lab Precision Direction*
*Generated: 2026-06-11*
