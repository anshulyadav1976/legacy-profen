"""OpenRouter client utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class OpenRouterConfig:
    api_key: str
    model: str
    base_url: str = "https://openrouter.ai/api/v1"
    app_url: str | None = None
    app_title: str | None = None
    timeout_seconds: float = 60.0


class OpenRouterRequestError(RuntimeError):
    def __init__(self, status_code: int, payload: Any) -> None:
        super().__init__(f"OpenRouter request failed ({status_code})")
        self.status_code = status_code
        self.payload = payload


def chat_completions(
    config: OpenRouterConfig,
    messages: list[dict[str, Any]],
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{config.base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    if config.app_url:
        headers["HTTP-Referer"] = config.app_url
    if config.app_title:
        headers["X-Title"] = config.app_title

    payload: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
    }
    if response_format:
        payload["response_format"] = response_format

    response = httpx.post(
        url, headers=headers, json=payload, timeout=config.timeout_seconds
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            payload = response.json()
        except Exception:
            payload = response.text
        raise OpenRouterRequestError(response.status_code, payload) from exc
    return response.json()
