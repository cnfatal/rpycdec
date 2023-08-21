from packaging import version

from .ast import Call, Label, Menu, Pass, Say, With
import types


IDENT_CHAR = "    "

# register callback to modify node
node_callbacks = []


def get_renpy_version() -> str:
    # TODO: get renpy version from somewhere
    return version.parse("7.3.5")


def on_node_callback(node, **kwargs):
    """
    modify node here
    """
    for callback in node_callbacks:
        callback(node, **kwargs)


def indent(code: str, level: int = 1) -> str:
    return "".join(
        map(
            lambda x: f"{IDENT_CHAR * level}{x}",
            filter(lambda x: x.strip(), code.splitlines(keepends=True)),
        )
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


def __append_first_line(text, add) -> str:
    lines = text.splitlines()
    if lines:
        v = lines[0]
        i = len(v) - 1 if ":" in v else len(v)
        lines[0] = v[:i] + add + v[i:]
    return "\n".join(lines)


def get_code(node, level: int = 0, **kwargs) -> str:
    if isinstance(node, list):
        rv = []
        skip_next = 0
        for idx, item in enumerate(node):
            if skip_next > 0:
                skip_next -= 1
                continue

            prev = node[idx - 1] if idx > 0 else None
            next = node[idx + 1] if idx < len(node) - 1 else None

            #
            # TODO: it's a hack, fix it later
            if isinstance(item, Say) and not item.interact and isinstance(next, Menu):
                continue
            if isinstance(item, Label) and isinstance(next, Menu):
                if next.statement_start == item:
                    continue  # skip label before menu
            if isinstance(item, With):
                if item.paired:
                    continue
                prevprev = node[idx - 2] if idx - 2 >= 0 else None
                if isinstance(prevprev, With) and prevprev.paired == item.expr:
                    rv[-1] = __append_first_line(rv[-1], f" with {item.expr}")
                    continue
            if isinstance(item, Label) and isinstance(prev, Call):
                rv[-1] = __append_first_line(rv[-1], f" from {item.name}")
                if isinstance(next, Pass):
                    # skip pass after call
                    skip_next += 1
                continue

            kwargs["prev_node"] = prev
            kwargs["next_node"] = next
            rv.append(indent(get_code(item, level=level + 1, **kwargs), level=level))
        return "\n".join(rv)

    # other types
    on_node_callback(node, **kwargs)
    return node.get_code(**kwargs)
