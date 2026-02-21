from __future__ import annotations

from codeintel.extract import extract_symbols
from codeintel.parser import PythonParser


SAMPLE = """
import os, json
from sys import path as sys_path, version_info

X = 1
Y, Z = 2, 3

class Foo:
    class_var = 1

    def method(self):
        print(X)
        self.helper()

    def helper(self):
        return os.path.join("a", "b")


def bar(a):
    foo = Foo()
    foo.method()
    return foo


class Bar(Foo):
    pass
"""


def test_extracts_functions_classes_variables_calls_imports():
    parser = PythonParser()
    parsed = parser.parse_text(SAMPLE)
    symbols = extract_symbols(parsed)

    func_names = {sym.qualname for sym in symbols["functions"]}
    class_names = {sym.qualname for sym in symbols["classes"]}
    var_names = {sym.name for sym in symbols["variables"]}
    call_names = {call.name for call in symbols["calls"]}

    assert "Foo.method" in func_names
    assert "Foo.helper" in func_names
    assert "bar" in func_names
    assert "Foo" in class_names

    assert "X" in var_names
    assert "class_var" in var_names

    assert "print" in call_names
    assert "Foo.helper" in call_names
    assert "os.path.join" in call_names

    imports = symbols["imports"]
    import_modules = {item.module for item in imports}
    import_names = {name for item in imports for name in item.names}

    assert None in import_modules
    assert "sys" in import_modules
    assert "os" in import_names
    assert "json" in import_names
    assert "path" in import_names
    assert "version_info" in import_names

    inherits = symbols["inherits"]
    inherit_pairs = {(item.class_name, item.bases) for item in inherits}
    assert ("Bar", ("Foo",)) in inherit_pairs
