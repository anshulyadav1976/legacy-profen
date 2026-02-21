"""NetworkX graph construction from extracted symbols."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import networkx as nx

from .models import Call, ImportItem, Inheritance, Symbol


NODE_FILE = "File"
NODE_FUNCTION = "Function"
NODE_CLASS = "Class"

EDGE_CALLS = "CALLS"
EDGE_IMPORTS = "IMPORTS"
EDGE_INHERITS = "INHERITS"


@dataclass
class ExtractedFile:
    path: str
    functions: list[Symbol]
    classes: list[Symbol]
    variables: list[Symbol]
    imports: list[ImportItem]
    calls: list[Call]
    inherits: list[Inheritance]


def file_node_id(path: str) -> str:
    return f"file:{path}"


def module_node_id(name: str) -> str:
    return f"module:{name}"


def function_node_id(path: str | None, qualname: str) -> str:
    if path:
        return f"func:{path}:{qualname}"
    return f"func:external:{qualname}"


def class_node_id(path: str | None, qualname: str) -> str:
    if path:
        return f"class:{path}:{qualname}"
    return f"class:external:{qualname}"


def build_graph(extracted: Iterable[dict]) -> nx.DiGraph:
    graph = nx.DiGraph()
    index = _DefinitionIndex()

    for entry in extracted:
        path = entry["path"]
        if not path:
            continue
        file_id = file_node_id(path)
        _ensure_node(
            graph,
            file_id,
            type=NODE_FILE,
            name=path,
            path=path,
        )

        for symbol in entry["functions"]:
            node_id = function_node_id(path, symbol.qualname)
            _ensure_node(
                graph,
                node_id,
                type=NODE_FUNCTION,
                name=symbol.name,
                qualname=symbol.qualname,
                path=path,
            )
            index.add_function(path, symbol, node_id)

        for symbol in entry["classes"]:
            node_id = class_node_id(path, symbol.qualname)
            _ensure_node(
                graph,
                node_id,
                type=NODE_CLASS,
                name=symbol.name,
                qualname=symbol.qualname,
                path=path,
            )
            index.add_class(path, symbol, node_id)

    for entry in extracted:
        path = entry["path"]
        if not path:
            continue
        file_id = file_node_id(path)

        for imp in entry["imports"]:
            _add_import_edges(graph, file_id, imp)

        for inherit in entry.get("inherits", []):
            sub_id = index.resolve_class(path, inherit.class_name)
            if sub_id is None:
                continue
            for base in inherit.bases:
                base_id = index.resolve_class(path, base)
                if base_id is None:
                    base_id = class_node_id(None, base)
                    _ensure_node(
                        graph,
                        base_id,
                        type=NODE_CLASS,
                        name=base,
                        qualname=base,
                        path=None,
                        external=True,
                    )
                graph.add_edge(sub_id, base_id, type=EDGE_INHERITS)

        for call in entry["calls"]:
            caller_id = index.resolve_function(path, call.caller)
            if caller_id is None:
                continue
            target_id = index.resolve_function(path, call.name)
            if target_id is None:
                target_id = function_node_id(None, call.name)
                _ensure_node(
                    graph,
                    target_id,
                    type=NODE_FUNCTION,
                    name=call.name.split(".")[-1],
                    qualname=call.name,
                    path=None,
                    external=True,
                )
            graph.add_edge(caller_id, target_id, type=EDGE_CALLS)

    return graph


def _add_import_edges(graph: nx.DiGraph, file_id: str, item: ImportItem) -> None:
    targets: list[str] = []
    if item.kind == "import":
        targets.extend(item.names)
    else:
        if item.module:
            targets.append(item.module)

    for target in targets:
        module_id = module_node_id(target)
        _ensure_node(
            graph,
            module_id,
            type=NODE_FILE,
            name=target,
            path=None,
            external=True,
        )
        graph.add_edge(file_id, module_id, type=EDGE_IMPORTS)


def _ensure_node(graph: nx.DiGraph, node_id: str, **attrs) -> None:
    if node_id not in graph:
        graph.add_node(node_id, **attrs)


class _DefinitionIndex:
    def __init__(self) -> None:
        self._func_by_path_qual: dict[tuple[str, str], str] = {}
        self._func_by_path_name: dict[tuple[str, str], str] = {}
        self._func_by_qual: dict[str, list[str]] = {}
        self._func_by_name: dict[str, list[str]] = {}
        self._class_by_path_qual: dict[tuple[str, str], str] = {}
        self._class_by_qual: dict[str, list[str]] = {}
        self._class_by_name: dict[str, list[str]] = {}

    def add_function(self, path: str, symbol: Symbol, node_id: str) -> None:
        self._func_by_path_qual[(path, symbol.qualname)] = node_id
        self._func_by_path_name[(path, symbol.name)] = node_id
        self._func_by_qual.setdefault(symbol.qualname, []).append(node_id)
        self._func_by_name.setdefault(symbol.name, []).append(node_id)

    def add_class(self, path: str, symbol: Symbol, node_id: str) -> None:
        self._class_by_path_qual[(path, symbol.qualname)] = node_id
        self._class_by_qual.setdefault(symbol.qualname, []).append(node_id)
        self._class_by_name.setdefault(symbol.name, []).append(node_id)

    def resolve_function(self, path: str, name: str | None) -> str | None:
        if not name:
            return None
        if "." in name:
            if (path, name) in self._func_by_path_qual:
                return self._func_by_path_qual[(path, name)]
            return self._first(self._func_by_qual.get(name))

        if (path, name) in self._func_by_path_name:
            return self._func_by_path_name[(path, name)]
        return self._first(self._func_by_name.get(name))

    def resolve_class(self, path: str, name: str | None) -> str | None:
        if not name:
            return None
        if "." in name:
            if (path, name) in self._class_by_path_qual:
                return self._class_by_path_qual[(path, name)]
            return self._first(self._class_by_qual.get(name))

        if (path, name) in self._class_by_path_qual:
            return self._class_by_path_qual[(path, name)]
        return self._first(self._class_by_name.get(name))

    @staticmethod
    def _first(values: list[str] | None) -> str | None:
        if not values:
            return None
        return values[0]