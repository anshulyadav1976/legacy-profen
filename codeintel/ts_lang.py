"""Tree-sitter language loader helpers."""

from __future__ import annotations


def load_python_language():
    """Return a Tree-sitter Language object for Python."""
    from tree_sitter import Language

    try:
        import tree_sitter_python as tspython
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError("tree_sitter_python is not installed") from exc

    # tree_sitter_python exposes either `language` (callable or object) or `LANGUAGE`.
    if hasattr(tspython, "language"):
        lang = tspython.language
        lang = lang() if callable(lang) else lang
    elif hasattr(tspython, "LANGUAGE"):
        lang = tspython.LANGUAGE
    else:
        raise RuntimeError("Unsupported tree_sitter_python API")

    # tree_sitter_python may return a PyCapsule; wrap to Language if needed.
    if isinstance(lang, Language):
        return lang
    return Language(lang)
