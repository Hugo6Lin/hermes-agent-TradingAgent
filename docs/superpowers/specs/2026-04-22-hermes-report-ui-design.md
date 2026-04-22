# Hermes Report UI Design Spec

**Date:** 2026-04-22
**Phase:** Report UI Redesign
**Status:** Draft

---

## 1. Purpose

### What This Report UI Is For

The Hermes Report UI is the primary artifact surface through which the boss makes investment decisions. It translates the full bullish decision pipeline — thesis evaluation, instrument selection, options structuring, early exit planning, watchlist monitoring, and validation — into a format the boss can read in two modes:

- **Poster view**: single-page decision board, optimized for quick 3-second comprehension and printing on a single A4/Letter sheet
- **PDF report view**: multi-page executive report, optimized for archival and committee distribution

### Who Reads It

- **Primary**: Boss / investment committee chair — reads only the poster
- **Secondary**: Operator or analyst — may read the full PDF report for research depth

### Why Poster + PDF Rather Than Slide Deck

Slides are wrong because:

- slides imply presentation mode (someone presenting to the boss)
- slides encourage too much content per page
- slides do not print predictably
- slides are not archival documents

Poster + PDF is correct because:

- poster gives the boss a single fixed decision card — no navigation required
- PDF gives the committee a paginated archival record with full depth
- both are printable and do not require special software to render
- both are deterministic — same content every time

---

## 2. Audience

### Boss / Investment Committee

**In 3 seconds**, the reader must understand:

- What is the action? (buy stock / buy call / bull call spread / sell put / covered call / watchlist)
- What is the conviction? (high / medium / low)
- What is the ticker?
- What is the target price and window?
- What is the single most important reason to act now?

**In 30–60 seconds**, the reader can go deeper and understand:

- Why this instrument was chosen over alternatives
- What the options structure looks like (if applicable)
- What the early exit plan looks like
- What the key risks are
- What the watchlist and validation status are

**Beyond 60 seconds** is out of scope for this surface. Deep research belongs in the analyst-level view.

---

## 3. Design Principles

### 3.1 Decision-First Hierarchy

The most important information comes first, in the highest visual priority position. The information hierarchy is:

1. **Action + Conviction** — dominant visual element
2. **Ticker + Company**
3. **Target Price + Window**
4. **Why Now** (top 3 bullets)
5. **KPI Snapshot** (price, P/E, EPS growth, analyst rating)
6. **Thesis & Catalysts**
7. **Technical Summary**
8. **Instrument Choice** (primary + conservative + alternative)
9. **Options Structure** (if applicable)
10. **Early Exit Zones** (if applicable)
11. **Risk Chips**
12. **Watchlist State**
13. **Validation Summary**

### 3.2 Chinese-First Bilingual

- All section labels use Chinese as the primary text
- English translations appear as secondary labels on the same element
- The pattern is always: `中文 / English`
- No section uses English-only labels in the primary view
- No mojibake — all strings are defined in `strings_zh.py` and `strings_en.py` with strict one-to-one mapping

### 3.3 Printable Executive Brief

- Both poster and PDF must render correctly when printed from a standard browser
- Colors must not disappear when printing (use `print-color-adjust: exact`)
- Text must not overflow page boundaries
- The poster must fit on a single A4 or Letter page without scrolling
- The PDF must paginate cleanly with `page-break-*` rules

### 3.4 Premium Institutional Tone

- No clip-art, no cartoons, no playful illustrations
- Clean grid layouts with clear section boundaries
- Color semantics: orange-red = action/alert, teal-green = positive/conviction, deep red = risk only
- Typography: clean sans-serif with clear size hierarchy (large action text, smaller body text)
- No raw data dumps — every number displayed must have a label

### 3.5 Compact Monitoring Support

- The poster footer (bottom zone) must show watchlist state and validation at a glance
- The PDF final page must show the full watchlist table and validation table
- These must be readable even when many entries are present

### 3.6 No Raw Database Dump Feel

