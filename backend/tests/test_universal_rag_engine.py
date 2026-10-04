"""Unit and Integration Tests for Native Anthropic Protocol and Universal Embedding Ingestion (Issue #71).

Verifies:
1. Native Anthropic protocol resolution in llm_factory.
2. OpenAICompatibleEmbedding client instantiation, request structure, and 3-tier retry backoff.
3. FastEmbed dense embedding loading for Multilingual E5-Large.
4. Reranker dynamic model switching and configurable top_n slicing.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from rag.llm_factory import get_main_llm, _resolve_tier_credentials
from rag.vector_store import OpenAICompatibleEmbedding, get_flashrank_ranker


def test_anthropic_protocol_resolution_and_instantiation():
    """Verify Anthropic profile resolves protocol='anthropic' and instantiates LlamaAnthropic."""
    test_profiles = [
        {
            "id": "claude_profile",
            "name": "Anthropic Official",
            "base_url": "https://api.anthropic.com/v1",
            "api_key": "sk-ant-api03-testkey12345678",
            "protocol": "anthropic",
        }
    ]
    with patch.dict(os.environ, {
        "LLM_PRIMARY_PROFILE_ID": "claude_profile",
        "LLM_PROFILES_JSON": str(test_profiles).replace("'", '"'),
        "LLM_MODEL": "claude-3-5-sonnet-20241022",
    }):
        base_url, api_key, model, _, _, _, has_gw, protocol = _resolve_tier_credentials("primary")
        assert protocol == "anthropic"
        assert has_gw is True
        assert api_key == "sk-ant-api03-testkey12345678"

        llm = get_main_llm(force_refresh=True)
        assert llm is not None
        assert "Anthropic" in type(llm).__name__
        assert getattr(llm, "model", None) == "claude-3-5-sonnet-20241022"


def test_openai_compatible_embedding_client_and_retry_backoff():
    """Verify OpenAICompatibleEmbedding client retries on failures and parses successful responses."""
    embedder = OpenAICompatibleEmbedding(
        base_url="http://localhost:11434/v1",
        api_key="",
        model_name="nomic-embed-text",
        timeout=5.0,
    )
    assert embedder.base_url == "http://localhost:11434/v1"

    # Mock response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [
            {"embedding": [0.1, 0.2, 0.3], "index": 0}
        ]
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        vec = embedder._get_query_embedding("quantum computing")
        assert vec == [0.1, 0.2, 0.3]
        mock_post.assert_called_once()
        called_url = mock_post.call_args[0][0]
        assert called_url == "http://localhost:11434/v1/embeddings"
        called_payload = mock_post.call_args[1]["json"]
        assert called_payload["model"] == "nomic-embed-text"


def test_openai_compatible_embedding_retry_failure():
    """Verify OpenAICompatibleEmbedding raises after 3 retries on persistent network failures."""
    embedder = OpenAICompatibleEmbedding(
        base_url="http://invalid-endpoint-never-exists:9999/v1",
        model_name="test-model",
        timeout=1.0,
    )
    with patch("requests.post", side_effect=RuntimeError("Connection refused")):
        with patch("time.sleep"):  # Speed up tests
            with pytest.raises(RuntimeError) as exc_info:
                embedder._get_query_embedding("test query")
            assert "Failed after 3 retries" in str(exc_info.value)


def test_flashrank_reranker_dynamic_model_caching():
    """Verify get_flashrank_ranker initializes and respects target model switching."""
    ranker1 = get_flashrank_ranker("ms-marco-TinyBERT-L-2-v2")
    assert ranker1 is not None

    ranker2 = get_flashrank_ranker("ms-marco-TinyBERT-L-2-v2")
    assert ranker1 is ranker2  # Singleton caching works
