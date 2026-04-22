# Boss Model Handoff Prompt

Use this file when the boss changes models and wants the new model to enter Hermes correctly on the first try.

This prompt is designed to prevent the new model from:

- free-form stock chatting
- skipping the real Hermes pipeline
- reviving the old Phase 19 PDF/web-template direction
- inventing its own action vocabulary
- ignoring the image-report delivery path

---

## 1. Full Takeover Prompt

Use this when a new model is taking over Hermes for the first time.

```text
You are taking over Hermes.

Before doing any work, read these files in order:

1. E:\hermes-agent\README.md
2. E:\hermes-agent\agent\research_v1\README.md
3. E:\hermes-agent\agent\research_v1\AGENT.md
4. E:\hermes-agent\docs\superpowers\specs\2026-04-22-hermes-image-report-pipeline-spec.md
5. E:\hermes-agent\docs\superpowers\specs\2026-04-22-hermes-visual-design-v2.md

After reading them, follow these rules:

1. Treat `HermesResearchApp.run()` as the research truth.
2. Treat `HermesResearchApp.generate_image_report()` as the boss-report delivery entrypoint.
3. Do not revive the old Phase 19 HTML/CSS/PDF-first direction as the main path.
4. Do not replace Hermes financial judgment with your own free-form opinion.
5. Keep the approved Hermes action vocabulary:
   - Buy Stock
   - Buy Call
   - Bull Call Spread
   - Sell Cash-Secured Put
   - Covered Call
   - Watchlist
   - No Trade
6. Keep bullish-only and alert-only boundaries.
7. Use the image-report pipeline for boss-facing deliverables.
8. Respect the visual spec when preparing or judging report artifacts.

When I give you ticker(s), do this workflow automatically:

Step 1. Understand the request and identify the target ticker(s).
Step 2. Run or inspect the Hermes research pipeline for those ticker(s).
Step 3. Use the real `TickerResearchResult` fields:
   - signal
   - report
   - decision_card
   - instrument_recommendation
   - options_structure
   - early_exit
   - watchlist_entry
   - validation
Step 4. Generate the boss-facing report through the current Phase 19 path:
   - `mode="manual"` if no API key is available
   - `mode="openai"` if API generation is configured and appropriate
Step 5. Tell me:
   - the primary action
   - the key why-now logic
   - the top risks
   - whether report generation was manual or automatic
   - where the generated artifacts were saved

Default behavior:
- If I only give you ticker(s), assume I want the full Hermes workflow, not just a chat answer.
- If the image path is manual, generate the job bundle and tell me where it is.
- If the image path is automatic, generate the images and tell me where they are.
- If research succeeds but image generation fails, clearly separate the research conclusion from the image-generation failure.
```

---

## 2. Boss Daily Shortcut

Use this when the boss just wants to paste one command into a fresh model:

```text
Read E:\hermes-agent\README.md, E:\hermes-agent\agent\research_v1\README.md, E:\hermes-agent\agent\research_v1\AGENT.md, E:\hermes-agent\docs\superpowers\specs\2026-04-22-hermes-image-report-pipeline-spec.md, and E:\hermes-agent\docs\superpowers\specs\2026-04-22-hermes-visual-design-v2.md first. Then use Hermes' real pipeline, not free-form opinion, to research these ticker(s): <PUT TICKERS HERE>. After research, run the current image-report path and tell me the primary action, why-now, top risks, whether it ran in manual or openai mode, and the saved artifact paths.
```

---

## 3. Single-Ticker Working Prompt

Use this when the boss wants one ticker only:

```text
Read the Hermes handoff docs first, then run the real Hermes pipeline for this ticker: <PUT ONE TICKER HERE>. After the run, give me:
1. the primary action
2. the conviction
3. the three-part why-now logic
4. the top risks
5. the saved image-report artifact path(s)

If automatic image generation is not available, use manual mode and give me the job bundle path.
```

---

## 4. Multi-Ticker Working Prompt

Use this when the boss wants several names processed together:

```text
Read the Hermes handoff docs first, then run the real Hermes pipeline for these tickers: <PUT MULTIPLE TICKERS HERE>.

For each ticker, do not free-form summarize from memory. Use Hermes' actual outputs.

For each ticker, return:
1. primary action
2. conviction
3. why now
4. top risks
5. image-report generation mode used
6. saved artifact path(s)

If the system produces separate outputs per ticker, keep them clearly separated.
If image generation falls back to manual mode, give me the correct job bundle path for each ticker.
```

---

## 5. Expected Behavior From a Good Successor Model

A correct successor model should:

- read the listed Hermes docs first
- use the real pipeline
- preserve Hermes action vocabulary
- produce or request image-report artifacts through the current P19 path
- clearly tell the boss what was concluded and what was generated

A wrong successor model will:

- give stock opinions without using Hermes
- speak in generic `BUY/HOLD/SELL`
- ignore `generate_image_report()`
- describe old PDF/web templates as the mainline

If a new model behaves like the second group, stop it and give it the full takeover prompt again.
