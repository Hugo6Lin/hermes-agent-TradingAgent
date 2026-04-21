# Hermes Boss Research Desk Design

## Goal

Turn Hermes into a local single-user research desk that can:

- accept a batch of US tickers from the boss through this conversation
- let the assistant act as the research agent
- persist structured research results locally
- show a boss-friendly overview page first
- generate a readable PDF report

This phase does **not** require Hermes to perform its own autonomous LLM research. Hermes should first become a stable product shell that can accept externally produced research results and display them well.

## Product Definition

Hermes becomes a **conversation-driven local research desk**:

1. The boss sends one or more US tickers in chat.
2. The assistant performs research and produces structured conclusions.
3. Hermes stores the batch, per-ticker report data, signal data, and summaries.
4. Hermes renders:
   - a batch overview page
   - per-ticker detail pages
   - a PDF report for the batch

The assistant provides the intelligence layer. Hermes provides persistence, presentation, and export.

## Primary User Workflow

1. Boss sends a list of US tickers.
2. Assistant researches the tickers and prepares structured outputs.
3. Hermes creates a new research batch and stores all results.
4. Boss opens the local Hermes page and sees the batch overview first.
5. Boss drills into any ticker detail page as needed.
6. Boss can request a PDF export for sharing or review.
7. Future updates append new versions instead of overwriting history.

## Scope For This Phase

### In Scope

- local startup flow
- local SQLite persistence
- batch-oriented research storage
- overview-first web UI
- per-ticker detail pages
- PDF generation
- clear interfaces for ingesting assistant-produced research output

### Out Of Scope

- autonomous Hermes reasoning or self-directed research
- broker connectivity
- automated trade execution
- multi-user support
- cloud deployment
- full service orchestration

## Architecture

The system should have three layers.

### 1. Conversation Intelligence Layer

Handled by the assistant in this session.

Responsibilities:

- interpret the boss request
- research the provided tickers
- produce structured conclusions and summaries

This layer is external to the local product shell.

### 2. Hermes Product Layer

Implemented inside the repository.

Responsibilities:

- create and manage research batches
- accept structured research payloads
- save summaries, signals, and narrative reports
- generate overview and detail views
- generate PDF exports

### 3. Persistence And Presentation Layer

Responsibilities:

- store product data in SQLite
- render local web pages
- store generated report artifacts

## Data Model Changes

Existing research tables are useful but insufficient for a boss-facing product. Add product-level tables.

### `research_batches`

Represents one boss request covering multiple tickers.

Suggested fields:

- `batch_id`
- `title`
- `requested_tickers`
- `status`
- `boss_summary`
- `created_at`
- `updated_at`

### `research_batch_items`

Represents one ticker inside a batch.

Suggested fields:

- `item_id`
- `batch_id`
- `symbol`
- `display_rank`
- `overall_rating`
- `confidence`
- `priority_score`
- `action`
- `top_thesis`
- `top_risk`
- `entry_price`
- `stop_loss`
- `take_profit`
- `holding_horizon`
- `updated_at`

### `company_reports`

Stores the readable per-ticker research brief.

Suggested fields:

- `report_id`
- `batch_item_id`
- `bottom_line`
- `why_it_matters`
- `action_plan`
- `bull_case`
- `risk_watch`
- `research_summary`
- `signal_snapshot_json`
- `created_at`

### `report_versions`

Stores historical revisions.

Suggested fields:

- `version_id`
- `report_id`
- `version_label`
- `content_json`
- `created_at`

## Product Entry Points

Add a real application entry module, for example `agent.research_v1.app`.

Required commands:

- `python -m agent.research_v1.app init`
- `python -m agent.research_v1.app viewer`

Strongly recommended commands:

- `python -m agent.research_v1.app create-batch --tickers AAPL,MSFT,NVDA`
- `python -m agent.research_v1.app status`
- `python -m agent.research_v1.app export-pdf --batch-id <id>`

This phase does not require a self-contained autonomous `analyze` command. Research may be injected through a structured ingest flow driven by the assistant.

## Assistant Ingest Contract

Hermes needs one stable path for accepting externally produced research.

Recommended pattern:

- a Python service/helper function such as `save_batch_research(batch_input)`
- or a CLI subcommand that accepts JSON input

The ingest payload should include:

- batch metadata
- per-ticker rank
- per-ticker rating and confidence
- signal fields
- boss-facing summary text
- detailed narrative sections

This contract is the bridge between the assistant's research output and Hermes persistence.

## Web UI Design

The first page must be the batch overview, not a raw table of signals.

### Overview Page

Purpose:

- tell the boss what matters first

Sections:

- batch header
- executive summary
- top opportunities
- ranked ticker cards or rows

Each ticker summary should include:

- ticker
- overall rating
- confidence
- priority rank
- suggested action
- entry / stop / take profit
- top thesis
- top risk
- updated time

### Detail Page

Each ticker detail page should follow a top-down briefing style:

1. bottom line
2. suggested action
3. trade plan
4. bull case
5. risk watch
6. research summary
7. history / prior versions

## PDF Report Design

The PDF should be written for a boss, not an engineer.

Structure:

1. Cover page
2. Executive summary
3. Ranking table
4. Individual stock briefs
5. Appendix and history

The first two pages must be sufficient for a quick decision read.

## Error Handling

The product must fail clearly and locally.

Required behaviors:

- create missing app directories automatically
- initialize missing database tables automatically
- show actionable startup errors
- show empty states when no batches exist
- avoid crashing viewer pages when some sections are missing

## Verification Requirements

Before calling this phase complete, Hermes must demonstrate:

1. `init` creates required local state successfully
2. a research batch can be created and persisted
3. stored batch data renders on the overview page
4. a ticker detail page renders correctly
5. a PDF can be exported from saved batch data

## Implementation Boundaries

This design intentionally avoids building a second research engine inside Hermes right now. The repository should first become reliable at:

- accepting structured research results
- preserving them cleanly
- presenting them clearly

Only after this shell is stable should future work consider making Hermes perform more of the research autonomously.
