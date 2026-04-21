# AGENT.md — agent/ Directory

## Responsibilities

This directory is the Python package namespace. Its only role is to be a valid Python
package that exposes `agent.research_v1` as the canonical implementation module.

## Boundaries

- **Do NOT** add business logic at the `agent/` root level.
- **Do NOT** create new top-level modules here — all new code goes under `agent/research_v1/`.
- **Do NOT** add packages other than `research_v1` unless they are truly orthogonal
  (e.g., a future `research_v2`).

## What Lives Here

| File/Dir | Purpose | Notes |
|---|---|---|
| `research_v1/` | Canonical pipeline | Primary implementation |
| `research_v1/researchers/` | Legacy bull/bear researchers | Frozen — do not modify |

## Modifying This Directory

No code changes should be made to `agent/` root. If you find yourself wanting to modify
this directory, you almost certainly want to modify `agent/research_v1/` instead.

## Key Interfaces

This directory has no business logic. All interfaces are in `agent/research_v1/`.

## Upstream / Downstream

- **Upstream**: Python import system resolves `agent.research_v1`
- **Downstream**: `tests/agent/research_v1/` tests this package

## Change Propagation

No code changes should be made to `agent/`. If you find yourself wanting to modify
this directory, you almost certainly want to modify `agent/research_v1/` instead.

## Tests

Tests live in `tests/agent/research_v1/` — not in `agent/`.
