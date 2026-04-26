# Executor Prompt: Phase 28 Execution Realism Pack

Implement Phase 28 execution realism.

Read:
- `docs/superpowers/specs/2026-04-26-hermes-phase28-execution-realism-pack-spec.md`
- `docs/superpowers/plans/2026-04-26-phase28-execution-realism-pack.md`

Create:
- `agent/research_v1/phase28_execution_realism.py`
- `tests/agent/research_v1/test_phase28_execution_realism.py`

Do not connect to brokers, execute trades, train PPO, or import RL/model libraries.

Run:
```bash
python3.11 -m pytest tests/agent/research_v1/test_phase28_execution_realism.py -q
```

Return the acceptance checklist.
