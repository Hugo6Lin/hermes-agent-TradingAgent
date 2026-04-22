# P19 Image Report Pipeline Spec

Date: 2026-04-22
Status: Approved architecture draft
Owner: Reviewer-authored clean spec
Scope: Replaces Phase 19 HTML/CSS/PDF-first direction with an image-report-first pipeline

## 1. Purpose

Hermes should stop treating the boss-facing report as a Web UI or PDF templating problem.
The new Phase 19 direction is:

1. Hermes completes research normally.
2. Hermes produces a structured report content pack.
3. An image model turns that pack into a boss-facing poster plus a small image report set.
4. Hermes saves the generated images locally and reports completion.

This phase exists to improve report style and presentation quality without weakening the underlying research pipeline.

## 2. Core Product Decision

The final boss-facing deliverable is an image set, not a template-rendered HTML/PDF page.

Default deliverable shape:

- Page 1: Boss decision poster
- Page 2: Formal research summary page
- Page 3: Optional detail page when the ticker is structurally complex

Page count is adaptive, but should usually stay at 1 to 3 pages.

## 3. Non-Goals

This phase does not:

- change thesis logic
- change instrument-selection logic
- change options logic
- change watchlist logic
- change validation logic
- introduce bearish actions
- introduce auto-trading
- make the image model the investment decision authority
- preserve HTML/CSS/PDF as the main user-facing report route

Legacy HTML/CSS/PDF report code may remain temporarily for compatibility, but it is no longer the product direction.

## 4. Authority Split

This phase depends on a strict split of responsibility.

### 4.1 Hermes / orchestrator authority

Hermes remains the source of truth for:

- research conclusions
- primary action
- conviction
- position sizing guidance
- target window
- risk framing
- thesis summary
- instrument choice
- options structure
- early exit guidance
- watchlist state
- validation state
- must-show numeric facts

### 4.2 Image model authority

The image model is responsible only for:

- visual composition
- layout hierarchy
- poster/report page styling
- concise page-ready phrasing expansion
- converting structured content into readable image artifacts

The image model must not:

- invent a different trade action
- replace Hermes risk conclusions
- alter numeric facts
- reinterpret the thesis independently

## 5. Architectural Principle

The new Phase 19 architecture is:

```text
Research Inputs
-> HermesResearchApp pipeline
-> TickerResearchResult
-> OrchestratorReportPack
-> ImagePromptPack
-> gpt-image-2 generation
-> Local image artifacts
-> Hermes completion notification
```

The investment decision is finalized before image generation begins.

## 6. Product Surfaces

### 6.1 Primary surface: image report set

The user-facing report should be generated as image artifacts:

- poster image
- report page images

Preferred initial format:

- `.png`

Optional later additions:

- `.jpg`
- image bundle manifest

### 6.2 Deprecated primary surface

The following are no longer the main Phase 19 product surface:

- HTML report templates
- CSS report templates
- PDF-first report rendering
- poster-as-web-page

These may remain in code temporarily, but must not define the new architecture.

## 7. Required Objects

Phase 19 must introduce three new core objects.

### 7.1 OrchestratorReportPack

This is the content truth that the image generation layer consumes.

It is built after the research pipeline completes.

It must be derived primarily from:

- `TickerResearchResult`
- `decision_card`
- `instrument_recommendation`
- `options_structure`
- `early_exit`
- `watchlist_entry`
- `validation`
- `CanonicalSignal`
- `CanonicalReport`
- `trade_plan`

It must not be derived primarily from old generic rating/trade-plan presentation shells.

### 7.2 ImagePromptPack

This is the image-generation control layer.

It translates `OrchestratorReportPack` into:

- page-specific prompts
- style rules
- content priorities
- forbidden phrasing
- page-count decision

### 7.3 ImageReportArtifacts

This is the saved-output layer.

It must record:

- task id
- ticker
- generated page count
- local file paths
- generation timestamps
- model used
- prompt metadata

## 8. OrchestratorReportPack Contract

