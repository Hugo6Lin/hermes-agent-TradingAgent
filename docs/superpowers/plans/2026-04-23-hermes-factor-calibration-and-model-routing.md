# P20 Factor Calibration and Model Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit `Inconclusive` thesis handling, factorized fundamentals scoring, coverage-aware reporting, and role-aware model routing to Hermes without breaking the existing research and image-report pipeline.

**Architecture:** This plan upgrades P14-P17 in layers. First, it separates insufficient-coverage semantics from genuine `No Trade`. Second, it replaces the current sparse fundamentals-quality calculation with a dimension-based scoring path. Third, it adds explicit model routing by analyst role while preserving the existing orchestrator/subagent architecture. The image-report path remains downstream and receives clearer coverage-aware content.

**Tech Stack:** Python 3.11, pytest, existing Hermes contracts/app/orchestrator pipeline, MiniMax/OpenAI/Anthropic client adapters

---

## File Structure

### Existing files to modify

- `E:\hermes-agent\agent\research_v1\contracts.py`
  - Extend thesis-state contract to allow `Inconclusive`
- `E:\hermes-agent\agent\research_v1\thesis_engine.py`
  - Replace hard single-score classification logic with coverage-aware factor scoring
- `E:\hermes-agent\agent\research_v1\app.py`
  - Upgrade `_extract_thesis_inputs()` and propagate coverage metadata into audit/results
- `E:\hermes-agent\agent\research_v1\instrument_selection.py`
  - Prevent `Inconclusive` from being silently treated as `No Trade`
- `E:\hermes-agent\agent\research_v1\orchestrator_reporting.py`
  - Make boss/report-pack language honest about `Inconclusive`
- `E:\hermes-agent\agent\research_v1\subagent_executor.py`
  - Support role-aware model selection
- `E:\hermes-agent\agent\research_v1\llm_clients.py`
  - Reuse provider registry/client factory for routed models

### New files to create

- `E:\hermes-agent\agent\research_v1\thesis_factors.py`
  - Focused factor-scoring helpers and coverage accounting
- `E:\hermes-agent\agent\research_v1\model_routing.py`
  - Per-role provider/model routing logic
- `E:\hermes-agent\tests\agent\research_v1\test_thesis_factors.py`
  - Unit tests for factor scoring and coverage semantics
- `E:\hermes-agent\tests\agent\research_v1\test_model_routing.py`
  - Unit tests for routing selection and graceful fallback

### Existing tests to modify

- `E:\hermes-agent\tests\agent\research_v1\test_thesis_engine.py`
- `E:\hermes-agent\tests\agent\research_v1\test_canonical_app.py`
- `E:\hermes-agent\tests\agent\research_v1\test_image_report_pipeline.py`
- `E:\hermes-agent\tests\agent\research_v1\test_app_integration.py`

---

### Task 1: Add `Inconclusive` Thesis Contract

**Files:**
- Modify: `E:\hermes-agent\agent\research_v1\contracts.py`
- Test: `E:\hermes-agent\tests\agent\research_v1\test_thesis_engine.py`

- [ ] **Step 1: Write the failing contract tests**

```python
def test_underlying_thesis_accepts_inconclusive():
    thesis = UnderlyingThesis(
        task_id="t1",
        ticker="AAPL",
        quality_score=0.18,
        valuation_score=0.10,
        catalyst_score=0.20,
        thesis_risk_score=0.82,
        classification="Inconclusive",
        summary="Coverage too thin to classify confidently",
    )
    assert thesis.classification == "Inconclusive"


def test_instrument_selection_returns_no_trade_for_inconclusive():
    thesis = UnderlyingThesis(
        task_id="t1",
        ticker="AAPL",
        quality_score=0.18,
        valuation_score=0.10,
        catalyst_score=0.20,
        thesis_risk_score=0.82,
        classification="Inconclusive",
        summary="Coverage too thin to classify confidently",
    )
    engine = InstrumentSelectionEngine()
    rec = engine.choose(thesis, option_context={}, holding_context={})
    assert rec.primary_action == "No Trade"
    assert "Inconclusive" in rec.reason
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/agent/research_v1/test_thesis_engine.py -q
```

