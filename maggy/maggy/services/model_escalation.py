"""Ollama → Claude API automatic model escalation."""

from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
from typing import AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3-coder:30b-a3b-q8_0"
VISION_MODEL = "qwen3-vl:32b"
TIMEOUT = 10.0


async def _ollama_request(prompt: str) -> str | None:
    """Send prompt to Ollama. Returns text or None."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 20},
                },
                timeout=TIMEOUT,
            )
        return resp.json().get("message", {}).get("content", "")
    except Exception as e:
        logger.debug("Ollama request failed: %s", e)
        return None


async def _claude_request(prompt: str) -> str | None:
    """Send prompt to Claude API as fallback."""
    from maggy.services.ai_client import _api_complete
    import os
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    return await _api_complete(prompt, key, "claude-sonnet-4")


async def ollama_with_escalation(prompt: str) -> str | None:
    """Try Ollama, escalate to Claude API on failure."""
    result = await _ollama_request(prompt)
    if result is not None:
        return result
    logger.info("Ollama unavailable, escalating to Claude API")
    return await _claude_request(prompt)


async def _qwen_vision(
    path: str, prompt: str,
) -> list[dict] | None:
    """Try Qwen3-VL for image analysis."""
    from maggy.services.vision import analyze_image
    try:
        chunks = await asyncio.to_thread(
            lambda: list(analyze_image(path, prompt)),
        )
        if any(c.get("type") == "error" for c in chunks):
            return None
        return chunks
    except Exception as e:
        logger.debug("Qwen vision failed: %s", e)
        return None


async def _claude_vision(
    path: str, prompt: str,
) -> str | None:
    """Send base64 image to Claude API."""
    import os
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    try:
        import anthropic
        p = Path(path)
        b64 = base64.b64encode(p.read_bytes()).decode()
        media = f"image/{p.suffix.lstrip('.').lower()}"
        if media == "image/jpg":
            media = "image/jpeg"
        client = anthropic.AsyncAnthropic(api_key=key)
        msg = await client.messages.create(
            model="claude-sonnet-4",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": media,
                        "data": b64,
                    }},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return msg.content[0].text
    except Exception as e:
        logger.warning("Claude vision failed: %s", e)
        return None


async def vision_with_escalation(
    path: str, prompt: str,
) -> AsyncGenerator[dict, None]:
    """Try Qwen3-VL, escalate to Claude API on failure."""
    chunks = await _qwen_vision(path, prompt)
    if chunks is not None:
        for c in chunks:
            yield c
        return
    logger.info("Qwen3-VL unavailable, escalating to Claude API")
    result = await _claude_vision(path, prompt)
    if result:
        yield {"type": "text", "content": result}
        yield {"type": "done"}
        return
    yield {"type": "error", "content": "Both Ollama and Claude API unavailable for vision."}
