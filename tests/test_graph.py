from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from codeintel.extract import extract_symbols
from codeintel.graph import (
    EDGE_CALLS,
    EDGE_IMPORTS,
    EDGE_INHERITS,
    build_graph,
    class_node_id,
    file_node_id,
    function_node_id,
    module_node_id,
)
from codeintel.parser import PythonParser
from codeintel.storage import load_graph, save_graph


SAMPLE = """
import os, json
from sys import path as sys_path

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


def _build_graph():
    parser = PythonParser()
    parsed = parser.parse_text(SAMPLE)
    symbols = extract_symbols(parsed, path="sample.py")
    return build_graph([symbols])


def test_build_graph_nodes_and_edges():
    graph = _build_graph()
    file_id = file_node_id("sample.py")

    assert file_id in graph.nodes
    assert class_node_id("sample.py", "Foo") in graph.nodes
    assert class_node_id("sample.py", "Bar") in graph.nodes
    assert function_node_id("sample.py", "Foo.helper") in graph.nodes
    assert function_node_id("sample.py", "Foo.method") in graph.nodes
    assert function_node_id("sample.py", "bar") in graph.nodes

    assert graph.has_edge(file_id, module_node_id("os"))
    assert graph.has_edge(file_id, module_node_id("json"))
    assert graph[file_id][module_node_id("os")]["type"] == EDGE_IMPORTS

    assert graph.has_edge(
        function_node_id("sample.py", "Foo.method"),
        function_node_id("sample.py", "Foo.helper"),
    )
    assert (
        graph[
            function_node_id("sample.py", "Foo.method")
        ][function_node_id("sample.py", "Foo.helper")]["type"]
        == EDGE_CALLS
    )

    assert graph.has_edge(
        class_node_id("sample.py", "Bar"),
        class_node_id("sample.py", "Foo"),
    )
    assert (
        graph[
            class_node_id("sample.py", "Bar")
        ][class_node_id("sample.py", "Foo")]["type"]
        == EDGE_INHERITS
    )


def test_graph_serialization_roundtrip():
    graph = _build_graph()
    with TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "graph.json"
        save_graph(graph, path)
        loaded = load_graph(path)

    assert loaded.number_of_nodes() == graph.number_of_nodes()
    assert loaded.number_of_edges() == graph.number_of_edges()