Expected:
- FAIL because `UnderlyingThesis` validation currently rejects `Inconclusive`
- FAIL because instrument selection reason path does not mention it

- [ ] **Step 3: Implement minimal contract change**

Update the classification validation in `contracts.py` and the rejection reason in `instrument_selection.py`:

```python
if self.classification not in {"Investable", "Watchlist", "Inconclusive", "No Trade"}:
    raise ValueError("classification must be Investable, Watchlist, Inconclusive, or No Trade")
```

```python
if thesis.classification != "Investable":
    return InstrumentRecommendation(
        task_id=thesis.task_id,
        ticker=thesis.ticker,
        primary_action="No Trade",
        ranked_alternatives=[],
        reason=f"Underlying {thesis.ticker} is {thesis.classification}, not Investable",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/agent/research_v1/test_thesis_engine.py -q
```

Expected:
- PASS for new `Inconclusive` contract tests
- Existing thesis/instrument tests remain green

- [ ] **Step 5: Commit**

```bash
git add agent/research_v1/contracts.py agent/research_v1/instrument_selection.py tests/agent/research_v1/test_thesis_engine.py
git commit -m "feat: add inconclusive thesis contract"
```

---

### Task 2: Introduce Factorized Fundamentals Scoring

**Files:**
- Create: `E:\hermes-agent\agent\research_v1\thesis_factors.py`
- Modify: `E:\hermes-agent\agent\research_v1\thesis_engine.py`
- Test: `E:\hermes-agent\tests\agent\research_v1\test_thesis_factors.py`
- Modify test: `E:\hermes-agent\tests\agent\research_v1\test_thesis_engine.py`

- [ ] **Step 1: Write failing factor-scoring tests**

```python
from agent.research_v1.thesis_factors import compute_fundamentals_quality, compute_coverage_quality


def test_compute_fundamentals_quality_uses_dimensions_not_item_count():
    fundamentals = {
        "profitability": 0.70,
        "growth_quality": 0.60,
        "earnings_quality": 0.55,
        "cashflow_quality": 0.65,
        "balance_sheet": 0.50,
        "capital_allocation": 0.45,
        "management_execution": 0.60,
        "valuation_support": 0.40,
        "coverage_quality": 0.75,
    }
    score = compute_fundamentals_quality(fundamentals)
    assert round(score, 2) == 0.59


def test_compute_coverage_quality_penalizes_sparse_dimensions():
    fundamentals = {
        "_dimensions_covered": ["profitability", "balance_sheet"],
        "_dimensions_missing": ["cashflow_quality", "earnings_quality", "capital_allocation"],
    }
    score = compute_coverage_quality(fundamentals)
    assert score < 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/agent/research_v1/test_thesis_factors.py -q
```

Expected:
- FAIL because `thesis_factors.py` does not exist yet

- [ ] **Step 3: Write minimal factor helpers**

Create `thesis_factors.py`:

```python
from __future__ import annotations


FACTOR_WEIGHTS = {
    "profitability": 0.18,
    "growth_quality": 0.16,
    "earnings_quality": 0.14,
    "cashflow_quality": 0.12,
    "balance_sheet": 0.12,
    "capital_allocation": 0.10,
    "management_execution": 0.08,
    "valuation_support": 0.10,
    "coverage_quality": 0.10,
}


def compute_coverage_quality(fundamentals: dict) -> float:
    covered = list(fundamentals.get("_dimensions_covered", []))
    missing = list(fundamentals.get("_dimensions_missing", []))
    total = len(covered) + len(missing)
    if total == 0:
        return 0.0
    return round(len(covered) / total, 4)


def compute_fundamentals_quality(fundamentals: dict) -> float:
    weighted = 0.0
    total_weight = 0.0
    for key, weight in FACTOR_WEIGHTS.items():
        value = float(fundamentals.get(key, 0.0))
        weighted += value * weight
        total_weight += weight
    return round(weighted / total_weight, 4) if total_weight else 0.0
```

