"""LLM client adapters for MiniMax, OpenAI, and Anthropic."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class LLMResponse:
    """Response from an LLM API call."""
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_estimate: float
    raw_response: dict


def get_timeout_for_model(model: str) -> int:
    """Get timeout in seconds for model.

    Args:
        model: The model name to get timeout for.

    Returns:
        Timeout in seconds: minimax=60, gpt=90, claude=120.
    """
    model_lower = model.lower()
    if "minimax" in model_lower:
        return 60
    elif "gpt" in model_lower or "openai" in model_lower:
        return 90
    elif "claude" in model_lower or "anthropic" in model_lower:
        return 120
    else:
        return 60  # default


class BaseLLMClient(ABC):
    """Base class for LLM clients."""

    @classmethod
    @abstractmethod
    def provider_name(cls) -> str:
        """Return the provider name."""
        pass

    @abstractmethod
    def generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            LLMResponse with content and metadata.
        """
        pass


class MiniMaxClient(BaseLLMClient):
    """MiniMax LLM client."""

    def __init__(
        self,
        api_key: str = None,
        model: str = "MiniMax-2.7",
        timeout: int = 60
    ):
        """Initialize MiniMax client.

        Args:
            api_key: MiniMax API key.
            model: Model name to use.
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @classmethod
    def provider_name(cls) -> str:
        return "minimax"

    def format_messages(self, messages: list[dict]) -> list[dict]:
        """Format messages for MiniMax API.

        Args:
            messages: List of message dicts.

        Returns:
            Formatted messages list.
        """
        return messages

    def generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> LLMResponse:
        """Generate a response from MiniMax API.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            LLMResponse with content and metadata.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": self.format_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        response = requests.post(
            "https://api.minimax.chat/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=self.model,
            input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
            output_tokens=data.get("usage", {}).get("completion_tokens", 0),
            cost_estimate=0.0,
            raw_response=data
        )


class OpenAIClient(BaseLLMClient):
    """OpenAI LLM client."""

    def __init__(
        self,
        api_key: str = None,
        model: str = "gpt-5.4",
        timeout: int = 90
    ):
        """Initialize OpenAI client.

        Args:
            api_key: OpenAI API key.
            model: Model name to use.
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @classmethod
    def provider_name(cls) -> str:
        return "openai"

    def format_messages(self, messages: list[dict]) -> list[dict]:
        """Format messages for OpenAI API.

        Args:
            messages: List of message dicts.

        Returns:
            Formatted messages list.
        """
        return messages

    def generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> LLMResponse:
        """Generate a response from OpenAI API.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            LLMResponse with content and metadata.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": self.format_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=self.model,
            input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
            output_tokens=data.get("usage", {}).get("completion_tokens", 0),
            cost_estimate=0.0,
            raw_response=data
        )


class AnthropicClient(BaseLLMClient):
    """Anthropic LLM client."""

    def __init__(
        self,
        api_key: str = None,
        model: str = "claude-opus-4-6",
        timeout: int = 120
    ):
        """Initialize Anthropic client.

        Args:
            api_key: Anthropic API key.
            model: Model name to use.
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @classmethod
    def provider_name(cls) -> str:
        return "anthropic"

    def format_messages(self, messages: list[dict]) -> list[dict]:
        """Format messages for Anthropic API.

        Anthropic uses a different message format with system, user, and assistant roles.

        Args:
            messages: List of message dicts.

        Returns:
            Formatted messages list for Anthropic.
        """
        formatted = []
        for msg in messages:
            if msg.get("role") == "system":
                formatted.append({"role": "user", "content": f"<system>{msg['content']}</system>"})
            else:
                formatted.append(msg)
        return formatted

    def generate(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> LLMResponse:
        """Generate a response from Anthropic API.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            LLMResponse with content and metadata.
        """
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

        # Anthropic uses a different API format
        formatted_messages = self.format_messages(messages)

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data["content"][0]["text"],
            model=self.model,
            input_tokens=data.get("usage", {}).get("input_tokens", 0),
            output_tokens=data.get("usage", {}).get("output_tokens", 0),
            cost_estimate=0.0,
            raw_response=data
        )


def get_llm_client(
    provider: str,
    model: str = None,
    api_key: str = None
) -> BaseLLMClient:
    """Factory to get appropriate LLM client based on provider string.

    Args:
        provider: Provider name ('minimax', 'openai', 'anthropic', or 'gpt', 'claude').
        model: Optional model name override.
        api_key: Optional API key.

    Returns:
        An instance of the appropriate LLM client.

    Raises:
        ValueError: If provider is not recognized.
    """
    provider_lower = provider.lower()

    if provider_lower in ("minimax",):
        return MiniMaxClient(api_key=api_key, model=model or "MiniMax-2.7")
    elif provider_lower in ("openai", "gpt"):
        return OpenAIClient(api_key=api_key, model=model or "gpt-5.4")
    elif provider_lower in ("anthropic", "claude"):
        return AnthropicClient(api_key=api_key, model=model or "claude-opus-4-6")
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")