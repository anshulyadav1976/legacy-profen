# Architecture

## Current (Phase 1-2)

```mermaid
flowchart LR
    subgraph Ingestion
        FW[File Walker] --> TS[Tree-sitter Parser]
        TS --> EX[Symbol Extractor]
    end
    EX --> OUT[Extracted Symbols]
    OUT --> GB[Graph Builder]
    GB --> G[NetworkX DiGraph]
    G --> JS[JSON Serialization]
```

## Modules
- `codeintel/file_walker.py`: Locates Python files under a target root.
- `codeintel/parser.py`: Tree-sitter parsing wrapper.
- `codeintel/extract.py`: AST traversal + symbol extraction.
- `codeintel/models.py`: Dataclasses for symbol output.
- `codeintel/graph.py`: NetworkX graph builder and schema.
- `codeintel/storage.py`: JSON save/load helpers for the graph.
- `codeintel/pipeline.py`: End-to-end graph build pipeline and CLI entrypoint.
- `codeintel/mcp_graph.py`: Graph query service powering MCP tools.
- `codeintel/mcp_server.py`: MCP server exposing graph tools over stdio/HTTP.
- `codeintel/migration.py`: Migration plan generator (OpenRouter + graph context).
- `codeintel/openrouter_client.py`: OpenRouter HTTP client helper.
- `frontend/`: Static browser-based graph viewer (Cytoscape).

## Planned (Future Phases)
- Graph construction and JSON serialization via NetworkX.
- MCP server with dependency and impact tools.
- Partner integrations (Lovable, CodeWords, Dust).
