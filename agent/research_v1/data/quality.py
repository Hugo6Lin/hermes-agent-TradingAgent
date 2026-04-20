"""Data quality checks for provider outputs."""

from datetime import datetime, timezone


class DataQualityValidator:
    """Validate required fields and freshness for market history rows."""

    def __init__(self, max_staleness_days: int = 5):
        self.max_staleness_days = max_staleness_days

    def validate_price_points(self, rows: list[dict]) -> tuple[list[dict], list[dict]]:
        """Return cleaned rows and validation issues."""
        cleaned = []
        issues = []
        required = ("day", "date", "close")

        for index, row in enumerate(rows):
            missing_fields = [field for field in required if field not in row or row[field] is None]
            if missing_fields:
                issues.append({
                    "type": "missing_field",
                    "row_index": index,
                    "fields": missing_fields,
                })
                continue
            cleaned.append(row)
        return cleaned, issues

    def check_freshness(self, rows: list[dict]) -> tuple[bool, dict | None]:
        """Check whether latest row date is fresh enough for configured threshold."""
        if not rows:
            return False, {"type": "empty_series"}

        latest = max(rows, key=lambda item: item["date"])
        latest_date = datetime.fromisoformat(latest["date"]).replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        age_days = (now_utc - latest_date).days
        if age_days > self.max_staleness_days:
            return False, {
                "type": "stale_data",
                "latest_date": latest["date"],
                "age_days": age_days,
                "threshold_days": self.max_staleness_days,
            }
        return True, None
