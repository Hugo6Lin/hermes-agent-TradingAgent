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