- Every table row must have meaningful labels
- Empty fields show em-dash `—` not blank
- Dates use YYYY-MM-DD format
- Percentages use `XX%` notation, not decimals

---

## 4. Poster Structure

The poster is a single A4/Letter page divided into three visual zones.

### Zone 1 — Decision Hero (top ~55%)

Role: Contains all the information needed for a 3-second decision.

Sub-sections (left-to-right, top-to-bottom):

1. **Action Block** (left, dominant)
   - Section label: `操作 / Action`
   - Large Chinese action text: e.g., `买入看涨`
   - Smaller English action: e.g., `Buy Call`
   - Conviction badge below: e.g., `高信心 / HIGH CONVICTION`

2. **Ticker + Conviction Block** (right, top)
   - Ticker symbol in large text: e.g., `NVDA`
   - Company name below in smaller text
   - Conviction badge: colored border badge

3. **Target + Size Block** (right, middle)
   - `目标窗口 / Target Window`: e.g., `12个月`
   - `目标价 / Target Price`: e.g., `$180 → $250`
   - `建议仓位 / Suggested Size`: e.g., `15% Portfolio`

4. **Why Now** (right, lower)
   - Section label: `为何此时 / Why Now`
   - Up to 3 numbered bullet points
   - Each bullet has Chinese primary + English secondary

5. **Risk Chips** (bottom of zone 1, full width)
   - Horizontal row of risk chips
   - Each chip: Chinese risk label + English secondary
   - Background: semi-transparent deep red

### Zone 2 — Detail Cards (middle ~35%)

Role: Contains the analytical depth for a 30-second read.

Sub-sections:

1. **KPI Cards** (4-column grid)
   - `当前价 / Price`
   - `市盈率 / P/E`
   - `EPS增长 / EPS Growth`
   - `分析师评级 / Analyst Rating`

2. **Thesis + Technical** (2-column layout)
   - Left: `投资逻辑 / Thesis & Catalysts` — up to 4 numbered bullets
   - Right: `技术分析 / Technical Analysis` — support, resistance, trend summary

3. **Instrument Choice** (5-column horizontal row)
   - Each box shows one instrument type
   - Role labels: `首选 / PRIMARY`, `保守方案 / CONSERVATIVE`, `备选方案 / ALTERNATIVE`, `—` for rejected
   - Only 3 instruments shown (primary + conservative + alternative), not all 5

4. **Options Structure** (single compact card, shown only when options are applicable)
   - Fields: `到期日 / Expiry`, `行权价 / Strike`, `盈亏平衡 / Break-Even`, `Delta / Delta`, `提前退出 / Early Exit`
   - 5-column layout within one card

5. **Early Exit** (shown only when EarlyExitPlan is present)
   - Three zones displayed: `首轮减仓 / First Trim`, `主要利润 / Main Profit`, `完全退出 / Full Exit`
   - Each zone: action + trigger condition + target return

### Zone 3 — Status Footer (bottom ~10%)

Role: Contains monitoring context — lightweight but always present.

Sub-sections:

1. **Watchlist State** (left)
   - Status badge: `持仓中 / Held` | `重点关注 / High Priority` | `研究进行中 / Research` | `被动跟踪 / Passive`
   - `操作倾向 / Action Bias` label and value

2. **Validation Summary** (center)
   - `市场状态 / Regime`: e.g., `趋势向上 / Trend Up`
   - `验证信心 / Validation Confidence`: e.g., `78%`
   - Color-coded: high = teal-green, medium = orange-red

3. **Brand + Timestamp** (right)
   - `Hermes 研究台 / Hermes Research Desk`
   - `决策看板 / Decision Board`
   - Generated timestamp: `YYYY-MM-DD HH:MM`

---

## 5. Printable Report Structure

The PDF report is a multi-page document.

### Page 1 — Batch Overview

- Report header: `批次总览 / Batch Overview` + date + count
- Batch overview table with columns: Rank, Ticker, Company, Rating, Confidence %, Action Bias, Target Price
- Executive summary text block below the table

