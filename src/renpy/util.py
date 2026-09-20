import ast as pyast  # the real one: the fake renpy.ast is imported below
import warnings
from collections import deque
from typing import Any

from . import ast

IDENT_CHAR = "    "

# Marks a line whose indentation is part of a value renpy recorded as written.
# `indent` leaves such lines alone, so text that must keep its own indentation
# survives being nested deeper, and `rpycdec.utils.write_file` strips the marks
# before the file is written.
VERBATIM = "\x00"


def verbatim(code: str, lines=None) -> str:
    """Marks lines `indent` must not shift, all but the first by default."""
    parts = code.split("\n")
    marked = range(2, len(parts) + 1) if lines is None else lines
    return "\n".join(
        VERBATIM + part if number in marked else part
        for number, part in enumerate(parts, start=1)
    )


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
    rv = []
    for line in code.split("\n"):
        if line.startswith(VERBATIM):
            # written as it was recorded: keep its indentation, and keep the
            # mark, so that nesting it deeper still leaves it alone
            rv.append(line)
        elif line.strip():
            rv.append(indent_str + line)
        else:
            rv.append(line)
    return "\n".join(rv)


def string_continuation_lines(source: str) -> set[int]:
    """Lines of a python block that must not be moved when it is written out.

    Ren'Py stores a python block dedented, but the lines inside a multi line
    string may keep the indentation of the file they were written in, and
    shifting those would change the string itself -- a docstring, for one -- on
    every round trip. That is what it does for a string with a blank line in
    it, and what versions up to 8.2 did for every string.

    Whether a string was stored as written can be told from the source itself:
    when the closing quotes end up deeper than the opening ones, that
    indentation came from the file rather than from the string's own layout.
    """
    try:
        with warnings.catch_warnings():
            # python sources here are not ours to lint
            warnings.simplefilter("ignore")
            tree = pyast.parse(source)
    except (SyntaxError, ValueError):
        # python 2 sources, as stored by Ren'Py 7, do not parse here
        return set()

    lines = source.split("\n")
    kept: set[int] = set()
    for node in pyast.walk(tree):
        if not isinstance(node, pyast.Constant) or not isinstance(node.value, str):
            continue
        if "\n" not in node.value:
            continue
        end = getattr(node, "end_lineno", None)
        if not end:
            continue
        span = range(node.lineno + 1, end + 1)
        blank = any(not lines[number - 1].strip() for number in span)
        if blank or _leading_spaces(lines[end - 1]) > _leading_spaces(lines[node.lineno - 1]):
            kept.update(span)
    return kept


def _leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip())


