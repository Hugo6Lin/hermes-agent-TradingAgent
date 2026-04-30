# Executor Prompt: Phase 27 Factor Expansion Pack

Implement Phase 27: shadow-only macro, event-surprise, and sector-relation candidate factor expansion.

Read:
- `docs/superpowers/specs/2026-04-26-hermes-phase27-factor-expansion-pack-spec.md`
- `docs/superpowers/plans/2026-04-26-phase27-factor-expansion-pack.md`

Create:
- `agent/research_v1/phase27_factor_expansion.py`
- `tests/agent/research_v1/test_phase27_factor_expansion.py`

Hard rules:
- no canonical FactorSnapshot writes
- no production config writes
- no live signals
- no model libraries
- candidate namespace must start with `shadow_candidate_factor.`
- all outputs must be diagnostics-ready and JSON-serializable

Run:
```bash
python3.11 -m pytest tests/agent/research_v1/test_phase27_factor_expansion.py -q
```

Return a handoff using the Phase 27 acceptance checklist.
