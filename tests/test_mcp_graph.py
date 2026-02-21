from __future__ import annotations

from codeintel.extract import extract_symbols
from codeintel.graph import build_graph
from codeintel.mcp_graph import GraphService
from codeintel.parser import PythonParser


SAMPLE = """
import os

class Foo:
    def helper(self):
        return os.path.join("a", "b")

    def method(self):
        self.helper()
        print("hi")

class Bar(Foo):
    pass

def bar():
    foo = Foo()
    foo.method()
    return foo
"""


def _service() -> GraphService:
    parser = PythonParser()
    parsed = parser.parse_text(SAMPLE)
    symbols = extract_symbols(parsed, path="sample.py")
    graph = build_graph([symbols])
    return GraphService(graph)


def test_search():
    service = _service()
    result = service.search("Foo.method")
    assert result["matches"]
    assert any(match["qualname"] == "Foo.method" for match in result["matches"])


def test_get_dependencies():
    service = _service()
    result = service.get_dependencies("Foo.method", direction="outgoing", hops=1)
    node_names = {node.get("qualname") for node in result["nodes"]}
    assert "Foo.helper" in node_names


def test_impact_analysis():
    service = _service()
    result = service.impact_analysis("Foo.helper", hops=1)
    node_names = {node.get("qualname") for node in result["nodes"]}
    assert "Foo.method" in node_names


def test_graph_path():
    service = _service()
    result = service.graph_path("Foo.method", "Foo.helper")
    path = [node.get("qualname") for node in result["path"]]
    assert path[0] == "Foo.method"
    assert path[-1] == "Foo.helper"


def test_stats_metadata():
    service = _service()
    stats = service.stats()
    assert "Function" in stats["node_counts"]
    metadata = service.metadata()
    assert metadata["node_count"] > 0
