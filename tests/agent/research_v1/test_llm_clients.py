"""Tests for LLM client adapters."""

import pytest
from agent.research_v1.llm_clients import (
    LLMResponse,
    get_timeout_for_model,
    BaseLLMClient,
    MiniMaxClient,
    OpenAIClient,
    AnthropicClient,
    get_llm_client,
)


def test_minimax_client_initialization():
    """Create MiniMaxClient with api_key="test-key" and assert model == "MiniMax-2.7"."""
    client = MiniMaxClient(api_key="test-key")
    assert client.model == "MiniMax-2.7"


def test_minimax_client_format_messages():
    """Create MiniMaxClient, format messages, verify returns list."""
    client = MiniMaxClient(api_key="test-key")
    messages = [{"role": "user", "content": "Hello"}]
    formatted = client.format_messages(messages)
    assert isinstance(formatted, list)


def test_openai_client_initialization():
    """Create OpenAIClient with model="gpt-5.4" and assert model == "gpt-5.4"."""
    client = OpenAIClient(model="gpt-5.4")
    assert client.model == "gpt-5.4"


def test_anthropic_client_initialization():
    """Create AnthropicClient with model="claude-opus-4-6" and assert model == "claude-opus-4-6"."""
    client = AnthropicClient(model="claude-opus-4-6")
    assert client.model == "claude-opus-4-6"


def test_model_timeout_mapping():
    """Assert get_timeout_for_model returns correct values."""
    assert get_timeout_for_model("minimax") == 60
    assert get_timeout_for_model("MiniMax-2.7") == 60
    assert get_timeout_for_model("gpt") == 90
    assert get_timeout_for_model("gpt-5.4") == 90
    assert get_timeout_for_model("claude") == 120
    assert get_timeout_for_model("claude-opus-4-6") == 120