# `AGENT.md` - Hermes Repository Guide

## Repository Identity

Hermes is a boss-first trading research system.

The repository now has a clear mainline:

- canonical research pipeline in `agent/research_v1/`
- image-report delivery pipeline for boss-facing outputs

If you are a new model taking over this repo, do not start from old PDF/web-template assumptions.
The current strategic report direction is image-report-first.

## Primary Working Directory

The single most important code directory is:

- [agent/research_v1/](/E:/hermes-agent/agent/research_v1)

That is where:

- research judgment is produced
- bullish decision layers are computed
- report delivery inputs are assembled
- manual/openai image report generation is triggered

## Main Product Path

```text
request
-> HermesResearchApp.run()
-> TickerResearchResult
-> HermesResearchApp.generate_image_report()
-> OrchestratorReportPack
-> ImagePromptPack
-> manual job bundle OR OpenAI images
```

## What To Read First

Any successor model should read in this order:

1. [README.md](/E:/hermes-agent/README.md)
2. [agent/research_v1/README.md](/E:/hermes-agent/agent/research_v1/README.md)
3. [agent/research_v1/AGENT.md](/E:/hermes-agent/agent/research_v1/AGENT.md)
4. [2026-04-22-hermes-image-report-pipeline-spec.md](/E:/hermes-agent/docs/superpowers/specs/2026-04-22-hermes-image-report-pipeline-spec.md)

## Boundaries

### Research authority

Research authority remains in the canonical pipeline.

Do not let report delivery:

- redefine the action
- change the thesis
- change numeric facts
- override watchlist or validation semantics

### Delivery authority

Delivery may:

- repackage content
- build prompts
- generate image artifacts

Delivery may not:

- become the investment decision maker

## Current Report Delivery Modes

### Manual mode

- produces jobs bundle + prompt transcripts + manifest
- used for human-in-the-loop image generation

### OpenAI mode

- produces real image artifacts using `gpt-image-2`
- requires `OPENAI_API_KEY`

## Change Propagation

If you change:

- `agent/research_v1/app.py`
  - check image-report and research integration tests

- `agent/research_v1/orchestrator_reporting.py`
  - check `OrchestratorReportPack` fidelity

- `agent/research_v1/image_prompt_builder.py`
  - check page-count and prompt-generation tests

- `agent/research_v1/image_report_generator.py`
  - check manual/openai backend behavior and manifest handling

- `agent/research_v1/image_report_service.py`
  - check top-level generation path

## What Not To Do

1. Do not revive the old HTML/CSS/PDF-first Phase 19 as the mainline.
2. Do not regress boss-facing wording into generic `BUY/HOLD/SELL`.
3. Do not add bearish actions.
4. Do not add auto-trading.
5. Do not treat image generation failure as research failure.

## Verification

Run from repo root:

```bash
python -m pytest tests/agent/research_v1/test_image_report_pipeline.py -q
```

Also run any affected research tests if you touched upstream decision logic.
