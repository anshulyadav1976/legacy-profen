"""Tree-sitter based parser for Python sources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from tree_sitter import Parser

from .ts_lang import load_python_language


@dataclass
class ParsedSource:
    tree: object
    source_bytes: bytes


class PythonParser:
    def __init__(self) -> None:
        self._parser = Parser()
        language = load_python_language()
        # tree-sitter API supports either set_language or direct attribute.
        if hasattr(self._parser, "set_language"):
            self._parser.set_language(language)
        else:  # pragma: no cover - legacy API
            self._parser.language = language

    def parse_bytes(self, source_bytes: bytes) -> ParsedSource:
        tree = self._parser.parse(source_bytes)
        return ParsedSource(tree=tree, source_bytes=source_bytes)

    def parse_text(self, source_text: str) -> ParsedSource:
        return self.parse_bytes(source_text.encode("utf-8"))

    def parse_file(self, path: str) -> ParsedSource:
        with open(path, "rb") as handle:
            source_bytes = handle.read()
        return self.parse_bytes(source_bytes)


def parse_files(parser: PythonParser, paths: Iterable[str]) -> Iterable[tuple[str, ParsedSource]]:
    for path in paths:
        yield path, parser.parse_file(path)