The first implementation should define the following sections.

### 8.1 report_identity

Fields:

- `task_id`
- `ticker`
- `company_name`
- `generated_at`
- `language`
- `report_type`
- `recommended_page_count`

Rules:

- `language` defaults to `zh-CN`
- `report_type` defaults to `boss_image_report`

### 8.2 decision_locked

These are read-only mapped decision facts.

Fields:

- `primary_action`
- `conviction`
- `suggested_size`
- `target_window`
- `entry_reference`
- `target_reference`
- `stop_reference`
- `primary_instrument`
- `validation_confidence`
- `watchlist_state`
- `alert_level`

Rules:

- These fields must not be creatively rewritten.
- Formatting is allowed.
- Meaning changes are not allowed.

### 8.3 boss_narrative

These are orchestrator-authored boss-readable content blocks.

Fields:

- `boss_summary`
- `why_now`
- `top_risks`
- `one_line_call`

Rules:

- These may be rewritten for clarity.
- They must remain faithful to `decision_locked`.
- If narrative conflicts with locked facts, locked facts win.

### 8.4 research_core

Fields:

- `thesis_summary`
- `bull_case`
- `bear_case`
- `catalysts`
- `technical_summary`
- `valuation_summary`
- `must_show_numbers`

Rules:

- `must_show_numbers` contains all numeric facts that must be preserved visually.
- The image model may rephrase narrative around them, but not alter them.

### 8.5 instrument_plan

Fields:

- `primary_instrument_label`
- `conservative_alternative`
- `alternative_instrument`
- `instrument_choice_reason`
- `options_structure_summary`
- `early_exit_summary`
- `options_key_numbers`

Rules:

- This section must reflect the true Phase 14-15 outputs.
- It must not collapse back to generic BUY/HOLD/SELL wording.

### 8.6 monitoring_state

Fields:

- `watchlist_summary`
- `validation_summary`
- `main_failure_mode`
- `environment_fit`
- `historical_support`
- `regime`

Rules:

- This section is support material, not the main poster conclusion.

## 9. Content Writing Rules

### 9.1 boss_summary

Purpose:

- let a boss understand the call in 3 seconds

Rules:

- 2 to 4 short sentences
- sentence 1 gives the action
- sentence 2 gives the thesis
- sentence 3 gives the time horizon or payoff framing
- sentence 4, if used, states the biggest limiting condition

Must not:

- contradict `primary_action`
- sound like marketing copy
- become a long paragraph

### 9.2 why_now

Purpose:

- explain why the timing is justified now

Rules:

- exactly 3 bullets by default
- each bullet is one short sentence
- should usually cover:
  - thesis or earnings direction
  - catalyst or valuation support
  - timing or instrument fit

### 9.3 top_risks

Purpose:

- show what is most likely to break the trade or thesis

Rules:

- 3 bullets by default
- ordered by severity
- should usually cover:
  - thesis risk
  - timing or market risk
  - instrument or options execution risk

## 10. Approved Action Vocabulary

Visible action language must use the approved Hermes bullish-only set:

- `Buy Stock`
- `Buy Call`
- `Bull Call Spread`
- `Sell Cash-Secured Put`
- `Covered Call`
- `Watchlist`
- `No Trade`

Chinese display labels must align to this exact set.

Generic visible UI labels such as:

- `BUY`
- `HOLD`
- `SELL`

must not become the visible primary report language.

They may exist only as compatibility data inside older system layers.

## 11. Chinese-First Requirement

The generated images must be Chinese-first.

That means:

- Chinese is the main visible label language
- English is secondary support text
- all fixed Chinese label strings must be provided by Hermes
- image prompts must explicitly require readable Chinese text

Because text rendering in image generation can drift, Phase 19A manual validation may tolerate some iteration.
However, the intended product surface remains Chinese-first.

## 12. ImagePromptPack Contract

The first implementation should define:

- `model`
- `page_count`
- `global_style_rules`
- `page_prompts`
- `must_show_labels`
- `forbidden_phrasing`
- `visual_priority_order`

