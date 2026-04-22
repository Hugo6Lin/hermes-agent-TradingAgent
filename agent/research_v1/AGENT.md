# `agent/research_v1/AGENT.md`

## Responsibilities

This directory owns the canonical Hermes research pipeline and the Phase 19 image-report delivery layer.

It is responsible for:

- request routing
- workflow orchestration
- evidence normalization
- final signal/report generation
- bullish decision layering
- persistence
- boss-facing image-report preparation and generation

It is not responsible for:

- brokerage execution
- bearish trading features
- autonomous trading
- replacing the underlying decision authority with image generation

## Boundaries

### Research authority

Financial judgment is decided before report generation.

The actual decision authority remains:

- `FinalJudge`
- `thesis_engine`
- `instrument_selection`
- `options_decision`
- `early_exit`
- `watchlist_alerts`
- `validation_engine`

### Report authority

Phase 19 report delivery is downstream of the research result.

- `OrchestratorReportPack` = content truth
- `ImagePromptPack` = generation control layer
- image backend = visual output only

The image layer must not invent a different trade action or numeric fact.

## Key Interfaces

### `HermesResearchApp`

Primary application API:

```python
class HermesResearchApp:
    def run(self, request: str) -> ResearchResult
    def generate_image_report(
        self,
        ticker_result: TickerResearchResult,
        company_name: str = "",
        output_dir: str = "./image_reports",
        mode: str = "manual",
    ) -> ImageReportServiceResult
```

### `TickerResearchResult`

This is the canonical completed research object for one ticker.

Phase 19 work should derive from:

- `signal`
- `report`
- `trade_plan`
- `decision_card`
- `instrument_recommendation`
- `options_structure`
- `early_exit`
- `watchlist_entry`
- `validation`

### `build_report_pack(...)`

Defined in:

- `orchestrator_reporting.py`

Purpose:

- convert `TickerResearchResult` into `OrchestratorReportPack`

### `build_prompt_pack(...)`

Defined in:

- `image_prompt_builder.py`

Purpose:

- convert `OrchestratorReportPack` into page-by-page prompts

### `ImageReportService`

Defined in:

- `image_report_service.py`

Purpose:

- orchestrate the full image-report pipeline

## Upstream / Downstream

### Upstream dependencies

- market data providers
- SQLite persistence
- LLM clients
- optional OpenAI image API via `OPENAI_API_KEY`

### Downstream consumers

- boss/operator workflows
- tests in `tests/agent/research_v1/`
- image artifact directories and manifests

## Main Path

Current main path:

```text
request
-> HermesResearchApp.run()
-> TickerResearchResult
-> HermesResearchApp.generate_image_report()
-> OrchestratorReportPack
-> ImagePromptPack
-> manual job bundle OR OpenAI image generation
```

Important:

- `viewer.py` and `report_pdf.py` are not the strategic Phase 19 mainline anymore
- they may still exist as secondary paths

## Change Propagation

| If you change | You MUST also check |
|---|---|
| `app.py` | `test_app_integration.py`, `test_bullish_decision_integration.py`, `test_image_report_pipeline.py` |
| `contracts.py` | all dataclass consumers, DB serialization, tests |
| `orchestrator.py` | `test_orchestrator.py`, app integration |
| `orchestrator_reporting.py` | `test_image_report_pipeline.py`, action vocabulary, locked-fact fidelity |
| `image_report_contracts.py` | `test_image_report_pipeline.py`, service/generator imports |
| `image_prompt_builder.py` | `test_image_report_pipeline.py`, approved action wording, page-count logic |
| `image_report_generator.py` | `test_image_report_pipeline.py`, manifest behavior, backend mode behavior |
| `image_report_service.py` | `test_image_report_pipeline.py`, `app.py` entrypoint behavior |
| `viewer.py` | `test_p6_viewer.py` |
| `report_pdf.py` | legacy compatibility checks only; do not confuse with new mainline |

## What NOT To Do

1. Do not make the image model the decision authority.
2. Do not let prompt generation override `decision_card.primary_action`.
3. Do not regress visible report language into generic `BUY/HOLD/SELL`.
4. Do not treat manual job bundles as equivalent to actual generated images unless the path is explicitly manual.
5. Do not revive the old HTML/CSS/PDF-first route as the new Phase 19 mainline.
6. Do not change thesis/instrument/options/watchlist/validation semantics while working on report delivery.
7. Do not add bearish actions or auto-trading.

## Phase 19 Modes

### Manual mode

Use when:

- validating prompts
- no API key is configured
- doing human-in-the-loop image generation

Expected outputs:

- jobs bundle JSON
- per-page prompt files
- manifest JSON

### OpenAI mode

Use when:

- `OPENAI_API_KEY` is present
- real image artifacts should be generated automatically

Expected outputs:

- `.png` images
- manifest JSON
- per-page failure isolation

## Tests / Verification

Run from repo root:

```bash
python -m pytest tests/agent/research_v1/test_image_report_pipeline.py -q
python -m pytest tests/agent/research_v1/test_bullish_decision_integration.py -q
python -m pytest tests/agent/research_v1/test_validation_engine.py -q
python -m pytest tests/agent/research_v1/test_watchlist_alerts.py -q
```

If modifying report delivery logic, the image-report pipeline suite is mandatory.

## What a Successor Model Must Understand

A new model taking over Hermes should understand:

1. `run()` produces the real research result
2. `generate_image_report()` is the current boss-report delivery entrypoint
3. `OrchestratorReportPack` is the content truth
4. report generation is downstream and must not change the financial call
5. manual and openai are both valid operating modes