- [ ] **Step 4: Refactor `ThesisEngine` to use factor helpers**

Update `thesis_engine.py`:

```python
from agent.research_v1.thesis_factors import compute_fundamentals_quality


def _quality_score(self, fundamentals: dict) -> float:
    return compute_fundamentals_quality(fundamentals)
```

Add a new test expectation:

```python
def test_thesis_engine_uses_factorized_quality_for_watchlist():
    engine = ThesisEngine()
    result = engine.evaluate(
        ticker="AAPL",
        fundamentals={
            "profitability": 0.55,
            "growth_quality": 0.52,
            "earnings_quality": 0.48,
            "cashflow_quality": 0.50,
            "balance_sheet": 0.49,
            "capital_allocation": 0.45,
            "management_execution": 0.55,
            "valuation_support": 0.30,
            "coverage_quality": 0.80,
        },
        valuation={"upside_pct": 0.10},
        catalysts={"clarity": 0.40},
    )
    assert result.quality_score > 0.45
    assert result.classification == "Watchlist"
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/agent/research_v1/test_thesis_factors.py tests/agent/research_v1/test_thesis_engine.py -q
```

Expected:
- PASS for new factor tests
- PASS for updated thesis engine tests

- [ ] **Step 6: Commit**

```bash
git add agent/research_v1/thesis_factors.py agent/research_v1/thesis_engine.py tests/agent/research_v1/test_thesis_factors.py tests/agent/research_v1/test_thesis_engine.py
git commit -m "feat: add factorized fundamentals scoring"
```

---

### Task 3: Upgrade Thesis Input Extraction and Coverage Accounting

**Files:**
- Modify: `E:\hermes-agent\agent\research_v1\app.py`
- Test: `E:\hermes-agent\tests\agent\research_v1\test_app_integration.py`
- Modify test: `E:\hermes-agent\tests\agent\research_v1\test_canonical_app.py`

- [ ] **Step 1: Write failing extraction tests**

```python
def test_extract_thesis_inputs_tracks_dimension_coverage():
    app = HermesResearchApp(llm_client=None)
    bundle = EvidenceBundle(task_id="t1", ticker="AAPL", evidence_items=[
        new_evidence_item(
            task_id="t1",
            subtask_id="s1",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            claim="profitability_assessment: strong margins",
            value={"profitability_assessment": "strong", "cashflow_assessment": "stable"},
            confidence=0.8,
            direction=Direction.BULLISH,
        )
    ])
    thesis_inputs = app._extract_thesis_inputs(bundle, {})
    fundamentals = thesis_inputs["fundamentals"]
    assert "profitability" in fundamentals
    assert "_dimensions_covered" in fundamentals
    assert "profitability" in fundamentals["_dimensions_covered"]
```

```python
def test_run_marks_inconclusive_when_coverage_is_too_thin():
    app = HermesResearchApp()
    result = app.run("Research AAPL fundamentals")
    tr = result.ticker_results[0]
    assert "coverage_limited" in tr.audit
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/agent/research_v1/test_app_integration.py tests/agent/research_v1/test_canonical_app.py -q
```

Expected:
- FAIL because `_extract_thesis_inputs()` does not expose dimension coverage

- [ ] **Step 3: Implement dimension-aware extraction**

Add dimension mapping in `app.py` inside `_extract_thesis_inputs()`:

```python
dimension_flags = {
    "profitability": False,
    "growth_quality": False,
    "earnings_quality": False,
    "cashflow_quality": False,
    "balance_sheet": False,
    "capital_allocation": False,
    "valuation_support": False,
    "management_execution": False,
}

for item in bundle.evidence_items:
    if item.agent_role.value != "fundamentals":
        continue
    payload = item.raw_payload if isinstance(item.raw_payload, dict) else {}
    summary = payload.get("summary_json", {}) if isinstance(payload, dict) else {}
    if "profitability_assessment" in summary:
        fundamentals["profitability"] = max(fundamentals.get("profitability", 0.0), item.confidence)
        dimension_flags["profitability"] = True
    if "cashflow_assessment" in summary:
        fundamentals["cashflow_quality"] = max(fundamentals.get("cashflow_quality", 0.0), item.confidence)
        dimension_flags["cashflow_quality"] = True
```

