"""Dump a compiled Ren'Py script.

Exposed as ``rpycdec dump``, and used by the round-trip tests as their oracle.

Two views over the same tree:

* :func:`dump` keeps everything the script carries -- including filenames and
  line numbers -- which is what you want when inspecting a script or reporting
  an issue.
* :func:`canonical` strips what no decompiler can preserve (position and node
  identity) and normalizes python snippets, leaving the shape two scripts can
  be compared on. :func:`diff` compares that shape.
"""

import ast as pyast
import difflib
import pprint
import re

from renpy import ast as fake_ast
from rpycdec import stmts

# names Ren'Py derives from where a statement sits, e.g. `script.rpy_12`
GENERATED_NAME = re.compile(r"(\.rpym?c?)_\d+(?:_\d+)*")

# Where a statement came from, and who it is. Both change on every compilation,
# so comparing them would only produce noise.
LOCATION_ATTRS = frozenset(
    {
        "filename",
        "linenumber",
        "column",
        "loc",
        "location",
        "newloc",
        "serial",
        "name_version",
        "name_serial",
    }
)

# `next` pulls the remainder of the script into every node. Blocks already
# carry the order, keeping it turns a dump into quadratic noise.
ORDER_ATTRS = frozenset({"next"})


def normalize_python(source: str) -> str:
    """Canonical form of a python source snippet.

    Compares parsed python when possible, so that pure formatting differences
    (blank lines, indentation) do not count as a difference. Falls back to
    stripped text for sources this interpreter cannot parse, e.g. the python 2
    snippets stored in Ren'Py 7 scripts.
    """
    if not source:
        return ""
    try:
        return _dump_pyast(pyast.parse(source))
    except SyntaxError:
        lines = [line.strip() for line in source.strip().splitlines()]
        return "\n".join(line for line in lines if line)


def _dump_pyast(node) -> str:
    if isinstance(node, pyast.AST):
        fields = []
        for field, value in pyast.iter_fields(node):
            # 'lineno'/'col_offset' and friends move whenever the generated
            # file differs by a line, which says nothing about correctness.
            if field in ("lineno", "col_offset", "end_lineno", "end_col_offset"):
                continue
            fields.append(f"{field}={_dump_pyast(value)}")
        return f"{type(node).__name__}({','.join(fields)})"
    if isinstance(node, list):
        return "[" + ",".join(_dump_pyast(item) for item in node) + "]"
    return repr(node)


def _pycode_source(obj) -> str:
    state = getattr(obj, "state", None)
    source = getattr(obj, "source", None)
    if isinstance(state, dict):
        source = state.get("source") or state.get("code") or source
    elif isinstance(state, (list, tuple)) and len(state) > 1:
        source = state[1]
    return source if isinstance(source, str) else ""


def dump(obj, active=()):
    """Full fidelity representation of an AST (sub)tree, minus node chaining.

    Cycle-safe: node graphs reference each other, e.g. ``Say.statement_start``
    points back to the ``Menu`` it belongs to.
    """
    if isinstance(obj, fake_ast.PyCode):
        return {
            "PyCode": {
                "source": _pycode_source(obj),
                "state": dump(getattr(obj, "state", None), active),
            }
        }
    if obj is None or isinstance(obj, (bool, int, float)):
        return obj
    if isinstance(obj, fake_ast.PyExpr):
        return str(obj)
    if isinstance(obj, (str, bytes)):
        return obj.decode("utf-8", "surrogateescape") if isinstance(obj, bytes) else obj
    if id(obj) in active:
        return f"<cycle {type(obj).__name__}>"
    nested = active + (id(obj),)
    if isinstance(obj, (list, tuple)):
        return [dump(item, nested) for item in obj]
    if isinstance(obj, dict):
        return {str(key): dump(value, nested) for key, value in obj.items()}
    if hasattr(obj, "__dict__"):
        attrs = {}
        for key, value in vars(obj).items():
            if key in ORDER_ATTRS or key.startswith("__"):
                continue
            value = dump(value, nested)
            # False is kept: a round trip that turns a missing attribute into
            # an explicit False changed the script, even though both read as
            # "off". The rest are just absent values.
            if value in (None, {}, "", []) and value is not False:
                continue
            attrs[key] = value
        return {type(obj).__name__: attrs}
    return repr(obj)


