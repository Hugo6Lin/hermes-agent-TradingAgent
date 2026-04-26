"""P24-C safe shadow experiment runner scaffold."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from agent.research_v1.p24_experiment_registry import ShadowExperimentManifest


FORBIDDEN_ARTIFACTS = frozenset(
    {
        "company_quality_score",
        "valuation_attractiveness_score",
        "timing_market_fit_score",
        "llm_adjustment_total",
        "classification",
        "production_config",
        "canonical_factor_snapshot",
        "live_trade_signal",
    }
)

ALLOWED_RUN_MODES = frozenset({"dry_run", "shadow_stub"})


@dataclass(frozen=True)
class ShadowExperimentRunRequest:
    run_id: str
    experiment_id: str
    run_mode: str
    input_window: dict
    requested_artifacts: list[str]
    operator: str
    reason: str
    notes: str = ""


@dataclass(frozen=True)
class ShadowAdapterResult:
    adapter_name: str
    adapter_version: str
    produced_artifacts: list[str]
    attempted_outputs: list[str]
    metrics: dict
    logs: list[str]
    warnings: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ShadowExperimentRunRecord:
    schema_version: str
    run_id: str
    experiment_id: str
    candidate_id: str
    candidate_family: str
    manifest_schema_version: str
    manifest_status: str
    run_mode: str
    input_window: dict
    output_namespace: str
    adapter_name: str
    adapter_version: str
    status: str
    produced_artifacts: list[str]
    blocked_artifacts: list[str]
    safety_checks: dict
    warnings: list[str]
    error_message: str
    no_production_write_confirmed: bool
    canonical_snapshot_write_blocked: bool
    production_config_write_blocked: bool
    live_trading_blocked: bool
    started_at: str
    completed_at: str
    notes: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ShadowRunnerResult:
    record: ShadowExperimentRunRecord
    adapter_result: ShadowAdapterResult | None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _within_namespace(name: str, namespace: str) -> bool:
    return str(name) == namespace or str(name).startswith(namespace + ".")


def _is_forbidden(name: str) -> bool:
    return str(name) in FORBIDDEN_ARTIFACTS


def _evaluate_pre_run_safety(
    manifest: ShadowExperimentManifest,
    run_request: ShadowExperimentRunRequest,
) -> list[str]:
    blocked = []
    output_contract = manifest.output_contract
    if manifest.status != "registered":
        blocked.append("manifest_not_registered")
    if manifest.promotion_blocked is not True:
        blocked.append("promotion_not_blocked")
    if manifest.production_write_blocked is not True:
        blocked.append("production_write_not_blocked")
    if manifest.canonical_snapshot_write_blocked is not True:
        blocked.append("canonical_snapshot_write_not_blocked")
    if output_contract.get("writes_canonical_factor_snapshot") is not False:
        blocked.append("manifest_allows_canonical_snapshot_write")
    if output_contract.get("writes_production_config") is not False:
        blocked.append("manifest_allows_production_config_write")
    if output_contract.get("affects_live_trading") is not False:
        blocked.append("manifest_allows_live_trading")
    if output_contract.get("return_basis") != "net":
        blocked.append("manifest_return_basis_not_net")
    if run_request.experiment_id != manifest.experiment_id:
        blocked.append("experiment_id_mismatch")
    if run_request.run_mode not in ALLOWED_RUN_MODES:
        blocked.append("run_mode_not_allowed")
    if run_request.input_window.get("point_in_time_required") is not True:
        blocked.append("input_window_not_point_in_time")
    if run_request.input_window.get("data_as_of_policy") != "manifest_point_in_time_policy":
        blocked.append("data_as_of_policy_invalid")
    for artifact in run_request.requested_artifacts:
        if not _within_namespace(artifact, manifest.shadow_namespace):
            blocked.append(f"requested_artifact_outside_namespace:{artifact}")
        if _is_forbidden(artifact):
            blocked.append(f"requested_forbidden_artifact:{artifact}")
    return blocked


def _evaluate_adapter_safety(
    manifest: ShadowExperimentManifest,
    adapter_result: ShadowAdapterResult,
) -> list[str]:
    blocked = []
    for artifact in list(adapter_result.produced_artifacts) + list(adapter_result.attempted_outputs):
        if not _within_namespace(artifact, manifest.shadow_namespace):
            blocked.append(f"adapter_output_outside_namespace:{artifact}")
        if _is_forbidden(artifact):
            blocked.append(f"adapter_forbidden_output:{artifact}")
    return blocked


def _build_record(
    manifest: ShadowExperimentManifest,
    run_request: ShadowExperimentRunRequest,
    started_at: str,
    status: str,
    adapter_name: str,
    adapter_version: str,
    produced_artifacts: list[str],
    blocked_artifacts: list[str],
    warnings: list[str],
    error_message: str,
) -> ShadowExperimentRunRecord:
    return ShadowExperimentRunRecord(
        schema_version="p24_run.0",
        run_id=run_request.run_id,
        experiment_id=run_request.experiment_id,
        candidate_id=manifest.candidate_id,
        candidate_family=manifest.candidate_family,
        manifest_schema_version=manifest.schema_version,
        manifest_status=manifest.status,
        run_mode=run_request.run_mode,
        input_window=dict(run_request.input_window),
        output_namespace=manifest.shadow_namespace,
        adapter_name=adapter_name,
        adapter_version=adapter_version,
        status=status,
        produced_artifacts=produced_artifacts,
        blocked_artifacts=blocked_artifacts,
        safety_checks={
            "no_production_write": True,
            "canonical_snapshot_write_blocked": True,
            "production_config_write_blocked": True,
            "live_trading_blocked": True,
        },
        warnings=warnings,
        error_message=error_message,
        no_production_write_confirmed=True,
        canonical_snapshot_write_blocked=True,
        production_config_write_blocked=True,
        live_trading_blocked=True,
        started_at=started_at,
        completed_at=_utc_now(),
        notes=run_request.notes,
    )


def run_shadow_experiment(
    manifest: ShadowExperimentManifest,
    adapter: Any,
    run_request: ShadowExperimentRunRequest,
) -> ShadowRunnerResult:
    started_at = _utc_now()
    pre_block = _evaluate_pre_run_safety(manifest, run_request)
    if pre_block:
        return ShadowRunnerResult(
            record=_build_record(
                manifest=manifest,
                run_request=run_request,
                started_at=started_at,
                status="blocked",
                adapter_name="none",
                adapter_version="none",
                produced_artifacts=[],
                blocked_artifacts=pre_block,
                warnings=[],
                error_message=f"pre-run safety block: {', '.join(pre_block)}",
            ),
            adapter_result=None,
        )

    if run_request.run_mode == "dry_run":
        return ShadowRunnerResult(
            record=_build_record(
                manifest=manifest,
                run_request=run_request,
                started_at=started_at,
                status="completed",
                adapter_name="none",
                adapter_version="none",
                produced_artifacts=list(run_request.requested_artifacts),
                blocked_artifacts=[],
                warnings=[],
                error_message="",
            ),
            adapter_result=None,
        )

    if adapter is None:
        return ShadowRunnerResult(
            record=_build_record(
                manifest=manifest,
                run_request=run_request,
                started_at=started_at,
                status="blocked",
                adapter_name="none",
                adapter_version="none",
                produced_artifacts=[],
                blocked_artifacts=["adapter_missing_for_shadow_stub"],
                warnings=[],
                error_message="pre-run safety block: adapter_missing_for_shadow_stub",
            ),
            adapter_result=None,
        )

    try:
        adapter_result = adapter.run(manifest, run_request)
    except Exception as exc:
        return ShadowRunnerResult(
            record=_build_record(
                manifest=manifest,
                run_request=run_request,
                started_at=started_at,
                status="failed",
                adapter_name=getattr(adapter, "adapter_name", "unknown"),
                adapter_version=getattr(adapter, "adapter_version", "unknown"),
                produced_artifacts=[],
                blocked_artifacts=[],
                warnings=[],
                error_message=f"{exc.__class__.__name__}: {exc}",
            ),
            adapter_result=None,
        )

    post_block = _evaluate_adapter_safety(manifest, adapter_result)
    return ShadowRunnerResult(
        record=_build_record(
            manifest=manifest,
            run_request=run_request,
            started_at=started_at,
            status="blocked" if post_block else "completed",
            adapter_name=adapter_result.adapter_name,
            adapter_version=adapter_result.adapter_version,
            produced_artifacts=[] if post_block else list(adapter_result.produced_artifacts),
            blocked_artifacts=post_block,
            warnings=list(adapter_result.warnings),
            error_message=f"adapter safety block: {', '.join(post_block)}" if post_block else "",
        ),
        adapter_result=adapter_result,
    )