### Pages 2+ — Individual Company Reports (one per ticker)

- Report header: ticker + company name + confidence
- Company report card containing:
  - Bottom line box (dark background): `核心结论 / Bottom Line`
  - Trade plan grid: Action, Entry, Stop Loss, Target
  - Why Now section
  - Two-column: Bull Case (left) + Risk Watch (right)
- Research summary section (if present)

### Final Page — Watchlist + Validation

- Report header: `监控状态 / Watchlist & 验证摘要 / Validation Summary`
- Watchlist table with columns: Ticker, Action Bias, Status, Thesis State, Alert Level
- Validation table with columns: Ticker, Regime, Historical Support, Environment Fit, Main Failure Mode, Confidence

---

## 6. Data Mapping

This section maps Hermes canonical objects to UI sections.

### decision_card (PositionDecisionCard)

| Field | UI Target |
|-------|-----------|
| `primary_action` | Poster Zone 1, Action Block; Report Page 2+, Trade Plan grid |
| `conviction` | Poster Zone 1, Conviction Badge |
| `thesis_summary` | Poster Zone 2, Thesis & Catalysts |
| `why_now` | Poster Zone 1, Why Now bullets |
| `alternatives` | Poster Zone 2, Instrument Choice (rejected column) |

### instrument_recommendation (InstrumentRecommendation)

| Field | UI Target |
|-------|-----------|
| `primary_action` | Poster Zone 2, Instrument Choice — PRIMARY box |
| `ranked_alternatives` | Poster Zone 2, Instrument Choice — CONSERVATIVE + ALTERNATIVE boxes |
| `reason` | Instrument box reason text |

### options_structure (OptionsStructure)

| Field | UI Target |
|-------|-----------|
| `instrument_action` | Poster Zone 2, Options Structure card label |
| `primary_contract.expiry_months` | Poster Zone 2, Options Structure — Expiry |
| `primary_contract.strike` | Poster Zone 2, Options Structure — Strike |
| `break_even_price` | Poster Zone 2, Options Structure — Break-Even |
| `primary_contract.delta_estimate` | Poster Zone 2, Options Structure — Delta |
| `early_exit_summary` | Poster Zone 2, Options Structure — Early Exit |
| `strategy_net_debit` | Report trade plan detail |
| `strategy_net_credit` | Report trade plan detail |
| `max_profit_pct` | Report trade plan detail |
| `max_loss_pct` | Report trade plan detail |

### early_exit_plan (EarlyExitPlan)

| Field | UI Target |
|-------|-----------|
| `primary_exit_trigger` | Poster Zone 2, Early Exit section |
| `severity` | Poster Zone 2, Early Exit severity chip |
| `primary_reason` | Poster Zone 2, Early Exit reason text |
| `first_trim` | Poster Zone 2, Early Exit — First Trim zone |
| `main_profit` | Poster Zone 2, Early Exit — Main Profit zone |
| `full_exit` | Poster Zone 2, Early Exit — Full Exit zone |

### watchlist_entry (WatchlistEntry)

| Field | UI Target |
|-------|-----------|
| `ticker` | Poster Zone 3, Watchlist State; Report Final Page |
| `status` | Poster Zone 3, Status Badge |
| `thesis_state` | Poster Zone 3, Thesis State chip; Report Final Page |
| `alert_level` | Poster Zone 3, Alert chip; Report Final Page |
| `current_action_bias` | Poster Zone 3, Action Bias label |

### validation (ValidationResult)

| Field | UI Target |
|-------|-----------|
| `regime` | Poster Zone 3, Validation chips — Regime |
| `validation_confidence` | Poster Zone 3, Validation chips — Confidence % |
| `historical_support` | Report Final Page, Validation table |
| `environment_fit` | Report Final Page, Validation table |
| `main_failure_mode` | Report Final Page, Validation table |

### canonical report/signal (legacy fields, still needed)

