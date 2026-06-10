"""Tests for the centralized LLM helper: truncation guard + safe text extraction."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from geo_agent.llm import TruncatedResponseError, complete, extract_text


def _block(btype: str, text: str = "") -> MagicMock:
    b = MagicMock()
    b.type = btype
    b.text = text
    return b


def _message(blocks, stop_reason="end_turn") -> MagicMock:
    m = MagicMock()
    m.content = blocks
    m.stop_reason = stop_reason
    return m


def _client_returning(message) -> MagicMock:
    client = MagicMock()
    client.messages.stream.return_value.__enter__.return_value.get_final_message.return_value = message
    return client


def test_extract_text_skips_thinking_blocks():
    msg = _message([_block("thinking", "internal"), _block("text", "hello "), _block("text", "world")])
    assert extract_text(msg) == "hello world"


def test_complete_raises_on_truncation():
    client = _client_returning(_message([_block("text", "partial")], stop_reason="max_tokens"))
    with pytest.raises(TruncatedResponseError):
        complete(client, model="m", user="u", max_tokens=10, label="t")


def test_complete_returns_text_when_complete():
    client = _client_returning(_message([_block("text", "  done  ")], stop_reason="end_turn"))
    assert complete(client, model="m", user="u", max_tokens=10) == "done"


def test_complete_passes_system_and_model():
    client = _client_returning(_message([_block("text", "ok")]))
    complete(client, model="claude-opus-4-8", system="sys", user="hi", max_tokens=99)
    kwargs = client.messages.stream.call_args.kwargs
    assert kwargs["model"] == "claude-opus-4-8"
    assert kwargs["system"] == "sys"
    assert kwargs["max_tokens"] == 99
    assert "output_config" not in kwargs  # not set unless a schema is given


def test_complete_sends_output_schema_when_given():
    client = _client_returning(_message([_block("text", '{"recommendations": []}')]))
    schema = {"type": "object", "properties": {}, "additionalProperties": False}
    complete(client, model="m", user="u", max_tokens=10, output_schema=schema)
    kwargs = client.messages.stream.call_args.kwargs
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    assert kwargs["output_config"]["format"]["schema"] is schema
