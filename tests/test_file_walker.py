from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from codeintel.file_walker import iter_python_files


def test_iter_python_files_filters_non_py():
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "a.py").write_text("print('a')", encoding="utf-8")
        (root / "b.txt").write_text("nope", encoding="utf-8")
        sub = root / "sub"
        sub.mkdir()
        (sub / "c.py").write_text("print('c')", encoding="utf-8")

        matches = iter_python_files(root)
        names = {Path(path).name for path in matches}

        assert names == {"a.py", "c.py"}