| Field | UI Target |
|-------|-----------|
| `signal.ticker` | All pages |
| `signal.rating` | Report Page 1, Batch table; Page 2+ header |
| `signal.confidence` | Report Page 1, Batch table; Page 2+ header |
| `signal.entry_price` | Poster Zone 1, Target Price; Report Trade Plan |
| `signal.take_profit` | Poster Zone 1, Target Price; Report Trade Plan |
| `report.bottom_line` | Report Page 2+, Bottom Line box |
| `report.why_now` | Poster Zone 1, Why Now; Report Why Now section |
| `report.bull_case` | Poster Zone 2, Thesis & Catalysts; Report Bull Case |
| `report.risk_watch` | Poster Zone 1, Risk Chips; Report Risk Watch |
| `report.company_name` | All pages |

---

## 7. Bilingual Rules

### Chinese Primary, English Secondary

All labels follow the pattern: `中文 / English`

Examples:

- `操作 / Action`
- `为何此时 / Why Now`
- `核心结论 / Bottom Line`
- `看多逻辑 / Bull Case`
- `风险观察 / Risk Watch`
- `期权结构 / Options Structure`
- `提前退出 / Early Exit`
- `监控状态 / Watchlist`
- `验证摘要 / Validation`

### Terminology Consistency

The following terms are fixed and must not be translated differently across the UI:

| Chinese | English | Applied To |
|---------|---------|-----------|
| 买入 | BUY | Action |
| 观望 | HOLD | Action |
| 买入看涨 | Buy Call | Instrument |
| 牛市看涨价差 | Bull Call Spread | Instrument |
| 卖出备兑看跌 | Sell CSP | Instrument |
| 备兑看涨 | Covered Call | Instrument |
| 高信心 | HIGH CONVICTION | Conviction |
| 中信心 | MEDIUM CONVICTION | Conviction |
| 低信心 | LOW CONVICTION | Conviction |
| 首选 | PRIMARY | Instrument role |
| 保守方案 | CONSERVATIVE | Instrument role |
| 备选方案 | ALTERNATIVE | Instrument role |
| 持仓中 | Held | Watchlist status |
| 重点关注 | High Priority | Watchlist status |
| 研究进行中 | Research | Watchlist status |
| 被动跟踪 | Passive | Watchlist status |
| 逻辑强化 | Strengthening | Thesis state |
| 逻辑稳定 | Stable | Thesis state |
| 逻辑弱化 | Weakening | Thesis state |
| 逻辑破坏 | Broken | Thesis state |
| 趋势向上 | Trend Up | Regime |
| 区间震荡 | Range Bound | Regime |
| 高波动 | High Volatility | Regime |
| 风险规避 | Risk Off | Regime |

### No Mixed Encoding

- All strings are defined in `strings_zh.py` (Chinese) and `strings_en.py` (English)
- The renderer loads both and maps them at render time
- No string is ever assembled from concatenated bytes
- All HTML files declare `<meta charset="utf-8"/>` and save as UTF-8

---

## 8. Visual System

### Color Palette

```css
/* Primary action color — orange-red */
--color-action: #E85A3C;

/* Positive / conviction / support — teal-green */
--color-positive: #2DD4A8;

/* Risk only — deep red */
--color-risk: #C0392B;

/* Main background — warm off-white */
--color-bg: #FAF8F5;

/* Card/panel background — white */
--color-panel: #FFFFFF;

/* Header/footer background — deep charcoal */
--color-header: #1C1C1E;
--color-footer: #1C1C1E;

/* Body text — deep neutral */
--color-text: #1A1A1A;

/* Secondary/muted text — gray */
--color-text-secondary: #6B7280;

/* Text on dark backgrounds — white */
--color-text-inverse: #FFFFFF;

/* Borders */
--color-border: #E5E5E5;
```

### Typography

```css
/* Main UI font — CJK-compatible sans-serif stack */
--font-main: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;

/* Numbers and financial data */
--font-numbers: "SF Pro Display", "Helvetica Neue", Arial, sans-serif;

/* Monospace — for codes and tickers if needed */
--font-mono: "SF Mono", "Consolas", monospace;
```

