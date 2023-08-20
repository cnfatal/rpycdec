import os
import pickle
import pickletools
import struct
import types
import zlib



IDENT_COUNT = 2
IDENT_CHAR = " "


def indent(code: str, level: int = 1) -> str:
    return "".join(
        [
            f"{IDENT_CHAR * IDENT_COUNT * level}{line}"
            for line in code.splitlines(keepends=True)
        ]
    )


def get_code_properties(props: tuple | dict, newline: bool = False) -> str:
    """
    :param keyword: tuple | dict
    :param newline: bool
    :return: str

    >>> get_code_properties((("a", 1), ("b", 2)))
    "a 1 b 2"
    >>> get_code_properties((("a", 1), (None, b)), newline=True)
    "a 1\\nb"
    """
    list = []
    if isinstance(props, dict):
        props = props.items()
    for k, v in props:
        if v is None:
            list.append(k)
        else:
            list.append(f"{k} {v}")
    return ("\n" if newline else " ").join(list)


def get_code_section(sec: str, name=None, arguments=None) -> str:
    """
    :param sec: str | None
    :param name: str
    :param arguments: tuple | dict
    :return: str
    """
    if not sec:
        sec = ""
    if not name and not arguments:
        return sec
    return f"{sec} {name}{get_code(arguments)}"


def get_code_parameters(params) -> str:
    """
    :param params: tuple | dict
    :return: str

    >>> get_code_parameters((("a", 1), ("b", 2)))
    "(a=1, b=2)"

    >>> get_code_parameters((("a", 1), (None, b)))
    "(a=1, b)"

    >>> get_code_parameters()
    ""
    """
    if not params:
        return ""
    rv = []
    for k, v in params:
        if v is None:
            rv.append(k)
        else:
            rv.append(f"{k}={get_code(v)}")
    s = ", ".join(rv)
    return f"({s})"


def parse_store_name(name: str) -> str:
    if name == "store":
        return ""
    return name.lstrip("store.")


def get_code(node, level: int = 0, **kwargs) -> str:
    rv = []
    if isinstance(node, list):
        for item in node:
            rv.append(indent(get_code(item, level=level + 1), level=level))
        return "\n".join(rv)
    elif isinstance(node, str):
        return node
    elif isinstance(node, (int, str, float, bool)):
        return str(node)
    elif isinstance(node, (dict, map)):
        return "{" + ", ".join([get_code(item) for item in node]) + "}"
    elif isinstance(node, tuple):
        return "(" + ", ".join([get_code(item) for item in node]) + ")"
    elif isinstance(node, types.NoneType):
        return "None"
    else:
        return node.get_code(**kwargs)
