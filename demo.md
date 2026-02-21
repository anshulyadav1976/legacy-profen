# Demo Checklist

Use this checklist during the hackathon demo. Each item includes a one-liner to run or use the feature.

- [ ] Build the JWST graph JSON from the repo
  `.\.venv\Scripts\python -m codeintel.pipeline --root C:\Users\anshu\legacy-profen\jwst-main --output jwst_graph.json`

- [ ] Run the unit test suite
  `.\.venv\Scripts\pytest -q`

- [ ] Start the local web server
  `python -m http.server 8000`

- [ ] Open the graph viewer
  `http://localhost:8000/frontend/`

- [ ] Load the graph JSON in the viewer
  Click **Load Graph** with path `/jwst_graph.json`

- [ ] Filter node/edge types
  Toggle **Function/Class/File/External** and **CALLS/IMPORTS/INHERITS** then click **Apply Filters**

- [ ] Subgraph by module group
  Enter `jwst` in **Module group** and click **Apply**

- [ ] Subgraph by class
  Enter a class name (e.g., `Step`) in **Class** and click **Apply**

- [ ] Focus + context lens
  Check **Focus + Context**, click a node, and adjust **Neighborhood hops**

- [ ] Neighborhood expansion
  Select a node and click **Expand** to reveal N-hop neighbors

- [ ] Core logic view
  Enable **Core logic mode** and raise **Min degree** to surface hotspots

- [ ] Clustering
  Click **Recompute** then optionally toggle **Color by cluster** or select a cluster

- [ ] Search and jump
  Enter a term in **Search** and click **Find**

- [ ] Reset the view
  Click **Reset View** to clear expansions and cluster selection

- [ ] Start MCP server (stdio)
  `.\.venv\Scripts\python -m codeintel.mcp_server --graph jwst_graph.json --transport stdio`

- [ ] Start MCP server (HTTP)
  `.\.venv\Scripts\python -m codeintel.mcp_server --graph jwst_graph.json --transport streamable-http --host 127.0.0.1 --port 8001`

- [ ] MCP smoke test (stdio client)
  `.\.venv\Scripts\python scripts\mcp_smoke.py --graph jwst_graph.json`

- [ ] Generate migration plan (MCP tool)
  Use `migration_plan` with goal/scope/constraints and seed queries like `jwst` or `Step`

- [ ] Ensure OpenRouter env is set
  `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` must be available to the MCP server
