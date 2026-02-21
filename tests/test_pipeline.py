from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from codeintel.pipeline import build_graph_from_root, resolve_root


def test_resolve_root_prefers_existing_candidate():
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        candidate = root / "jwst-main"
        candidate.mkdir()
        original_cwd = Path.cwd()
        try:
            # Force cwd to our temp dir for predictable resolution.
            import os

            os.chdir(root)
            resolved = resolve_root(None)
        finally:
            os.chdir(original_cwd)

    assert resolved == candidate


def test_build_graph_from_root_saves_json():
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "pkg").mkdir()
        (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        (root / "pkg" / "mod.py").write_text(
            """
class Foo:
    def method(self):
        return 1


def bar():
    foo = Foo()
    return foo.method()
""",
            encoding="utf-8",
        )

        out_path = root / "graph.json"
        graph = build_graph_from_root(root, out_path)

        assert out_path.exists()
        assert graph.number_of_nodes() > 0
        assert graph.number_of_edges() > 0