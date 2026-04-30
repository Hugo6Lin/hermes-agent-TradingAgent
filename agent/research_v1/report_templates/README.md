# `agent/research_v1/report_templates/` - Report Template Assets

## What This Directory Is

This directory contains report template helpers used by older or secondary
Hermes report surfaces.

## Core Files

- `renderer.py` renders HTML report content for legacy report paths.
- `strings_en.py` provides English string constants for report templates.
- `strings_zh.py` provides Chinese string constants for report templates.
- `boss_poster_base.html` is the base HTML template for boss poster reports.
- `boss_report_base.html` is the base HTML template for boss reports.
- `boss_report_pdf.css` is the CSS stylesheet for PDF-oriented boss reports.

## Relationship to Other Directories

Templates here consume canonical research and report objects from
`agent/research_v1/`. They should not create new trading decisions or bypass the
canonical `TickerResearchResult` flow.

## Data Flow

Canonical research output is produced by the main research pipeline, then report
surfaces may format that output for HTML or PDF delivery. P31-P35 governance
artifacts are separate boss-governance outputs and should not be mixed into these
legacy templates unless a future phase explicitly designs that bridge.

## If You Modify This Directory

Update tests for any rendered field or template contract that changes. Keep the
templates presentation-only and avoid adding market-data, broker, or governance
decision logic here.
