"""Tests for signal-family readiness governance dossier."""

from __future__ import annotations

import json

import pytest

from agent.research_v1.signal_family_readiness import (
    ALLOWED_FAMILY_TYPES,
    FamilyEvidence,
    SignalFamilyReadinessError,
    SignalFamilyReadinessRequest,
    build_signal_family_readiness_dossier,
)


def _evidence(
    *,
    p20_p23: bool = True,
    p24_p26: bool = False,
    p28: bool = False,
    p30: bool = False,
    mature: bool = True,
) -> FamilyEvidence:
    return FamilyEvidence(
        p20_p23_present=p20_p23,
        p24_p26_present=p24_p26,
        p28_present=p28,
        p30_present=p30,
        maturity=mature,
        edge_summary="net IC positive in shadow observations",
        risk_summary="no critical degradation warnings",
    )


def _request(
    *,
    parent_status: str = "ready_for_human_review",
    family_type: str = "signal_family",
    namespace: str = "signal_family.high_conviction_bullish_equity",
    evidence: FamilyEvidence | None = None,
) -> SignalFamilyReadinessRequest:
    return SignalFamilyReadinessRequest(
        parent_version_status=parent_status,
        family_type=family_type,
        family_namespace=namespace,
        evidence=evidence if evidence is not None else _evidence(),
        notes="candidate for human review",
    )


class TestSignalFamilyContracts:
    def test_allowed_family_types(self):
        assert ALLOWED_FAMILY_TYPES == frozenset({
            "factor_family",
            "signal_family",
            "shadow_model_family",
            "advanced_model_candidate",
        })

    def test_family_evidence_contract(self):
        d = _evidence().to_dict()
        assert d["p20_p23_present"] is True
        assert d["edge_summary"] == "net IC positive in shadow observations"

    def test_invalid_family_type_rejected(self):
        with pytest.raises(SignalFamilyReadinessError, match="family_type must be one of"):
            _request(family_type="portfolio_optimizer")

    def test_json_round_trip(self):
        dossier = build_signal_family_readiness_dossier(_request())
        parsed = json.loads(json.dumps(dossier.to_dict()))
        assert parsed["family_status"] == "ready_for_human_review"
        assert parsed["family_namespace"] == "signal_family.high_conviction_bullish_equity"


class TestSignalFamilyGates:
    def test_blocked_parent_blocks_family(self):
        dossier = build_signal_family_readiness_dossier(
            _request(parent_status="blocked_missing_evidence")
        )
        assert dossier.family_status == "blocked_system_not_ready"
        assert "parent_version_not_ready:blocked_missing_evidence" in dossier.promotion_forbidden_reasons

    def test_missing_core_evidence_blocks(self):
        dossier = build_signal_family_readiness_dossier(
            _request(evidence=_evidence(p20_p23=False))
        )
        assert dossier.family_status == "blocked_missing_family_evidence"
        assert "p20_p23_family_evidence_missing" in dossier.promotion_forbidden_reasons

    def test_partial_evidence_is_shadow_observation_only(self):
        dossier = build_signal_family_readiness_dossier(
            _request(evidence=_evidence(mature=False))
        )
        assert dossier.family_status == "shadow_observation_only"
        assert dossier.allowed_next_step == "continue_shadow_observation"

    def test_shadow_model_requires_p24_p26(self):
        dossier = build_signal_family_readiness_dossier(
            _request(
                family_type="shadow_model_family",
                namespace="shadow_meta_model.xgboost_dry_candidate",
                evidence=_evidence(p24_p26=False, mature=True),
            )
        )
        assert dossier.family_status == "blocked_missing_family_evidence"
        assert "p24_p26_shadow_model_evidence_missing" in dossier.promotion_forbidden_reasons

    def test_advanced_model_requires_p30_and_stays_sandbox_only(self):
        dossier = build_signal_family_readiness_dossier(
            _request(
                family_type="advanced_model_candidate",
                namespace="shadow_advanced_model.real_xgboost_meta_model",
                evidence=_evidence(p24_p26=True, p30=True, mature=True),
            )
        )
        assert dossier.family_status == "ready_for_human_review"
        assert "advanced_model_remains_sandbox_only" in dossier.promotion_forbidden_reasons

    def test_to_dict_rebuilds_family_status(self):
        dossier = build_signal_family_readiness_dossier(_request())
        object.__setattr__(dossier, "family_status", "blocked_system_not_ready")
        assert dossier.to_dict()["family_status"] == "ready_for_human_review"
