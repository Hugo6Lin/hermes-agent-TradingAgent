# Hermes P55 Boss Cockpit V2.1 UI Integration Spec

## Purpose

P55 is the engineering implementation pass that ports the Claude Design V2.1
cockpit visual language into the actual generated boss surfaces:

- the P51 boss web console (`output/boss/<as-of>/boss_console.html`)
- the P50 boss PDF brief HTML preview that feeds the PDF render

P55 is presentation-only. It does not run research, call providers, invoke
`final_judge`, mutate recommendations, expose broker/order/trading controls,
or include any imperative trading copy.

## Inputs

Claude Design V2.1 package (already on disk):

- `Hermes Cockpit V2.1.html`
- `tokens-v21.css`
- `components-v21.jsx`
- `screen-console-v21.jsx`
- `screen-workspace-v21.jsx`
- `screen-brief-v21.jsx`
- `screen-notes-v21.jsx`

Hermes implementation references:

- `agent/research_v1/boss_console/console_renderer.py`
- `agent/research_v1/boss_console/console_model.py`
- `agent/research_v1/boss_console/static/boss_console.css`
- `agent/research_v1/boss_pdf_brief_renderer.py`

P54 design spec/plan:

- `docs/superpowers/specs/2026-05-02-hermes-p54-boss-cockpit-visual-upgrade-spec.md`
- `docs/superpowers/plans/2026-05-02-p54-boss-cockpit-visual-upgrade.md`

## Implementation Scope

### 1. Boss Console (P51)

Apply the V2.1 cockpit language to the rendered HTML:

- glass top chrome with brand mark, nav tabs, as-of timestamp, overall
  evidence-health badge,
- glass command bar with ticker input, primary `Run Boss Preview`, glass
  `Open workspace` and `Request brief` actions,
- full-width market regime strip,
- watchlist heatmap card (P52 visual asset slot preserved),
- report center as a terminal-like dense table with `Open PDF` and
  `Open HTML` actions per row,
- ticker workspace with chart-first layout and Evidence Matrix,
- side rail with live data status, evidence health, today's review queue.

All status badges must reduce to the boss-readable set:

`Ready`, `Limited`, `Stale`, `Sample`, `Blocked`, `Missing`.

### 2. Boss PDF Brief (P50)

Apply the V2.1 brief preview language to the rendered HTML/PDF:

- paper-memo letterhead and editorial spacing,
- top "10-second read" executive strip with five cells:
  `Verdict · Price context · Trusted evidence · Evidence gaps · Next review action`,
- always-visible evidence-gaps section (`Evidence gaps · do not hide`),
- evidence matrix and trusted-vs-not-decision-grade split,
- PDF-safe typography fallbacks (Georgia / system-ui / ui-monospace).

Evidence gaps must be visible, separate, and never collapsed.

### 3. Static CSS Tokens

Tokens live in `agent/research_v1/boss_console/static/boss_console.css`. P55
adds the V2.1 token system — surfaces, glass, ink, status, market direction,
type, radii, spacing, shadows, motion — and a reduced-glass fallback for
browsers that do not support `backdrop-filter`. The CSS is static-first: no
external JS, no CDN, no web-font dependency.

## Hard Boundaries

P55 must NOT add any of the following:

- broker/order/trading controls,
- account, position, margin, unlock, trade ticket, order ticket, submit
  order, place order, copy trade, auto trade UI,
- imperative trading copy (`buy now`, `sell now`, `follow this trade`,
  `guaranteed edge`),
- production-approved or model-promoted language,
- calls to `HermesResearchApp.run()`, `final_judge`, `SubagentExecutor`, or
  any LLM client,
- creation of `CanonicalSignal` or `CanonicalReport`,
- mutation of `JudgeInputPacket`,
- Futu trade/account/order APIs,
- raw phase codes (e.g. `P37`, `P48`) or raw provider/monitor statuses
  (e.g. `provider_ready`, `monitor_red`, `prompt_pack_limited`,
  `visual_assets_missing_data`, `blocked_missing_context`) in the visible
  boss UI.

## Allowed Labels

`Open workspace`, `Request brief`, `Open PDF`, `Open HTML`, `Refresh
evidence`, `Configure view`, `Review guardrails`, `Build brief`,
`Run preview`.

## Forbidden Labels

`Buy now`, `Sell now`, `Hold thesis`, `Place order`, `Submit order`,
`Unlock trade`, `Trade unlock`, `Copy trade`, `Auto trade`, `Follow this
trade`, `Guaranteed edge`, `Production approved`, `Model promoted`. Raw
phase codes such as `P37`/`P48` may appear in internal docs and tests but
not in the boss-facing main UI.

## DO List (V2.1 boss copy)

- Use `Thesis stable` (not `Hold thesis · Stable`).
- Show every sample/stale/missing evidence state explicitly.
- Lead the brief with the verdict, not the ticker.
- Show `Open PDF` before `Open HTML`.
- Keep raw provider/monitor codes out of the visible UI.

## DON'T List (V2.1 boss copy)

- No `Buy now`, `Sell now`, `Hold thesis`, `Place order`, `Submit order`,
  `Unlock trade`, `Trade unlock`, `Copy trade`, `Auto trade`,
  `Follow this trade`, `Guaranteed edge`, `Production approved`,
  `Model promoted`.
- No raw phase codes or database/table names in the primary UI.

No forbidden trading-instruction vocabulary outside the explicit DON'T list.

## Acceptance Criteria

P55 is acceptable when:

- The rendered console contains the V2.1 visual anchors: glass top chrome,
  brand mark, command bar, market regime strip, watchlist heatmap card,
  report center, ticker workspace, evidence matrix, evidence health, today's
  review queue.
- The rendered console contains zero raw provider/monitor statuses.
- The rendered console contains zero forbidden trading-instruction phrases.
- Boss-readable status badges (Ready / Limited / Stale / Sample / Blocked /
  Missing) replace lowercase / raw labels.
- The brief HTML contains the 10-second read strip with all five labels.
- The brief HTML contains the always-visible evidence-gaps section.
- The brief HTML uses PDF-safe typography fallbacks (no Google Fonts /
  unpkg / `@import`).
- SVG inlining remains hardened (no script, no event handlers, no
  foreignObject, no external href/src).
- All P55 regressions plus P50/P51/P52/P53 baseline tests pass.

## Verification

```
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_boss_console.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_boss_pdf_brief_renderer.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_market_visual_assets.py tests/agent/research_v1/test_boss_one_command.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Optional offline smoke:

```
/opt/homebrew/bin/python3.11 -m agent.research_v1.batch_cli \
  --app-root /Users/yogo/Documents/Codex-Homeland/hermes-agent-TradingAgent \
  boss-one-command-run \
  --tickers ZETA,NVDA --as-of-date 2026-05-02 \
  --output-root output/boss/p55-ui-smoke \
  --governance-root output/governance/p55-ui-smoke \
  --no-live --no-pdf
```

Inspect: `output/boss/p55-ui-smoke/2026-05-02/boss_console.html`.