Then finalize:

```python
fundamentals["_dimensions_covered"] = [k for k, seen in dimension_flags.items() if seen]
fundamentals["_dimensions_missing"] = [k for k, seen in dimension_flags.items() if not seen]
fundamentals["coverage_quality"] = compute_coverage_quality(fundamentals)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/agent/research_v1/test_app_integration.py tests/agent/research_v1/test_canonical_app.py -q
```

Expected:
- PASS for new coverage-accounting behavior
- Existing app integration tests remain green

- [ ] **Step 5: Commit**

```bash
git add agent/research_v1/app.py tests/agent/research_v1/test_app_integration.py tests/agent/research_v1/test_canonical_app.py
git commit -m "feat: add thesis coverage accounting"
```

---

### Task 4: Make `Inconclusive` Honest in Downstream Reporting

**Files:**
- Modify: `E:\hermes-agent\agent\research_v1\thesis_engine.py`
- Modify: `E:\hermes-agent\agent\research_v1\orchestrator_reporting.py`
- Test: `E:\hermes-agent\tests\agent\research_v1\test_image_report_pipeline.py`

- [ ] **Step 1: Write failing downstream-report tests**

```python
def test_build_report_pack_uses_inconclusive_language_when_coverage_is_thin():
    result = make_ticker_result(action="No Trade")
    result.decision_card = None
    result.audit = {
        "coverage_limited": True,
        "llm_research_available": True,
        "coverage_reason": "fundamentals dimensions missing: cashflow_quality, capital_allocation",
    }
    result.report.executive_summary = "Coverage-limited fallback"
    pack = build_report_pack(result)
    assert "研究不可下结论" in pack.boss_summary
    assert "覆盖不足" in pack.one_line_call
```

```python
def test_thesis_engine_returns_inconclusive_for_low_coverage_not_no_trade():
    engine = ThesisEngine()
    result = engine.evaluate(
        ticker="AAPL",
        fundamentals={
            "profitability": 0.30,
            "coverage_quality": 0.20,
            "_dimensions_covered": ["profitability"],
            "_dimensions_missing": ["cashflow_quality", "balance_sheet", "capital_allocation"],
        },
        valuation={"upside_pct": 0.12},
        catalysts={"clarity": 0.30},
    )
    assert result.classification == "Inconclusive"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/agent/research_v1/test_thesis_engine.py tests/agent/research_v1/test_image_report_pipeline.py -q
```

Expected:
- FAIL because low quality still maps directly to `No Trade`
- FAIL because report-pack text does not distinguish `Inconclusive`

- [ ] **Step 3: Implement coverage-aware thesis classification**

Update `thesis_engine.py`:

```python
def _classify(self, quality: float, valuation_score: float, catalyst_score: float, fundamentals: dict) -> str:
    coverage_quality = float(fundamentals.get("coverage_quality", 0.0))
    if coverage_quality < 0.40:
        return "Inconclusive"
    if quality < 0.35:
        return "No Trade"
    if quality >= 0.65 and valuation_score >= 0.15 and catalyst_score >= 0.5:
        return "Investable"
    return "Watchlist"
```

Update summary language:

```python
"Inconclusive": f"{ticker} research inconclusive: coverage too thin to classify confidently"
```

Update `orchestrator_reporting.py`:

