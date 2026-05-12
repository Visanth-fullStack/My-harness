"""Semantic intent classification via local Ollama model.

Sends a short prompt to the local Qwen model to classify the user's
intent into a known task type. Falls back to keyword matching when
Ollama is unavailable.
"""

from __future__ import annotations

import json
import logging

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3-coder:30b-a3b-q8_0"
TIMEOUT = 5.0

KNOWN_TYPES = frozenset({
    "review", "security", "search", "docs",
    "tests", "frontend", "general",
})

_PROMPT = (
    "Classify the following user message into exactly one category.\n"
    "Categories: review, security, search, docs, tests, frontend, general\n"
    "Respond with JSON only: {\"type\": \"<category>\"}\n"
    "No explanation. No markdown.\n\n"
    "Message: {message}"
)


def _parse_response(text: str) -> str:
    """Extract type from model JSON response."""
    try:
        data = json.loads(text.strip())
        t = data.get("type", "general").lower().strip()
        return t if t in KNOWN_TYPES else "general"
    except (json.JSONDecodeError, AttributeError):
        return "general"


async def classify_intent(message: str) -> str:
    """Classify intent via local Ollama model.

    Falls back to keyword matching if Ollama is down.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{
                        "role": "user",
                        "content": _PROMPT.format(message=message),
                    }],
                    "stream": False,
                    "options": {"temperature": 0.0},
                },
                timeout=TIMEOUT,
            )
        text = resp.json().get("message", {}).get("content", "")
        return _parse_response(text)
    except Exception:
        logger.debug("Ollama unavailable, using keyword fallback")
        from maggy.services.chat_router import estimate_type
        return estimate_type(message)
