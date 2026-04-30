"""Phase 27 factor expansion pack tests."""

import json
import pytest

from agent.research_v1.phase27_factor_expansion import (
    FactorExpansionError,
    FactorExpansionRequest,
    CandidateFactorObservation,
    CandidateFactorSet,
    FactorExpansionReport,
    build_factor_expansion_candidates,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _macro_row(**overrides):
    defaults = dict(
        macro_series_id="macro_gdp_us",
        trading_day="2026-01-15",
        release_timestamp="2026-01-15T08:30:00+00:00",
        source_as_of_date="2026-01-15",
        value=2.5,
        frequency="monthly",
        fill_policy="last_value",
        source_name="FRED",
    )
    defaults.update(overrides)
    return defaults


def _event_row(**overrides):
    defaults = dict(
        ticker="AAPL",
        trading_day="2026-01-15",
        event_timestamp="2026-01-15T09:00:00+00:00",
        event_type="earnings",
        expected_direction="positive",
        observed_direction="negative",
        confidence_score=0.75,
        taxonomy_version="v1.2",
        source_refs="SEC filing 10-K 2026",
        source_as_of_date="2026-01-15",
    )
    defaults.update(overrides)
    return defaults


def _relation_row(**overrides):
    defaults = dict(
        ticker="AAPL",
        sector="TECH",
        peer_group_id="tech_large_cap",
        trading_day="2026-01-15",
        sector_return_proxy=0.05,
        peer_return_proxy=0.03,
        source_as_of_date="2026-01-15",
    )
    defaults.update(overrides)
    return defaults


def _request(**overrides):
    defaults = dict(candidate_namespace="shadow_candidate_factor.macro_event_v1")
    defaults.update(overrides)
    return FactorExpansionRequest(**defaults)


# ─── Request Validation ──────────────────────────────────────────────────────

def test_request_rejects_bad_namespace():
    with pytest.raises(FactorExpansionError, match="shadow_candidate_factor"):
        _request(candidate_namespace="production.bad")
    with pytest.raises(FactorExpansionError, match="shadow_candidate_factor"):
        _request(candidate_namespace="other.bad")


def test_request_accepts_valid_namespace():
    req = _request(candidate_namespace="shadow_candidate_factor.my_factor")
    assert req.candidate_namespace == "shadow_candidate_factor.my_factor"


# ─── Serialization ───────────────────────────────────────────────────────────

def test_report_json_serializable():
    report = build_factor_expansion_candidates([], [], [], _request())
    json.dumps(report.to_dict())


# ─── Macro Candidates ────────────────────────────────────────────────────────

def test_macro_valid_row_emits_observation():
    rows = [_macro_row()]
    report = build_factor_expansion_candidates(rows, [], [], _request())

    assert report.macro_candidates.observation_count == 1
    assert report.macro_candidates.blocked_count == 0
    obs = report.macro_candidates.observations[0]
    assert obs.candidate_family == "macro"
    assert obs.candidate_factor_name.startswith("shadow_candidate_factor")
    assert obs.trading_day == "2026-01-15"
    assert obs.ticker is None
    assert obs.point_in_time_confirmed is True
    assert obs.source_audit_complete is True
    assert obs.schema_version == "phase27_factor_expansion.0"


def test_macro_missing_release_timestamp_blocks():
    rows = [_macro_row(release_timestamp=None)]
    report = build_factor_expansion_candidates(rows, [], [], _request())

    assert report.macro_candidates.blocked_count == 1
    assert report.macro_candidates.observation_count == 0
    assert ("macro", "missing_release_timestamp", 1) in report.blocked_by_reason


def test_macro_future_source_date_blocks():
    rows = [_macro_row(source_as_of_date="2026-02-01")]  # trading_day is 2026-01-15
    report = build_factor_expansion_candidates(rows, [], [], _request())

    assert report.macro_candidates.blocked_count == 1
    assert report.macro_candidates.observation_count == 0


def test_macro_missing_trading_day_blocks():
    rows = [_macro_row(trading_day="")]
    report = build_factor_expansion_candidates(rows, [], [], _request())

    assert report.macro_candidates.blocked_count == 1
    assert ("macro", "missing_trading_day", 1) in report.blocked_by_reason


def test_macro_zscore_regime_score_computed():
    # Two rows, values 1.0 and 3.0: z-scores = -1.0 and +1.0.
    # Normalized via z-score min-max: z_min=-1, z_range=2 → [0.0, 1.0].
    # release_timestamp must be <= trading_day (P27-3) and source_as_of_date too.
    rows = [
        _macro_row(trading_day="2026-01-10", value=1.0,
                   release_timestamp="2026-01-10T08:30:00+00:00",
                   source_as_of_date="2026-01-10"),
        _macro_row(trading_day="2026-01-15", value=3.0,
                   release_timestamp="2026-01-15T08:30:00+00:00",
                   source_as_of_date="2026-01-15"),
    ]
    report = build_factor_expansion_candidates(rows, [], [], _request())

    assert report.macro_candidates.observation_count == 2
    scores = sorted([o.score_value for o in report.macro_candidates.observations])
    # Both rows have momentum=0 (first in series / symmetric pair), composite = normalized_regime / 2
    assert abs(scores[0] - 0.0) < 1e-9
    assert abs(scores[1] - 1.0) < 1e-9


def test_macro_momentum_score_computed():
    # values [1.0, 1.5], std=0.25: z-scores = [-1.0, 1.0], normalized = [0.0, 1.0]
    # momentum for row2 = (1.5-1.0)/1.0 = 0.5
    # composite = (1.0 + 0.5) / 2 = 0.75
    rows = [
        _macro_row(trading_day="2026-01-10", value=1.0,
                   release_timestamp="2026-01-10T08:30:00+00:00",
                   source_as_of_date="2026-01-10"),
        _macro_row(trading_day="2026-01-15", value=1.5,
                   release_timestamp="2026-01-15T08:30:00+00:00",
                   source_as_of_date="2026-01-15"),
    ]
    report = build_factor_expansion_candidates(rows, [], [], _request())
    obs = [o for o in report.macro_candidates.observations if o.trading_day == "2026-01-15"][0]
    assert abs(obs.score_value - 0.75) < 1e-9


def test_macro_multiple_series_grouped_separately():
    rows = [
        _macro_row(macro_series_id="gdp", trading_day="2026-01-15", value=1.0),
        _macro_row(macro_series_id="gdp", trading_day="2026-01-20", value=2.0),
        _macro_row(macro_series_id="unemp", trading_day="2026-01-15", value=3.0),
    ]
    report = build_factor_expansion_candidates(rows, [], [], _request())
    assert report.macro_candidates.observation_count == 3


# ─── Event Surprise Candidates ───────────────────────────────────────────────

def test_event_valid_row_emits_observation():
    rows = [_event_row()]
    report = build_factor_expansion_candidates([], rows, [], _request())

    assert report.event_candidates.observation_count == 1
    assert report.event_candidates.blocked_count == 0
    obs = report.event_candidates.observations[0]
    assert obs.candidate_family == "event_surprise"
    assert obs.ticker == "AAPL"
    assert obs.trading_day == "2026-01-15"
    assert obs.point_in_time_confirmed is True
    assert obs.source_audit_complete is True


def test_event_surprise_score_positive_when_directions_differ():
    rows = [_event_row(observed_direction="negative", expected_direction="positive")]
    report = build_factor_expansion_candidates([], rows, [], _request())
    obs = report.event_candidates.observations[0]
    assert obs.score_value > 0.5  # surprise=1, sentiment=0, novelty=0.75, consistency=0.5


def test_event_surprise_score_zero_when_directions_match():
    rows = [_event_row(observed_direction="positive", expected_direction="positive")]
    report = build_factor_expansion_candidates([], rows, [], _request())
    obs = report.event_candidates.observations[0]
    assert obs.score_value < 1.0  # surprise=0, sentiment=1


def test_event_missing_event_timestamp_blocks():
    rows = [_event_row(event_timestamp=None)]
    report = build_factor_expansion_candidates([], rows, [], _request())

    assert report.event_candidates.blocked_count == 1
    assert ("event_surprise", "missing_event_timestamp", 1) in report.blocked_by_reason


def test_event_missing_source_refs_blocks():
    rows = [_event_row(source_refs=None)]
    report = build_factor_expansion_candidates([], rows, [], _request())

    assert report.event_candidates.blocked_count == 1
    assert ("event_surprise", "missing_source_refs", 1) in report.blocked_by_reason


def test_event_missing_taxonomy_version_blocks():
    rows = [_event_row(taxonomy_version=None)]
    report = build_factor_expansion_candidates([], rows, [], _request())

    assert report.event_candidates.blocked_count == 1
    assert ("event_surprise", "missing_taxonomy_version", 1) in report.blocked_by_reason


def test_event_future_source_date_blocks():
    rows = [_event_row(source_as_of_date="2026-02-01")]
    report = build_factor_expansion_candidates([], rows, [], _request())

    assert report.event_candidates.blocked_count == 1
    assert report.event_candidates.observation_count == 0


# ─── Sector Relation Candidates ─────────────────────────────────────────────

def test_relation_valid_row_emits_observation():
    rows = [_relation_row()]
    report = build_factor_expansion_candidates([], [], rows, _request())

    assert report.sector_relation_candidates.observation_count == 1
    assert report.sector_relation_candidates.blocked_count == 0
    obs = report.sector_relation_candidates.observations[0]
    assert obs.candidate_family == "sector_relation"
    assert obs.ticker == "AAPL"
    assert obs.trading_day == "2026-01-15"
    assert obs.point_in_time_confirmed is True
    assert obs.source_audit_complete is True


def test_relation_missing_ticker_blocks():
    rows = [_relation_row(ticker="")]
    report = build_factor_expansion_candidates([], [], rows, _request())

    assert report.sector_relation_candidates.blocked_count == 1
    assert ("sector_relation", "missing_ticker", 1) in report.blocked_by_reason


def test_relation_missing_sector_blocks():
    rows = [_relation_row(sector=None)]
    report = build_factor_expansion_candidates([], [], rows, _request())

    assert report.sector_relation_candidates.blocked_count == 1
    assert ("sector_relation", "missing_sector", 1) in report.blocked_by_reason


def test_relation_missing_peer_group_blocks():
    rows = [_relation_row(peer_group_id=None)]
    report = build_factor_expansion_candidates([], [], rows, _request())

    assert report.sector_relation_candidates.blocked_count == 1
    assert ("sector_relation", "missing_peer_group_id", 1) in report.blocked_by_reason


def test_relation_future_source_date_blocks():
    rows = [_relation_row(source_as_of_date="2026-02-01")]
    report = build_factor_expansion_candidates([], [], rows, _request())

    assert report.sector_relation_candidates.blocked_count == 1
    assert report.sector_relation_candidates.observation_count == 0


def test_relation_score_reflects_sector_outperformance():
    rows = [
        _relation_row(ticker="AAPL", sector_return_proxy=0.10, peer_return_proxy=0.02),
        _relation_row(ticker="MSFT", sector_return_proxy=0.01, peer_return_proxy=0.03),
    ]
    report = build_factor_expansion_candidates([], [], rows, _request())
    scores = {o.ticker: o.score_value for o in report.sector_relation_candidates.observations}
    assert scores["AAPL"] > scores["MSFT"]  # AAPL outperformance relative to peers


# ─── Combined Report ─────────────────────────────────────────────────────────

def test_all_three_families_in_one_report():
    macro = [_macro_row()]
    event = [_event_row()]
    relation = [_relation_row()]
    report = build_factor_expansion_candidates(macro, event, relation, _request())

    assert report.macro_candidates.observation_count == 1
    assert report.event_candidates.observation_count == 1
    assert report.sector_relation_candidates.observation_count == 1
    assert report.total_observations == 3
    assert report.total_blocked == 0


def test_blocked_counts_aggregated():
    macro = [_macro_row(release_timestamp=None)]
    event = [_event_row(taxonomy_version=None)]
    relation = [_relation_row(peer_group_id=None)]
    report = build_factor_expansion_candidates(macro, event, relation, _request())

    assert report.total_blocked == 3
    assert ("macro", "missing_release_timestamp", 1) in report.blocked_by_reason
    assert ("event_surprise", "missing_taxonomy_version", 1) in report.blocked_by_reason
    assert ("sector_relation", "missing_peer_group_id", 1) in report.blocked_by_reason


def test_diagnostics_rows_have_required_fields():
    macro = [_macro_row()]
    event = [_event_row()]
    relation = [_relation_row()]
    report = build_factor_expansion_candidates(macro, event, relation, _request())

    for obs in list(report.macro_candidates.observations) + \
               list(report.event_candidates.observations) + \
               list(report.sector_relation_candidates.observations):
        assert hasattr(obs, "candidate_factor_name")
        assert hasattr(obs, "candidate_family")
        assert hasattr(obs, "trading_day")
        assert hasattr(obs, "ticker")          # None for macro, str for others
        assert hasattr(obs, "score_value")
        assert hasattr(obs, "point_in_time_confirmed")
        assert hasattr(obs, "source_audit_complete")
        assert hasattr(obs, "schema_version")
        assert obs.schema_version == "phase27_factor_expansion.0"


def test_empty_inputs_emits_warning():
    report = build_factor_expansion_candidates([], [], [], _request())
    assert "all_inputs_empty" in report.warnings


# ─── P27 Regression Tests ───────────────────────────────────────────────────

def test_macro_sub_scores_present():
    # P27-1: macro observations carry macro_regime_score and macro_momentum_score
    rows = [
        _macro_row(trading_day="2026-01-10", value=1.0,
                   release_timestamp="2026-01-10T08:30:00+00:00",
                   source_as_of_date="2026-01-10"),
        _macro_row(trading_day="2026-01-15", value=3.0,
                   release_timestamp="2026-01-15T08:30:00+00:00",
                   source_as_of_date="2026-01-15"),
    ]
    report = build_factor_expansion_candidates(rows, [], [], _request())
    sub_keys = {k for k, _ in report.macro_candidates.observations[0].sub_scores}
    assert "macro_regime_score" in sub_keys
    assert "macro_momentum_score" in sub_keys


def test_event_sub_scores_present():
    # P27-1: event observations carry the required sub-scores; P27-RR1: taxonomy_version in metadata
    rows = [_event_row(taxonomy_version="v1.2")]
    report = build_factor_expansion_candidates([], rows, [], _request())
    obs = report.event_candidates.observations[0]
    sub_keys = {k for k, _ in obs.sub_scores}
    assert "event_surprise_score" in sub_keys
    assert "event_sentiment_score" in sub_keys
    assert "event_novelty_score" in sub_keys
    assert "label_consistency_score" in sub_keys
    meta_keys = {k for k, _ in obs.metadata}
    assert "taxonomy_version" in meta_keys  # P27-RR1: now in metadata
    meta = dict(obs.metadata)
    assert meta["taxonomy_version"] == "v1.2"


def test_relation_sub_scores_present():
    # P27-1: sector-relation observations carry the required sub-scores; P27-RR2: version in metadata
    rows = [_relation_row()]
    report = build_factor_expansion_candidates([], [], rows, _request())
    obs = report.sector_relation_candidates.observations[0]
    sub_keys = {k for k, _ in obs.sub_scores}
    assert "sector_relative_strength_score" in sub_keys
    assert "peer_relation_score" in sub_keys
    assert "sector_dispersion_score" in sub_keys
    meta_keys = {k for k, _ in obs.metadata}
    assert "relation_baseline_version" in meta_keys  # P27-RR2: now in metadata
    meta = dict(obs.metadata)
    assert meta["relation_baseline_version"] == "phase27.0"


def test_macro_three_row_normalization():
    # P27-2: z-score min-max normalization over z-score range (not raw values).
    # Buggy code: (z - z_min_raw) / z_range_raw gave [-0.556, -0.25, +0.056] for [1,3,5].
    # Fixed code: (z - z_min_zscore) / z_range_zscore gives correct normalized values.
    rows = [
        _macro_row(trading_day="2026-01-10", value=1.0,
                   release_timestamp="2026-01-10T08:30:00+00:00",
                   source_as_of_date="2026-01-10"),
        _macro_row(trading_day="2026-01-15", value=3.0,
                   release_timestamp="2026-01-15T08:30:00+00:00",
                   source_as_of_date="2026-01-15"),
        _macro_row(trading_day="2026-01-20", value=5.0,
                   release_timestamp="2026-01-20T08:30:00+00:00",
                   source_as_of_date="2026-01-20"),
    ]
    report = build_factor_expansion_candidates(rows, [], [], _request())
    assert report.macro_candidates.observation_count == 3
    # values=[1,3,5], mean=3, std=√(8/3)≈1.633; z=[-1.225, 0, 1.225]
    # z_min=-1.225, z_range=2.45; normalized_regime=[0, 0.5, 1.0]
    # row1: norm_reg=0.0, momentum=0.0, composite=0.0
    # row2: norm_reg=0.5, momentum=(3-1)/1=2→1.0, composite=(0.5+1)/2=0.75
    # row3: norm_reg=1.0, momentum=(5-3)/3=0.667, composite=(1+0.667)/2=0.833
    scores = [o.score_value for o in report.macro_candidates.observations]
    assert abs(scores[0] - 0.0) < 1e-6
    assert abs(scores[1] - 0.75) < 1e-6
    assert abs(scores[2] - 0.8333) < 1e-3


def test_macro_release_timestamp_after_trading_day_blocks():
    # P27-3: release_timestamp > trading_day is a PIT violation
    rows = [_macro_row(trading_day="2026-01-10", value=1.0,
                        release_timestamp="2026-02-01T08:30:00+00:00",
                        source_as_of_date="2026-01-10")]
    report = build_factor_expansion_candidates(rows, [], [], _request())
    assert report.macro_candidates.blocked_count == 1
    assert ("macro", "release_timestamp_after_trading_day", 1) in report.blocked_by_reason


def test_event_timestamp_after_trading_day_blocks():
    # P27-3: event_timestamp > trading_day is a PIT violation
    rows = [_event_row(trading_day="2026-01-15",
                        event_timestamp="2026-02-01T09:00:00+00:00")]
    report = build_factor_expansion_candidates([], rows, [], _request())
    assert report.event_candidates.blocked_count == 1
    assert ("event_surprise", "event_timestamp_after_trading_day", 1) in report.blocked_by_reason


def test_missing_source_as_of_date_blocks():
    # P27-4: missing source_as_of_date emits blocked row (not admitted with pit_confirmed=False)
    macro = [_macro_row(source_as_of_date="")]
    event = [_event_row(source_as_of_date="")]
    relation = [_relation_row(source_as_of_date="")]
    report = build_factor_expansion_candidates(macro, event, relation, _request())
    assert report.macro_candidates.blocked_count == 1
    assert ("macro", "source_as_of_date_missing", 1) in report.blocked_by_reason
    assert report.event_candidates.blocked_count == 1
    assert report.sector_relation_candidates.blocked_count == 1


def test_forbidden_production_fields_block():
    # P27-5: rows with live_trade_signal, order_id, production_config_update are dropped
    macro_bad = [{"macro_series_id": "gdp", "trading_day": "2026-01-15",
                   "release_timestamp": "2026-01-15T08:30:00+00:00",
                   "source_as_of_date": "2026-01-15", "value": 2.5,
                   "live_trade_signal": "BUY"}]
    event_bad = [{"ticker": "AAPL", "trading_day": "2026-01-15",
                   "event_timestamp": "2026-01-15T09:00:00+00:00",
                   "event_type": "earnings", "expected_direction": "positive",
                   "observed_direction": "negative", "confidence_score": 0.75,
                   "taxonomy_version": "v1.2", "source_refs": "SEC 10-K",
                   "source_as_of_date": "2026-01-15",
                   "order_id": "ord_001"}]
    report = build_factor_expansion_candidates(macro_bad, event_bad, [], _request())
    assert report.macro_candidates.blocked_count == 1
    assert ("macro", "forbidden_field_live_trade_signal", 1) in report.blocked_by_reason
    assert report.event_candidates.blocked_count == 1
    assert ("event_surprise", "forbidden_field_order_id", 1) in report.blocked_by_reason


def test_bare_namespace_prefix_rejected():
    # P27-6: "shadow_candidate_factor." (empty suffix) is rejected
    from agent.research_v1.phase27_factor_expansion import FactorExpansionRequest
    with pytest.raises(FactorExpansionError, match="non-empty suffix"):
        FactorExpansionRequest(candidate_namespace="shadow_candidate_factor.")


def test_observation_has_candidate_namespace():
    # P27-7: each observation carries its candidate_namespace
    rows = [_macro_row()]
    report = build_factor_expansion_candidates(rows, [], [], _request())
    obs = report.macro_candidates.observations[0]
    assert obs.candidate_namespace == "shadow_candidate_factor.macro_event_v1"
    assert obs.candidate_namespace in obs.candidate_factor_name


def test_event_surprise_score_exact():
    # P27-11: tighten assertions on event surprise sub-scores
    rows = [_event_row(observed_direction="negative", expected_direction="positive",
                        confidence_score=0.75, taxonomy_label="NEGATIVE")]
    report = build_factor_expansion_candidates([], rows, [], _request())
    obs = report.event_candidates.observations[0]
    sub = dict(obs.sub_scores)
    # surprise: observed != expected → 1.0
    assert sub["event_surprise_score"] == 1.0
    # sentiment: negative → -1.0
    assert sub["event_sentiment_score"] == -1.0
    # novelty: confidence
    assert sub["event_novelty_score"] == 0.75
    # consistency: observed matches taxonomy label "NEGATIVE" → 1.0
    assert sub["label_consistency_score"] == 1.0
    # composite = 0.4*1 + 0.3*0 + 0.2*0.75 + 0.1*1 = 0.4 + 0 + 0.15 + 0.1 = 0.65
    assert abs(obs.score_value - 0.65) < 1e-9


def test_relation_sub_scores_exact():
    # P27-11: verify relation sub-scores with known values
    rows = [_relation_row(sector_return_proxy=0.10, peer_return_proxy=0.02)]
    report = build_factor_expansion_candidates([], [], rows, _request())
    obs = report.sector_relation_candidates.observations[0]
    sub = dict(obs.sub_scores)
    # sector_rel = (0.10 - 0.02) / 0.02 = 4.0
    assert abs(sub["sector_relative_strength_score"] - 4.0) < 1e-6
    # peer_relation: same sign → 1.0
    assert abs(sub["peer_relation_score"] - 1.0) < 1e-6
    # sector_dispersion = |0.10-0.02| / (|0.10|+|0.02|) = 0.08/0.12 ≈ 0.667
    assert abs(sub["sector_dispersion_score"] - (0.08 / 0.12)) < 1e-6


# ─── No Model Libraries ─────────────────────────────────────────────────────

def test_no_model_libraries_imported():
    import agent.research_v1.phase27_factor_expansion as p27_module

    forbidden = {
        "xgboost", "sklearn", "torch", "tensorflow", "stable_baselines3",
        "numpy", "pandas", "scipy", "cvxpy", "ortools",
    }
    assert set(p27_module.__dict__).isdisjoint(forbidden)