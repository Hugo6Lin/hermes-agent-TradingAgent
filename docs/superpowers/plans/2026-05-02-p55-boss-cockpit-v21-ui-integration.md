# P55 Boss Cockpit V2.1 UI Integration Plan

**Goal:** Apply the Claude Design V2.1 cockpit visual language to Hermes' actual
generated boss console (P51) and boss PDF brief HTML (P50). Keep the work
presentation-only and inside Hermes' hard boundaries.

**Architecture:** Static HTML/CSS rendered server-side from existing P49/P50/P51
artifacts. No external JS, no CDN, no web-font dependency. Tokens live under
`agent/research_v1/boss_console/static/`.

**Tech Stack:** Python 3.11, deterministic HTML strings, single inline CSS,
existing P50/P51/P53 runtimes.

---

## Source Files To Read

- `/tmp/hermes-design-v21/Hermes Cockpit V2.1.html`
- `/tmp/hermes-design-v21/tokens-v21.css`
- `/tmp/hermes-design-v21/components-v21.jsx`
- `/tmp/hermes-design-v21/screen-console-v21.jsx`
- `/tmp/hermes-design-v21/screen-workspace-v21.jsx`
- `/tmp/hermes-design-v21/screen-brief-v21.jsx`
- `/tmp/hermes-design-v21/screen-notes-v21.jsx`
- `docs/superpowers/specs/2026-05-02-hermes-p54-boss-cockpit-visual-upgrade-spec.md`
- `docs/superpowers/specs/2026-05-02-hermes-p55-boss-cockpit-v21-ui-integration-spec.md`
- `agent/research_v1/boss_console/console_renderer.py`
- `agent/research_v1/boss_pdf_brief_renderer.py`

## Deliverables

1. Updated `agent/research_v1/boss_console/static/boss_console.css` with the
   V2.1 token system and components.
2. Updated `agent/research_v1/boss_console/console_renderer.py` with the V2.1
   cockpit layout and boss-readable status reduction.
3. Updated `agent/research_v1/boss_pdf_brief_renderer.py` with the V2.1
   paper-memo layout and the 10-second read strip.
4. New regressions in `tests/agent/research_v1/test_boss_console.py` and
   `tests/agent/research_v1/test_boss_pdf_brief_renderer.py`.
5. Updated READMEs (`agent/research_v1/README.md`,
   `agent/research_v1/boss_console/README.md`).
6. Updated docs (this plan + matching spec).

## Task 1: Add P55 Design Tokens

Append the V2.1 tokens to `boss_console.css`:

- glass tokens: `--glass-bg`, `--glass-bg-strong`, `--glass-border`,
  `--glass-border-strong`, `--glass-blur`, `--glass-shadow`,
  `--glass-bg-reduced`, `--glass-border-reduced`,
- ink-glass tokens for dark surfaces,
- status tokens: ready / limited / blocked / sample / stale,
- market direction tokens: up / down / flat,
- type tokens: `--font-display`, `--font-ui`, `--font-data` with PDF-safe
  fallbacks,
- spacing, radii, shadows, and motion tokens.

Add `@supports not (backdrop-filter: blur(...))` reduced-glass fallback and
`prefers-reduced-motion` motion fallback.

**Acceptance:** CSS file present, lints clean, contains glass + status +
chart + motion + radius + shadow tokens, no `@import`, no external font
URLs.

## Task 2: Apply V2.1 Layout to Boss Console

Rewrite `render_console_html` in `console_renderer.py` so the emitted HTML
follows the V2.1 cockpit composition:

1. Glass top chrome with brand mark + nav tabs + as-of timestamp + overall
   evidence-health badge.
2. Glass command bar with ticker input, primary `Run Boss Preview`, glass
   `Open workspace`, glass `Request brief`, and a live data badge group.
3. Full-width market regime strip (8 cells, populated from
   `model.market_tape` when present).
4. Two-column cockpit grid:
   - left: watchlist heatmap card (P52 visual asset slot preserved),
     report center table, ticker workspace card,
   - right: live data status, evidence health, today's review queue.

Centralize boss-readable status reduction so every status field passes
through `_reduce_status` and emits the V2.1 set: Ready / Limited / Stale /
Sample / Blocked / Missing. Add a final HTML-level forbidden-phrase scan
that raises `ValueError` if any of `buy now`, `sell now`, `place order`,
`submit order`, `unlock trade`, `trade unlock`, `copy trade`, `auto trade`,
`follow this trade`, `guaranteed edge`, `production approved`, or
`model promoted` leak through.

