from . import ast

IDENT_CHAR = "    "


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


def __append_first_line(text, add) -> str:
    lines = text.splitlines()
    if lines:
        v = lines[0]
        i = len(v) - 1 if ":" in v else len(v)
        lines[0] = v[:i] + add + v[i:]
    return "\n".join(lines)


def get_code(node, **kwargs) -> str:
    """
    Parameters
    ----------
    node : ast.Node
    kwargs : dict
        indent : int
            space indent level
        modifier : Callable[[ast.Node], ast.Node]
            modify node before get code

    Returns
    -------
    str
        generated code

    Raises
    ------
    NotImplementedError
        if node type is not implemented or some attributes unable to handle.

    """
    if isinstance(node, list):
        rv = []
        skip_next = 0
        for idx, item in enumerate(node):
            if skip_next > 0:
                skip_next -= 1
                continue

            prev = node[idx - 1] if idx > 0 else None
            next = node[idx + 1] if idx < len(node) - 1 else None

            # TODO: it's a hack, fix it later
            if (
                isinstance(item, ast.Say)
                and not item.interact
                and isinstance(next, ast.Menu)
            ):
                continue
            if isinstance(item, ast.Label) and isinstance(next, ast.Menu):
                if next.statement_start == item:
                    continue  # skip label before menu
            if isinstance(item, ast.With):
                if item.paired:
                    continue
                prevprev = node[idx - 2] if idx - 2 >= 0 else None
                if isinstance(prevprev, ast.With) and prevprev.paired == item.expr:
                    rv[-1] = __append_first_line(rv[-1], f" with {item.expr}")
                    continue
            if isinstance(item, ast.Label) and isinstance(prev, ast.Call):
                rv[-1] = __append_first_line(rv[-1], f" from {item.name}")
                if isinstance(next, ast.Pass):
                    # skip pass after call
                    skip_next += 1
                continue
            rv.append(get_code(item, **kwargs))
        return "\n".join(rv)

    # modify node before get code
    modifier = kwargs.get("modifier")
    if modifier:
        modifier(node, **kwargs)
    return node.get_code(**kwargs)


def get_block_code(node, **kwargs) -> str:
    """
    https://www.renpy.org/doc/html/layeredimage.html#layeredimage
    """
    if isinstance(node, list):
        return "\n".join(map(lambda x: get_block_code(x, **kwargs), node))
    lines = []
    if isinstance(node, tuple) and len(node) >= 4:
        _, _, code, block = node
        lines.append(code)
        lines.append(indent(get_block_code(block, **kwargs)))
    else:
        raise NotImplementedError
    return "\n".join(lines)
