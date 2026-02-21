# Architecture

## Current (Phase 1-4)

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
    JS --> FE[Frontend Graph Viewer]
    JS --> MCP[MCP Server]
```

```mermaid
flowchart LR
    JS[jwst_graph.json] --> WM[Workflow Mining]
    WM --> OR[OpenRouter + Gemini]
    OR --> WF[workflow_artifacts.json]
    WF --> FE2[Frontend Workflows Tab]
```

```mermaid
flowchart LR
    ZIP[Repo ZIP Upload] --> API[FastAPI /parse]
    API --> TS2[Tree-sitter + Graph Builder]
    TS2 --> JSON[Graph JSON Response]
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
- `codeintel/workflow_mining.py`: Workflow mining artifacts (OpenRouter + graph context).
- `codeintel/openrouter_client.py`: OpenRouter HTTP client helper.
- `codeintel/llm_utils.py`: Shared LLM response parsing and JSON repair helpers.
- `codeintel/api.py`: FastAPI server for graph generation from uploaded archives.
- `frontend/`: Static browser-based graph viewer (Cytoscape).

## Planned (Remaining)
- Partner integrations (CodeWords, Dust) and end-to-end PR workflow demo.
