# Hermes Design System

## Product Context

Hermes is a local boss research cockpit for market analysis, evidence review,
and PDF-first investment research briefs. It is for a single decision-maker and
their research operator. The product should feel like an institutional research
desk: calm, precise, premium, and evidence-aware.

Hermes is not a broker, trading terminal, social feed, marketing landing page,
or generic SaaS dashboard.

## Aesthetic Direction

Direction: warm institutional research cockpit.

Use a warm paper base, disciplined information density, restrained status
colors, and clear report actions. The interface should feel closer to an
investment committee workbench than a startup landing page.

Influences:

- ZenTrading: low-friction ticker entry, market tape, chart-first ticker page.
- Coinbase: financial trust through restrained surfaces and functional accent.
- Revolut: semantic status colors and confident touch targets.
- Linear: precise dashboard hierarchy and subtle borders.
- Existing Hermes reports: premium, editorial, boss decision-first.

## Color Palette

```css
:root {
  --bg-page: #f6f1e8;
  --bg-surface: #fffaf2;
  --bg-surface-muted: #eee6d8;
  --bg-ink: #151515;
  --text-primary: #24211f;
  --text-secondary: #5d5750;
  --text-muted: #8c8378;
  --accent-rust: #b5543e;
  --accent-copper: #d19a72;
  --accent-blue: #315f8c;
  --status-ready: #327a5b;
  --status-limited: #b7791f;
  --status-blocked: #a13d3d;
  --status-sample: #626a76;
  --border-soft: rgba(36, 33, 31, 0.12);
  --border-strong: rgba(36, 33, 31, 0.22);
}
```

Color rules:

- Use rust/copper for primary interface actions.
- Use green/yellow/red only for evidence status.
- Use blue only for informational links and market-context details.
- Do not use decorative gradients or large ornamental color fields.

## Typography

- Display: `Georgia`, `Times New Roman`, serif.
- UI/body: `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, sans-serif.
- Data: `ui-monospace`, `SFMono-Regular`, `Menlo`, monospace.

Scale:

| Role | Size | Weight | Notes |
|------|------|--------|-------|
| Page title | 32px | 500 | Serif, rare |
| Section title | 20px | 600 | Sans |
| Card title | 16px | 650 | Sans |
| Body | 14px | 400 | Sans |
| Meta | 12px | 600 | Uppercase allowed |
| Data | 12px | 500 | Monospace |

No viewport-scaled font sizes. No negative letter-spacing.

## Components

- Market tape: compact horizontal strip, small data chips, positive/negative state.
- Command bar: one dominant ticker input and one primary action.
- Status badge: Ready, Limited, Missing, Sample, Stale.
- Report card: ticker, verdict, evidence status, PDF/HTML actions.
- Evidence matrix: rows for Live Data, Regime, Fundamentals, Outcomes, Guardrails, Monitor.
- Ticker workspace: chart slot, verdict card, tabs/anchors, files section.
- Chart slot: placeholder in P51 labeled "P52 Futu chart".
- Heatmap slot: placeholder in P51 labeled "P52 watchlist heatmap".

## Layout

- Max content width: 1240px.
- Base spacing: 8px.
- Page gutters: 24px desktop, 16px tablet, 12px mobile.
- Border radius: 6px for controls and cards, 999px for compact badges only.
- Cards must not be nested inside other cards.
- Dense tables are allowed only in evidence/files sections.

## Do's and Don'ts

Do:

- Put the ticker input and latest report actions above the fold.
- Label sample evidence as "Preview sample — not decision-grade".
- Show PDF links before JSON links.
- Keep status colors semantic.
- Keep chart/heatmap placeholders honest when data is not loaded.

Don't:

- Show raw phase logs as the main page.
- Put long absolute paths in primary cards.
- Use BUY/SELL as the primary UI language.
- Add place order, submit order, unlock trade, production approved, model promoted, guaranteed edge, or follow this trade affordances.
- Hide missing evidence.

## Responsive Behavior

- Desktop: cockpit grid with market tape, command bar, status cards, report center, ticker workspace.
- Tablet: status cards become two columns; report center remains table/card hybrid.
- Mobile: single column; report actions remain visible; market tape becomes horizontal scroll.

## Agent Prompt Guide

When building Hermes UI:

1. Read this file before visual decisions.
2. Build a research cockpit, not a landing page.
3. Use `--bg-page: #f6f1e8` and restrained rust/copper actions.
4. Prefer PDF/HTML report actions over raw artifact paths.
5. Always show sample/missing/stale evidence explicitly.
6. Never introduce broker/order controls.
