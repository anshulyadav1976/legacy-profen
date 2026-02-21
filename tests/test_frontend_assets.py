from __future__ import annotations

from pathlib import Path


def test_frontend_assets_exist():
    root = Path(__file__).resolve().parents[1]
    frontend = root / "frontend"
    index_file = frontend / "index.html"
    styles_file = frontend / "styles.css"
    app_file = frontend / "app.js"

    assert index_file.exists()
    assert styles_file.exists()
    assert app_file.exists()

    content = index_file.read_text(encoding="utf-8")
    assert "cytoscape" in content
    assert "JWST Knowledge Graph" in content
    assert "moduleFilter" in content
    assert "classFilter" in content
    assert "clusterSelect" in content
    assert "workflowTab" in content
    assert "workflowPath" in content
