# Project Implementation Plan

This document outlines the step-by-step phases to build the Code Intelligence Engine. Mark items as [x] once complete and verified.

## Phase 1: Setup and AST Ingestion

- [x] Initialize the project repository and set up the package manager.
- [x] Install Tree-sitter and the Python-specific grammar bindings.
- [x] Write a file-walking script targeting the local `/jwst-main` directory to locate all Python source code files.
- [x] Build the core parsing module to generate an Abstract Syntax Tree (AST) for each file. [Image of Abstract Syntax Tree]
- [x] Extract key structural elements: Functions, Classes, Variables, and Imports.
- [x] Write terminal-executed unit tests to verify the parser correctly identifies definitions and function calls.

## Phase 2: Knowledge Graph Construction

- [x] Install the `networkx` library to act as the fast, in-memory graph engine.
- [x] Define the NetworkX `DiGraph` schema (Nodes: `File`, `Function`, `Class`; Edges: `CALLS`, `IMPORTS`, `INHERITS`). [Image of a NetworkX graph visualization]
- [x] Write an ingestion pipeline that maps the extracted AST data into the NetworkX directed graph.
- [x] Implement JSON serialization using `networkx.readwrite.json_graph.node_link_data` to save the parsed graph locally (so the massive codebase isn't re-parsed on every run).
- [x] Verify graph integrity by loading the JSON back into NetworkX and running a script to trace a known function call chain.

## Phase 3: Model Context Protocol (MCP) Server

- [x] Install the official Model Context Protocol Python SDK.
- [x] Initialize a basic MCP server that listens on `stdio` and loads the NetworkX graph from the JSON file into memory. [Image of Model Context Protocol architecture]
- [x] Implement the `get_dependencies` tool: Given a function name, use NetworkX functions (e.g., `G.successors()`) to return its incoming and outgoing calls.
- [x] Implement the `impact_analysis` tool: Given a changed file or class, calculate its blast radius by finding upstream dependencies.
- [x] Implement the `graph_path` tool: Use `nx.shortest_path()` to allow the agent to find the connection between any two structural nodes.
- [x] Implement the `search` tool: Find nodes by partial name, qualname, or path with type filters.
- [x] Implement the `subgraph` tool: Return a bounded neighborhood around a seed node with filters and hop limits.
- [x] Implement the `stats` tool: Provide hub nodes, cluster sizes, and module breakdowns for quick orientation.
- [x] Implement graph snapshot metadata (timestamp, source root, counts) so agents can validate freshness.
- [x] Test the MCP server locally using an MCP inspector or basic client script.
- [x] Implement `migration_plan` tool: generate a migration plan using OpenRouter + Gemini 3.1.
- [x] Add OpenRouter config support in MCP server (model name, API key via env).
- [x] Include graph context in migration prompts (stats, hubs, module breakdown, subgraph).
- [x] Return a Cursor-ready prompt to create a Markdown plan file with Mermaid diagrams and checklists.
- [x] Support `outline_only`/`dry_run` mode to keep output short for iteration.
- [x] Add tests for the migration planning tool (mocked HTTP).

## Phase 4: Workflow Mining & Partner Tech Integration

- [x] Build the Lovable web UI: Create a simple dashboard to visually display the Knowledge Graph and query results.
- [ ] Set up CodeWords automation: Create a workflow that triggers an automated codebase audit via the MCP server whenever a new Pull Request is opened.
- [ ] Configure a Dust agent: Connect a Dust agent to the MCP server to act as the "Code Migration Assistant" capable of mapping out legacy code refactoring plans for the JWST codebase.
- [ ] Finalize the end-to-end test: Run a CodeWords workflow against `/jwst-main`, query the in-memory graph, and have the Dust agent output a migration plan.
- [x] Workflow mining artifacts: generate `workflow_artifacts.json` from graph subgraphs (entrypoints + hubs).
- [x] LLM summarization: use OpenRouter + Gemini to label business workflows (steps, decisions, inputs/outputs, risks).
- [x] Leadership UX: add a "Workflows" tab in the frontend with workflow cards, Mermaid diagrams, and supporting nodes.
- [x] Traceability: "View in Graph" links from workflow cards to the underlying code subgraph.
- [x] Graph build API: upload a repo zip and return the graph JSON.

## Phase 5: Hackathon Final Polish

- [ ] Record a 2-minute video demo of your project (using Loom or an equivalent platform) showcasing the live walkthrough.
- [ ] Ensure the GitHub repository is public and contains clear setup instructions and technical documentation.
- [ ] Verify that the required minimum of 3 partner technologies are explicitly documented in the README.