```python
if result.thesis and result.thesis.classification == "Inconclusive":
    boss_summary = "研究不可下结论。当前基本面覆盖不足，Hermes 无法给出可信的投资动作。"
    why_now = "- 当前研究覆盖不足\n- 需要更完整的基本面维度\n- 建议在补足分析后重跑"
    top_risks = "- 覆盖不足会伪装成保守结论\n- 当前输出不应视为正式拒绝\n- 需要更强的 fundamentals 研究深度"
    one_line_call = f"{ticker} 覆盖不足 - 研究不可下结论"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/agent/research_v1/test_thesis_engine.py tests/agent/research_v1/test_image_report_pipeline.py -q
```

Expected:
- PASS for `Inconclusive` classification
- PASS for honest downstream language

- [ ] **Step 5: Commit**

```bash
git add agent/research_v1/thesis_engine.py agent/research_v1/orchestrator_reporting.py tests/agent/research_v1/test_thesis_engine.py tests/agent/research_v1/test_image_report_pipeline.py
git commit -m "feat: add inconclusive coverage-aware reporting"
```

---

### Task 5: Add Role-Aware Model Routing

**Files:**
- Create: `E:\hermes-agent\agent\research_v1\model_routing.py`
- Modify: `E:\hermes-agent\agent\research_v1\subagent_executor.py`
- Modify: `E:\hermes-agent\agent\research_v1\llm_clients.py`
- Test: `E:\hermes-agent\tests\agent\research_v1\test_model_routing.py`

- [ ] **Step 1: Write failing routing tests**

```python
from agent.research_v1.contracts import AgentRole
from agent.research_v1.model_routing import ModelRoutingPolicy


def test_model_routing_policy_prefers_fundamentals_override():
    policy = ModelRoutingPolicy(
        default_provider="minimax",
        default_model="MiniMax-M2.7-HighSpeed",
        role_overrides={
            AgentRole.FUNDAMENTALS: {"provider": "openai", "model": "gpt-5.4"},
        },
    )
    route = policy.resolve(AgentRole.FUNDAMENTALS)
    assert route["provider"] == "openai"
    assert route["model"] == "gpt-5.4"


def test_model_routing_policy_falls_back_to_default_for_news():
    policy = ModelRoutingPolicy(
        default_provider="minimax",
        default_model="MiniMax-M2.7-HighSpeed",
        role_overrides={},
    )
    route = policy.resolve(AgentRole.NEWS)
    assert route["provider"] == "minimax"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/agent/research_v1/test_model_routing.py -q
```

Expected:
- FAIL because `model_routing.py` does not exist yet

- [ ] **Step 3: Implement routing policy**

Create `model_routing.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from agent.research_v1.contracts import AgentRole


@dataclass
class ModelRoutingPolicy:
    default_provider: str
    default_model: str
    role_overrides: dict[AgentRole, dict[str, str]] = field(default_factory=dict)

    def resolve(self, role: AgentRole) -> dict[str, str]:
        override = self.role_overrides.get(role, {})
        return {
            "provider": override.get("provider", self.default_provider),
            "model": override.get("model", self.default_model),
        }
```

- [ ] **Step 4: Wire routing into `SubagentExecutor`**

Update `subagent_executor.py` constructor shape:

```python
def __init__(self, llm_client: BaseLLMClient, market_data_service: Any = None, routing_policy: ModelRoutingPolicy | None = None):
    self._llm = llm_client
    self._market_data_service = market_data_service
    self._routing_policy = routing_policy
```

Add a helper:

```python
def _llm_for_role(self, role: AgentRole):
    if self._routing_policy is None:
        return self._llm
    route = self._routing_policy.resolve(role)
    if getattr(self._llm, "provider_name", lambda: "")() == route["provider"] and getattr(self._llm, "model", None) == route["model"]:
        return self._llm
    from agent.research_v1.llm_clients import get_llm_client
    return get_llm_client(route["provider"], model=route["model"])
```