Font size hierarchy:

- Action text (large): 56px, font-weight 800
- Action sub-text: 28px, font-weight 300
- Ticker symbol: 28px, font-weight 700
- Section labels (Chinese): 13px, font-weight 700
- Section labels (English): 10px, font-weight 400
- Body text: 12px
- Small labels: 10px

### Spacing System

```css
--space-xs: 4px;
--space-sm: 8px;
--space-md: 16px;
--space-lg: 24px;
--space-xl: 32px;
```

### Chips / Badges / Cards

**Status Badge** (used for watchlist status):

- `Held`: teal-green background at 15% opacity, solid teal text
- `High Priority`: orange-red background at 15% opacity, solid orange-red text
- `Research`: amber background at 15% opacity, solid amber text
- `Passive`: gray background at 10% opacity, solid gray text

**Conviction Badge** (poster zone 1):

- 2px solid border in `--color-positive`
- Transparent background
- Chinese conviction text + English secondary

**Risk Chip** (poster zone 1):

- Deep red border
- Semi-transparent deep red background
- Chinese risk text + English secondary

**KPI Card** (poster zone 2):

- White background
- 3px top border in `--color-positive`
- 4px border-radius
- Subtle card shadow

**Section Card** (poster zone 2):

- White background
- Left accent bar: 3px `--color-action` vertical line
- Section label in Chinese (bold) + English (light)

### Instrument Hierarchy Rules

The instrument row shows at most 3 instruments in priority order:

1. **PRIMARY** (`首选`): orange-red border, light orange-red background tint, orange-red role label
2. **CONSERVATIVE** (`保守方案`): teal-green border, light teal-green background tint, teal-green role label
3. **ALTERNATIVE** (`备选方案`): gray border, no background tint, gray role label

Rejected instruments are not shown in the poster instrument row.

---

## 9. Technical Analysis Rendering Rules

### Boss-Readable Only

The technical analysis section is a **summary**, not an indicator dump.

### What to Show

- **Support**: a single price level or range, e.g., `$165–170`
- **Resistance**: a single price level or range, e.g., `$220–225`
- **Trend**: a short directional phrase, e.g., `上升趋势 / Uptrend` or `震荡整理 / Range Bound`
- **Momentum** (if available): a short phrase, e.g., `动能较强 / Strong Momentum`

### What NOT to Show

- No raw indicator values (RSI, MACD, Bollinger values, etc.)
- No chart descriptions beyond a single trend label
- No multiple timeframe analysis unless it fits in one short phrase

### Rendering Pattern

```
支撑位 / Support: $165–170
阻力位 / Resistance: $220–225
趋势 / Trend: 上升趋势 / Uptrend
```

---

## 10. Pagination / Print Rules

### Poster

- Fixed aspect ratio: 3:4 (portrait)
- Rendered at A4 or Letter size depending on locale
- `overflow: hidden` to prevent content from spilling off page
- `@page { size: A4 portrait; margin: 0; }` to eliminate browser margins

### PDF Report

- Page size: A4 portrait, standard margins (15mm)
- `page-break-after: always` on every report page except the last
- `page-break-inside: avoid` on company report cards to prevent mid-card splits
- `page-break-after: auto` on the last page

### Keep-Together Rules

These elements must not be split across pages:

- Company report card (keep together on one page if possible)
- Watchlist table header (keep with first row)
- Validation table header (keep with first row)
- Bottom line box (keep together)

### Section Splitting Constraints

- The batch overview table may break between rows
- The trade plan grid (4 columns) may break between columns only if absolutely necessary
- Instrument row must not break mid-row

---

## 11. Non-Goals

This spec explicitly does **not** include:

- **New trading logic**: No new buy/sell/wait decision algorithms
- **New validation logic**: No new validation engine implementations
- **Pipeline redesign**: The orchestrator, subagent executor, and evidence store are out of scope
- **New data sources**: Futu remains the primary market data provider
- **Auto-execution**: No broker integration or order placement
- **Bearish surfaces**: The system remains bullish-only and alert-only
- **Marketing landing page**: This is not a marketing document
- **PPT deck**: Slides are not the target output
- **Real-time streaming UI**: This spec covers print/export surfaces only, not live web dashboards

