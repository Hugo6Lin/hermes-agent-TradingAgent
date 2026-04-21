# docs/ — System Documentation

## What This Directory Is

Documentation for Hermes: system overviews, developer guides, and user manuals.

## Contents

| File | Language | Audience | Purpose |
|---|---|---|---|
| `system-overview.md` | Chinese | Boss/User | System capabilities overview |
| `boss-manual.md` | Chinese | Boss | How to use the research desk |
| `system-architecture.md` | English | Developer | Canonical pipeline architecture |
| `product-acceptance.md` | English | Developer | Phase 13 acceptance criteria |
| `developer-workflow.md` | English | Developer | Dev conventions and workflow |
| `workflow-diagram.html` | English | Developer | Pipeline flow diagram |
| `skills/` | Various | Operator | Futu OpenD setup and API reference |
| `superpowers/` | Various | Agent | Planning and execution skills |

## Relationship to Other Directories

- `agent/research_v1/` — implementation that docs describe
- `README.md` (root) — entry point for all docs
- `AGENT.md` (root) — agent instructions

## If You Modify Code Here

- No business logic code should be added to `docs/`
- Adding new docs does not require test updates
- If you add a new doc about a new feature, link it from `README.md`

## Data Flow / How It Fits

`docs/` is purely descriptive — it captures system intent and design decisions rather than
implementing behavior. Documents here are consumed by developers and operators to
understand how the codebase works. They do not affect runtime behavior.