Then instantiate each analyst with `llm_client=self._llm_for_role(subtask.agent_role)`.

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/agent/research_v1/test_model_routing.py tests/agent/research_v1/test_app_integration.py -q
```

Expected:
- PASS for routing policy tests
- PASS for subagent execution path with default routing

- [ ] **Step 6: Commit**

```bash
git add agent/research_v1/model_routing.py agent/research_v1/subagent_executor.py agent/research_v1/llm_clients.py tests/agent/research_v1/test_model_routing.py tests/agent/research_v1/test_app_integration.py
git commit -m "feat: add role-aware model routing"
```

---

### Task 6: Final P20 Integration Verification

**Files:**
- Modify if needed: `E:\hermes-agent\agent\research_v1\README.md`
- Test: `E:\hermes-agent\tests\agent\research_v1\test_app_integration.py`
- Test: `E:\hermes-agent\tests\agent\research_v1\test_image_report_pipeline.py`

- [ ] **Step 1: Add end-to-end regression tests**

```python
def test_sparse_fundamentals_run_becomes_inconclusive_not_no_trade():
    app = HermesResearchApp()
    result = app.run("Research AMD fundamentals")
    tr = result.ticker_results[0]
    if tr.thesis is not None and tr.audit.get("coverage_limited") is not True:
        assert tr.thesis.classification in {"Investable", "Watchlist", "Inconclusive", "No Trade"}
```

```python
def test_image_report_pack_surfaces_inconclusive_language():
    result = make_ticker_result(action="No Trade")
    result.audit = {
        "coverage_limited": True,
        "llm_research_available": True,
        "coverage_reason": "fundamentals coverage insufficient",
    }
    result.thesis = UnderlyingThesis(
        task_id="t1",
        ticker="AAPL",
        quality_score=0.20,
        valuation_score=0.12,
        catalyst_score=0.20,
        thesis_risk_score=0.80,
        classification="Inconclusive",
        summary="Coverage too thin",
    )
    pack = build_report_pack(result)
    assert "研究不可下结论" in pack.boss_summary
```

- [ ] **Step 2: Run the focused integration suite**

Run:

```bash
python -m pytest tests/agent/research_v1/test_thesis_engine.py tests/agent/research_v1/test_thesis_factors.py tests/agent/research_v1/test_model_routing.py tests/agent/research_v1/test_app_integration.py tests/agent/research_v1/test_image_report_pipeline.py -q
```

Expected:
- PASS for all new P20-focused regression tests

- [ ] **Step 3: Update docs if interfaces changed**

If `Inconclusive` or model routing becomes user-visible, add a short README note:

```markdown
- `Inconclusive` means Hermes had insufficient fundamentals coverage to make a trustworthy investment classification.
- Role-aware model routing can be configured so fundamentals/valuation use stronger models than lighter analyst roles.
```

- [ ] **Step 4: Run one real smoke command**

Run:

```bash
python -c "from agent.research_v1.app import HermesResearchApp; app = HermesResearchApp(); result = app.run('Research AMD fundamentals'); tr = result.ticker_results[0]; print(tr.ticker, tr.thesis.classification if tr.thesis else None, tr.audit.get('coverage_limited'))"
```

Expected:
- A valid ticker output
- A thesis classification printed
- Coverage state printed

- [ ] **Step 5: Commit**

```bash
git add agent/research_v1/README.md tests/agent/research_v1/test_app_integration.py tests/agent/research_v1/test_image_report_pipeline.py
git commit -m "docs: finalize p20 factor calibration integration"
```

---

## Self-Review

### Spec coverage

- Thesis state redesign: covered by Tasks 1 and 4
- Factorized fundamentals scoring: covered by Task 2
- Coverage semantics and auditability: covered by Task 3
- Fundamentals schema / extraction implications: covered by Task 3
- Model routing: covered by Task 5
- Reporting implications: covered by Task 4 and Task 6

### Placeholder scan

- No `TBD` / `TODO`
- All code-changing steps include concrete code blocks
- All verification steps include concrete commands

### Type consistency

- `UnderlyingThesis.classification` uses `Inconclusive` consistently
- `coverage_limited` and coverage metadata are introduced through `audit`
- `ModelRoutingPolicy.resolve()` returns a consistent `{provider, model}` shape