**Acceptance:** existing P51 tests still pass; new P55 anchor + raw-status
+ forbidden-phrase tests pass.

## Task 3: Apply V2.1 Layout to Boss Brief

Rewrite `render_boss_brief_html` in `boss_pdf_brief_renderer.py` so the
emitted HTML follows the V2.1 paper-memo composition:

1. Letterhead with `Hermes` wordmark + memo tag + paper meta.
2. Subject row with the title (CLI-overridable) and a status badge.
3. **10-second read** strip with five cells: `Verdict · Price context ·
   Trusted evidence · Evidence gaps · Next review action`.
4. Headline status grid (live data, market regime, evidence base,
   guardrails) — keeps the existing `score-bar` for regime confidence.
5. Trusted-vs-not-decision-grade split.
6. Always-visible **`Evidence gaps · do not hide`** section with a status
   badge, pillar name, and one-line reason per non-Ready phase.
7. Evidence Matrix and Next Actions.
8. Appendix with phase-status table and the standing P50 disclaimer.

PDF-safe typography fallbacks must be inline (`Georgia`, `-apple-system`,
`ui-monospace`). No web-font imports, no `@import`, no external CSS.

**Acceptance:** existing P50 tests still pass; new P55 ten-second-read,
never-collapsed gap, typography-fallback, and forbidden-language tests
pass.

## Task 4: Tests

Add focused regressions covering:

1. Boss console contains the V2.1 visual anchors:
   - `cockpit-chrome`, `brandmark`, `Hermes`, `Boss Console`,
     `command-region`, `Open workspace`, `Request brief`, `market-strip`,
     `Watchlist heatmap`, `Report Center`, `report-table`,
     `Ticker Workspace`, `Evidence Matrix`, `Today's review queue`,
     `Evidence health`.
2. Boss console does NOT contain raw statuses:
   - `provider_ready`, `monitor_red`, `monitor_yellow`,
     `visual_assets_missing_data`, `blocked_missing_context`,
     `prompt_pack_limited`, `boss_preview_ready`, `boss_pdf_brief_ready`,
     `preview-only / Incomplete`.
3. Boss console does NOT leak forbidden trading-instruction language.
4. Console refuses to emit a verdict that contains a forbidden phrase.
5. Status badges in the matrix use V2.1 boss-readable labels and not their
   lowercase variants.
6. Boss brief contains the 10-second read strip with all five labels.
7. Boss brief evidence gaps section is always visible, never collapsed.
8. Boss brief uses PDF-safe typography fallbacks.
9. Boss brief does not leak forbidden trading-instruction language.
10. SVG inlining still rejects script / event handlers / foreignObject /
    external href.

## Task 5: Documentation

- Add the P55 spec under `docs/superpowers/specs/`.
- Add this plan under `docs/superpowers/plans/`.
- Update `agent/research_v1/README.md` with a P55 paragraph.
- Update `agent/research_v1/boss_console/README.md` with the P55 V2.1
  notes (allowed labels, forbidden labels, hard boundaries).

## Task 6: Final Review Checklist

Before declaring P55 done:

- pytest `test_boss_console.py` green
- pytest `test_boss_pdf_brief_renderer.py` green
- pytest `test_market_visual_assets.py` + `test_boss_one_command.py` green
- pytest `test_doc_standards.py` green
- offline smoke run produces `boss_console.html` containing the V2.1 anchors
  and zero raw status / forbidden-phrase leaks
- READMEs and docs updated
- 3-4 logical commits

## Hard Boundaries

P55 must not:

- run research, call providers, invoke `final_judge`, instantiate
  `SubagentExecutor`, create `CanonicalSignal`/`CanonicalReport`, or mutate
  `JudgeInputPacket`,
- expose broker/order/account/position controls or any imperative trading
  copy,
- introduce external JS, CDN, or web-font dependencies.

## Commit Plan

1. `feat: add p55 boss cockpit design tokens` — CSS overhaul.
2. `feat: apply p55 boss console v2.1 layout` — console renderer + tests.
3. `feat: apply p55 boss brief v2.1 layout` — brief renderer + tests.
4. `docs: document p55 boss cockpit visual upgrade` — READMEs, plan, spec.
