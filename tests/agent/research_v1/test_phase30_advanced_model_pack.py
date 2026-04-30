"""Tests for Phase 30 advanced model pack."""

from __future__ import annotations

import json

import pytest

from agent.research_v1.phase30_advanced_model_pack import (
    ADMITTED_FAMILIES,
    MIN_EXECUTION_LOG_COUNT,
    SHADOW_ADVANCED_MODEL_PREFIX,
    AdvancedModelAdmissionRequest,
    AdvancedModelGovernanceDecision,
    AdvancedModelPackError,
    AdvancedModelSandboxManifest,
    build_advanced_model_sandbox_manifest,
    evaluate_advanced_model_admission,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _p24_report(passed: bool = True, production_write_blocked: bool = True) -> dict:
    return {
        "schema_version": "p24_gate.v1",
        "passed": passed,
        "production_write_blocked": production_write_blocked,
        "blocking_reasons": [],
    }


def _admission_request(
    family: str = "real_xgboost_meta_model",
    p24_report: dict | None = None,
    p25_evidence: dict | None = None,
    p26_evidence: dict | None = None,
    **kwargs,
) -> AdvancedModelAdmissionRequest:
    return AdvancedModelAdmissionRequest(
        candidate_family=family,
        candidate_namespace=f"{SHADOW_ADVANCED_MODEL_PREFIX}{family}.test",
        p24_gate_report=p24_report,
        p25_evaluation_evidence=p25_evidence,
        p26_portfolio_evidence=p26_evidence,
        **kwargs,
    )


# ─── Contract tests ────────────────────────────────────────────────────────────

class TestContracts:
    def test_admission_request_contract(self):
        req = _admission_request()
        d = req.to_dict()
        assert d["candidate_family"] == "real_xgboost_meta_model"
        assert d["p24_gate_report"] is None

    def test_governance_decision_contract(self):
        dec = AdvancedModelGovernanceDecision(
            candidate_family="real_xgboost_meta_model",
            candidate_namespace="shadow_xgboost.test",
            admitted=True,
            blocked_reasons=("all_gates_passed",),
            warnings=(),
            sub_scores=(("p24_gate_passed", 1.0),),
        )
        d = dec.to_dict()
        assert d["admitted"] is True
        assert "all_gates_passed" in d["blocked_reasons"]

    def test_sandbox_manifest_contract(self):
        manifest = AdvancedModelSandboxManifest(
            candidate_family="sequence_timing_model_candidate",
            candidate_namespace="shadow_sequence.test",
            sandbox_type="shadow_only",
            allowed_horizons=("intraday", "daily"),
            required_pit_dataset=True,
            required_walk_forward_split=True,
            baseline_comparison_required=True,
            oos_evaluation_required=True,
            blocked_production_paths=("live_trade_signal", "broker_instruction"),
        )
        d = manifest.to_dict()
        assert d["sandbox_type"] == "shadow_only"
        assert "live_trade_signal" in d["blocked_production_paths"]

    def test_request_rejects_unknown_family(self):
        with pytest.raises(AdvancedModelPackError, match="candidate_family must be one of"):
            _admission_request(family="unknown_model")

    def test_to_dict_json_round_trip(self):
        dec = AdvancedModelGovernanceDecision(
            candidate_family="ppo_execution_candidate",
            candidate_namespace="shadow_ppo.test",
            admitted=False,
            blocked_reasons=("ppo_objective_not_execution_cost_reduction",),
            warnings=(),
            sub_scores=(("ppo_execution_only_gate", 0.0),),
        )
        d = dec.to_dict()
        parsed = json.loads(json.dumps(d))
        assert parsed["candidate_family"] == "ppo_execution_candidate"
        assert parsed["admitted"] is False

    def test_admitted_families(self):
        assert "real_xgboost_meta_model" in ADMITTED_FAMILIES
        assert "sector_relation_gnn_candidate" in ADMITTED_FAMILIES
        assert "sequence_timing_model_candidate" in ADMITTED_FAMILIES
        assert "llm_event_surprise_model_candidate" in ADMITTED_FAMILIES
        assert "ppo_execution_candidate" in ADMITTED_FAMILIES

    def test_min_execution_log_count(self):
        assert MIN_EXECUTION_LOG_COUNT == 10


# ─── P24 Gate tests ───────────────────────────────────────────────────────────

class TestP24Gate:
    def test_p24_missing_blocks(self):
        req = _admission_request(p24_report=None)
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "p24_gate_report_missing" in dec.blocked_reasons

    def test_p24_wrong_schema_blocks(self):
        req = _admission_request(p24_report={"schema_version": "wrong.v1", "passed": True})
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "p24_gate_schema_invalid" in str(dec.blocked_reasons)

    def test_p24_not_passed_blocks(self):
        req = _admission_request(
            p24_report={"schema_version": "p24_gate.v1", "passed": False, "blocking_reasons": ["bad_thing"], "production_write_blocked": True}
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "p24_gate_failed:bad_thing" in dec.blocked_reasons

    def test_p24_production_write_not_blocked_blocks(self):
        req = _admission_request(p24_report={"schema_version": "p24_gate.v1", "passed": True, "production_write_blocked": False, "blocking_reasons": []})
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "p24_gate_production_write_not_blocked" in dec.blocked_reasons

    def test_p24_passed_sub_score(self):
        req = _admission_request(p24_report=_p24_report())
        dec = evaluate_advanced_model_admission(req)
        score = dict(dec.sub_scores).get("p24_gate_passed", 0.0)
        assert score == 1.0


# ─── XGBoost gate tests ───────────────────────────────────────────────────────

class TestXGBoostGate:
    def test_xgboost_requires_p24(self):
        req = _admission_request(family="real_xgboost_meta_model", p24_report=None)
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "xgboost_requires_p24_gate" in dec.blocked_reasons

    def test_xgboost_requires_p25(self):
        req = _admission_request(
            family="real_xgboost_meta_model",
            p24_report=_p24_report(),
            p25_evidence=None,
            p26_evidence={},
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "xgboost_requires_p25_evidence" in dec.blocked_reasons

    def test_xgboost_requires_p26(self):
        req = _admission_request(
            family="real_xgboost_meta_model",
            p24_report=_p24_report(),
            p25_evidence={},
            p26_evidence=None,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "xgboost_requires_p26_evidence" in dec.blocked_reasons

    def test_xgboost_all_gates_pass(self):
        req = _admission_request(
            family="real_xgboost_meta_model",
            p24_report=_p24_report(),
            p25_evidence={"model_evaluation": "passed"},
            p26_evidence={"portfolio_simulation": "passed"},
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is True
        assert "all_gates_passed" in dec.blocked_reasons


# ─── GNN gate tests ───────────────────────────────────────────────────────────

class TestGNNGate:
    def test_gnn_requires_relation_data_sufficient(self):
        req = _admission_request(
            family="sector_relation_gnn_candidate",
            p24_report=_p24_report(),
            relation_data_sufficient=False,
            point_in_time_relation_graph=True,
            relation_group_count=5,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "gnn_relation_data_not_sufficient" in dec.blocked_reasons

    def test_gnn_requires_pit_graph(self):
        req = _admission_request(
            family="sector_relation_gnn_candidate",
            p24_report=_p24_report(),
            relation_data_sufficient=True,
            point_in_time_relation_graph=False,
            relation_group_count=5,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "gnn_relation_graph_not_point_in_time" in dec.blocked_reasons

    def test_gnn_requires_min_groups(self):
        req = _admission_request(
            family="sector_relation_gnn_candidate",
            p24_report=_p24_report(),
            relation_data_sufficient=True,
            point_in_time_relation_graph=True,
            relation_group_count=1,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "gnn_relation_group_count_insufficient" in dec.blocked_reasons

    def test_gnn_all_gates_pass(self):
        req = _admission_request(
            family="sector_relation_gnn_candidate",
            p24_report=_p24_report(),
            relation_data_sufficient=True,
            point_in_time_relation_graph=True,
            relation_group_count=5,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is True


# ─── Sequence model gate tests ─────────────────────────────────────────────────

class TestSequenceModelGate:
    def test_sequence_requires_wfw(self):
        req = _admission_request(
            family="sequence_timing_model_candidate",
            p24_report=_p24_report(),
            walk_forward_validation_defined=False,
            sequence_history_sufficient=True,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "sequence_walk_forward_validation_not_defined" in dec.blocked_reasons

    def test_sequence_requires_history(self):
        req = _admission_request(
            family="sequence_timing_model_candidate",
            p24_report=_p24_report(),
            walk_forward_validation_defined=True,
            sequence_history_sufficient=False,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "sequence_history_not_sufficient" in dec.blocked_reasons

    def test_sequence_all_gates_pass(self):
        req = _admission_request(
            family="sequence_timing_model_candidate",
            p24_report=_p24_report(),
            walk_forward_validation_defined=True,
            sequence_history_sufficient=True,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is True


# ─── LLM event model gate tests ───────────────────────────────────────────────

class TestLLMEventGate:
    def test_llm_requires_taxonomy(self):
        req = _admission_request(
            family="llm_event_surprise_model_candidate",
            p24_report=_p24_report(),
            event_taxonomy_defined=False,
            label_consistency_score=0.8,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "llm_event_taxonomy_not_defined" in dec.blocked_reasons

    def test_llm_requires_consistency_score(self):
        req = _admission_request(
            family="llm_event_surprise_model_candidate",
            p24_report=_p24_report(),
            event_taxonomy_defined=True,
            label_consistency_score=0.3,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "llm_event_label_consistency_score_too_low" in str(dec.blocked_reasons)

    def test_llm_all_gates_pass(self):
        req = _admission_request(
            family="llm_event_surprise_model_candidate",
            p24_report=_p24_report(),
            event_taxonomy_defined=True,
            label_consistency_score=0.8,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is True


# ─── PPO gate tests ───────────────────────────────────────────────────────────

class TestPPOGate:
    def test_ppo_requires_execution_cost_reduction(self):
        req = _admission_request(
            family="ppo_execution_candidate",
            p24_report=_p24_report(),
            ppo_objective="alpha_generation",
            affects_stock_selection=False,
            p28_execution_logs_count=50,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "ppo_objective_not_execution_cost_reduction:alpha_generation" in dec.blocked_reasons

    def test_ppo_requires_no_stock_selection(self):
        req = _admission_request(
            family="ppo_execution_candidate",
            p24_report=_p24_report(),
            ppo_objective="execution_cost_reduction",
            affects_stock_selection=True,
            p28_execution_logs_count=50,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "ppo_affects_stock_selection" in dec.blocked_reasons

    def test_ppo_requires_sufficient_logs(self):
        req = _admission_request(
            family="ppo_execution_candidate",
            p24_report=_p24_report(),
            ppo_objective="execution_cost_reduction",
            affects_stock_selection=False,
            p28_execution_logs_count=5,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "p28_execution_logs_insufficient" in str(dec.blocked_reasons)

    def test_ppo_all_gates_pass(self):
        req = _admission_request(
            family="ppo_execution_candidate",
            p24_report=_p24_report(),
            ppo_objective="execution_cost_reduction",
            affects_stock_selection=False,
            p28_execution_logs_count=50,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is True
        assert "all_gates_passed" in dec.blocked_reasons

    def test_ppo_requires_p24_gate(self):
        req = _admission_request(
            family="ppo_execution_candidate",
            p24_report=None,
            ppo_objective="execution_cost_reduction",
            affects_stock_selection=False,
            p28_execution_logs_count=50,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert "ppo_requires_p24_gate" in dec.blocked_reasons


# ─── Sandbox manifest tests ────────────────────────────────────────────────────

class TestSandboxManifest:
    def test_sandbox_rejects_non_admitted(self):
        req = _admission_request(family="real_xgboost_meta_model", p24_report=None)
        dec = evaluate_advanced_model_admission(req)
        with pytest.raises(AdvancedModelPackError, match="non-admitted"):
            build_advanced_model_sandbox_manifest(dec, req)

    def test_xgboost_sandbox_shadow_only(self):
        req = _admission_request(
            family="real_xgboost_meta_model",
            p24_report=_p24_report(),
            p25_evidence={},
            p26_evidence={},
        )
        dec = evaluate_advanced_model_admission(req)
        manifest = build_advanced_model_sandbox_manifest(dec, req)
        assert manifest.sandbox_type == "shadow_only"
        assert manifest.baseline_comparison_required is True
        assert manifest.oos_evaluation_required is True

    def test_sequence_sandbox_requires_wfw(self):
        req = _admission_request(
            family="sequence_timing_model_candidate",
            p24_report=_p24_report(),
            walk_forward_validation_defined=True,
            sequence_history_sufficient=True,
        )
        dec = evaluate_advanced_model_admission(req)
        manifest = build_advanced_model_sandbox_manifest(dec, req)
        assert manifest.required_walk_forward_split is True
        assert manifest.allowed_horizons == ("intraday", "daily")

    def test_ppo_sandbox_execution_horizon(self):
        req = _admission_request(
            family="ppo_execution_candidate",
            p24_report=_p24_report(),
            ppo_objective="execution_cost_reduction",
            affects_stock_selection=False,
            p28_execution_logs_count=50,
        )
        dec = evaluate_advanced_model_admission(req)
        manifest = build_advanced_model_sandbox_manifest(dec, req)
        assert manifest.allowed_horizons == ("execution",)

    def test_sandbox_blocks_production_paths(self):
        req = _admission_request(
            family="sector_relation_gnn_candidate",
            p24_report=_p24_report(),
            relation_data_sufficient=True,
            point_in_time_relation_graph=True,
            relation_group_count=5,
        )
        dec = evaluate_advanced_model_admission(req)
        manifest = build_advanced_model_sandbox_manifest(dec, req)
        assert "live_trade_signal" in manifest.blocked_production_paths
        assert "broker_instruction" in manifest.blocked_production_paths
        assert "deploy_to_production" in manifest.blocked_production_paths

    def test_sandbox_requires_pit_dataset(self):
        req = _admission_request(
            family="llm_event_surprise_model_candidate",
            p24_report=_p24_report(),
            event_taxonomy_defined=True,
            label_consistency_score=0.8,
        )
        dec = evaluate_advanced_model_admission(req)
        manifest = build_advanced_model_sandbox_manifest(dec, req)
        assert manifest.required_pit_dataset is True


# ─── P30-1: Spec signature documentation ──────────────────────────────────────

class TestSpecSignature:
    """P30-1: The spec signature is evaluate_advanced_model_admission(candidate_evidence, request).
    The implementation folds candidate_evidence into request fields internally.
    The public API accepts a single request argument that carries all evidence.
    """

    def test_public_api_single_request_arg(self):
        # The function takes exactly one argument (the request object)
        import inspect
        sig = inspect.signature(evaluate_advanced_model_admission)
        params = list(sig.parameters.keys())
        assert params == ["request"], f"Expected ['request'], got {params}"

    def test_request_aggregates_all_evidence(self):
        # All evidence fields are on the request, not a separate arg
        req = _admission_request(
            p24_report=_p24_report(),
            p25_evidence={"p25": "x"},
            p26_evidence={"p26": "y"},
            p28_execution_logs_count=20,
        )
        assert req.p24_gate_report is not None
        assert req.p25_evaluation_evidence is not None
        assert req.p26_portfolio_evidence is not None
        assert req.p28_execution_logs_count == 20


# ─── P30-2: Namespace prefix ───────────────────────────────────────────────────

class TestNamespacePrefix:
    def test_rejects_production_namespace(self):
        with pytest.raises(AdvancedModelPackError, match="shadow_advanced_model"):
            AdvancedModelAdmissionRequest(
                candidate_family="real_xgboost_meta_model",
                candidate_namespace="production.bad",
                p24_gate_report=_p24_report(),
                p25_evaluation_evidence={},
                p26_portfolio_evidence={},
            )

    def test_rejects_bare_namespace(self):
        with pytest.raises(AdvancedModelPackError, match="shadow_advanced_model"):
            AdvancedModelAdmissionRequest(
                candidate_family="real_xgboost_meta_model",
                candidate_namespace="just_a_name",
                p24_gate_report=_p24_report(),
                p25_evaluation_evidence={},
                p26_portfolio_evidence={},
            )

    def test_accepts_shadow_advanced_model_prefix(self):
        req = AdvancedModelAdmissionRequest(
            candidate_family="real_xgboost_meta_model",
            candidate_namespace="shadow_advanced_model.my_xgboost",
            p24_gate_report=_p24_report(),
            p25_evaluation_evidence={},
            p26_portfolio_evidence={},
        )
        assert req.candidate_namespace == "shadow_advanced_model.my_xgboost"


# ─── P30-3: Defensive rebuild ───────────────────────────────────────────────────

class TestDefensiveRebuild:
    def test_setattr_forge_admitted_to_dict_rebuilds(self):
        # Forge admitted=True on a blocked decision via __setattr__
        dec = AdvancedModelGovernanceDecision(
            candidate_family="real_xgboost_meta_model",
            candidate_namespace=f"{SHADOW_ADVANCED_MODEL_PREFIX}xgboost.test",
            admitted=False,
            blocked_reasons=("xgboost_requires_p25_evidence",),
            warnings=(),
            sub_scores=(("p24_gate_passed", 1.0), ("p25_evidence_present", 0.0)),
        )
        object.__setattr__(dec, "admitted", True)
        d = dec.to_dict()
        # to_dict() must rebuild from blocked_reasons, not use the forged admitted field
        assert d["admitted"] is False

    def test_setattr_forge_blocked_to_admitted_rebuilds(self):
        # Forge admitted=False on an admitted decision
        dec = AdvancedModelGovernanceDecision(
            candidate_family="real_xgboost_meta_model",
            candidate_namespace=f"{SHADOW_ADVANCED_MODEL_PREFIX}xgboost.test",
            admitted=True,
            blocked_reasons=("all_gates_passed",),
            warnings=(),
            sub_scores=(("p24_gate_passed", 1.0), ("xgboost_family_gate", 1.0)),
        )
        object.__setattr__(dec, "admitted", False)
        d = dec.to_dict()
        assert d["admitted"] is True


# ─── P30-4: P25/P26 applicability per family ───────────────────────────────────

class TestP25P26Applicability:
    """Spec §4 'where applicable' is implemented per FAMILY_EVIDENCE_REQUIREMENTS:
    XGBoost requires P25+P26; GNN/Sequence/LLM are first-time admissions (no P25/P26);
    PPO is execution-only (no P25/P26).
    """

    def test_gnn_admits_without_p25_p26(self):
        # GNN first-time admission: no prior P25/P26 evidence
        req = _admission_request(
            family="sector_relation_gnn_candidate",
            p24_report=_p24_report(),
            p25_evidence=None,
            p26_evidence=None,
            relation_data_sufficient=True,
            point_in_time_relation_graph=True,
            relation_group_count=5,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is True

    def test_sequence_admits_without_p25_p26(self):
        req = _admission_request(
            family="sequence_timing_model_candidate",
            p24_report=_p24_report(),
            p25_evidence=None,
            p26_evidence=None,
            walk_forward_validation_defined=True,
            sequence_history_sufficient=True,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is True

    def test_llm_admits_without_p25_p26(self):
        req = _admission_request(
            family="llm_event_surprise_model_candidate",
            p24_report=_p24_report(),
            p25_evidence=None,
            p26_evidence=None,
            event_taxonomy_defined=True,
            label_consistency_score=0.8,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is True

    def test_xgboost_still_requires_p25_p26(self):
        req = _admission_request(
            family="real_xgboost_meta_model",
            p24_report=_p24_report(),
            p25_evidence=None,
            p26_evidence=None,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False

    def test_ppo_execution_only_skips_p25_p26(self):
        req = _admission_request(
            family="ppo_execution_candidate",
            p24_report=_p24_report(),
            p25_evidence=None,
            p26_evidence=None,
            ppo_objective="execution_cost_reduction",
            affects_stock_selection=False,
            p28_execution_logs_count=50,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is True


# ─── P30-5: Uniform reason string prefixes ─────────────────────────────────────

class TestReasonStringPrefixes:
    def test_gnn_reasons_have_gnn_prefix(self):
        req = _admission_request(
            family="sector_relation_gnn_candidate",
            p24_report=_p24_report(),
            relation_data_sufficient=False,
            point_in_time_relation_graph=False,
            relation_group_count=0,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        prefixes = {r.split("_")[0] for r in dec.blocked_reasons}
        assert "gnn" in prefixes or any(r.startswith("gnn_") for r in dec.blocked_reasons)

    def test_sequence_reasons_have_sequence_prefix(self):
        req = _admission_request(
            family="sequence_timing_model_candidate",
            p24_report=_p24_report(),
            walk_forward_validation_defined=False,
            sequence_history_sufficient=False,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert any(r.startswith("sequence_") for r in dec.blocked_reasons)

    def test_llm_reasons_have_llm_prefix(self):
        req = _admission_request(
            family="llm_event_surprise_model_candidate",
            p24_report=_p24_report(),
            event_taxonomy_defined=False,
            label_consistency_score=0.3,
        )
        dec = evaluate_advanced_model_admission(req)
        assert dec.admitted is False
        assert any(r.startswith("llm_event_") for r in dec.blocked_reasons)
