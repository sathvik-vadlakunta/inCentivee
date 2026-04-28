"""Tests for embeddings.py — batching, missing key error, no global state."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestEmbedTexts:
    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
        from geo_agent.embeddings import embed_texts
        with pytest.raises(ValueError, match="VOYAGE_API_KEY"):
            embed_texts(["hello"])

    @patch("geo_agent.embeddings._new_client")
    def test_single_batch(self, mock_new_client):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.embeddings = [[0.1] * 1024, [0.2] * 1024]
        mock_client.embed.return_value = mock_result
        mock_new_client.return_value = mock_client

        from geo_agent.embeddings import embed_texts
        result = embed_texts(["text1", "text2"])

        assert len(result) == 2
        mock_client.embed.assert_called_once_with(
            ["text1", "text2"], model="voyage-3.5-lite", input_type="document"
        )

    @patch("geo_agent.embeddings._new_client")
    def test_multi_batch(self, mock_new_client):
        """Texts exceeding 128 are split into multiple batches."""
        mock_client = MagicMock()

        def fake_embed(texts, **kwargs):
            result = MagicMock()
            result.embeddings = [[0.1] * 1024 for _ in texts]
            return result

        mock_client.embed.side_effect = fake_embed
        mock_new_client.return_value = mock_client

        from geo_agent.embeddings import embed_texts
        texts = [f"text_{i}" for i in range(200)]
        result = embed_texts(texts)

        assert len(result) == 200
        assert mock_client.embed.call_count == 2  # 128 + 72

    @patch("geo_agent.embeddings._new_client")
    def test_no_global_state_between_calls(self, mock_new_client):
        """Each call to embed_texts should create a fresh client (no singleton)."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.embeddings = [[0.1] * 1024]
        mock_client.embed.return_value = mock_result
        mock_new_client.return_value = mock_client

        from geo_agent.embeddings import embed_texts
        embed_texts(["first call"])
        embed_texts(["second call"])

        # _new_client should be called twice — one fresh client per call
        assert mock_new_client.call_count == 2


class TestEmbedQuery:
    @patch("geo_agent.embeddings._new_client")
    def test_single_query(self, mock_new_client):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.embeddings = [[0.5] * 1024]
        mock_client.embed.return_value = mock_result
        mock_new_client.return_value = mock_client

        from geo_agent.embeddings import embed_query
        result = embed_query("dental implants Austin")

        assert len(result) == 1024
        mock_client.embed.assert_called_once_with(
            ["dental implants Austin"], model="voyage-3.5-lite", input_type="query"
        )
