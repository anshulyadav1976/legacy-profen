"""Migration plan generator using LLM + graph context."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from .mcp_graph import GraphService
from .openrouter_client import (
    OpenRouterConfig,
    OpenRouterRequestError,
    chat_completions,
)


@dataclass(frozen=True)
class MigrationPlanRequest:
    goal: str
    target_stack: str | None = None
    scope: str | None = None
    constraints: list[str] | None = None
    seed_queries: list[str] | None = None
    hops: int = 1
    edge_types: list[str] | None = None
    outline_only: bool = False
    plan_filename: str = "MIGRATION_PLAN.md"
    include_graph_context: bool = True
    max_nodes: int = 50
    max_edges: int = 120


@dataclass(frozen=True)
class MigrationPlanResult:
    model: str
    plan: dict[str, Any] | None
    cursor_prompt: str | None
    plan_markdown: str | None
    raw_text: str | None
    usage: dict[str, Any] | None
    error: str | None
    graph_context: dict[str, Any] | None


def generate_migration_plan(
    service: GraphService,
    request: MigrationPlanRequest,
    config: OpenRouterConfig,
) -> MigrationPlanResult:
    graph_context = None
    if request.include_graph_context:
        graph_context = build_graph_context(
            service,
            seed_queries=request.seed_queries,
            hops=request.hops,
            edge_types=request.edge_types,
            max_nodes=request.max_nodes,
            max_edges=request.max_edges,
        )

    system_prompt = (
        "You are a senior migration architect. Produce a clear, actionable migration plan "
        "for a legacy codebase. Output must be valid JSON only. "
        "The plan should be specific, phased, include risks, validation, and Mermaid diagrams."
    )

    user_prompt = build_user_prompt(request, graph_context)

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
        error_message = _format_openrouter_error(exc)
        # Retry without JSON mode for models that don't support response_format.
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
                error_message = _format_openrouter_error(retry_exc)
    except Exception as exc:  # pragma: no cover - unexpected
        error_message = str(exc)

    content = _extract_content(response)
    plan_data = None
    error = error_message
    cursor_prompt = None
    plan_markdown = None

    if content:
        plan_data, parse_error = _parse_plan_json(content)
        if plan_data is None and parse_error:
            repaired = _repair_json(content, config)
            if repaired:
                plan_data, parse_error = _parse_plan_json(repaired)
        if plan_data is None and parse_error:
            error = parse_error

        if isinstance(plan_data, dict):
            cursor_prompt = plan_data.get("cursor_prompt")
            plan_markdown = plan_data.get("plan_markdown")
            if plan_markdown is None and plan_data.get("plan_markdown_lines"):
                plan_markdown = "\n".join(plan_data.get("plan_markdown_lines", []))
    else:
        if error is None:
            error = "No content returned from model"

    usage = response.get("usage") if isinstance(response, dict) else None

    return MigrationPlanResult(
        model=config.model,
        plan=plan_data,
        cursor_prompt=cursor_prompt,
        plan_markdown=plan_markdown,
        raw_text=content,
        usage=usage,
        error=error,
        graph_context=graph_context,
    )


def _extract_content(response: dict[str, Any] | None) -> str | None:
    if not response or not isinstance(response, dict):
        return None
    choices = response.get("choices")
    if not choices:
        return None
    first = choices[0] if isinstance(choices, list) else None
    if not isinstance(first, dict):
        return None
    message = first.get("message", {})
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    return content if isinstance(content, str) else None


def _parse_plan_json(content: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return json.loads(content), None
    except json.JSONDecodeError as exc:
        candidate = _extract_json_candidate(content)
        if candidate:
            try:
                return json.loads(candidate), None
            except json.JSONDecodeError as exc2:
                return None, f"Failed to parse JSON: {exc2}"
        return None, f"Failed to parse JSON: {exc}"


def _extract_json_candidate(content: str) -> str | None:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return content[start : end + 1]


def _repair_json(content: str, config: OpenRouterConfig) -> str | None:
    repair_prompt = (
        "Fix the following output so it is valid JSON ONLY. "
        "Do not include markdown or explanations. Preserve all fields.\n\n"
        + content
    )
    try:
        response = chat_completions(
            config,
            messages=[
                {"role": "system", "content": "You are a JSON repair tool."},
                {"role": "user", "content": repair_prompt},
            ],
            response_format=None,
        )
    except OpenRouterRequestError:
        return None
    return _extract_content(response)


def build_graph_context(
    service: GraphService,
    seed_queries: list[str] | None,
    hops: int,
    edge_types: list[str] | None,
    max_nodes: int,
    max_edges: int,
) -> dict[str, Any]:
    stats = service.stats(limit=8)
    context: dict[str, Any] = {
        "metadata": service.metadata(),
        "stats": stats,
    }

    subgraphs = []
    if seed_queries:
        for query in seed_queries:
            subgraph = service.subgraph(
                query,
                hops=hops,
                direction="both",
                edge_types=edge_types,
                limit=max_nodes,
            )
            nodes = subgraph.get("nodes", [])[:max_nodes]
            edges = subgraph.get("edges", [])[:max_edges]
            subgraphs.append(
                {
                    "query": query,
                    "nodes": nodes,
                    "edges": edges,
                }
            )
    context["subgraphs"] = subgraphs
    return context


def build_user_prompt(request: MigrationPlanRequest, graph_context: dict[str, Any] | None) -> str:
    constraints = request.constraints or []
    seed_queries = request.seed_queries or []

    prompt = {
        "goal": request.goal,
        "target_stack": request.target_stack,
        "scope": request.scope,
        "constraints": constraints,
        "seed_queries": seed_queries,
        "outline_only": request.outline_only,
        "plan_filename": request.plan_filename,
        "graph_context": graph_context,
        "output_schema": {
            "title": "string",
            "summary": "string",
            "assumptions": ["string"],
            "scope": "string",
            "phases": [
                {
                    "name": "string",
                    "goal": "string",
                    "steps": ["string"],
                    "deliverables": ["string"],
                    "checks": ["string"],
                }
            ],
            "risks": ["string"],
            "validation": ["string"],
            "checklist": ["string"],
            "mermaid": [
                {"title": "string", "diagram": "string"}
            ],
            "cursor_prompt": "string",
            "plan_markdown": "string",
            "plan_markdown_lines": ["string"],
        },
        "instructions": (
            "Return a JSON object matching output_schema. "
            "Make cursor_prompt explicitly instruct the agent to create the plan file "
            "named plan_filename using Markdown headings, checklists, and Mermaid code fences. "
            "Include at least one flowchart and one sequence or graph diagram. "
            "If outline_only is true, keep phases and plan_markdown short. "
            "If plan_markdown would be long, prefer plan_markdown_lines to avoid escaping issues."
        ),
    }
    return json.dumps(prompt, indent=2)


def resolve_openrouter_config() -> OpenRouterConfig:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    model = os.getenv("OPENROUTER_MODEL") or "google/gemini-1.5-pro"
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    app_url = os.getenv("OPENROUTER_APP_URL")
    app_title = os.getenv("OPENROUTER_APP_TITLE") or "JWST Code Graph MCP"
    timeout_seconds = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "60"))

    return OpenRouterConfig(
        api_key=api_key,
        model=model,
        base_url=base_url,
        app_url=app_url,
        app_title=app_title,
        timeout_seconds=timeout_seconds,
    )


def _format_openrouter_error(exc: OpenRouterRequestError) -> str:
    payload = exc.payload
    if isinstance(payload, dict):
        message = payload.get("error") or payload.get("message") or payload
        return f"OpenRouter error ({exc.status_code}): {message}"
    return f"OpenRouter error ({exc.status_code}): {payload}"
