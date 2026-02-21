"""Extract structural symbols from a Python Tree-sitter AST."""

from __future__ import annotations

import ast
from typing import Iterable

from .models import Call, ImportItem, Inheritance, Location, Symbol


ASSIGNMENT_TYPES = {"assignment", "augmented_assignment", "ann_assignment"}
IMPORT_TYPES = {"import_statement", "import_from_statement"}
ASSIGNMENT_OPERATORS = {
    "=",
    "+=",
    "-=",
    "*=",
    "/=",
    "%=",
    "**=",
    "//=",
    "@=",
    "&=",
    "|=",
    "^=",
    ">>=",
    "<<=",
}


def extract_symbols(parsed, path: str | None = None) -> dict:
    tree = parsed.tree
    source_bytes = parsed.source_bytes

    results = {
        "path": path,
        "functions": [],
        "classes": [],
        "variables": [],
        "imports": [],
        "calls": [],
        "inherits": [],
    }

    scope: list[tuple[str, str]] = []

    def walk(node):
        node_type = node.type

        if node_type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = _node_text(name_node, source_bytes)
                qualname = _qualname(scope, name)
                results["functions"].append(
                    Symbol(
                        kind="function",
                        name=name,
                        qualname=qualname,
                        location=_location(name_node),
                    )
                )
                scope.append(("function", name))
                for child in node.children:
                    walk(child)
                scope.pop()
                return

        if node_type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = _node_text(name_node, source_bytes)
                qualname = _qualname(scope, name)
                results["classes"].append(
                    Symbol(
                        kind="class",
                        name=name,
                        qualname=qualname,
                        location=_location(name_node),
                    )
                )
                bases = _class_bases(node, source_bytes)
                if bases:
                    results["inherits"].append(
                        Inheritance(
                            class_name=qualname,
                            bases=tuple(bases),
                            location=_location(node),
                        )
                    )
                scope.append(("class", name))
                for child in node.children:
                    walk(child)
                scope.pop()
                return

        if node_type in ASSIGNMENT_TYPES:
            for target in _assignment_targets(node, source_bytes):
                results["variables"].append(
                    Symbol(
                        kind="variable",
                        name=target,
                        qualname=_qualname(scope, target),
                        location=_location(node),
                    )
                )

        if node_type in IMPORT_TYPES:
            results["imports"].extend(_extract_imports(node, source_bytes))

        if node_type == "call":
            func_node = node.child_by_field_name("function") or node.child(0)
            if func_node is not None:
                name = _node_to_dotted_name(func_node, source_bytes)
                caller = _current_function(scope)
                class_scope = _current_class(scope)
                if name and name.startswith("self.") and class_scope:
                    _, method = name.split(".", 1)
                    name = f"{class_scope}.{method}"
                if name:
                    results["calls"].append(
                        Call(name=name, caller=caller, location=_location(node))
                    )

        for child in node.children:
            walk(child)

    walk(tree.root_node)

    return results


def _qualname(scope: Iterable[tuple[str, str]], name: str) -> str:
    names = [value for _, value in scope]
    if not names:
        return name
    return ".".join([*names, name])


def _current_function(scope: list[tuple[str, str]]) -> str | None:
    for idx in range(len(scope) - 1, -1, -1):
        kind, _ = scope[idx]
        if kind == "function":
            names = [value for _, value in scope[: idx + 1]]
            return ".".join(names)
    return None


def _current_class(scope: list[tuple[str, str]]) -> str | None:
    for idx in range(len(scope) - 1, -1, -1):
        kind, _ = scope[idx]
        if kind == "class":
            names = [value for _, value in scope[: idx + 1]]
            return ".".join(names)
    return None


def _location(node) -> Location:
    line, column = node.start_point
    return Location(line=line + 1, column=column + 1)


def _node_text(node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8")


def _node_to_dotted_name(node, source_bytes: bytes) -> str:
    if node.type == "identifier":
        return _node_text(node, source_bytes)
    if node.type == "dotted_name":
        return _node_text(node, source_bytes)
    if node.type == "attribute":
        obj = node.child_by_field_name("object") or node.child(0)
        attr = node.child_by_field_name("attribute") or node.child(node.child_count - 1)
        if obj is None or attr is None:
            return _node_text(node, source_bytes)
        obj_name = _node_to_dotted_name(obj, source_bytes)
        attr_name = _node_to_dotted_name(attr, source_bytes)
        if obj_name and attr_name:
            return f"{obj_name}.{attr_name}"
    return _node_text(node, source_bytes)


def _collect_identifiers(node, source_bytes: bytes) -> list[str]:
    names: list[str] = []

    if node.type == "identifier":
        return [_node_text(node, source_bytes)]
    if node.type == "attribute":
        return [_node_to_dotted_name(node, source_bytes)]

    for child in node.children:
        names.extend(_collect_identifiers(child, source_bytes))

    return names


def _assignment_targets(node, source_bytes: bytes) -> list[str]:
    for field in ("left", "target", "targets", "name"):
        child = node.child_by_field_name(field)
        if child is not None:
            return _collect_identifiers(child, source_bytes)

    names: list[str] = []
    for child in node.children:
        if child.type in ASSIGNMENT_OPERATORS:
            break
        names.extend(_collect_identifiers(child, source_bytes))

    return names


def _class_bases(node, source_bytes: bytes) -> list[str]:
    for field in ("superclasses", "superclass"):
        bases_node = node.child_by_field_name(field)
        if bases_node is not None:
            return _collect_identifiers(bases_node, source_bytes)

    return []


def _extract_imports(node, source_bytes: bytes) -> list[ImportItem]:
    text = _node_text(node, source_bytes)
    try:
        module = ast.parse(text)
    except SyntaxError:
        return []

    imports: list[ImportItem] = []
    for stmt in module.body:
        if isinstance(stmt, ast.Import):
            names = tuple(alias.name for alias in stmt.names)
            imports.append(
                ImportItem(
                    kind="import",
                    module=None,
                    names=names,
                    location=_location(node),
                )
            )
        elif isinstance(stmt, ast.ImportFrom):
            names = tuple(alias.name for alias in stmt.names)
            imports.append(
                ImportItem(
                    kind="from",
                    module=stmt.module,
                    names=names,
                    location=_location(node),
                )
            )

    return imports
