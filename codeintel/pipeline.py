"""End-to-end pipeline for building a graph from a repository."""

from __future__ import annotations

import argparse
from pathlib import Path

from .extract import extract_symbols
from .file_walker import iter_python_files
from .graph import build_graph
from .parser import PythonParser
from .storage import save_graph


def _candidate_roots() -> tuple[Path, Path]:
    return (
        Path.cwd() / "jwst-main",
        Path("/jwst-main"),
    )


def resolve_root(root: str | None) -> Path:
    if root:
        return Path(root)
    for candidate in _candidate_roots():
        if candidate.exists():
            return candidate
    return _candidate_roots()[0]


def build_graph_from_root(
    root: str | Path,
    output_path: str | Path | None = None,
    max_files: int | None = None,
) -> object:
    root_path = Path(root)
    files = iter_python_files(root_path)
    if max_files is not None:
        files = files[:max_files]

    parser = PythonParser()
    extracted = []
    for path in files:
        parsed = parser.parse_file(path)
        extracted.append(extract_symbols(parsed, path=path))

    graph = build_graph(extracted)

    if output_path:
        save_graph(graph, output_path)

    return graph


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a NetworkX graph from a codebase")
    parser.add_argument("--root", help="Root directory of the codebase")
    parser.add_argument(
        "--output",
        default="jwst_graph.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Limit number of files parsed (for quick checks)",
    )
    args = parser.parse_args()

    root = resolve_root(args.root)
    graph = build_graph_from_root(root, args.output, args.max_files)
    print(graph.number_of_nodes(), graph.number_of_edges())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