def _is_source_row(value) -> bool:
    """A (filename, linenumber, ..) row, as a user statement records its lines."""
    return (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], str)
        and value[0].endswith((".rpy", ".rpym", ".rpyc", ".rpymc"))
        and isinstance(value[1], int)
    )


def _normalize_generated_name(value: str) -> str:
    """`game/script.rpy_12` becomes `game/script.rpy_<line>`.

    Ren'Py builds such names out of the position a statement was written at,
    which no decompiler can keep.
    """
    return GENERATED_NAME.sub(r"\1_<line>", value)


def _normalize_strings(value):
    if isinstance(value, str):
        return _normalize_generated_name(value)
    if isinstance(value, list):
        return [_normalize_strings(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_strings(item) for key, item in value.items()}
    return value


def canonical(dumped):
    """Projection of a :func:`dump` that two scripts can be compared on.

    Drops position and node identity, and reduces python blocks to their parsed
    form. ``_name`` holds either an author chosen name (labels) or a
    (filename, version, serial) identity tuple, so only the latter goes.
    """
    if isinstance(dumped, dict):
        if list(dumped) == ["PyCode"]:
            return {"PyCode": normalize_python(dumped["PyCode"].get("source", ""))}
        # a user statement keeps the arguments its parser derived, and some of
        # those are positions: the line it started on, names built from it
        located = "filename" in dumped
        result = {}
        for key, value in dumped.items():
            if key in LOCATION_ATTRS:
                continue
            if key == "_name" and not isinstance(value, str):
                continue
            if located and key == "number":
                result[key] = "<line>"
                continue
            value = canonical(value)
            result[key] = _normalize_strings(value) if located else value
        return result
    if isinstance(dumped, list):
        if _is_source_row(dumped):
            return ["<file>", "<line>"] + [canonical(item) for item in dumped[2:]]
        return [canonical(item) for item in dumped]
    return dumped


def dump_file(path: str):
    """Full fidelity dump of a .rpyc/.rpymc file."""
    return dump(stmts.load_file(path))


def diff(
    dump_a, dump_b, fromfile: str = "a", tofile: str = "b", context: int = 3
) -> str:
    """Unified diff of two dumps, compared on their canonical form."""
    text_a = pprint.pformat(canonical(dump_a), width=110).splitlines()
    text_b = pprint.pformat(canonical(dump_b), width=110).splitlines()
    return "\n".join(
        difflib.unified_diff(
            text_a, text_b, fromfile=fromfile, tofile=tofile, lineterm="", n=context
        )
    )


def first_difference(dump_a, dump_b, path: str = "") -> str:
    """Path of the first difference between two dumps, "" when they match.

    Used to say *what* differs, not to compare: the round trip test compares
    the canonical forms instead.
    """
    if type(dump_a) is not type(dump_b):
        return path or "<root>"
    if isinstance(dump_a, dict):
        for key in dump_a:
            if key not in dump_b:
                return f"{path}.{key}"
            found = first_difference(dump_a[key], dump_b[key], f"{path}.{key}")
            if found:
                return found
        for key in dump_b:
            if key not in dump_a:
                return f"{path}.{key}"
        return ""
    if isinstance(dump_a, list):
        if len(dump_a) != len(dump_b):
            return f"{path}[]"
        for index, (left, right) in enumerate(zip(dump_a, dump_b)):
            found = first_difference(left, right, f"{path}[{index}]")
            if found:
                return found
        return ""
    return path if dump_a != dump_b else ""
