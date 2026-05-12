"""Tests for semantic intent classification via local model."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from maggy.services.intent_classifier import (
    KNOWN_TYPES,
    classify_intent,
    _parse_response,
)


def test_parse_valid_type():
    """Valid JSON type is returned as-is."""
    assert _parse_response('{"type": "review"}') == "review"


def test_parse_unknown_falls_back():
    """Unknown type falls back to 'general'."""
    assert _parse_response('{"type": "banana"}') == "general"


def test_parse_garbage_falls_back():
    """Non-JSON falls back to 'general'."""
    assert _parse_response("not json at all") == "general"


def test_known_types_complete():
    """KNOWN_TYPES includes the expected categories."""
    for t in ("review", "security", "search", "docs", "tests", "frontend"):
        assert t in KNOWN_TYPES


@pytest.mark.asyncio
async def test_classify_returns_model_answer():
    """When Ollama responds, use its classification."""
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "message": {"content": '{"type": "review"}'},
    }
    with patch(
        "maggy.services.intent_classifier.httpx.AsyncClient",
    ) as mock_cls:
        client = MagicMock()
        client.post = _async_return(fake_resp)
        client.__aenter__ = _async_return(client)
        client.__aexit__ = _async_return(None)
        mock_cls.return_value = client
        result = await classify_intent("review the auth code")
    assert result == "review"


@pytest.mark.asyncio
async def test_classify_fallback_on_error():
    """When Ollama is down, fall back to keyword matching."""
    import httpx

    with patch(
        "maggy.services.intent_classifier.httpx.AsyncClient",
    ) as mock_cls:
        client = MagicMock()
        client.post = _async_raise(httpx.ConnectError("down"))
        client.__aenter__ = _async_return(client)
        client.__aexit__ = _async_return(None)
        mock_cls.return_value = client
        result = await classify_intent("fix the login bug")
    assert result == "general"


@pytest.mark.asyncio
async def test_classify_timeout_fallback():
    """Timeout falls back to keyword matching."""
    import httpx

    with patch(
        "maggy.services.intent_classifier.httpx.AsyncClient",
    ) as mock_cls:
        client = MagicMock()
        client.post = _async_raise(httpx.ReadTimeout("slow"))
        client.__aenter__ = _async_return(client)
        client.__aexit__ = _async_return(None)
        mock_cls.return_value = client
        result = await classify_intent("review the PR")
    # keyword fallback: "review" is in TYPE_KEYWORDS
    assert result == "review"


# ── Helpers ──────────────────────────────────────────────────────────


def _async_return(value):
    """Create an async function that returns value."""
    async def _inner(*args, **kwargs):
        return value
    return _inner


def _async_raise(exc):
    """Create an async function that raises exc."""
    async def _inner(*args, **kwargs):
        raise exc
    return _inner
