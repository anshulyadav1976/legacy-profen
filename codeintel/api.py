"""FastAPI service to build a graph JSON from an uploaded repo archive."""

from __future__ import annotations

import argparse
import zipfile
from urllib.parse import urlparse
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from networkx.readwrite import json_graph

from .pipeline import build_graph_from_root


app = FastAPI(title="CodeIntel Graph API")


def _extract_zip_bytes(zip_bytes: bytes, target_dir: Path) -> Path:
    if not zip_bytes:
        raise HTTPException(status_code=400, detail="Empty archive.")

    archive_path = target_dir / "repo.zip"
    archive_path.write_bytes(zip_bytes)

    try:
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(target_dir / "repo")
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid zip archive.") from exc

    extracted_root = target_dir / "repo"
    entries = [entry for entry in extracted_root.iterdir() if entry.name not in {".", ".."}]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return extracted_root


def _normalize_github_repo_url(repo_url: str) -> list[str]:
    parsed = urlparse(repo_url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="repo_url must be http/https.")

    if repo_url.lower().endswith(".zip"):
        return [repo_url]

    host = parsed.netloc.lower()
    if host not in {"github.com", "www.github.com"}:
        raise HTTPException(
            status_code=400,
            detail="repo_url must be a GitHub repo URL or direct zip link.",
        )

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        raise HTTPException(status_code=400, detail="repo_url must be a repo or zip link.")

    owner = path_parts[0]
    repo = path_parts[1].removesuffix(".git")
    branch = None
    if "tree" in path_parts:
        tree_idx = path_parts.index("tree")
        if tree_idx + 1 < len(path_parts):
            branch = path_parts[tree_idx + 1]

    if "archive" in path_parts and "refs" in path_parts:
        return [repo_url]

    if branch:
        return [f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"]

    default_branch = _resolve_github_default_branch(owner, repo)
    if default_branch:
        return [f"https://github.com/{owner}/{repo}/archive/refs/heads/{default_branch}.zip"]

    return [
        f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip",
        f"https://github.com/{owner}/{repo}/archive/refs/heads/master.zip",
    ]


def _resolve_github_default_branch(owner: str, repo: str) -> str | None:
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "codeintel-graph-api",
    }
    try:
        response = httpx.get(api_url, headers=headers, timeout=20.0)
    except httpx.RequestError:
        return None
    if response.status_code != 200:
        return None
    try:
        payload = response.json()
    except Exception:
        return None
    default_branch = payload.get("default_branch")
    if isinstance(default_branch, str) and default_branch:
        return default_branch
    return None


def _download_repo_zip(repo_url: str) -> bytes:
    candidates = _normalize_github_repo_url(repo_url)
    last_status = None
    for url in candidates:
        try:
            response = httpx.get(url, timeout=60.0)
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Failed to reach {url}.") from exc
        if response.status_code == 200:
            return response.content
        if response.status_code == 404:
            last_status = response.status_code
            continue
        last_status = response.status_code
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download repo zip (status {response.status_code}).",
        )

    raise HTTPException(
        status_code=400,
        detail=(
            f"Failed to download repo zip (status {last_status}). "
            f"Tried: {', '.join(candidates)}"
        ),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/parse")
def parse_repo(
    file: UploadFile | None = File(default=None),
    repo_url: str | None = Query(default=None),
    max_files: int | None = None,
) -> JSONResponse:
    if file is None and not repo_url:
        raise HTTPException(
            status_code=400, detail="Provide either a zip file upload or repo_url."
        )

    with TemporaryDirectory() as temp_dir:
        if repo_url:
            zip_bytes = _download_repo_zip(repo_url)
        else:
            if not file or not file.filename or not file.filename.lower().endswith(".zip"):
                raise HTTPException(status_code=400, detail="Upload a .zip archive.")
            zip_bytes = file.file.read()
        root = _extract_zip_bytes(zip_bytes, Path(temp_dir))
        graph = build_graph_from_root(root, output_path=None, max_files=max_files)
        data = json_graph.node_link_data(graph)
        return JSONResponse(content=data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the CodeIntel graph API server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=9000, help="Bind port")
    args = parser.parse_args()

    import uvicorn

    uvicorn.run("codeintel.api:app", host=args.host, port=args.port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
