"""Argparse-based CLI entrypoint for the Hermes research app."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Sequence

from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.data.futu_opend import FutuQuoteClient
from agent.research_v1.governance_runtime import GovernanceRuntimeRequest, run_governance_runtime
from agent.research_v1.fundamental_quality import run_fundamental_quality
from agent.research_v1.candidate_pool import run_candidate_pool
from agent.research_v1.research_memory_pack import run_research_memory_pack
from agent.research_v1.decision_journal_guardrails import run_decision_journal_guardrails
from agent.research_v1.boss_copilot_daily_brief import run_boss_copilot_daily_brief
from agent.research_v1.copilot_console_index import run_copilot_console_index
from agent.research_v1.evidence_freshness_drift_monitor import run_evidence_freshness_drift_monitor
from agent.research_v1.evidence_refresh_planner import run_evidence_refresh_planner
from agent.research_v1.market_data_readiness import run_market_data_readiness
from agent.research_v1.research_context_pack import run_research_context_pack
from agent.research_v1.research_context_prompt_pack import run_research_context_prompt_pack
from agent.research_v1.boss_preview_runner import run_boss_preview
from agent.research_v1.boss_pdf_brief_renderer import run_boss_pdf_brief
from agent.research_v1.boss_console.console_runtime import run_boss_console
from agent.research_v1.market_regime_context import run_market_regime_context
from agent.research_v1.market_visual_assets import run_market_visual_assets
from agent.research_v1.recommendation_outcomes import run_recommendation_outcome_tracking
from agent.research_v1.paths import HermesPaths
from agent.research_v1.report_pdf_legacy import export_batch_pdf
from agent.research_v1.research_batch_service import save_batch_research
from agent.research_v1.viewer import serve_viewer


def _load_paths(root: str | Path | None = None) -> HermesPaths:
    return HermesPaths.from_root(Path.cwd() if root is None else root)


def _ensure_database(paths: HermesPaths) -> ResearchDatabase:
    paths.ensure_directories()
    database = ResearchDatabase(str(paths.database_path))
    database.initialize()
    return database


def _cmd_init(paths: HermesPaths) -> int:
    _ensure_database(paths)
    print(f"Initialized Hermes research app at {paths.app_root}")
    print(f"Database ready at {paths.database_path}")
    return 0


def _cmd_status(paths: HermesPaths) -> int:
    database_exists = paths.database_path.exists()
    print("Hermes research app status")
    print(f"App root: {paths.app_root}")
    print(f"Data dir: {paths.data_dir} ({'ready' if paths.data_dir.exists() else 'missing'})")
    print(f"Reports dir: {paths.reports_dir} ({'ready' if paths.reports_dir.exists() else 'missing'})")
    print(f"Exports dir: {paths.exports_dir} ({'ready' if paths.exports_dir.exists() else 'missing'})")
    print(f"Database: {paths.database_path} ({'ready' if database_exists else 'missing'})")
    return 0


def _cmd_ingest(paths: HermesPaths, input_path: str) -> int:
    database = _ensure_database(paths)
    payload_path = Path(input_path).expanduser().resolve()
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    result = save_batch_research(database, payload)

    print(f"Ingested batch {result['batch_id']} from {payload_path}")
    print(f"Saved {len(result['item_ids'])} items and {len(result['report_ids'])} reports")
    return 0


def _cmd_viewer(paths: HermesPaths, host: str, port: int) -> int:
    database = _ensure_database(paths)
    server = serve_viewer(database, host=host, port=port)
    print(f"Serving Hermes viewer on http://{host}:{port}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


def _cmd_export_pdf(paths: HermesPaths, batch_id: int) -> int:
    database = _ensure_database(paths)
    pdf_path = export_batch_pdf(database, batch_id=batch_id, output_dir=paths.exports_dir)
    print(f"Exported batch {batch_id} PDF to {pdf_path}")
    return 0


def _cmd_quote(symbols: str) -> int:
    client = FutuQuoteClient()
    rows = client.fetch_snapshot([symbol.strip() for symbol in symbols.split(",") if symbol.strip()])
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def _cmd_option_chain(symbol: str, start: str | None, end: str | None) -> int:
    client = FutuQuoteClient()
    rows = client.fetch_option_chain(symbol=symbol, start=start, end=end)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def _cmd_governance_run(
    paths: HermesPaths,
    config_path: str,
    run_date: str,
    output_root: str,
    freshness_policy_days: int,
) -> int:
    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path
    result = run_governance_runtime(
        GovernanceRuntimeRequest(
            run_date=run_date,
            repo_root=paths.app_root,
            output_root=output_path.resolve(),
            config_path=Path(config_path).expanduser().resolve(),
            freshness_policy_days=freshness_policy_days,
        )
    )
    print(f"Governance runtime status: {result.status}")
    print(f"Output dir: {result.output_dir}")
    print(f"Boss brief status: {result.boss_brief_status}")
    for artifact in result.artifacts_written:
        print(f"Artifact: {artifact}")
    for warning in result.warnings:
        print(f"Warning: {warning}")
    return 2 if result.status == "blocked_invalid_config" else 0


def _cmd_outcome_run(
    paths: HermesPaths,
    as_of_date: str,
    output_root: str,
    limit: int,
    flat_cost_bps: float,
) -> int:
    if limit < 0 or flat_cost_bps < 0:
        print("invalid outcome-run input: limit and flat-cost-bps must be non-negative")
        return 2

    try:
        evaluated_date = date.fromisoformat(as_of_date)
    except (ValueError, TypeError):
        print(f"invalid outcome-run input: invalid date format '{as_of_date}'")
        return 2

    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path

    database = _ensure_database(paths)
    result = run_recommendation_outcome_tracking(
        db=database,
        evaluated_for_date=evaluated_date,
        limit=limit,
        flat_cost_bps=flat_cost_bps,
        output_root=output_path.resolve(),
    )
    print(f"Outcome tracking status: {result['status']}")
    print(f"Output dir: {result['output_dir']}")
    print(f"Outcome rows written: {result['outcome_rows_written']}")
    print(f"Duplicate rows skipped: {result['duplicate_rows_skipped']}")
    for warning in result.get("warnings", []):
        print(f"Warning: {warning}")
    return 0


def _cmd_market_regime_run(
    paths: HermesPaths,
    as_of_date: str,
    lookback_days: int,
    output_root: str,
) -> int:
    try:
        run_date = date.fromisoformat(as_of_date)
    except (ValueError, TypeError):
        print(f"invalid market-regime-run input: invalid date format '{as_of_date}'")
        return 2

    if lookback_days <= 0:
        print("invalid market-regime-run input: lookback-days must be positive")
        return 2

    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path

    database = _ensure_database(paths)
    result = run_market_regime_context(
        db=database,
        as_of_date=run_date,
        lookback_days=lookback_days,
        output_root=output_path.resolve(),
    )
    print(f"Market regime status: {result['status']}")
    print(f"Output dir: {result['output_dir']}")
    print(f"Regime label: {result['regime_label']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Missing symbols: {len(result['missing_symbols'])}")
    for warning in result.get("warnings", []):
        print(f"Warning: {warning}")
    return 0


def _cmd_fundamental_quality_run(
    paths: HermesPaths,
    input_path: str,
    as_of_date: str | None,
    output_root: str,
) -> int:
    # Validate date format before proceeding
    effective_date = as_of_date
    if effective_date is None:
        # Will be resolved later from payload; skip CLI-level date check
        pass
    else:
        try:
            date.fromisoformat(effective_date)
        except (ValueError, TypeError):
            print(f"invalid fundamental-quality-run input: invalid date format '{effective_date}'")
            return 2

    payload_path = Path(input_path).expanduser().resolve()
    if not payload_path.exists():
        print(f"invalid fundamental-quality-run input: file not found '{input_path}'")
        return 2

    try:
        input_payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"invalid fundamental-quality-run input: {exc}")
        return 2

    if not isinstance(input_payload.get("tickers"), list):
        print("invalid fundamental-quality-run input: missing 'tickers' list")
        return 2

    # Validate each ticker item is a dict
    for i, item in enumerate(input_payload["tickers"]):
        if not isinstance(item, dict):
            print(f"invalid fundamental-quality-run input: ticker item {i} is not a dict")
            return 2

    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path

    database = _ensure_database(paths)
    result = run_fundamental_quality(
        db=database,
        input_payload=input_payload,
        as_of_date=as_of_date,
        output_root=output_path.resolve(),
    )
    print(f"Fundamental quality status: {result['status']}")
    print(f"Output dir: {result['output_dir']}")
    print(f"Report count: {result['report_count']}")
    print(f"Blocked count: {result['blocked_count']}")
    print(f"Warning count: {result['warning_count']}")
    return 0


def _cmd_candidate_pool_run(
    paths: HermesPaths,
    input_path: str,
    as_of_date: str | None,
    output_root: str,
    max_candidates: int,
) -> int:
    # Validate date format before proceeding
    if as_of_date is not None:
        try:
            date.fromisoformat(as_of_date)
        except (ValueError, TypeError):
            print(f"invalid candidate-pool-run input: invalid date format '{as_of_date}'")
            return 2

    if max_candidates <= 0:
        print("invalid candidate-pool-run input: max-candidates must be positive")
        return 2

    payload_path = Path(input_path).expanduser().resolve()
    if not payload_path.exists():
        print(f"invalid candidate-pool-run input: file not found '{input_path}'")
        return 2

    try:
        input_payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"invalid candidate-pool-run input: {exc}")
        return 2

    if not isinstance(input_payload.get("tickers"), list):
        print("invalid candidate-pool-run input: missing 'tickers' list")
        return 2

    for i, item in enumerate(input_payload["tickers"]):
        if not isinstance(item, dict):
            print(f"invalid candidate-pool-run input: ticker item {i} is not a dict")
            return 2

    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path

    database = _ensure_database(paths)
    result = run_candidate_pool(
        db=database,
        input_payload=input_payload,
        as_of_date=as_of_date,
        output_root=output_path.resolve(),
        max_candidates=max_candidates,
    )
    print(f"Candidate pool status: {result['status']}")
    print(f"Output dir: {result['output_dir']}")
    print(f"Candidate count: {result['candidate_count']}")
    print(f"Excluded count: {result['excluded_count']}")
    print(f"Top candidate: {result['top_candidate'] or 'none'}")
    print(f"Warning count: {result['warning_count']}")
    return 0


def _cmd_memory_pack_run(
    paths: HermesPaths,
    tickers: str | None,
    input_path: str | None,
    as_of_date: str | None,
    lookback_days: int,
    output_root: str,
    max_items_per_ticker: int,
) -> int:
    from datetime import date as _date

    # Load from JSON input if provided
    input_payload: dict = {}
    if input_path:
        payload_path = Path(input_path).expanduser().resolve()
        if not payload_path.exists():
            print(f"invalid memory-pack-run input: file not found '{input_path}'")
            return 2
        try:
            input_payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"invalid memory-pack-run input: {exc}")
            return 2

    # Merge tickers from CLI and JSON
    ticker_list: list[str] = []
    if tickers:
        ticker_list.extend(tickers.split(","))
    if input_payload.get("tickers"):
        ticker_list.extend(input_payload["tickers"])

    # Resolve as_of_date
    effective_date = as_of_date or input_payload.get("as_of_date")
    if not effective_date:
        print("invalid memory-pack-run input: --as-of-date is required")
        return 2

    try:
        _date.fromisoformat(effective_date)
    except (ValueError, TypeError):
        print(f"invalid memory-pack-run input: invalid date format '{effective_date}'")
        return 2

    # Validate lookback
    effective_lookback = lookback_days or input_payload.get("lookback_days", 180)
    if effective_lookback <= 0:
        print("invalid memory-pack-run input: lookback-days must be positive")
        return 2

    # Validate max items
    if max_items_per_ticker <= 0:
        print("invalid memory-pack-run input: max-items-per-ticker must be positive")
        return 2

    # Resolve output root
    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path

    database = _ensure_database(paths)
    result = run_research_memory_pack(
        db=database,
        tickers=ticker_list,
        as_of_date=effective_date,
        lookback_days=effective_lookback,
        output_root=output_path.resolve(),
        max_items_per_ticker=max_items_per_ticker,
    )

    if result.get("status") == "blocked_invalid_input":
        print(f"invalid memory-pack-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2

    print(f"Research memory status: {result['status']}")
    print(f"Output dir: {result['output_dir']}")
    print(f"Ticker count: {result['ticker_count']}")
    print(f"Memory available: {result['memory_available']}")
    print(f"Limited memory: {result['limited_memory']}")
    print(f"No prior memory: {result['no_prior_memory']}")
    print(f"Warning count: {result['warning_count']}")
    return 0


def _cmd_decision_journal_run(
    paths: HermesPaths,
    input_path: str,
    as_of_date: str | None,
    output_root: str,
) -> int:
    from datetime import date as _date

    # Validate file exists
    payload_path = Path(input_path).expanduser().resolve()
    if not payload_path.exists():
        print(f"invalid decision-journal-run input: file not found '{input_path}'")
        return 2

    # Validate JSON
    try:
        input_payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"invalid decision-journal-run input: {exc}")
        return 2

    # Validate date if provided
    effective_date = as_of_date or input_payload.get("as_of_date")
    if effective_date:
        try:
            _date.fromisoformat(effective_date)
        except (ValueError, TypeError):
            print(f"invalid decision-journal-run input: invalid date format '{effective_date}'")
            return 2

    # Validate decisions list
    decisions = input_payload.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        print("invalid decision-journal-run input: missing or empty 'decisions' list")
        return 2

    for i, item in enumerate(decisions):
        if not isinstance(item, dict):
            print(f"invalid decision-journal-run input: decision item {i} is not a dict")
            return 2

    # Resolve output root
    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path

    database = _ensure_database(paths)
    result = run_decision_journal_guardrails(
        db=database,
        input_payload=input_payload,
        as_of_date=effective_date,
        output_root=output_path.resolve(),
    )

    if result.get("status") == "blocked_invalid_input":
        warnings = result.get("warnings", ["unknown"])
        print(f"invalid decision-journal-run input: {warnings[0]}")
        return 2

    print(f"Decision journal status: {result['status']}")
    print(f"Output dir: {result['output_dir']}")
    print(f"Entry count: {result['entry_count']}")
    print(f"Manual review count: {result['manual_review_count']}")
    print(f"Slow down count: {result['slow_down_count']}")
    print(f"Warning count: {result['warning_count']}")
    return 0


def _cmd_boss_copilot_brief_run(paths: HermesPaths, as_of_date: str, output_root: str, max_priorities: int) -> int:
    from datetime import date as _date

    try:
        _date.fromisoformat(as_of_date)
    except (ValueError, TypeError):
        print(f"invalid boss-copilot-brief-run input: invalid date format '{as_of_date}'")
        return 2
    if max_priorities <= 0:
        print("invalid boss-copilot-brief-run input: max-priorities must be positive")
        return 2

    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path

    database = _ensure_database(paths)
    result = run_boss_copilot_daily_brief(
        db=database,
        as_of_date=as_of_date,
        output_root=output_path.resolve(),
        max_priorities=max_priorities,
    )
    if result.get("status") == "blocked_invalid_input":
        print(f"invalid boss-copilot-brief-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2

    print(f"Boss co-pilot brief status: {result['status']}")
    print(f"Output dir: {result['output_dir']}")
    print(f"Priority count: {result['priority_count']}")
    print(f"High priority count: {result['high_priority_count']}")
    print(f"Manual review count: {result['manual_review_count']}")
    print(f"Missing context count: {result['missing_context_count']}")
    return 0


def _cmd_copilot_console_index_run(
    paths: HermesPaths,
    as_of_date: str,
    lookback_days: int,
    governance_root: str,
    output_root: str,
) -> int:
    from datetime import date as _date

    try:
        _date.fromisoformat(as_of_date)
    except (ValueError, TypeError):
        print(f"invalid copilot-console-index-run input: invalid date format '{as_of_date}'")
        return 2
    if lookback_days <= 0:
        print("invalid copilot-console-index-run input: lookback-days must be positive")
        return 2

    governance_path = Path(governance_root).expanduser()
    if not governance_path.is_absolute():
        governance_path = paths.app_root / governance_path
    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path

    database = _ensure_database(paths)
    result = run_copilot_console_index(
        governance_root=governance_path.resolve(),
        output_root=output_path.resolve(),
        as_of_date=as_of_date,
        lookback_days=lookback_days,
        db=database,
    )
    if result.get("status") == "blocked_invalid_input":
        print(f"invalid copilot-console-index-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2
    print(f"Co-pilot console index status: {result['status']}")
    print(f"Output dir: {result['output_dir']}")
    print(f"Day count: {result['day_count']}")
    print(f"Latest day: {result['latest_day']}")
    print(f"Missing artifact count: {result['missing_artifact_count']}")
    print(f"Invalid artifact count: {result['invalid_artifact_count']}")
    return 0


def _cmd_evidence_monitor_run(
    paths: HermesPaths,
    as_of_date: str,
    lookback_days: int,
    freshness_days: int,
    governance_root: str,
    output_root: str,
) -> int:
    from datetime import date as _date

    try:
        _date.fromisoformat(as_of_date)
    except (ValueError, TypeError):
        print(f"invalid evidence-monitor-run input: invalid date format '{as_of_date}'")
        return 2
    if lookback_days <= 0:
        print("invalid evidence-monitor-run input: lookback-days must be positive")
        return 2
    if freshness_days <= 0:
        print("invalid evidence-monitor-run input: freshness-days must be positive")
        return 2

    governance_path = Path(governance_root).expanduser()
    if not governance_path.is_absolute():
        governance_path = paths.app_root / governance_path
    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path

    database = _ensure_database(paths)
    result = run_evidence_freshness_drift_monitor(
        db=database,
        governance_root=governance_path.resolve(),
        output_root=output_path.resolve(),
        as_of_date=as_of_date,
        lookback_days=lookback_days,
        freshness_days=freshness_days,
    )
    if result.get("status") == "blocked_invalid_input":
        print(f"invalid evidence-monitor-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2
    print(f"Evidence monitor status: {result['status']}")
    print(f"Output dir: {result['output_dir']}")
    print(f"Phase count: {result['phase_count']}")
    print(f"Red count: {result['red_count']}")
    print(f"Yellow count: {result['yellow_count']}")
    print(f"Missing context pattern count: {result['missing_context_pattern_count']}")
    return 0


def _cmd_market_data_readiness_run(
    paths: HermesPaths,
    as_of_date: str,
    symbols: str,
    history_days: int,
    option_symbol: str,
    host: str,
    port: int,
    live: bool,
    output_root: str,
) -> int:
    import os

    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    opt_sym = option_symbol if option_symbol else ""
    effective_host = os.environ.get("FUTU_OPEND_HOST", host)
    try:
        effective_port = int(os.environ.get("FUTU_OPEND_PORT", str(port)))
    except ValueError:
        effective_port = port

    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path

    database = _ensure_database(paths)
    result = run_market_data_readiness(
        output_root=output_path.resolve(),
        as_of_date=as_of_date,
        host=effective_host,
        port=effective_port,
        symbols=symbol_list,
        history_days=history_days,
        option_symbol=opt_sym,
        live=live,
        db=database,
    )
    if result.get("status") == "blocked_invalid_input":
        warnings = result.get("warnings", ["unknown"])
        print(f"invalid market-data-readiness-run input: {warnings[0]}")
        return 2
    print(f"Market data readiness status: {result['status']}")
    print(f"Output dir: {result['output_dir']}")
    if result.get("recommended_actions"):
        for action in result["recommended_actions"]:
            print(f"  recommended: {action}")
    if result["status"] == "provider_unavailable":
        return 3
    return 0


def _cmd_evidence_refresh_plan_run(
    paths: HermesPaths,
    as_of_date: str,
    lookback_days: int,
    max_items: int,
    governance_root: str,
    output_root: str,
) -> int:
    from datetime import date as _date

    try:
        _date.fromisoformat(as_of_date)
    except (ValueError, TypeError):
        print(f"invalid evidence-refresh-plan-run input: invalid date format '{as_of_date}'")
        return 2
    if lookback_days <= 0:
        print("invalid evidence-refresh-plan-run input: lookback-days must be positive")
        return 2
    if max_items <= 0:
        print("invalid evidence-refresh-plan-run input: max-items must be positive")
        return 2
    governance_path = Path(governance_root).expanduser()
    if not governance_path.is_absolute():
        governance_path = paths.app_root / governance_path
    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path
    database = _ensure_database(paths)
    result = run_evidence_refresh_planner(
        db=database,
        governance_root=governance_path.resolve(),
        output_root=output_path.resolve(),
        as_of_date=as_of_date,
        lookback_days=lookback_days,
        max_items=max_items,
    )
    if result.get("status") == "blocked_invalid_input":
        print(f"invalid evidence-refresh-plan-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2
    print(f"Evidence refresh plan status: {result['status']}")
    print(f"Output dir: {result['output_dir']}")
    print(f"Plan id: {result['plan_id']}")
    print(f"Candidate count: {result['candidate_count']}")
    print(f"Blocked count: {result['blocked_count']}")
    return 0


def _cmd_research_context_pack_run(
    paths: HermesPaths,
    as_of_date: str,
    tickers: str,
    lookback_days: int,
    max_items_per_ticker: int,
    governance_root: str,
    output_root: str,
) -> int:
    from datetime import date as _date

    try:
        _date.fromisoformat(as_of_date)
    except (ValueError, TypeError):
        print(f"invalid research-context-pack-run input: invalid date format '{as_of_date}'")
        return 2
    if not tickers:
        print("invalid research-context-pack-run input: tickers required")
        return 2
    if lookback_days <= 0:
        print("invalid research-context-pack-run input: lookback-days must be positive")
        return 2
    if max_items_per_ticker <= 0:
        print("invalid research-context-pack-run input: max-items-per-ticker must be positive")
        return 2
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    governance_path = Path(governance_root).expanduser()
    if not governance_path.is_absolute():
        governance_path = paths.app_root / governance_path
    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path
    database = _ensure_database(paths)
    result = run_research_context_pack(
        db=database,
        governance_root=governance_path.resolve(),
        output_root=output_path.resolve(),
        as_of_date=as_of_date,
        tickers=ticker_list,
        lookback_days=lookback_days,
        max_items_per_ticker=max_items_per_ticker,
    )
    if result.get("status") == "blocked_invalid_input":
        print(f"invalid research-context-pack-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2
    print(f"Research context pack status: {result['status']}")
    print(f"Pack id: {result['pack_id']}")
    print(f"Tickers: {', '.join(result['tickers'])}")
    print(f"Missing context: {len(result['missing_context'])}")
    print(f"Warnings: {len(result['warnings'])}")
    return 0


def _cmd_research_context_prompt_pack_run(
    paths: HermesPaths,
    as_of_date: str,
    tickers: str,
    roles: str,
    max_block_chars: int,
    governance_root: str,
    output_root: str,
) -> int:
    from datetime import date as _date

    try:
        _date.fromisoformat(as_of_date)
    except (ValueError, TypeError):
        print(f"invalid research-context-prompt-pack-run input: invalid date format '{as_of_date}'")
        return 2
    if not tickers:
        print("invalid research-context-prompt-pack-run input: tickers required")
        return 2
    if max_block_chars <= 0:
        print("invalid research-context-prompt-pack-run input: max-block-chars must be positive")
        return 2
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    role_list = [r.strip() for r in roles.split(",") if r.strip()] if roles.strip() else None
    governance_path = Path(governance_root).expanduser()
    if not governance_path.is_absolute():
        governance_path = paths.app_root / governance_path
    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path
    database = _ensure_database(paths)
    result = run_research_context_prompt_pack(
        db=database,
        governance_root=governance_path.resolve(),
        output_root=output_path.resolve(),
        as_of_date=as_of_date,
        tickers=ticker_list,
        roles=role_list,
        max_block_chars=max_block_chars,
    )
    if result.get("status") in {"blocked_invalid_input", "blocked_missing_context"}:
        print(f"invalid research-context-prompt-pack-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2
    print(f"Research context prompt pack status: {result['status']}")
    print(f"Prompt pack id: {result['prompt_pack_id']}")
    print(f"Tickers: {', '.join(result['tickers'])}")
    print(f"Roles: {', '.join(result['roles'])}")
    print(f"Omitted context: {len(result['omitted_context'])}")
    print(f"Warnings: {len(result['warnings'])}")
    return 0


def _cmd_boss_preview_run(
    paths: HermesPaths,
    tickers: str,
    as_of_date: str | None,
    output_root: str,
    governance_root: str,
    live: bool,
    max_candidates: int,
) -> int:
    from datetime import date as _date

    effective_date = as_of_date or _date.today().isoformat()
    try:
        _date.fromisoformat(effective_date)
    except (ValueError, TypeError):
        print(f"invalid boss-preview-run input: invalid date format '{effective_date}'")
        return 2
    if max_candidates <= 0:
        print("invalid boss-preview-run input: max-candidates must be positive")
        return 2

    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        print("invalid boss-preview-run input: tickers required")
        return 2

    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path
    governance_path = Path(governance_root).expanduser()
    if not governance_path.is_absolute():
        governance_path = paths.app_root / governance_path

    database = _ensure_database(paths)
    result = run_boss_preview(
        db=database,
        tickers=ticker_list,
        as_of_date=effective_date,
        output_root=output_path.resolve(),
        governance_root=governance_path.resolve(),
        live=live,
        max_candidates=max_candidates,
    )
    if result.get("status") == "boss_preview_blocked_invalid_input":
        print(f"invalid boss-preview-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2
    print(f"Boss preview status: {result['status']}")
    print(f"Preview id: {result['preview_id']}")
    print(f"Tickers: {', '.join(result['tickers'])}")
    print(f"Top candidates: {', '.join(result.get('top_candidates', [])) or 'none'}")
    for path in result.get("artifact_paths", []):
        if str(path).endswith("boss_preview.md"):
            print(f"Boss report: {path}")
    return 0


def _cmd_boss_pdf_brief_run(
    paths: HermesPaths,
    preview_dir: str,
    ticker: str,
    output_dir: str | None,
    title: str | None,
    max_pages: int,
    no_pdf: bool,
) -> int:
    preview_path = Path(preview_dir).expanduser()
    if not preview_path.is_absolute():
        preview_path = paths.app_root / preview_path
    out_path = None
    if output_dir:
        out_path = Path(output_dir).expanduser()
        if not out_path.is_absolute():
            out_path = paths.app_root / out_path
    result = run_boss_pdf_brief(
        preview_dir=preview_path.resolve(),
        ticker=ticker,
        output_dir=out_path.resolve() if out_path is not None else None,
        title=title,
        max_pages=max_pages,
        render_pdf=not no_pdf,
    )
    if result.get("status") == "boss_pdf_brief_blocked_invalid_input":
        print(f"invalid boss-pdf-brief-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2
    print(f"Boss PDF brief status: {result['status']}")
    print(f"Ticker: {result.get('ticker', ticker)}")
    print(f"HTML: {result.get('html_path', '')}")
    print(f"PDF: {result.get('pdf_path', '') or 'not generated'}")
    print(f"Manifest: {result.get('manifest_path', '')}")
    print(f"Verdict: {result.get('verdict', '')}")
    for warning in result.get("warnings", []):
        print(f"Warning: {warning}")
    return 0


def _cmd_boss_console_run(
    paths: HermesPaths,
    governance_root: str,
    output_dir: str,
    as_of_date: str | None,
    tickers: str | None,
) -> int:
    root = Path(governance_root).expanduser()
    if not root.is_absolute():
        root = paths.app_root / root
    out = Path(output_dir).expanduser()
    if not out.is_absolute():
        out = paths.app_root / out
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()] if tickers else None
    result = run_boss_console(
        governance_root=root.resolve(),
        output_dir=out.resolve(),
        as_of_date=as_of_date,
        tickers=ticker_list,
    )
    if result.get("status") == "boss_console_blocked_invalid_input":
        print(f"invalid boss-console-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2
    print(f"Boss console status: {result['status']}")
    print(f"Reports: {result.get('report_count', 0)}")
    print(f"HTML: {result.get('html_path', '')}")
    print(f"JSON: {result.get('json_path', '')}")
    for warning in result.get("warnings", []):
        print(f"Warning: {warning}")
    return 0


def _cmd_market_visual_run(
    paths: HermesPaths,
    tickers: str,
    as_of_date: str,
    output_root: str,
    history_days: int,
    heatmap_metric: str,
    live: bool,
    host: str,
    port: int,
) -> int:
    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    result = run_market_visual_assets(
        tickers=ticker_list,
        as_of_date=as_of_date,
        output_root=output_path.resolve(),
        history_days=history_days,
        heatmap_metric=heatmap_metric,
        live=live,
        host=host,
        port=port,
    )
    if result.get("status") == "blocked_invalid_input":
        print(f"invalid market-visual-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2
    print(f"Market visual status: {result['status']}")
    print(f"Output dir: {result.get('output_dir', '')}")
    for path in result.get("artifact_paths", []):
        print(f"Artifact: {path}")
    for warning in result.get("warnings", []):
        print(f"Warning: {warning}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hermes-research")
    parser.add_argument(
        "--app-root",
        default=None,
        help="Override the local Hermes app root directory.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Create the local Hermes data layout and database.")
    subparsers.add_parser("status", help="Show whether the local Hermes data layout exists.")

    ingest_parser = subparsers.add_parser("ingest", help="Ingest a batch research payload.")
    ingest_parser.add_argument("--input", required=True, help="Path to a JSON batch payload.")

    viewer_parser = subparsers.add_parser("viewer", help="Start the local Hermes viewer.")
    viewer_parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    viewer_parser.add_argument("--port", default=8008, type=int, help="Port to bind.")

    export_parser = subparsers.add_parser("export-pdf", help="Export a batch report as PDF.")
    export_parser.add_argument("--batch-id", required=True, type=int, help="Batch id to export.")

    quote_parser = subparsers.add_parser("quote", help="Query Futu OpenD market snapshot.")
    quote_parser.add_argument("--symbols", required=True, help="Comma-separated symbols, e.g. AAPL,HK.00700.")

    option_parser = subparsers.add_parser("option-chain", help="Query Futu OpenD option chain.")
    option_parser.add_argument("--symbol", required=True, help="Underlying symbol, e.g. GLW or US.GLD.")
    option_parser.add_argument("--start", default=None, help="Start expiration date YYYY-MM-DD.")
    option_parser.add_argument("--end", default=None, help="End expiration date YYYY-MM-DD.")

    governance_parser = subparsers.add_parser("governance-run", help="Run the local governance evidence loop.")
    governance_parser.add_argument("--config", required=True, help="Path to governance runtime JSON config.")
    governance_parser.add_argument("--run-date", required=True, help="Governance run date YYYY-MM-DD.")
    governance_parser.add_argument(
        "--output-root",
        default="output/governance",
        help="Root directory for governance artifacts.",
    )
    governance_parser.add_argument(
        "--freshness-policy-days",
        default=7,
        type=int,
        help="Maximum artifact age before registry marks an artifact stale.",
    )

    outcome_parser = subparsers.add_parser("outcome-run", help="Run recommendation outcome tracking.")
    outcome_parser.add_argument("--as-of-date", required=True, help="Evaluation as-of date YYYY-MM-DD.")
    outcome_parser.add_argument(
        "--output-root",
        default="output/governance",
        help="Root directory for outcome artifacts.",
    )
    outcome_parser.add_argument(
        "--limit",
        default=100,
        type=int,
        help="Maximum number of signals to evaluate.",
    )
    outcome_parser.add_argument(
        "--flat-cost-bps",
        default=0.0,
        type=float,
        help="Flat round-trip cost in basis points.",
    )

    regime_parser = subparsers.add_parser("market-regime-run", help="Run market regime context snapshot.")
    regime_parser.add_argument("--as-of-date", required=True, help="Snapshot as-of date YYYY-MM-DD.")
    regime_parser.add_argument(
        "--lookback-days",
        default=90,
        type=int,
        help="Lookback window in days for proxy history.",
    )
    regime_parser.add_argument(
        "--output-root",
        default="output/governance",
        help="Root directory for regime artifacts.",
    )

    fq_parser = subparsers.add_parser("fundamental-quality-run", help="Run fundamental quality scoring.")
    fq_parser.add_argument("--input", required=True, help="Path to a JSON fundamentals input file.")
    fq_parser.add_argument("--as-of-date", default=None, help="Override as-of date YYYY-MM-DD.")
    fq_parser.add_argument(
        "--output-root",
        default="output/governance",
        help="Root directory for fundamental quality artifacts.",
    )

    candidate_parser = subparsers.add_parser("candidate-pool-run", help="Run candidate pool discovery.")
    candidate_parser.add_argument("--input", required=True, help="Path to a JSON universe input file.")
    candidate_parser.add_argument("--as-of-date", default=None, help="Override as-of date YYYY-MM-DD.")
    candidate_parser.add_argument(
        "--output-root",
        default="output/governance",
        help="Root directory for candidate pool artifacts.",
    )
    candidate_parser.add_argument(
        "--max-candidates",
        default=20,
        type=int,
        help="Maximum candidates to keep.",
    )

    memory_parser = subparsers.add_parser("memory-pack-run", help="Run research memory pack for tickers.")
    memory_parser.add_argument("--tickers", default=None, help="Comma-separated ticker list.")
    memory_parser.add_argument("--input", default=None, help="Path to a JSON input file.")
    memory_parser.add_argument("--as-of-date", default=None, help="As-of date YYYY-MM-DD.")
    memory_parser.add_argument(
        "--lookback-days",
        default=180,
        type=int,
        help="Lookback window in days.",
    )
    memory_parser.add_argument(
        "--output-root",
        default="output/governance",
        help="Root directory for memory pack artifacts.",
    )
    memory_parser.add_argument(
        "--max-items-per-ticker",
        default=5,
        type=int,
        help="Maximum items per ticker section.",
    )

    journal_parser = subparsers.add_parser("decision-journal-run", help="Run decision journal guardrails.")
    journal_parser.add_argument("--input", required=True, help="Path to a JSON decision journal input file.")
    journal_parser.add_argument("--as-of-date", default=None, help="Override as-of date YYYY-MM-DD.")
    journal_parser.add_argument(
        "--output-root",
        default="output/governance",
        help="Root directory for decision journal artifacts.",
    )

    copilot_parser = subparsers.add_parser("boss-copilot-brief-run", help="Run boss co-pilot daily brief.")
    copilot_parser.add_argument("--as-of-date", required=True, help="As-of date YYYY-MM-DD.")
    copilot_parser.add_argument("--output-root", default="output/governance", help="Root directory for boss co-pilot brief artifacts.")
    copilot_parser.add_argument("--max-priorities", default=8, type=int, help="Maximum research priorities to include.")

    console_parser = subparsers.add_parser("copilot-console-index-run", help="Run static co-pilot console index.")
    console_parser.add_argument("--as-of-date", required=True, help="As-of date YYYY-MM-DD.")
    console_parser.add_argument("--lookback-days", default=14, type=int, help="Number of calendar days to scan.")
    console_parser.add_argument("--governance-root", default="output/governance", help="Governance artifact root.")
    console_parser.add_argument("--output-root", default="output/governance", help="Output root for console index artifacts.")

    monitor_parser = subparsers.add_parser("evidence-monitor-run", help="Run evidence freshness and drift monitor.")
    monitor_parser.add_argument("--as-of-date", required=True, help="As-of date YYYY-MM-DD.")
    monitor_parser.add_argument("--lookback-days", default=14, type=int, help="Number of calendar days to inspect.")
    monitor_parser.add_argument("--freshness-days", default=3, type=int, help="Freshness threshold in calendar days.")
    monitor_parser.add_argument("--governance-root", default="output/governance", help="Governance artifact root.")
    monitor_parser.add_argument("--output-root", default="output/governance", help="Output root for evidence monitor artifacts.")

    readiness_parser = subparsers.add_parser("market-data-readiness-run", help="Run Futu market-data provider readiness check.")
    readiness_parser.add_argument("--as-of-date", required=True, help="As-of date YYYY-MM-DD.")
    readiness_parser.add_argument("--symbols", default="US.AAPL,HK.00700", help="Comma-separated symbols.")
    readiness_parser.add_argument("--history-days", default=30, type=int, help="History lookback in days.")
    readiness_parser.add_argument("--option-symbol", default="US.AAPL", help="Option chain symbol; empty string to skip.")
    readiness_parser.add_argument("--host", default="127.0.0.1", help="OpenD host.")
    readiness_parser.add_argument("--port", default=11111, type=int, help="OpenD port.")
    readiness_parser.add_argument("--live", action="store_true", help="Enable live OpenD quote calls.")
    readiness_parser.add_argument("--output-root", default="output/governance", help="Output root for readiness artifacts.")

    refresh_parser = subparsers.add_parser("evidence-refresh-plan-run", help="Run controlled evidence refresh planner.")
    refresh_parser.add_argument("--as-of-date", required=True, help="As-of date YYYY-MM-DD.")
    refresh_parser.add_argument("--lookback-days", default=14, type=int, help="Number of calendar days to inspect.")
    refresh_parser.add_argument("--max-items", default=12, type=int, help="Maximum plan items.")
    refresh_parser.add_argument("--governance-root", default="output/governance", help="Governance artifact root.")
    refresh_parser.add_argument("--output-root", default="output/governance", help="Output root for refresh plan artifacts.")

    ctx_parser = subparsers.add_parser("research-context-pack-run", help="Run read-only research context pack assembly.")
    ctx_parser.add_argument("--as-of-date", required=True, help="As-of date YYYY-MM-DD.")
    ctx_parser.add_argument("--tickers", required=True, help="Comma-separated ticker symbols.")
    ctx_parser.add_argument("--lookback-days", default=180, type=int, help="Number of calendar days to look back.")
    ctx_parser.add_argument("--max-items-per-ticker", default=8, type=int, help="Max source refs per ticker.")
    ctx_parser.add_argument("--governance-root", default="output/governance", help="Governance artifact root.")
    ctx_parser.add_argument("--output-root", default="output/governance", help="Output root for context pack artifacts.")

    prompt_parser = subparsers.add_parser("research-context-prompt-pack-run", help="Run P48 research context prompt-pack dry-run.")
    prompt_parser.add_argument("--as-of-date", required=True, help="As-of date YYYY-MM-DD.")
    prompt_parser.add_argument("--tickers", required=True, help="Comma-separated ticker symbols.")
    prompt_parser.add_argument("--roles", default="", help="Comma-separated role names (default: all supported).")
    prompt_parser.add_argument("--max-block-chars", type=int, default=1200, help="Max chars per role context block.")
    prompt_parser.add_argument("--governance-root", default="output/governance", help="Governance artifact root.")
    prompt_parser.add_argument("--output-root", default="output/governance", help="Output root for prompt pack artifacts.")

    preview_parser = subparsers.add_parser("boss-preview-run", help="Run one-command boss preview from tickers.")
    preview_parser.add_argument("--tickers", required=True, help="Comma-separated ticker symbols.")
    preview_parser.add_argument("--as-of-date", default=None, help="Preview date YYYY-MM-DD; default today.")
    preview_parser.add_argument("--output-root", default="output/governance", help="Governance output root.")
    preview_parser.add_argument("--governance-root", default="output/governance", help="Governance artifact root.")
    preview_parser.add_argument("--live", dest="live", action="store_true", default=True, help="Enable live Futu readiness by default.")
    preview_parser.add_argument("--no-live", dest="live", action="store_false", help="Disable live Futu calls.")
    preview_parser.add_argument("--max-candidates", default=8, type=int, help="Maximum preview candidates.")

    pdf_brief_parser = subparsers.add_parser("boss-pdf-brief-run", help="Render a boss-facing PDF brief from a P49 preview directory.")
    pdf_brief_parser.add_argument("--preview-dir", required=True)
    pdf_brief_parser.add_argument("--ticker", required=True)
    pdf_brief_parser.add_argument("--output-dir", default=None)
    pdf_brief_parser.add_argument("--title", default=None)
    pdf_brief_parser.add_argument("--max-pages", type=int, default=3)
    pdf_brief_parser.add_argument("--no-pdf", action="store_true")

    boss_console_parser = subparsers.add_parser("boss-console-run", help="Render the local boss web console from governance artifacts.")
    boss_console_parser.add_argument("--governance-root", default="output/governance")
    boss_console_parser.add_argument("--output-dir", default="output/console")
    boss_console_parser.add_argument("--as-of-date", default=None)
    boss_console_parser.add_argument("--tickers", default=None)

    visual_parser = subparsers.add_parser("market-visual-run", help="Render read-only Futu market visualization assets.")
    visual_parser.add_argument("--tickers", required=True)
    visual_parser.add_argument("--as-of-date", required=True)
    visual_parser.add_argument("--output-root", default="output/governance")
    visual_parser.add_argument("--history-days", type=int, default=120)
    visual_parser.add_argument("--heatmap-metric", default="return_20d", choices=["return_1d", "return_5d", "return_20d"])
    visual_parser.add_argument("--live", dest="live", action="store_true", default=True)
    visual_parser.add_argument("--no-live", dest="live", action="store_false")
    visual_parser.add_argument("--host", default="127.0.0.1")
    visual_parser.add_argument("--port", type=int, default=11111)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = _load_paths(args.app_root)

    if args.command == "init":
        return _cmd_init(paths)
    if args.command == "status":
        return _cmd_status(paths)
    if args.command == "ingest":
        return _cmd_ingest(paths, args.input)
    if args.command == "viewer":
        return _cmd_viewer(paths, args.host, args.port)
    if args.command == "export-pdf":
        return _cmd_export_pdf(paths, args.batch_id)
    if args.command == "quote":
        return _cmd_quote(args.symbols)
    if args.command == "option-chain":
        return _cmd_option_chain(args.symbol, args.start, args.end)
    if args.command == "governance-run":
        return _cmd_governance_run(
            paths,
            config_path=args.config,
            run_date=args.run_date,
            output_root=args.output_root,
            freshness_policy_days=args.freshness_policy_days,
        )
    if args.command == "outcome-run":
        return _cmd_outcome_run(
            paths,
            as_of_date=args.as_of_date,
            output_root=args.output_root,
            limit=args.limit,
            flat_cost_bps=args.flat_cost_bps,
        )
    if args.command == "market-regime-run":
        return _cmd_market_regime_run(
            paths,
            as_of_date=args.as_of_date,
            lookback_days=args.lookback_days,
            output_root=args.output_root,
        )
    if args.command == "fundamental-quality-run":
        return _cmd_fundamental_quality_run(
            paths,
            input_path=args.input,
            as_of_date=args.as_of_date,
            output_root=args.output_root,
        )
    if args.command == "candidate-pool-run":
        return _cmd_candidate_pool_run(
            paths,
            input_path=args.input,
            as_of_date=args.as_of_date,
            output_root=args.output_root,
            max_candidates=args.max_candidates,
        )
    if args.command == "memory-pack-run":
        return _cmd_memory_pack_run(
            paths,
            tickers=args.tickers,
            input_path=args.input,
            as_of_date=args.as_of_date,
            lookback_days=args.lookback_days,
            output_root=args.output_root,
            max_items_per_ticker=args.max_items_per_ticker,
        )
    if args.command == "decision-journal-run":
        return _cmd_decision_journal_run(
            paths,
            input_path=args.input,
            as_of_date=args.as_of_date,
            output_root=args.output_root,
        )
    if args.command == "boss-copilot-brief-run":
        return _cmd_boss_copilot_brief_run(
            paths,
            as_of_date=args.as_of_date,
            output_root=args.output_root,
            max_priorities=args.max_priorities,
        )
    if args.command == "copilot-console-index-run":
        return _cmd_copilot_console_index_run(
            paths,
            as_of_date=args.as_of_date,
            lookback_days=args.lookback_days,
            governance_root=args.governance_root,
            output_root=args.output_root,
        )
    if args.command == "evidence-monitor-run":
        return _cmd_evidence_monitor_run(
            paths,
            as_of_date=args.as_of_date,
            lookback_days=args.lookback_days,
            freshness_days=args.freshness_days,
            governance_root=args.governance_root,
            output_root=args.output_root,
        )
    if args.command == "market-data-readiness-run":
        return _cmd_market_data_readiness_run(
            paths,
            as_of_date=args.as_of_date,
            symbols=args.symbols,
            history_days=args.history_days,
            option_symbol=args.option_symbol,
            host=args.host,
            port=args.port,
            live=args.live,
            output_root=args.output_root,
        )
    if args.command == "evidence-refresh-plan-run":
        return _cmd_evidence_refresh_plan_run(
            paths,
            as_of_date=args.as_of_date,
            lookback_days=args.lookback_days,
            max_items=args.max_items,
            governance_root=args.governance_root,
            output_root=args.output_root,
        )
    if args.command == "research-context-pack-run":
        return _cmd_research_context_pack_run(
            paths,
            as_of_date=args.as_of_date,
            tickers=args.tickers,
            lookback_days=args.lookback_days,
            max_items_per_ticker=args.max_items_per_ticker,
            governance_root=args.governance_root,
            output_root=args.output_root,
        )
    if args.command == "research-context-prompt-pack-run":
        return _cmd_research_context_prompt_pack_run(
            paths,
            as_of_date=args.as_of_date,
            tickers=args.tickers,
            roles=args.roles,
            max_block_chars=args.max_block_chars,
            governance_root=args.governance_root,
            output_root=args.output_root,
        )
    if args.command == "boss-preview-run":
        return _cmd_boss_preview_run(
            paths,
            tickers=args.tickers,
            as_of_date=args.as_of_date,
            output_root=args.output_root,
            governance_root=args.governance_root,
            live=args.live,
            max_candidates=args.max_candidates,
        )
    if args.command == "boss-pdf-brief-run":
        return _cmd_boss_pdf_brief_run(
            paths,
            preview_dir=args.preview_dir,
            ticker=args.ticker,
            output_dir=args.output_dir,
            title=args.title,
            max_pages=args.max_pages,
            no_pdf=args.no_pdf,
        )
    if args.command == "boss-console-run":
        return _cmd_boss_console_run(paths, args.governance_root, args.output_dir, args.as_of_date, args.tickers)
    if args.command == "market-visual-run":
        return _cmd_market_visual_run(
            paths,
            tickers=args.tickers,
            as_of_date=args.as_of_date,
            output_root=args.output_root,
            history_days=args.history_days,
            heatmap_metric=args.heatmap_metric,
            live=args.live,
            host=args.host,
            port=args.port,
        )

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
