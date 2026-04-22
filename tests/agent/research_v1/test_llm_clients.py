"""Tests for LLM client adapters."""

from pathlib import Path

import pytest
from agent.research_v1.llm_clients import (
    LLMResponse,
    get_timeout_for_model,
    BaseLLMClient,
    MiniMaxClient,
    OpenAIClient,
    AnthropicClient,
    get_llm_client,
    _load_local_provider_key,
)


def test_minimax_client_initialization():
    """Create MiniMaxClient with api_key="test-key" and assert default model is usable.""" 
    client = MiniMaxClient(api_key="test-key")
    assert client.model == "MiniMax-M2.7-HighSpeed"


def test_load_local_provider_key_reads_minimax_key(tmp_path, monkeypatch):
    key_file = tmp_path / "API_KEY.txt"
    key_file.write_text(
        "OpenAI:gibberish\nMinimax-m2.7-highspeed：sk-test-minimax-key\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_LOCAL_API_KEY_FILE", str(key_file))
    assert _load_local_provider_key("minimax") == "sk-test-minimax-key"


def test_minimax_client_uses_local_key_file_when_env_missing(tmp_path, monkeypatch):
    key_file = tmp_path / "API_KEY.txt"
    key_file.write_text(
        "MINIMAX_API_KEY=sk-local-default\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.setenv("HERMES_LOCAL_API_KEY_FILE", str(key_file))
    client = MiniMaxClient()
    assert client.api_key == "sk-local-default"


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
