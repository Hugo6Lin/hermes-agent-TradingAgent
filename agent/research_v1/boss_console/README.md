# Boss Console

P51 boss web console package. Renders a static local WebUI from existing
P49/P50 governance artifacts.

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

## P53 Integration

P53 (`boss_one_command.py`) orchestrates P49 → P52 → P50 → P51 in a single
command and writes the console under `output/boss/YYYY-MM-DD/`. The boss
console HTML is the primary entrypoint printed by the CLI.
