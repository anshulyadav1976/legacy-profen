"""Shared LLM response helpers."""

from __future__ import annotations

import json
from typing import Any, Callable

from .openrouter_client import OpenRouterConfig, OpenRouterRequestError


def extract_content(response: dict[str, Any] | None) -> str | None:
    if not response or not isinstance(response, dict):
        return None
    choices = response.get("choices")
    if not choices:
        return None
    first = choices[0] if isinstance(choices, list) else None
    if not isinstance(first, dict):
        return None
    message = first.get("message", {})
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    return content if isinstance(content, str) else None


def parse_json_content(content: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return json.loads(content), None
    except json.JSONDecodeError as exc:
        candidate = _extract_json_candidate(content)
        if candidate:
            try:
                return json.loads(candidate), None
            except json.JSONDecodeError as exc2:
                return None, f"Failed to parse JSON: {exc2}"
        return None, f"Failed to parse JSON: {exc}"


def repair_json_content(
    content: str,
    config: OpenRouterConfig,
    chat_fn: Callable[..., dict[str, Any]],
) -> str | None:
    repair_prompt = (
        "Fix the following output so it is valid JSON ONLY. "
        "Do not include markdown or explanations. Preserve all fields.\n\n"
        + content
    )
    try:
        response = chat_fn(
            config,
            messages=[
                {"role": "system", "content": "You are a JSON repair tool."},
                {"role": "user", "content": repair_prompt},
            ],
            response_format=None,
        )
    except OpenRouterRequestError:
        return None
    return extract_content(response)


def _extract_json_candidate(content: str) -> str | None:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return content[start : end + 1]