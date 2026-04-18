#!/usr/bin/env python3
"""Shared LLM helper for meep-kb.

Prefers OpenAI GPT-5.4 when `OPENAI_API_KEY` is configured, and falls back to
Anthropic only when OpenAI is unavailable.
"""

from __future__ import annotations

import os
from typing import Any, Optional

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DEFAULT_OPENAI_MODEL = os.environ.get("MEEP_KB_LLM_MODEL", "gpt-5.4")
DEFAULT_ANTHROPIC_MODEL = os.environ.get("MEEP_KB_ANTHROPIC_FALLBACK_MODEL", "claude-sonnet-4-6")
DEFAULT_REASONING_EFFORT = os.environ.get("MEEP_KB_REASONING_EFFORT", "medium")


def has_openai() -> bool:
    return bool(OPENAI_API_KEY)


def has_anthropic() -> bool:
    return bool(ANTHROPIC_API_KEY)


def llm_available() -> bool:
    return has_openai() or has_anthropic()


def preferred_provider() -> Optional[str]:
    if has_openai():
        return "openai"
    if has_anthropic():
        return "anthropic"
    return None


def preferred_model(default_openai_model: str | None = None) -> str:
    if has_openai():
        return default_openai_model or DEFAULT_OPENAI_MODEL
    return DEFAULT_ANTHROPIC_MODEL


def _extract_openai_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text.strip()

    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip()


def _extract_anthropic_text(message: Any) -> str:
    chunks: list[str] = []
    for block in getattr(message, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            chunks.append(text)
    return "\n".join(chunks).strip()


def generate_text(
    user_prompt: str,
    *,
    system_prompt: str | None = None,
    preferred_openai_model: str | None = None,
    anthropic_fallback_model: str | None = None,
    max_tokens: int = 2000,
) -> dict[str, Any]:
    """Return unified text output from the preferred LLM provider."""
    if has_openai():
        from openai import OpenAI

        model = preferred_openai_model or DEFAULT_OPENAI_MODEL
        client = OpenAI(api_key=OPENAI_API_KEY)
        input_items = []
        if system_prompt:
            input_items.append({
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            })
        input_items.append({
            "role": "user",
            "content": [{"type": "input_text", "text": user_prompt}],
        })

        kwargs: dict[str, Any] = {
            "model": model,
            "input": input_items,
            "max_output_tokens": max_tokens,
        }
        if model.startswith("gpt-5"):
            kwargs["reasoning"] = {"effort": DEFAULT_REASONING_EFFORT}

        response = client.responses.create(**kwargs)
        text = _extract_openai_text(response)
        return {
            "provider": "openai",
            "model": model,
            "text": text,
            "raw": response,
        }

    if has_anthropic():
        import anthropic

        model = anthropic_fallback_model or DEFAULT_ANTHROPIC_MODEL
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        message = client.messages.create(**kwargs)
        text = _extract_anthropic_text(message)
        return {
            "provider": "anthropic",
            "model": model,
            "text": text,
            "raw": message,
        }

    raise RuntimeError("No LLM credentials configured. Set OPENAI_API_KEY (preferred) or ANTHROPIC_API_KEY.")
