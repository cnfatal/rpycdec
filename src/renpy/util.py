from . import ast
from collections import deque

IDENT_CHAR = "  "


def indent(code: str, level: int = 1) -> str:
    """
    Indent each line of code by a specified level.

    Args:
        code: The string to indent
        level: Number of indentation levels to apply (default: 1)

    Returns:
        The indented string
    """
    if not code:
        return ""
    indent_str = IDENT_CHAR * level
    # add indentation to each non-empty line
    # keep empty lines as they are
    rv = [indent_str + line if line.strip() else line for line in code.split("\n")]
    return "\n".join(rv)


def get_code_properties(props: tuple | dict, newline: bool = False, **kwargs) -> str:
    """
    :param keyword: tuple | dict
    :param newline: bool
    :return: str

    >>> get_code_properties((("a", 1), ("b", 2)))
    a 1 b 2
    >>> get_code_properties((("a", 1), (None, b)), newline=True)
    a 1
    b
    >>> get_code_properties({"a": 1, "b": None})
    a 1
    b None
    """
    list = []
    if isinstance(props, dict):
        props = props.items()
    for prop in props:
        if isinstance(prop, tuple) and len(prop) == 2:
            key, value = prop[0], prop[1]
            valstr = get_code(value, **kwargs)
            if not valstr:
                list.append(f"{key}")
            else:
                list.append(f"{key} {valstr}")
            continue
        else:
            prop_str = " ".join([str(x) for x in prop])
            if not prop_str:
                continue
            list.append(prop_str)
    return ("\n" if newline else " ").join(list)


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
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        rv = []
        items = deque(node)
        while items:
            item = items.popleft()

            if isinstance(item, ast.Say):
                next = items[0] if items else None
                if isinstance(next, ast.Menu):
                    menu = items.popleft()
                    call_kwargs = kwargs.copy()
                    call_kwargs["menu_say"] = item
                    rv.append(get_code(menu, **call_kwargs))
                    continue

            if isinstance(item, ast.Label):
                # [Label,[Say|UserStatement],Menu]
                next = items[0] if items else None
                if isinstance(next, ast.Say) or isinstance(next, ast.UserStatement):
                    next = items[1] if len(items) > 1 else None
                    if isinstance(next, ast.Menu):
                        call_kwargs = kwargs.copy()
                        call_kwargs["menu_label"] = items
                        call_kwargs["menu_say"] = items.popleft()
                        menu = items.popleft()
                        rv.append(get_code(menu, **call_kwargs))
                        continue
                if isinstance(next, ast.Menu):
                    # [Label, Menu]
                    call_kwargs = kwargs.copy()
                    call_kwargs["menu_label"] = item
                    menu = items.popleft()
                    rv.append(get_code(menu, **call_kwargs))
                    continue

            if isinstance(item, ast.With):
                # [ast.With(loc, "None", expr), node, ast.With(loc, expr)]
                expr, paired = attr(item, "expr"), attr(item, "paired")
                if (not expr or expr == "None") and paired:
                    next = items.popleft()
                    rv.append(get_code(next, **kwargs))
                    close_with = items.popleft()
                    rv.append(get_code(close_with, **kwargs))
                    continue

            if isinstance(item, ast.Call):
                # call = [Call, Label?, Pass]
                from_label = None
                # try to pop next Label|Pass
                next = items.popleft() if items else None
                if isinstance(next, ast.Label):
                    from_label = next
                    # pop Pass
                    items.popleft() if items else None

                if from_label is not None:
                    call_kwargs = kwargs.copy()
                    call_kwargs["from_label"] = from_label
                    rv.append(get_code(item, **call_kwargs))
                    continue

            if isinstance(item, ast.Return):
                # return at the end of file is ignored
                if len(node) > 1 and not items and not attr(item, "expression"):
                    continue

            # if isinstance(item, ast.Init):
            # if item.priority == 500:
            #     if len(item.block) == 1 and isinstance(item.block[0], ast.Image):
            #         rv.append(get_code(item.block[0]))
            #         continue

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


def attr(item, key: str) -> str:
    if hasattr(item, key):
        return getattr(item, key)
    return None


def label_code(label: str, child, **kwargs) -> str:
    """
    return a code block with a label
    example:
    >>> label_getcode("label foo", None)
    "label foo"
    >>> label_getcode("label foo", Expression("bar"))
    "label foo:
      bar"
    """
    if not child:
        return label
    return f"{label}:\n{indent(get_code(child, **kwargs))}\n"
