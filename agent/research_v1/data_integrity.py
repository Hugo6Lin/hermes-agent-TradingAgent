"""P22-A+ data integrity preflight checks."""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class DataIntegrityReport:
    sample_size: int
    lookahead_violation_count: int
    lookahead_violation_rate: float
    source_audit_gap_count: int
    source_audit_gap_rate: float
    restatement_risk_count: int
    sector_snapshot_missing_count: int
    excluded_snapshot_ids: list[str]
    diagnostic_flags: list[str]
    clean_rows: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


def _date(value: str | None) -> str | None:
    if not value:
        return None
    return str(value)[:10]


def _has_lookahead(row: dict) -> bool:
    source_as_of = _date(row.get("source_as_of_date"))
    data_as_of = _date(row.get("data_as_of_date"))
    trading_day = _date(row.get("trading_day"))
    source_fetched = str(row.get("source_fetched_at") or "")
    snapshot_time = str(row.get("as_of_timestamp") or "")
    if source_as_of and data_as_of and source_as_of > data_as_of:
        return True
    if data_as_of and trading_day and data_as_of > trading_day:
        return True
    if source_fetched and snapshot_time and source_fetched > snapshot_time:
        return True
    return False


def _has_source_audit_gap(row: dict) -> bool:
    return not (
        row.get("source_refs")
        and row.get("source_as_of_date")
        and row.get("source_fetched_at")
        and row.get("provider")
    )


def _has_sector_snapshot_gap(row: dict) -> bool:
    return not (row.get("sector_id") and row.get("classification_as_of_date"))


def _has_restatement_risk(row: dict) -> bool:
    return bool(row.get("restatement_flag") or row.get("possible_restatement_risk"))


def run_data_integrity_preflight(rows: list[dict]) -> DataIntegrityReport:
    sample_size = len(rows)
    excluded = []
    clean_rows = []
    source_gaps = 0
    sector_gaps = 0
    restatement_risks = 0

    for row in rows:
        snapshot_id = str(row.get("snapshot_id", ""))
        lookahead = _has_lookahead(row)
        if _has_source_audit_gap(row):
            source_gaps += 1
        if _has_sector_snapshot_gap(row):
            sector_gaps += 1
        if _has_restatement_risk(row):
            restatement_risks += 1
        if lookahead:
            excluded.append(snapshot_id)
        else:
            clean_rows.append(row)

    flags = []
    if excluded:
        flags.append("lookahead_violation")
    if source_gaps:
        flags.append("source_audit_gap")
    if sector_gaps:
        flags.append("sector_snapshot_missing")
    if restatement_risks:
        flags.append("restatement_risk")

    return DataIntegrityReport(
        sample_size=sample_size,
        lookahead_violation_count=len(excluded),
        lookahead_violation_rate=0.0 if sample_size == 0 else len(excluded) / sample_size,
        source_audit_gap_count=source_gaps,
        source_audit_gap_rate=0.0 if sample_size == 0 else source_gaps / sample_size,
        restatement_risk_count=restatement_risks,
        sector_snapshot_missing_count=sector_gaps,
        excluded_snapshot_ids=excluded,
        diagnostic_flags=flags,
        clean_rows=clean_rows,
    )