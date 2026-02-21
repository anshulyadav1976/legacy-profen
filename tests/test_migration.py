from __future__ import annotations

from typing import Any

import pytest

from codeintel.extract import extract_symbols
from codeintel.graph import build_graph
from codeintel.mcp_graph import GraphService
from codeintel.migration import MigrationPlanRequest, generate_migration_plan
from codeintel.openrouter_client import OpenRouterConfig
from codeintel.parser import PythonParser


SAMPLE = """
class Foo:
    def method(self):
        return 1

def bar():
    foo = Foo()
    return foo.method()
"""


def _service() -> GraphService:
    parser = PythonParser()
    parsed = parser.parse_text(SAMPLE)
    symbols = extract_symbols(parsed, path="sample.py")
    graph = build_graph([symbols])
    return GraphService(graph)


class DummyResponse:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def test_generate_migration_plan(monkeypatch: pytest.MonkeyPatch):
    service = _service()

    payload = {
        "choices": [
            {
                "message": {
                    "content": (
                        "{\n"
                        "  \"title\": \"Migration Plan\",\n"
                        "  \"summary\": \"Move to new stack\",\n"
                        "  \"assumptions\": [\"Repo builds\"],\n"
                        "  \"scope\": \"Core modules\",\n"
                        "  \"phases\": [],\n"
                        "  \"risks\": [],\n"
                        "  \"validation\": [],\n"
                        "  \"checklist\": [],\n"
                        "  \"mermaid\": [],\n"
                        "  \"cursor_prompt\": \"Create MIGRATION_PLAN.md\",\n"
                        "  \"plan_markdown\": \"# Plan\"\n"
                        "}\n"
                    )
                }
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }

    def fake_post(*args, **kwargs):
        return DummyResponse(payload)

    monkeypatch.setattr("codeintel.openrouter_client.httpx.post", fake_post)

    request = MigrationPlanRequest(
        goal="Migrate to new stack",
        target_stack="Example",
        seed_queries=["Foo"],
        outline_only=True,
    )
    config = OpenRouterConfig(api_key="test", model="test-model")

    result = generate_migration_plan(service, request, config)
    assert result.plan
    assert result.cursor_prompt == "Create MIGRATION_PLAN.md"
    assert result.plan_markdown == "# Plan"
    assert result.error is None


def test_generate_migration_plan_fallback_on_400(monkeypatch: pytest.MonkeyPatch):
    service = _service()

    error_payload = {"error": "response_format not supported"}
    success_payload = {
        "choices": [
            {
                "message": {
                    "content": (
                        "{\n"
                        "  \"title\": \"Migration Plan\",\n"
                        "  \"summary\": \"Move\",\n"
                        "  \"assumptions\": [],\n"
                        "  \"scope\": \"\",\n"
                        "  \"phases\": [],\n"
                        "  \"risks\": [],\n"
                        "  \"validation\": [],\n"
                        "  \"checklist\": [],\n"
                        "  \"mermaid\": [],\n"
                        "  \"cursor_prompt\": \"Create MIGRATION_PLAN.md\",\n"
                        "  \"plan_markdown\": \"# Plan\"\n"
                        "}\n"
                    )
                }
            }
        ]
    }

    call_count = {"count": 0}

    def fake_post(*args, **kwargs):
        call_count["count"] += 1
        if call_count["count"] == 1:
            request = __import__("httpx").Request("POST", "https://openrouter.ai/api/v1/chat/completions")
            return __import__("httpx").Response(400, json=error_payload, request=request)
        request = __import__("httpx").Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        return __import__("httpx").Response(200, json=success_payload, request=request)

    monkeypatch.setattr("codeintel.openrouter_client.httpx.post", fake_post)

    request = MigrationPlanRequest(goal="Migrate", outline_only=True)
    config = OpenRouterConfig(api_key="test", model="test-model")

    result = generate_migration_plan(service, request, config)
    assert result.plan
    assert result.error is None