def indent_python(source: str, level: int = 1) -> str:
    """Indent a python block, leaving multi line string contents alone.

    Ren'Py stores a python block dedented, except for the lines inside a multi
    line string, which keep the indentation they had in the file. Shifting
    those again would change the string, a docstring for one, on every round
    trip.
    """
    if not source:
        return ""
    # the leading blank lines are renpy's line number padding: writing them out
    # would make the next compilation add its own
    source = source.lstrip("\n")
    return indent(verbatim(source, string_continuation_lines(source)), level)





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
            # a property sits on a single line, so an unknown value has to
            # degrade to a one line comment
            valstr = get_code(value, **{**kwargs, "inline": True})
            # a value spanning several lines keeps the indentation renpy
            # recorded for them
            valstr = verbatim(valstr)
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

            # [Say|UserStatement?, Menu]
            if isinstance(item, ast.Say) or isinstance(item, ast.UserStatement):
                next = items[0] if items else None
                if isinstance(next, ast.Menu) and attr(next, "statement_start") == item:
                    menu = items.popleft()
                    call_kwargs = kwargs.copy()
                    call_kwargs["menu_say"] = item
                    rv.append(get_code(menu, **call_kwargs))
                    continue

            # [Label, Say|UserStatement?, Menu]
            if isinstance(item, ast.Label):
                next = items[0] if items else None
                # [Label, Say|UserStatement, Menu]
                if isinstance(next, ast.Say) or isinstance(next, ast.UserStatement):
                    next_next = items[1] if len(items) > 1 else None
                    if (
                        isinstance(next_next, ast.Menu)
                        and attr(next_next, "statement_start") == item
                    ):
                        say = items.popleft()
                        menu = items.popleft()
                        call_kwargs = kwargs.copy()
                        call_kwargs["menu_label"] = item
                        call_kwargs["menu_say"] = say
                        rv.append(get_code(menu, **call_kwargs))
                        continue
                # [Label, Menu]
                if isinstance(next, ast.Menu) and attr(next, "statement_start") == item:
                    menu = items.popleft()
                    call_kwargs = kwargs.copy()
                    call_kwargs["menu_label"] = item
                    rv.append(get_code(menu, **call_kwargs))
                    continue

            # [TranslateString, TranslateString, ..]
            if isinstance(item, ast.TranslateString):
                language = attr(item, "language")
                run = [item]
                while (
                    items
                    and isinstance(items[0], ast.TranslateString)
                    and attr(items[0], "language") == language
                ):
                    run.append(items.popleft())
                rv.append(ast.translate_strings_code(run, **kwargs))
                continue

            if isinstance(item, ast.With):
                # some node quoted by two ast.With if has with suffix expr, the sdk snippet:
                #
                # renpy.parser.parse_with(node):
                #   if not "with":
                #       return node
                #       expr = simple_expression
                #   return [ast.With(loc, "None", paired=expr), node, ast.With(loc, expr)]
                #
                # - ast.Scene
                # - ast.Show
                # - ast.Hide
                expr, paired = attr(item, "expr"), attr(item, "paired")
                if (not expr or expr == "None") and paired:
                    next_next = items[1] if len(items) > 1 else None
                    if (
                        isinstance(next_next, ast.With)
                        and attr(next_next, "expr") == paired
                    ):
                        node = items.popleft()
                        close_with = items.popleft()
                        call_kwargs = kwargs.copy()
                        call_kwargs.update({"with_expr": attr(close_with, "expr")})
                        rv.append(get_code(node, **call_kwargs))
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

            # Returns are not special here: a block that ends in two of them has
            # two, and the file's own trailing return is dropped by
            # rpycdec.decompile.trim_implicit_return, which is the layer that
            # knows the list is a whole file.

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


def get_block_code(node, level: int = 1, **kwargs) -> str:
    """Renders the source lines a custom statement recorded for its block.

    A row is ``(filename, linenumber, code, subblock)``, and `code` is the line
    as the author wrote it. A statement that spans several lines keeps the
    indentation of its continuation lines, so only the first line of a row is
    indented here.

    https://www.renpy.org/doc/html/layeredimage.html#layeredimage
    """
    if isinstance(node, list):
        return "\n".join(
            get_block_code(item, level=level, **kwargs) for item in node
        )
    if isinstance(node, tuple):
        if len(node) == 5:
            _, _, _, code, block = node
        elif len(node) == 4:
            _, _, code, block = node
        else:
            raise NotImplementedError
        # the continuation lines of a row are the ones renpy recorded as written
        rv = [IDENT_CHAR * level + verbatim(code)]
        if block:
            rv.append(get_block_code(block, level=level + 1, **kwargs))
        return "\n".join(rv)
    raise NotImplementedError


def attr(item: Any, key: str, required: bool = False) -> Any:
    """Reads `key` off a dict or a node, tolerating absent attributes.

    Nodes come out of a pickle written by whichever Ren'Py version compiled
    the script, so their attributes vary by version and missing ones are
    normal: over the SDK scripts roughly one in nine reads finds nothing, e.g.
    `SLDisplayable.tag` looks like this ~890 times and `Define.priority` ~56.

    Pass `required=True` when a node without that attribute cannot be rendered
    correctly, so a wrong guess fails loudly instead of emitting code that is
    quietly missing a clause.
    """
    if isinstance(item, dict):
        if key in item:
            return item[key]
    elif hasattr(item, key):
        return getattr(item, key)
    if required:
        raise AttributeError(f"{type(item).__name__} has no {key}")
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
    return f"{label}:\n{indent(get_code(child, **kwargs))}"
