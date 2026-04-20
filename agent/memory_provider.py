"""Minimal memory provider base class for Hermes memory integrations."""

from abc import ABC, abstractmethod
from typing import Any


class MemoryProvider(ABC):
    """Base interface for pluggable memory providers."""

    name = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the provider is configured and ready."""

    @abstractmethod
    def initialize(self, session_id: str, **kwargs) -> None:
        """Initialize provider state for a session."""

    @abstractmethod
    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Return memory tool schemas exposed by this provider."""

    @abstractmethod
    def handle_tool_call(self, tool_name: str, args: dict[str, Any], **kwargs) -> str:
        """Handle a tool call routed through the memory manager."""

    def prefetch(self, query: str, session_id: str = "") -> str:
        """Optionally prefetch context for an upcoming turn."""
        return ""

    def sync_turn(self, user_content: str, assistant_content: str, session_id: str = "") -> None:
        """Optionally persist turn state after a conversation step."""
        return None

    def system_prompt_block(self) -> str:
        """Optionally contribute a system prompt block."""
        return ""
