#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_PATH="$HOME/Library/LaunchAgents/com.hermes.agent.plist"
LOG_DIR="$HOME/Library/Logs/Hermes"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$LOG_DIR"
ROOT_DIR="$ROOT_DIR" PLIST_PATH="$PLIST_PATH" LOG_DIR="$LOG_DIR" python3 - <<'PY'
import os
from pathlib import Path

from agent.research_v1.macos_service import LaunchAgentConfig, build_launch_agent_plist

root_dir = os.environ["ROOT_DIR"]
plist_path = Path(os.environ["PLIST_PATH"])
log_dir = Path(os.environ["LOG_DIR"])
plist = build_launch_agent_plist(
    LaunchAgentConfig(
        label="com.hermes.agent",
        program_arguments=["/usr/bin/python3", "-m", "agent.research_v1.cli"],
        working_directory=root_dir,
        standard_out_path=str(log_dir / "hermes.out"),
        standard_error_path=str(log_dir / "hermes.err"),
        run_at_load=True,
        keep_alive=True,
        start_interval=300,
    )
)
plist_path.write_text(plist, encoding="utf-8")
PY
launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl load "$PLIST_PATH"

echo "Hermes launch agent installed at $PLIST_PATH"
