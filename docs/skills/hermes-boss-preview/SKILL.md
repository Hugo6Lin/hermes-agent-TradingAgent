---
name: hermes-boss-preview
description: Use when the boss gives tickers and wants a Hermes V1 preview. Run the one-command boss preview runner instead of manually chaining governance commands.
---

# Hermes Boss Preview

When the boss gives tickers, use:

```bash
/opt/homebrew/bin/python3.11 -m agent.research_v1.batch_cli boss-preview-run \
  --tickers NVDA,AMZN,MSFT \
  --output-root output/governance
```

Rules:

- Use live Futu readiness by default.
- Use `--no-live` only when the boss explicitly asks for offline preview.
- Pass `--output-root output/governance`, not a date-suffixed directory.
- Read `output/governance/YYYY-MM-DD/boss_preview.md` first.
- Explain live vs sample vs missing evidence before technical details.
- Do not place trades, submit orders, call `HermesResearchApp.run()`, call `final_judge`, train models, schedule jobs, or mutate production config.