### 12.1 model

Default:

- `gpt-image-2`

### 12.2 page_prompts

Each page prompt should include:

- page role
- source content section mapping
- hard facts to preserve
- visual hierarchy rules
- language rules
- things not to invent

## 13. Page Responsibilities

### 13.1 Page 1 - boss poster

Must emphasize:

- primary action
- conviction
- ticker / company
- suggested size
- target window
- why now
- top risks

It must feel like a decision board, not a web page and not a slideshow.

### 13.2 Page 2 - formal research summary

Must usually emphasize:

- thesis summary
- catalysts
- valuation view
- technical summary
- must-show numbers

### 13.3 Page 3 - optional detail page

Used only when needed.

Typical use cases:

- options structure detail
- early exit detail
- validation and monitoring detail
- complex multi-factor risks

## 14. Visual Direction

The image-generation prompts must target:

- premium executive finance design
- institutional tone
- Chinese-first hierarchy
- warm neutral background
- orange-red action emphasis
- teal-green positive support emphasis
- restrained red for risk

Must not target:

- marketing poster style
- startup landing page style
- social-media infographic style
- crypto aesthetic
- cartoon finance style

## 15. Local Output Contract

The first implementation should save files under a deterministic workspace path.

Recommended naming:

- `task_<task_id>_<ticker>_page_1.png`
- `task_<task_id>_<ticker>_page_2.png`
- `task_<task_id>_<ticker>_page_3.png`

And:

- `task_<task_id>_<ticker>_manifest.json`

Manifest should include:

- task id
- ticker
- page count
- model used
- local file paths
- generation timestamps
- key prompt metadata

## 16. Failure and Retry Rules

Image generation failure must not invalidate the research result.

Rules:

- research output is primary
- image output is downstream
- image generation failure should return a generation error, not a research failure
- individual page retry should be possible
- page 2 or page 3 failure should not automatically invalidate page 1

## 17. Recommended Module Layout

The first implementation should prefer new modules rather than overloading old report-template code.

Recommended additions:

- `agent/research_v1/image_report_contracts.py`
- `agent/research_v1/orchestrator_reporting.py`
- `agent/research_v1/image_prompt_builder.py`
- `agent/research_v1/image_report_generator.py`
- `agent/research_v1/image_report_service.py`

Recommended behavior:

- keep `orchestrator.py` focused on workflow control
- add report-pack assembly in a companion module
- keep image generation outside the research-decision core

## 18. Recommended Implementation Order

Implement in this order:

1. define image-report contracts
2. build `OrchestratorReportPack`
3. build `ImagePromptPack`
4. add image-generation service abstraction
5. add manual Phase 19A generation flow
6. validate with 3 representative scenarios

Do not start with:

- HTML template cleanup
- CSS redesign
- PDF refactor

## 19. Validation Scenarios

The first manual validation round should cover:

1. `Buy Stock`
2. `Buy Call` or `Bull Call Spread`
3. `Sell Cash-Secured Put` or `Covered Call`

For each scenario validate:

- poster quality
- action correctness
- Chinese-first readability
- report-page usefulness
- preservation of locked facts

## 20. Acceptance Criteria

Phase 19A is acceptable when:

1. Hermes can produce a valid `OrchestratorReportPack`
2. Hermes can derive a valid `ImagePromptPack`
3. the image pipeline can generate 1 to 3 local images per ticker
4. image output preserves the true Hermes action and key numeric facts
5. poster page is boss-readable
6. report pages are useful for human review
7. the old HTML/CSS/PDF path is no longer treated as the main architecture

## 21. Explicit Implementation Boundary

This spec authorizes a new image-report pipeline.

It does not authorize:

- deleting the full old report stack in the same change
- rewriting the entire research pipeline
- changing Phase 14-17 decision semantics
- introducing API billing assumptions into manual validation

Phase 19A manual validation may use Codex-assisted image generation for human-in-the-loop testing before full API automation.
