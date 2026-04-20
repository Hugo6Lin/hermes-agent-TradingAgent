"""macOS launchd service helpers for Hermes."""

from dataclasses import dataclass
from xml.sax.saxutils import escape


@dataclass
class LaunchAgentConfig:
    """Configuration for a Hermes launch agent plist."""

    label: str
    program_arguments: list[str]
    working_directory: str
    standard_out_path: str
    standard_error_path: str
    run_at_load: bool = True
    keep_alive: bool = True
    start_interval: int = 300


def _plist_bool(value: bool) -> str:
    return "<true/>" if value else "<false/>"


def build_launch_agent_plist(config: LaunchAgentConfig) -> str:
    """Render a launchd plist payload for Hermes."""
    arguments = "\n".join(
        f"        <string>{escape(argument)}</string>"
        for argument in config.program_arguments
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{escape(config.label)}</string>
    <key>ProgramArguments</key>
    <array>
{arguments}
    </array>
    <key>WorkingDirectory</key>
    <string>{escape(config.working_directory)}</string>
    <key>StandardOutPath</key>
    <string>{escape(config.standard_out_path)}</string>
    <key>StandardErrorPath</key>
    <string>{escape(config.standard_error_path)}</string>
    <key>RunAtLoad</key>
    {_plist_bool(config.run_at_load)}
    <key>KeepAlive</key>
    {_plist_bool(config.keep_alive)}
    <key>StartInterval</key>
    <integer>{int(config.start_interval)}</integer>
</dict>
</plist>
"""


def build_launchctl_command(action: str, plist_path: str) -> list[str]:
    """Build a deterministic launchctl invocation."""
    if action not in {"load", "unload"}:
        raise ValueError(f"Unsupported launchctl action: {action}")
    return ["launchctl", action, plist_path]
