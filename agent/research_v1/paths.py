"""Local filesystem paths for Hermes research app data."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HermesPaths:
    """Canonical local paths for a Hermes app root."""

    app_root: Path
    data_dir: Path
    reports_dir: Path
    exports_dir: Path
    database_path: Path

    @classmethod
    def from_root(cls, root: str | Path) -> "HermesPaths":
        """Build the Hermes path layout from an app root."""
        app_root = Path(root).expanduser().resolve()
        data_dir = app_root / "data"
        return cls(
            app_root=app_root,
            data_dir=data_dir,
            reports_dir=app_root / "reports",
            exports_dir=app_root / "exports",
            database_path=data_dir / "research.db",
        )

    def ensure_directories(self) -> None:
        """Create the app root and standard local data directories."""
        self.app_root.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
