# AGENT.md — docs/

## Responsibilities

Documentation only. No code or tests belong here.

## Boundaries

**Do NOT:**
- Add Python code to docs/
- Add tests to docs/
- Create architecture decision records (ADRs) unless explicitly asked

**Do:**
- Keep docs/ descriptions accurate when implementation changes
- Link new features from `README.md` (root)
- Update `system-architecture.md` when pipeline structure changes

## Doc Categories

| Category | Files | When to Update |
|---|---|---|
| System docs | `system-architecture.md`, `system-overview.md` | Pipeline structure changes |
| User docs | `boss-manual.md` | New user-facing features |
| Dev docs | `developer-workflow.md`, `product-acceptance.md` | Process changes |
| Skills | `skills/` | Futu setup/config changes |

## Key Interfaces

Documentation in this repository is written in Markdown. No code interfaces.

## Upstream / Downstream

- **Upstream**: `agent/research_v1/` — implementation changes may require doc updates
- **Downstream**: None — docs are leaf nodes

## Change Propagation

When implementation changes require user/developer-facing documentation:
- Pipeline structure → update `system-architecture.md`
- New user feature → update `boss-manual.md`
- New developer process → update `developer-workflow.md`
- Acceptance criteria change → update `product-acceptance.md`

## What NOT to Do

- Do NOT add Python code to docs/
- Do NOT add tests to docs/
- Do NOT create architecture decision records (ADRs) unless explicitly requested
- Do NOT hardcode implementation details that will change in system docs
