"""JSON serialization helpers for NetworkX graphs."""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph


def save_graph(graph: nx.DiGraph, path: str | Path) -> None:
    data = json_graph.node_link_data(graph)
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_graph(path: str | Path) -> nx.DiGraph:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return json_graph.node_link_graph(data, directed=True)