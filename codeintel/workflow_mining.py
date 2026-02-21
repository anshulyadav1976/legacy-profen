"""Workflow mining artifacts for leadership-friendly views."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import networkx as nx

from .llm_utils import extract_content, parse_json_content, repair_json_content
from .mcp_graph import GraphService
from .openrouter_client import OpenRouterConfig, OpenRouterRequestError, chat_completions


@dataclass(frozen=True)
class WorkflowSeed:
    node_id: str
    label: str
    node_type: str | None
    reason: str
    path: str | None


@dataclass(frozen=True)
class WorkflowMiningRequest:
    max_workflows: int = 8
    hops: int = 2
    edge_types: list[str] | None = None
    outline_only: bool = False
    max_nodes: int = 60
    max_edges: int = 120
    include_graph_context: bool = True


@dataclass(frozen=True)
class WorkflowArtifacts:
    generated_at: str
    source_graph: dict[str, Any]
    workflows: list[dict[str, Any]]
    seeds: list[dict[str, Any]]


def generate_workflow_artifacts(
    service: GraphService,
    request: WorkflowMiningRequest,
    config: OpenRouterConfig,
) -> WorkflowArtifacts:
    seeds = select_workflow_seeds(service.graph, request.max_workflows)
    workflows = []

    for seed in seeds:
        context = build_seed_context(
            service,
            seed,
            hops=request.hops,
            edge_types=request.edge_types,
            max_nodes=request.max_nodes,
            max_edges=request.max_edges,
        )
        workflow = summarize_workflow(context, request, config)
        if workflow:
            workflows.append(workflow)

    generated_at = datetime.now(timezone.utc).isoformat()
    return WorkflowArtifacts(
        generated_at=generated_at,
        source_graph=service.metadata(),
        workflows=workflows,
        seeds=[seed.__dict__ for seed in seeds],
    )


def summarize_workflow(
    context: dict[str, Any],
    request: WorkflowMiningRequest,
    config: OpenRouterConfig,
) -> dict[str, Any] | None:
    system_prompt = (
        "You are a product architect translating code into business workflows. "
        "Output valid JSON only, with business-friendly labels."
    )
    user_prompt = build_workflow_prompt(context, request)

    response = None
    error_message = None
    try:
        response = chat_completions(
            config,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
    except OpenRouterRequestError as exc:
        error_message = f"OpenRouter error ({exc.status_code}): {exc.payload}"
        if exc.status_code == 400:
            try:
                response = chat_completions(
                    config,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=None,
                )
                error_message = None
            except OpenRouterRequestError as retry_exc:
                error_message = f"OpenRouter error ({retry_exc.status_code}): {retry_exc.payload}"

    content = extract_content(response)
    if not content:
        return {
            "error": error_message or "No content returned",
            "seed": context.get("seed"),
            "supporting_nodes": context.get("supporting_nodes", []),
            "mermaid": None,
        }

    data, parse_error = parse_json_content(content)
    if data is None and parse_error:
        repaired = repair_json_content(content, config, chat_completions)
        if repaired:
            data, parse_error = parse_json_content(repaired)

    if data is None:
        return {
            "error": parse_error or "Failed to parse JSON",
            "seed": context.get("seed"),
            "supporting_nodes": context.get("supporting_nodes", []),
        }

    if isinstance(data, dict) and data.get("supporting_nodes") is None:
        data["supporting_nodes"] = context.get("supporting_nodes", [])
    if isinstance(data, dict) and data.get("seed") is None:
        data["seed"] = context.get("seed")
    return data


def build_seed_context(
    service: GraphService,
    seed: WorkflowSeed,
    hops: int,
    edge_types: list[str] | None,
    max_nodes: int,
    max_edges: int,
) -> dict[str, Any]:
    subgraph = service.subgraph(
        seed.node_id,
        hops=hops,
        direction="both",
        edge_types=edge_types,
        limit=max_nodes,
    )
    nodes = subgraph.get("nodes", [])[:max_nodes]
    edges = subgraph.get("edges", [])[:max_edges]

    return {
        "seed": seed.__dict__,
        "metadata": service.metadata(),
        "stats": service.stats(limit=8),
        "supporting_nodes": nodes,
        "supporting_edges": edges,
    }


def build_workflow_prompt(context: dict[str, Any], request: WorkflowMiningRequest) -> str:
    prompt = {
        "seed": context.get("seed"),
        "metadata": context.get("metadata"),
        "stats": context.get("stats"),
        "supporting_nodes": context.get("supporting_nodes"),
        "supporting_edges": context.get("supporting_edges"),
        "outline_only": request.outline_only,
        "output_schema": {
            "title": "string",
            "summary": "string",
            "steps": ["string"],
            "decision_points": ["string"],
            "inputs": ["string"],
            "outputs": ["string"],
            "risks": ["string"],
            "confidence": "low|medium|high",
            "mermaid": "string",
            "supporting_nodes": [
                {"id": "string", "label": "string", "type": "string", "path": "string"}
            ],
            "seed": {"node_id": "string", "label": "string"},
        },
        "instructions": (
            "Return a JSON object matching output_schema. "
            "Use business-friendly language, avoid raw code names in steps. "
            "Mermaid should be a flowchart with 5-12 nodes. "
            "If outline_only is true, keep steps concise."
        ),
    }
    return json.dumps(prompt, indent=2)


def select_workflow_seeds(graph: nx.DiGraph, max_seeds: int) -> list[WorkflowSeed]:
    seeds: list[WorkflowSeed] = []
    added = set()

    def add_seed(node_id: str, reason: str) -> None:
        if node_id in added:
            return
        data = graph.nodes[node_id]
        label = _node_label(node_id, data)
        seeds.append(
            WorkflowSeed(
                node_id=node_id,
                label=label,
                node_type=data.get("type"),
                reason=reason,
                path=data.get("path"),
            )
        )
        added.add(node_id)

    # Entrypoints by filename heuristics.
    for node_id, data in graph.nodes(data=True):
        if data.get("type") != "File":
            continue
        path = str(data.get("path") or "").lower()
        if any(token in path for token in ["__main__", "cli", "pipeline", "main.py"]):
            add_seed(node_id, "entrypoint")
            if len(seeds) >= max_seeds:
                return seeds

    # High-degree functions/classes as workflow hubs.
    degree = graph.degree()
    ranked = sorted(degree, key=lambda item: item[1], reverse=True)
    for node_id, _ in ranked:
        data = graph.nodes[node_id]
        if data.get("type") not in {"Function", "Class"}:
            continue
        if data.get("external"):
            continue
        add_seed(node_id, "hub")
        if len(seeds) >= max_seeds:
            break

    return seeds


def _node_label(node_id: str, data: dict[str, Any]) -> str:
    return data.get("qualname") or data.get("name") or data.get("path") or node_id


def resolve_openrouter_config() -> OpenRouterConfig:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    model = os.getenv("OPENROUTER_MODEL") or "google/gemini-3.1-pro-preview"
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    app_url = os.getenv("OPENROUTER_APP_URL")
    app_title = os.getenv("OPENROUTER_APP_TITLE") or "JWST Workflow Mining"
    timeout_seconds = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "60"))

    return OpenRouterConfig(
        api_key=api_key,
        model=model,
        base_url=base_url,
        app_url=app_url,
        app_title=app_title,
        timeout_seconds=timeout_seconds,
    )


def _extract_api_key(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""

    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            text = cleaned
            break

    if text.lower().startswith("export "):
        text = text[len("export ") :].strip()

    lowered = text.lower()
    if lowered.startswith("openrouter_api_key"):
        if "=" in text:
            _, value = text.split("=", 1)
            text = value.strip()
        elif ":" in text:
            _, value = text.split(":", 1)
            text = value.strip()

    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        text = text[1:-1].strip()

    return text


def write_workflow_artifacts(artifacts: WorkflowArtifacts, output_path: str | Path) -> None:
    payload = {
        "generated_at": artifacts.generated_at,
        "source_graph": artifacts.source_graph,
        "seeds": artifacts.seeds,
        "workflows": artifacts.workflows,
    }
    Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate workflow mining artifacts")
    parser.add_argument("--graph", default="jwst_graph.json", help="Graph JSON path")
    parser.add_argument("--output", default="workflow_artifacts.json", help="Output JSON path")
    parser.add_argument("--max-workflows", type=int, default=6, help="Max workflows")
    parser.add_argument("--hops", type=int, default=2, help="Neighborhood hops")
    parser.add_argument("--outline-only", action="store_true", help="Short output")
    parser.add_argument(
        "--openrouter-key-file",
        default=None,
        help="Optional path to OpenRouter API key file",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.openrouter_key_file:
        key_path = Path(args.openrouter_key_file)
        raw_key = key_path.read_text(encoding="utf-8")
        api_key = _extract_api_key(raw_key)
        if not api_key:
            raise RuntimeError("OpenRouter key file was empty or invalid.")
        os.environ["OPENROUTER_API_KEY"] = api_key

    service = GraphService.from_json(args.graph)
    config = resolve_openrouter_config()
    request = WorkflowMiningRequest(
        max_workflows=args.max_workflows,
        hops=args.hops,
        outline_only=args.outline_only,
    )
    artifacts = generate_workflow_artifacts(service, request, config)
    write_workflow_artifacts(artifacts, args.output)
    print(f"Wrote {args.output} with {len(artifacts.workflows)} workflows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
