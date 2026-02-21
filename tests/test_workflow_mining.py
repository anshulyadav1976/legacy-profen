from __future__ import annotations

from typing import Any

import pytest

from codeintel.extract import extract_symbols
from codeintel.graph import build_graph
from codeintel.mcp_graph import GraphService
from codeintel.openrouter_client import OpenRouterConfig
from codeintel.parser import PythonParser
from codeintel.workflow_mining import (
    WorkflowMiningRequest,
    generate_workflow_artifacts,
)


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


def test_workflow_artifacts_generation(monkeypatch: pytest.MonkeyPatch):
    service = _service()

    payload = {
        "choices": [
            {
                "message": {
                    "content": (
                        "{\n"
                        "  \"title\": \"Workflow\",\n"
                        "  \"summary\": \"Does a thing\",\n"
                        "  \"steps\": [\"Step A\"],\n"
                        "  \"decision_points\": [],\n"
                        "  \"inputs\": [],\n"
                        "  \"outputs\": [],\n"
                        "  \"risks\": [],\n"
                        "  \"confidence\": \"medium\",\n"
                        "  \"mermaid\": \"flowchart TD\\nA-->B\",\n"
                        "  \"supporting_nodes\": []\n"
                        "}\n"
                    )
                }
            }
        ]
    }

    def fake_post(*args, **kwargs):
        return DummyResponse(payload)

    monkeypatch.setattr("codeintel.openrouter_client.httpx.post", fake_post)

    request = WorkflowMiningRequest(max_workflows=1, outline_only=True)
    config = OpenRouterConfig(api_key="test", model="test-model")

    artifacts = generate_workflow_artifacts(service, request, config)
    assert artifacts.workflows
    assert artifacts.workflows[0]["title"] == "Workflow"