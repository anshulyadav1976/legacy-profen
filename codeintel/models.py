"""Lightweight data models for extracted symbols."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    line: int
    column: int


@dataclass(frozen=True)
class Symbol:
    kind: str
    name: str
    qualname: str
    location: Location


@dataclass(frozen=True)
class Call:
    name: str
    caller: str | None
    location: Location


@dataclass(frozen=True)
class ImportItem:
    kind: str  # import | from
    module: str | None
    names: tuple[str, ...]
    location: Location


@dataclass(frozen=True)
class Inheritance:
    class_name: str
    bases: tuple[str, ...]
    location: Location
