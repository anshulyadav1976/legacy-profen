# Code Intelligence Engine (JWST)

Local code intelligence engine for the James Webb Space Telescope pipeline, focused on fast parsing, structural extraction, and later graph/MCP tooling.

## Phase 1-2 Status
Phase 1 implements file walking, Tree-sitter parsing, and symbol extraction (functions, classes, variables, imports, calls) with tests. Phase 2 adds NetworkX graph construction and JSON serialization.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

## Run Tests

```powershell
.\.venv\Scripts\pytest
```

## Example: Parse a File

```powershell
.\.venv\Scripts\python - <<'PY'
from codeintel.parser import PythonParser
from codeintel.extract import extract_symbols

parser = PythonParser()
parsed = parser.parse_file(r"C:\Users\anshu\legacy-profen\jwst-main\jwst\__init__.py")
result = extract_symbols(parsed)
print(len(result["functions"]), len(result["classes"]))
PY
```

## Example: Build and Save Graph

```powershell
.\.venv\Scripts\python - <<'PY'
from codeintel.file_walker import iter_python_files
from codeintel.parser import PythonParser
from codeintel.extract import extract_symbols
from codeintel.graph import build_graph
from codeintel.storage import save_graph

root = r"C:\\Users\\anshu\\legacy-profen\\jwst-main"
parser = PythonParser()
symbols = []
for path in iter_python_files(root)[:10]:
    parsed = parser.parse_file(path)
    symbols.append(extract_symbols(parsed, path=path))

graph = build_graph(symbols)
save_graph(graph, "jwst_graph.json")
print(graph.number_of_nodes(), graph.number_of_edges())
PY
```

## Build Graph From Repo (No MCP)

```powershell
.\.venv\Scripts\python -m codeintel.pipeline --root C:\Users\anshu\legacy-profen\jwst-main --output jwst_graph.json
```

## Frontend Viewer (Static)

```powershell
python -m http.server 8000
```

Open `http://localhost:8000/frontend/` in the browser. The viewer loads `../jwst_graph.json` by default.

Viewer features: clustering, focus+context lens, neighborhood expansion, and module/class subgraph filters.

## MCP Server (Phase 3)

```powershell
.\.venv\Scripts\python -m codeintel.mcp_server --graph jwst_graph.json --transport stdio
```

For HTTP transport:

```powershell
.\.venv\Scripts\python -m codeintel.mcp_server --graph jwst_graph.json --transport streamable-http --host 127.0.0.1 --port 8001
```

Smoke test (stdio client):

```powershell
.\.venv\Scripts\python scripts\mcp_smoke.py --graph jwst_graph.json
```

Cursor MCP template is available at `cursor_mcp.json`.
Update `cursor_mcp.json` with your `OPENROUTER_API_KEY` and preferred `OPENROUTER_MODEL`.

## Migration Planning Tool

The MCP server exposes `migration_plan`, which uses OpenRouter for plan generation. Configure these environment variables:

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL` (e.g., a Gemini model on OpenRouter)
- `OPENROUTER_APP_TITLE` (optional)
- `OPENROUTER_APP_URL` (optional)

## Target Codebase
- Local JWST repository is expected at `/jwst-main`.
- Do not clone from GitHub; parse the local folder only.