---

## 12. Acceptance Criteria

### General

- [ ] All text is Chinese-primary, English-secondary with `中文 / English` pattern
- [ ] No mojibake — all strings come from `strings_zh.py` and `strings_en.py`
- [ ] No raw database dumps or unformatted numbers
- [ ] Empty fields display `—` not blank
- [ ] All colors render correctly in both screen and print

### Poster

- [ ] Poster renders correctly at A4 portrait dimensions without overflow
- [ ] Zone 1 (Decision Hero) contains all 3-second decision information
- [ ] Zone 2 (Detail Cards) contains KPI, Thesis, Technical, Instrument, Options, Early Exit
- [ ] Zone 3 (Status Footer) contains Watchlist State and Validation Summary
- [ ] Instrument row shows at most 3 instruments: PRIMARY + CONSERVATIVE + ALTERNATIVE
- [ ] Risk chips appear in Zone 1 and are readable
- [ ] Printed poster fits on a single page

### PDF Report

- [ ] Page 1 shows Batch Overview table and Executive Summary
- [ ] Pages 2+ show one company report per page
- [ ] Final page shows Watchlist table and Validation table
- [ ] Company report card does not split across pages
- [ ] Table headers repeat on page breaks if table continues
- [ ] `page-break-*` CSS rules work correctly in Edge headless PDF export

### Data Mapping

- [ ] `PositionDecisionCard` fields populate the correct poster sections
- [ ] `InstrumentRecommendation` correctly marks PRIMARY / CONSERVATIVE / ALTERNATIVE
- [ ] `OptionsStructure` renders the Options Structure card only when options are applicable
- [ ] `EarlyExitPlan` renders the Early Exit section with three zones
- [ ] `WatchlistEntry` populates the poster footer status badge and report final page table
- [ ] `ValidationResult` populates the poster footer chips and report final page table

### Bilingual

- [ ] All section labels use Chinese primary + English secondary
- [ ] Instrument names use the fixed terminology table (no synonyms)
- [ ] Watchlist status uses the fixed terminology table
- [ ] All dates use `YYYY-MM-DD` format
- [ ] All percentages use `XX%` notation

### Visual

- [ ] Action color `#E85A3C` used only for primary action and emphasis
- [ ] Positive color `#2DD4A8` used only for conviction, support, and positive indicators
- [ ] Risk color `#C0392B` used only for risk chips and loss indicators
- [ ] Font stack includes Noto Sans SC for CJK compatibility
- [ ] All interactive/decorative colors pass `print-color-adjust: exact`

### Technical

- [ ] `export_poster_pdf()` correctly accepts all decision objects
- [ ] `export_batch_report_pdf()` correctly accepts all decision objects
- [ ] `render_boss_poster()` correctly accepts all decision objects
- [ ] `render_batch_report()` correctly accepts all decision objects
- [ ] PDF export via Edge headless produces valid PDF files
- [ ] No regressions in existing `export_task_pdf()` function

---

## Appendix: File Targets

This spec governs changes to the following files:

| File | Role |
|------|------|
| `agent/research_v1/report_templates/renderer.py` | Poster and batch report rendering logic |
| `agent/research_v1/report_templates/boss_poster_base.html` | Poster HTML template |
| `agent/research_v1/report_templates/boss_report_base.html` | Batch report HTML template |
| `agent/research_v1/report_templates/boss_report_pdf.css` | Shared CSS for poster and report |
| `agent/research_v1/report_templates/strings_zh.py` | Chinese string constants |
| `agent/research_v1/report_templates/strings_en.py` | English string constants |
| `agent/research_v1/report_pdf.py` | PDF export functions (no business logic changes) |

No other files in `agent/research_v1/` are in scope for this redesign.
