"""Graph query helpers for MCP tools."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import networkx as nx


DEFAULT_EDGE_TYPES = {"CALLS", "IMPORTS", "INHERITS"}


@dataclass(frozen=True)
class GraphSnapshot:
    source_root: str | None
    generated_at: str | None
    node_count: int
    edge_count: int
    graph_path: str | None


class GraphService:
    def __init__(self, graph: nx.DiGraph, graph_json_path: str | None = None) -> None:
        self.graph = graph
        self.graph_json_path = graph_json_path
        self._nodes = []
        self._node_by_id: dict[str, dict] = {}
        self._exact_index: dict[str, dict[str, list[str]]] = {
            "id": {},
            "name": {},
            "qualname": {},
            "path": {},
        }
        self._build_indexes()

    @classmethod
    def from_json(cls, path: str | Path) -> "GraphService":
        from .storage import load_graph

        graph = load_graph(path)
        return cls(graph, graph_json_path=str(path))

    def snapshot(self) -> GraphSnapshot:
        snapshot = self.graph.graph.get("snapshot", {}) if self.graph else {}
        return GraphSnapshot(
            source_root=snapshot.get("source_root"),
            generated_at=snapshot.get("generated_at"),
            node_count=self.graph.number_of_nodes(),
            edge_count=self.graph.number_of_edges(),
            graph_path=self.graph_json_path,
        )

    def metadata(self) -> dict:
        snap = self.snapshot()
        return {
            "source_root": snap.source_root,
            "generated_at": snap.generated_at,
            "node_count": snap.node_count,
            "edge_count": snap.edge_count,
            "graph_path": snap.graph_path,
        }

    def search(
        self,
        query: str,
        node_types: list[str] | None = None,
        limit: int = 20,
    ) -> dict:
        matches = self._search_nodes(query, node_types=node_types, limit=limit)
        return {"query": query, "matches": matches}

    def get_dependencies(
        self,
        query: str,
        direction: str = "both",
        hops: int = 1,
        edge_types: list[str] | None = None,
        limit: int = 200,
    ) -> dict:
        seed_ids, matched = self._resolve_seed_nodes(query, limit=5)
        nodes, edges = self._bfs(
            seed_ids,
            direction=direction,
            hops=hops,
            edge_types=set(edge_types) if edge_types else None,
            limit=limit,
        )
        return {
            "query": query,
            "matched": matched,
            "direction": direction,
            "hops": hops,
            "nodes": [self._node_view(node_id) for node_id in nodes],
            "edges": [self._edge_view(edge) for edge in edges],
        }

    def impact_analysis(
        self,
        query: str,
        hops: int = 2,
        edge_types: list[str] | None = None,
        limit: int = 200,
    ) -> dict:
        seed_ids, matched = self._resolve_seed_nodes(query, limit=5)
        nodes, edges = self._bfs(
            seed_ids,
            direction="incoming",
            hops=hops,
            edge_types=set(edge_types) if edge_types else None,
            limit=limit,
        )
        return {
            "query": query,
            "matched": matched,
            "hops": hops,
            "nodes": [self._node_view(node_id) for node_id in nodes],
            "edges": [self._edge_view(edge) for edge in edges],
        }

    def graph_path(
        self,
        source: str,
        target: str,
        edge_types: list[str] | None = None,
        directed: bool = False,
    ) -> dict:
        source_ids, source_matches = self._resolve_seed_nodes(source, limit=1)
        target_ids, target_matches = self._resolve_seed_nodes(target, limit=1)
        if not source_ids or not target_ids:
            return {
                "source": source,
                "target": target,
                "matches": {
                    "source": source_matches,
                    "target": target_matches,
                },
                "path": [],
                "edges": [],
                "error": "Source or target not found",
            }

        source_id = next(iter(source_ids))
        target_id = next(iter(target_ids))
        graph = self._edge_filtered_graph(edge_types)
        if not directed:
            graph = graph.to_undirected()
        try:
            path = nx.shortest_path(graph, source_id, target_id)
        except nx.NetworkXNoPath:
            return {
                "source": source,
                "target": target,
                "matches": {
                    "source": source_matches,
                    "target": target_matches,
                },
                "path": [],
                "edges": [],
                "error": "No path found",
            }

        edges = []
        for idx in range(len(path) - 1):
            edge = (path[idx], path[idx + 1])
            edges.append(self._edge_view(edge))

        return {
            "source": source,
            "target": target,
            "matches": {
                "source": source_matches,
                "target": target_matches,
            },
            "path": [self._node_view(node_id) for node_id in path],
            "edges": edges,
        }

    def subgraph(
        self,
        query: str,
        hops: int = 1,
        direction: str = "both",
        edge_types: list[str] | None = None,
        limit: int = 200,
    ) -> dict:
        seed_ids, matched = self._resolve_seed_nodes(query, limit=5)
        nodes, edges = self._bfs(
            seed_ids,
            direction=direction,
            hops=hops,
            edge_types=set(edge_types) if edge_types else None,
            limit=limit,
        )
        return {
            "query": query,
            "matched": matched,
            "direction": direction,
            "hops": hops,
            "nodes": [self._node_view(node_id) for node_id in nodes],
            "edges": [self._edge_view(edge) for edge in edges],
        }

    def stats(self, edge_types: list[str] | None = None, limit: int = 10) -> dict:
        node_counts: dict[str, int] = {}
        for node_id, data in self.graph.nodes(data=True):
            node_type = data.get("type", "Unknown")
            node_counts[node_type] = node_counts.get(node_type, 0) + 1

        edge_counts: dict[str, int] = {}
        for _, _, data in self.graph.edges(data=True):
            edge_type = data.get("type", "Unknown")
            edge_counts[edge_type] = edge_counts.get(edge_type, 0) + 1

        graph = self._edge_filtered_graph(edge_types)
        degrees = graph.degree()
        hubs = sorted(degrees, key=lambda item: item[1], reverse=True)[:limit]
        hubs_payload = [
            {**self._node_view(node_id), "degree": degree}
            for node_id, degree in hubs
        ]

        module_counts: dict[str, int] = {}
        for node_id, data in self.graph.nodes(data=True):
            path = data.get("path")
            if not path:
                continue
            group = _module_group_from_path(str(path))
            module_counts[group] = module_counts.get(group, 0) + 1
        module_breakdown = sorted(
            module_counts.items(), key=lambda item: item[1], reverse=True
        )[:limit]

        cluster_sizes = _cluster_sizes(graph, limit=limit)

        return {
            "node_counts": node_counts,
            "edge_counts": edge_counts,
            "top_hubs": hubs_payload,
            "module_breakdown": [
                {"module": module, "count": count}
                for module, count in module_breakdown
            ],
            "clusters": cluster_sizes,
        }

    def _build_indexes(self) -> None:
        for node_id, data in self.graph.nodes(data=True):
            node = {
                "id": node_id,
                "type": data.get("type"),
                "name": data.get("name"),
                "qualname": data.get("qualname"),
                "path": data.get("path"),
                "external": bool(data.get("external")),
            }
            self._nodes.append(node)
            self._node_by_id[node_id] = node
            self._index_exact("id", node_id, node_id)
            if node.get("name"):
                self._index_exact("name", node["name"], node_id)
            if node.get("qualname"):
                self._index_exact("qualname", node["qualname"], node_id)
            if node.get("path"):
                self._index_exact("path", node["path"], node_id)

    def _index_exact(self, key: str, value: str, node_id: str) -> None:
        bucket = self._exact_index[key]
        bucket.setdefault(value.lower(), []).append(node_id)

    def _search_nodes(
        self, query: str, node_types: list[str] | None, limit: int
    ) -> list[dict]:
        q = query.lower()
        matches = []
        for node in self._nodes:
            if node_types and node.get("type") not in node_types:
                continue
            haystacks = [
                str(node.get("id", "")),
                str(node.get("name", "")),
                str(node.get("qualname", "")),
                str(node.get("path", "")),
            ]
            if any(q in haystack.lower() for haystack in haystacks if haystack):
                matches.append(node)
                if len(matches) >= limit:
                    break
        return matches

    def _resolve_seed_nodes(self, query: str, limit: int) -> tuple[set[str], list[dict]]:
        query_lower = query.lower()
        if query_lower in self._exact_index["id"]:
            ids = set(self._exact_index["id"][query_lower])
            return ids, [self._node_view(node_id) for node_id in ids]

        for key in ("qualname", "name", "path"):
            bucket = self._exact_index[key].get(query_lower)
            if bucket:
                ids = set(bucket[:limit])
                return ids, [self._node_view(node_id) for node_id in ids]

        matches = self._search_nodes(query, node_types=None, limit=limit)
        ids = {node["id"] for node in matches}
        return ids, [self._node_view(node_id) for node_id in ids]

    def _node_view(self, node_id: str) -> dict:
        node = self._node_by_id.get(node_id)
        if not node:
            return {"id": node_id}
        return {
            "id": node_id,
            "type": node.get("type"),
            "name": node.get("name"),
            "qualname": node.get("qualname"),
            "path": node.get("path"),
            "external": node.get("external"),
        }

    def _edge_view(self, edge: tuple[str, str]) -> dict:
        source, target = edge
        data = self.graph.get_edge_data(source, target) or {}
        return {
            "source": source,
            "target": target,
            "type": data.get("type", "Unknown"),
        }

    def _edge_filtered_graph(self, edge_types: list[str] | None) -> nx.DiGraph:
        if not edge_types:
            return self.graph
        allowed = set(edge_types)
        edges = [
            (u, v, data)
            for u, v, data in self.graph.edges(data=True)
            if data.get("type") in allowed
        ]
        graph = nx.DiGraph()
        graph.add_nodes_from(self.graph.nodes(data=True))
        graph.add_edges_from(edges)
        return graph

    def _bfs(
        self,
        seed_ids: Iterable[str],
        direction: str,
        hops: int,
        edge_types: set[str] | None,
        limit: int,
    ) -> tuple[list[str], list[tuple[str, str]]]:
        if not seed_ids:
            return [], []
        visited = set(seed_ids)
        frontier = set(seed_ids)
        edges: set[tuple[str, str]] = set()

        for _ in range(max(hops, 1)):
            if not frontier:
                break
            next_frontier = set()
            for node_id in frontier:
                if direction in ("outgoing", "both"):
                    for neighbor in self.graph.successors(node_id):
                        if not self._edge_allowed(node_id, neighbor, edge_types):
                            continue
                        edges.add((node_id, neighbor))
                        if neighbor not in visited and len(visited) < limit:
                            visited.add(neighbor)
                            next_frontier.add(neighbor)
                if direction in ("incoming", "both"):
                    for neighbor in self.graph.predecessors(node_id):
                        if not self._edge_allowed(neighbor, node_id, edge_types):
                            continue
                        edges.add((neighbor, node_id))
                        if neighbor not in visited and len(visited) < limit:
                            visited.add(neighbor)
                            next_frontier.add(neighbor)
            frontier = next_frontier

        return list(visited), list(edges)

    def _edge_allowed(
        self, source: str, target: str, edge_types: set[str] | None
    ) -> bool:
        if edge_types is None:
            return True
        data = self.graph.get_edge_data(source, target) or {}
        return data.get("type") in edge_types


def _module_group_from_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    marker = "/jwst-main/"
    idx = normalized.lower().find(marker)
    if idx != -1:
        remainder = normalized[idx + len(marker) :]
        parts = [part for part in remainder.split("/") if part]
        return parts[0] if parts else "root"
    parts = [part for part in normalized.split("/") if part]
    return parts[-2] if len(parts) >= 2 else (parts[0] if parts else "root")


def _cluster_sizes(graph: nx.Graph, limit: int = 10) -> list[dict]:
    if graph.number_of_nodes() == 0:
        return []
    undirected = graph.to_undirected()
    clusters = [
        len(component) for component in nx.connected_components(undirected)
    ]
    clusters.sort(reverse=True)
    return [
        {"cluster": idx + 1, "size": size}
        for idx, size in enumerate(clusters[:limit])
    ]


def ensure_snapshot(graph: nx.DiGraph, source_root: str | None = None) -> None:
    snapshot = graph.graph.get("snapshot")
    if snapshot:
        return
    graph.graph["snapshot"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": source_root,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }
