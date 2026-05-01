# Boss Console

P51 boss web console package. Renders a static local WebUI from existing
P49/P50 governance artifacts.

P55 applies the Claude Design V2.1 cockpit visual language to the rendered
HTML — glass top chrome, glass command bar, market regime strip, watchlist
heatmap card, terminal-like report center, chart-first ticker workspace, and
side-rail evidence health and review queue. Status badges are reduced to the
boss-readable set (Ready / Limited / Stale / Sample / Blocked / Missing) and
no raw provider/monitor codes leak into the visible UI.

## Modules

- `console_model.py` — scans governance directories and builds a boss-facing model.
- `console_renderer.py` — renders deterministic HTML from the console model.
- `console_runtime.py` — orchestrates model building and HTML/JSON output.
- `static/boss_console.css` — design tokens and layout CSS.

## Usage

```bash
/opt/homebrew/bin/python3.11 -m agent.research_v1.batch_cli boss-console-run \
  --governance-root output/governance \
  --output-dir output/console \
  --tickers ZETA,NVDA
```

P51 is presentation-only. It does not call Futu, run research, invoke
`final_judge`, or expose broker/order controls. Chart and heatmap slots
are placeholders for P52.

When P52 artifacts exist at `p52_market_visual_snapshot.json` and
`p52_assets/`, P51 reads them and inlines K-line SVGs and the watchlist
heatmap instead of the placeholders. P51 does not call the P52 runtime;
it only reads existing artifacts. OpenD must be running and logged in
for live P52 visualization.

## P55 V2.1 Notes

P55 is presentation-only. The renderer enforces the V2.1 boss-facing copy
rules at HTML emit time:

- Allowed labels: Open workspace, Request brief, Open PDF, Open HTML,
  Refresh evidence, Configure view, Review guardrails, Build brief,
  Run preview.
- Forbidden labels in the boss-facing main UI: Buy now, Sell now, Hold
  thesis, Place order, Submit order, Unlock trade, Trade unlock, Copy
  trade, Auto trade, Follow this trade, Guaranteed edge, Production
  approved, Model promoted. Raw phase codes (e.g. `P37`, `P48`) are not
  surfaced in the visible UI.
- No forbidden trading-instruction vocabulary outside the explicit DON'T
  list. The renderer raises `ValueError` if any forbidden term or phrase
  is detected in the final HTML.

The CSS lives in `static/boss_console.css`. Tokens are append-only from the
P51 base. Glass surfaces fall back to opaque tokens automatically when the
browser does not support `backdrop-filter`. Motion respects
`prefers-reduced-motion`.

## P53 Integration

P53 (`boss_one_command.py`) orchestrates P49 → P52 → P50 → P51 in a single
command and writes the console under `output/boss/YYYY-MM-DD/`. The boss
console HTML is the primary entrypoint printed by the CLI.
