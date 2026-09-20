"""Fake reimplementation of renpy.test.testast, for decompiling `testcase`.

Two incompatible generations of this module exist and both pickle under the
same class names, so each class here carries both shapes and tells them apart
per instance:

* Ren'Py <= 8.4.1 -- `testcase NAME:` holds a `Block` of clauses (`click`,
  `type`, `scroll`, `move`, `drag`, `run`, `pause`, `label`), each optionally
  followed by `until`.
* Ren'Py >= 8.5 -- `testcase NAME:` / `testsuite NAME:` hold a `TestCase` /
  `TestSuite` of statements driven by `Selector`s and `Condition`s.

https://www.renpy.org/doc/html/testcases.html
"""

import re
import textwrap

from .. import translation, util

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Hook keywords as they are written, keyed by TestHook.name (renpy.test.types)
HOOK_DEFAULTS = {
    "setup": 0,
    "before_testsuite": 0,
    "before_testcase": -1,
    "after_testcase": -1,
    "after_testsuite": 0,
    "teardown": 0,
}
HOOK_ORDER = (
    "setup",
    "before_testsuite",
    "before_testcase",
    "after_testcase",
    "after_testsuite",
    "teardown",
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _is_new(node) -> bool:
    """True for the Ren'Py 8.5+ flavour of the classes that share a name.

    Both generations pickle under one name, so the shape of the instance is
    the only way to tell them apart.
    """
    return "selector" in vars(node)


def _block(header: str, body: str) -> str:
    """A `header:` followed by an indented body, which must not be empty."""
    return f"{header}:\n{util.indent(body or 'pass')}"


def _quote(value) -> str:
    """Renders a string the way Ren'Py writes string literals."""
    return translation.encode_say_string(value)


def _literal(value) -> str:
    """A python literal, for values the parser read with py_eval."""
    return repr(value)


def _python(node, **kwargs) -> str:
    """`$ source` for one liners, a `python[ hide]:` block otherwise."""
    source = util.attr(node, "source")  # 8.5+
    if source is None:
        source = util.get_code(util.attr(node, "code"), **kwargs)  # <= 8.4.1
    source = source or ""
    if "\n" not in source:
        return f"$ {source.strip()}"
    header = "python hide" if util.attr(node, "hide") else "python"
    # the source keeps the indentation of the file it came from
    return _block(header, textwrap.dedent(source).strip("\n"))


def _selector_clause(node) -> str:
    """The `[selector] [pos E] [always]` keywords shared by the 8.5 commands."""
    rv = ""
    selector = util.attr(node, "selector")
    if selector is not None:
        rv += f" {util.get_code(selector)}"
    if util.attr(node, "position") is not None:
        rv += f" pos {util.attr(node, 'position')}"
    if util.attr(node, "always"):
        rv += " always"
    return rv


def _condition(node, **kwargs) -> str:
    return util.get_code(node, **kwargs)


def _operand(node, **kwargs) -> str:
    """Renders the left operand of a condition.

    The parser reads `a and b or c` right to left, so a nested condition on the
    left needs brackets to keep its shape: `not a and b` means `not (a and b)`.
    Brackets the author did not write are dropped on the way back in, so adding
    them here is safe.
    """
    code = util.get_code(node, **kwargs)
    if isinstance(node, (Binary, Not)):
        return f"({code})"
    return code


def _statements(nodes, **kwargs) -> str:
    return util.get_code(nodes or [], **kwargs)


# ---------------------------------------------------------------------------
# shared by both generations
# ---------------------------------------------------------------------------


class Node(object):
    """Abstract base of a test statement, renders nothing on its own."""


class Block(Node):
    """A group of statements, no header of its own."""

    block: list = []

    def get_code(self, **kwargs) -> str:
        return _statements(util.attr(self, "block"), **kwargs)


class Action(Node):
    expr: str | None = None

    def get_code(self, **kwargs) -> str:
        return f"run {util.attr(self, 'expr')}"


class Pause(Node):
    expr: str | None = None

    def get_code(self, **kwargs) -> str:
        return f"pause {util.attr(self, 'expr')}"


class Label(Node):
    name: str | None = None

    def get_code(self, **kwargs) -> str:
        return f"label {util.attr(self, 'name')}"


# ---------------------------------------------------------------------------
# Ren'Py <= 8.4.1 -- clauses, plus the 8.5 commands that replaced them
# ---------------------------------------------------------------------------


class Pattern(Node):
    """Base of the <= 8.4.1 clauses, holding the shared keywords."""

    pattern = None
    position = None
    always = False

    def _trailing(self) -> str:
        rv = ""
        if util.attr(self, "position") is not None:
            rv += f" pos {util.attr(self, 'position')}"
        if util.attr(self, "always"):
            rv += " always"
        return rv

    def _pattern_clause(self) -> str:
        pattern = util.attr(self, "pattern")
        if pattern is None:
            return ""
        return f" pattern {_quote(pattern)}"


class Click(Pattern):
    """`click` -- a pattern, or a displayable once selectors exist."""

    button = 1  # the class default, unwritten buttons are not stored

    def get_code(self, **kwargs) -> str:
        if _is_new(self):
            start = "click"
            if util.attr(self, "button") != 1:
                start += f" button {util.attr(self, 'button')}"
            return start + _selector_clause(self)

        pattern = util.attr(self, "pattern")
        start = _quote(pattern) if pattern is not None else "click"
        if util.attr(self, "button") != 1:
            start += f" button {util.attr(self, 'button')}"
        return start + self._trailing()


class Move(Pattern):
    def get_code(self, **kwargs) -> str:
        if _is_new(self):
            return "move" + _selector_clause(self)
        return f"move {util.attr(self, 'position')}" + self._pattern_clause()


class Type(Pattern):
    keys: list = []
    text: str | None = None

    def get_code(self, **kwargs) -> str:
        if _is_new(self):
            return f"type {_quote(util.attr(self, 'text'))}" + _selector_clause(self)

        keys = util.attr(self, "keys") or []
        name = keys[0] if len(keys) == 1 else None
        if name is not None and IDENTIFIER.match(name):
            text = name
        else:
            # a typed string is stored one character per entry
            text = _quote("".join(keys))
        return f"type {text}" + self._pattern_clause() + self._trailing()


class Scroll(Pattern):
    """`scroll "P"` before 8.5, a selector driven command from 8.5 on."""

    amount = 1  # the class default, unwritten amounts are not stored

    def get_code(self, **kwargs) -> str:
        if _is_new(self):
            start = "scroll"
            if util.attr(self, "amount") != 1:
                start += f" amount {util.attr(self, 'amount')}"
            return start + _selector_clause(self)
        return f"scroll {_quote(util.attr(self, 'pattern'))}"


class Drag(Node):
    """`drag POINTS ..` before 8.5, `drag SELECTOR .. to SELECTOR ..` after."""

    button = 1
    steps = 10
    pattern = None
    start_point = None
    end_point = None

    def get_code(self, **kwargs) -> str:
        if "start_point" in vars(self):
            rv = "drag"
            if util.attr(self, "button") != 1:
                rv += f" button {util.attr(self, 'button')}"
            if util.attr(self, "steps") != 10:
                rv += f" steps {util.attr(self, 'steps')}"
            return (
                rv
                + _selector_clause(util.attr(self, "start_point"))
                + " to"
                + _selector_clause(util.attr(self, "end_point"))
            )

        # <= 8.4.1 reads the points first, the keywords follow
        rv = f"drag {util.attr(self, 'points')}"
        if util.attr(self, "button") != 1:
            rv += f" button {util.attr(self, 'button')}"
        pattern = util.attr(self, "pattern")
        if pattern is not None:
            rv += f" pattern {_quote(pattern)}"
        if util.attr(self, "steps") != 10:
            rv += f" steps {util.attr(self, 'steps')}"
        return rv


class Until(Node):
    """`<statement> until <condition>`, wrapping the statement it follows."""

    timeout = None

    def get_code(self, **kwargs) -> str:
        left_node = util.attr(self, "left")
        left = util.get_code(left_node, **kwargs)
        if isinstance(left_node, Pause) and util.attr(left_node, "expr") == "0.1":
            # `pause until X` is stored with a default delay of 0.1 that was
            # never written down
            left = "pause"
        right = _condition(util.attr(self, "right"), **kwargs)

        rv = f"{left} until {right}"
        timeout = util.attr(self, "timeout")
        if timeout not in (None, "None"):
            rv += f" timeout {timeout}"
        return rv


class If(Node):
    """`if`/`elif`/`else` before 8.5 had a clause, from 8.5 conditions."""

    condition = None
    block: list = []
    entries: list = []

    def get_code(self, **kwargs) -> str:
        if "entries" not in vars(self):
            condition = util.get_code(util.attr(self, "condition"), **kwargs)
            body = _statements(util.attr(self, "block"), **kwargs)
            return _block(f"if {condition}", body)

        rv = []
        entries = util.attr(self, "entries") or []
        for index, (condition, block) in enumerate(entries):
            if index == 0:
                header = f"if {_condition(condition, **kwargs)}"
            elif index == len(entries) - 1 and _is_else(condition):
                # an `else` clause is stored as a trailing `eval True`
                header = "else"
            else:
                header = f"elif {_condition(condition, **kwargs)}"
            rv.append(_block(header, _statements(block.block, **kwargs)))
        return "\n".join(rv)


class Python(Node):
    code: object = None
    source: str | None = None
    hide: bool = False

    def get_code(self, **kwargs) -> str:
        return _python(self, **kwargs)


class Assert(Node):
    """`assert EXPR` before 8.5, `assert CONDITION [timeout E] [xfail E]` after."""

    expr: str | None = None
    condition: object = None
    timeout: str = "None"
    xfail_expr: str = "False"

    def get_code(self, **kwargs) -> str:
        if "condition" not in vars(self):
            return f"assert {util.attr(self, 'expr')}"

        rv = f"assert {_condition(util.attr(self, 'condition'), **kwargs)}"
        timeout = util.attr(self, "timeout")
        if timeout not in (None, "None"):
            rv += f" timeout {timeout}"
        xfail = util.attr(self, "xfail_expr")
        if xfail not in (None, "False"):
            rv += f" xfail {xfail}"
        return rv


class Jump(Node):
    target: str | None = None

    def get_code(self, **kwargs) -> str:
        return f"jump {util.attr(self, 'target')}"


class Call(Node):
    target: str | None = None

    def get_code(self, **kwargs) -> str:
        return f"call {util.attr(self, 'target')}"


# ---------------------------------------------------------------------------
# Ren'Py >= 8.5 -- conditions and selectors
# ---------------------------------------------------------------------------


class Condition(Node):
    """Abstract base of everything that can be tested for."""


class Selector(Condition):
    """Abstract base of the ways a displayable can be addressed."""

    wait_for_focus = False


class TextSelector(Selector):
    """`"text"` / `expression EXPR`, plus the `raw` and `focused` keywords."""

    pattern: str = ""
    raw: bool = False
    expression: bool = False

    def get_code(self, **kwargs) -> str:
        pattern = util.attr(self, "pattern")
        if util.attr(self, "expression"):
            rv = f"expression {pattern}"
        else:
            rv = _quote(pattern or "")
        if util.attr(self, "raw"):
            rv += " raw"
        if util.attr(self, "wait_for_focus"):
            rv += " focused"
        return rv


class DisplayableSelector(Selector):
    """`screen EXPR` / `id EXPR` / `layer EXPR`, plus `focused`."""

    screen: str | None = None
    id: str | None = None
    layer: str | None = None

    def get_code(self, **kwargs) -> str:
        rv = ""
        for keyword in ("screen", "id", "layer"):
            value = util.attr(self, keyword)
            if value is not None:
                rv += f" {keyword} {value}"
        if util.attr(self, "wait_for_focus"):
            rv += " focused"
        return rv.strip()


class Eval(Condition):
    expr: str = ""

    def get_code(self, **kwargs) -> str:
        expr = util.attr(self, "expr")
        if expr in ("True", "False"):
            return expr
        return f"eval {expr}"


class Not(Condition):
    condition: object = None

    def get_code(self, **kwargs) -> str:
        return f"not {_condition(util.attr(self, 'condition'), **kwargs)}"


class Binary(Condition):
    """Abstract base of the binary conditions."""

    keyword = ""
    left: object = None
    right: object = None

    def get_code(self, **kwargs) -> str:
        left = _operand(util.attr(self, "left"), **kwargs)
        right = _condition(util.attr(self, "right"), **kwargs)
        return f"{left} {self.keyword} {right}"


class And(Binary):
    keyword = "and"


class Or(Binary):
    keyword = "or"


class RepeatCounter(Condition):
    """Counts down the repeats of a `Repeat`, never written on its own."""

    initial_value: int = 0
    value: int = 0


# ---------------------------------------------------------------------------
# Ren'Py >= 8.5 -- commands
# ---------------------------------------------------------------------------


class SelectorDrivenNode(Node):
    """Base of the commands that act on a selector."""

    selector: object = None
    position: str | None = None
    always: bool = False

    def get_code(self, **kwargs) -> str:
        return _selector_clause(self).strip()


class Keysym(SelectorDrivenNode):
    keysym: str = ""

    def get_code(self, **kwargs) -> str:
        return f"keysym {_quote(util.attr(self, 'keysym'))}" + _selector_clause(self)


class Skip(Node):
    fast: bool = False

    def get_code(self, **kwargs) -> str:
        return "skip fast" if util.attr(self, "fast") else "skip"


class Screenshot(Node):
    filename_expr: str | None = None
    max_pixel_difference: str | None = None
    crop: str | None = None

    def get_code(self, **kwargs) -> str:
        rv = f"screenshot {util.attr(self, 'filename_expr')}"
        for keyword in ("max_pixel_difference", "crop"):
            value = util.attr(self, keyword)
            if value is not None:
                rv += f" {keyword} {value}"
        return rv


class Pass(Node):
    def get_code(self, **kwargs) -> str:
        return "pass"


class Advance(Node):
    def get_code(self, **kwargs) -> str:
        return "advance"


class Exit(Node):
    def get_code(self, **kwargs) -> str:
        return "exit"


class Repeat(Until):
    """`<statement> repeat N`, stored as a counter holding twice the count."""

    right: object = None

    def get_code(self, **kwargs) -> str:
        left = util.get_code(util.attr(self, "left"), **kwargs)
        counter = util.attr(self, "right")
        count = util.attr(counter, "initial_value", required=True) // 2
        rv = f"{left} repeat {count}"
        timeout = util.attr(self, "timeout")
        if timeout not in (None, "None"):
            rv += f" timeout {timeout}"
        return rv


# ---------------------------------------------------------------------------
# Ren'Py >= 8.5 -- suites, cases and hooks
# ---------------------------------------------------------------------------


def _is_else(condition) -> bool:
    return isinstance(condition, Eval) and util.attr(condition, "expr") == "True"


def _properties(node) -> list:
    """The `xfail`/`enabled`/`only`/`description`/`parameter` header lines."""
    rv = []
    xfail = util.attr(node, "xfail_expr")
    if xfail not in (None, "False"):
        rv.append(f"xfail {xfail}")
    if util.attr(node, "enabled") is False:
        rv.append("enabled False")
    if util.attr(node, "only"):
        rv.append("only True")
    description = util.attr(node, "description")
    if description:
        rv.append(f"description {_quote(description)}")
    parameters = util.attr(node, "parameters")
    if parameters:
        rv.extend(_parameter_lines(parameters))
    return rv


def _parameter_lines(parameters) -> list:
    """Rebuilds `parameter` statements from the flattened combinations.

    The parser expands a parameter statement into the cartesian product of its
    values, so one grouped statement reproduces all the combinations again.
    """
    names = list(parameters[0])
    if len(names) == 1:
        values = [combination[names[0]] for combination in parameters]
        return [f"parameter {names[0]} = {_literal(values)}"]
    values = [tuple(combination[name] for name in names) for combination in parameters]
    return [f"parameter ({', '.join(names)}) = {_literal(values)}"]


class TestHook(Node):
    name: str = ""
    block: list = []
    xfail_expr: str = "False"
    depth: int = 0

    def get_code(self, **kwargs) -> str:
        name = util.attr(self, "name") or ""
        header = name.replace("_", " ")

        body = []
        xfail = util.attr(self, "xfail_expr")
        if xfail not in (None, "False"):
            body.append(f"xfail {xfail}")
        depth = util.attr(self, "depth")
        if depth is not None and depth != HOOK_DEFAULTS.get(name, 0):
            body.append(f"depth {depth}")
        statements = _statements(util.attr(self, "block"), **kwargs)
        if statements:
            body.append(statements)
        return _block(header, "\n".join(body))


class TestCase(Node):
    name: str = ""
    block: list = []
    xfail_expr: str = "False"
    description: str = ""
    enabled: bool = True
    only: bool = False
    parameters: list = []

    def _header(self, keyword: str, **kwargs) -> str:
        body = _properties(self)
        statements = _statements(util.attr(self, "block"), **kwargs)
        if statements:
            body.append(statements)
        return _block(f"{keyword} {util.attr(self, 'name')}", "\n".join(body))

    def get_code(self, **kwargs) -> str:
        return self._header("testcase", **kwargs)


class TestSuite(TestCase):
    """A `testsuite` holds hooks and subtests, never plain statements."""

    subtests: list = []
    setup: object = None
    before_testsuite: object = None
    before_testcase: object = None
    after_testcase: object = None
    after_testsuite: object = None
    teardown: object = None

    def get_code(self, **kwargs) -> str:
        body = _properties(self)
        for name in HOOK_ORDER:
            hook = util.attr(self, name)
            if hook is not None:
                body.append(util.get_code(hook, **kwargs))
        body.extend(
            util.get_code(subtest, **kwargs)
            for subtest in util.attr(self, "subtests") or []
        )
        return _block(f"testsuite {util.attr(self, 'name')}", "\n".join(body))
