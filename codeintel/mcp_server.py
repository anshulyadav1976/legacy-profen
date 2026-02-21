"""MCP server exposing graph query tools."""

from __future__ import annotations

import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .mcp_graph import GraphService, ensure_snapshot
from .migration import MigrationPlanRequest, generate_migration_plan, resolve_openrouter_config


def create_server(service: GraphService) -> FastMCP:
    mcp = FastMCP(
        name="JWST Code Graph",
        instructions=(
            "Query the JWST knowledge graph. Use search() to find nodes, "
            "then get_dependencies(), impact_analysis(), graph_path(), or subgraph() "
            "to explore relationships."
        ),
        json_response=True,
    )

    @mcp.tool()
    def metadata() -> dict:
        """Return snapshot metadata about the loaded graph."""
        return service.metadata()

    @mcp.tool()
    def search(
        query: str,
        node_types: list[str] | None = None,
        limit: int = 20,
    ) -> dict:
        """Search nodes by partial name, qualname, or path."""
        return service.search(query, node_types=node_types, limit=limit)

    @mcp.tool()
    def get_dependencies(
        query: str,
        direction: str = "both",
        hops: int = 1,
        edge_types: list[str] | None = None,
        limit: int = 200,
    ) -> dict:
        """Return incoming/outgoing call dependencies from a node."""
        return service.get_dependencies(
            query,
            direction=direction,
            hops=hops,
            edge_types=edge_types,
            limit=limit,
        )

    @mcp.tool()
    def impact_analysis(
        query: str,
        hops: int = 2,
        edge_types: list[str] | None = None,
        limit: int = 200,
    ) -> dict:
        """Return upstream impact for a node, file, or class."""
        return service.impact_analysis(
            query,
            hops=hops,
            edge_types=edge_types,
            limit=limit,
        )

    @mcp.tool()
    def graph_path(
        source: str,
        target: str,
        edge_types: list[str] | None = None,
        directed: bool = False,
    ) -> dict:
        """Find the shortest path between two nodes."""
        return service.graph_path(
            source,
            target,
            edge_types=edge_types,
            directed=directed,
        )

    @mcp.tool()
    def subgraph(
        query: str,
        hops: int = 1,
        direction: str = "both",
        edge_types: list[str] | None = None,
        limit: int = 200,
    ) -> dict:
        """Return a bounded neighborhood around a node."""
        return service.subgraph(
            query,
            hops=hops,
            direction=direction,
            edge_types=edge_types,
            limit=limit,
        )

    @mcp.tool()
    def stats(edge_types: list[str] | None = None, limit: int = 10) -> dict:
        """Return graph stats, hubs, clusters, and module breakdowns."""
        return service.stats(edge_types=edge_types, limit=limit)

    @mcp.tool()
    def migration_plan(
        goal: str,
        target_stack: str | None = None,
        scope: str | None = None,
        constraints: list[str] | None = None,
        seed_queries: list[str] | None = None,
        hops: int = 1,
        edge_types: list[str] | None = None,
        outline_only: bool = False,
        plan_filename: str = "MIGRATION_PLAN.md",
        include_graph_context: bool = True,
        max_nodes: int = 50,
        max_edges: int = 120,
    ) -> dict:
        """Generate a migration plan using OpenRouter + Gemini and graph context."""
        request = MigrationPlanRequest(
            goal=goal,
            target_stack=target_stack,
            scope=scope,
            constraints=constraints,
            seed_queries=seed_queries,
            hops=hops,
            edge_types=edge_types,
            outline_only=outline_only,
            plan_filename=plan_filename,
            include_graph_context=include_graph_context,
            max_nodes=max_nodes,
            max_edges=max_edges,
        )
        config = resolve_openrouter_config()
        result = generate_migration_plan(service, request, config)
        return {
            "model": result.model,
            "plan": result.plan,
            "cursor_prompt": result.cursor_prompt,
            "plan_markdown": result.plan_markdown,
            "usage": result.usage,
            "error": result.error,
        }

    return mcp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MCP server for JWST graph")
    parser.add_argument(
        "--graph",
        default="jwst_graph.json",
        help="Path to graph JSON",
    )
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse", "streamable-http"],
        help="Transport type",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for HTTP transports",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for HTTP transports",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Load the graph and exit",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    graph_path = Path(args.graph)
    if not graph_path.exists():
        raise SystemExit(f"Graph not found: {graph_path}")

    service = GraphService.from_json(graph_path)
    ensure_snapshot(service.graph, source_root=str(graph_path))

    if args.validate:
        print(service.metadata())
        return 0

    mcp = create_server(service)
    mcp.host = args.host
    mcp.port = args.port
    mcp.run(transport=args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
