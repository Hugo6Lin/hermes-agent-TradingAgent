# AGENT.md — agent/research_v1/researchers/

## Responsibilities

None. This directory is **frozen legacy code**.

## Boundaries

**Do NOT:**
- Modify any file in this directory
- Add new researcher features here
- Import from this module in new canonical code

## What NOT to Do

- Do NOT add new features to `research_manager.py`
- Do NOT create new researcher subclasses here
- Do NOT wire these researchers into the canonical pipeline

## Legacy Replacement

Replaced by `subagent_executor.py` + `analysts/` (Phase 11+).
