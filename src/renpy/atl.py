from . import util, ast, astsupport
from .object import Object


class Context(object):
    pass


class ATLTransformBase(Object):
    pass


class RawStatement(object):
    pass


class Statement(Object):
    pass


class RawBlock(RawStatement):
    statements = None
    """
    https://www.renpy.org/doc/html/transforms.html#block-statement

    atl_block_stmt ::=  "block" ":"
                         atl_block

    A `block:` statement parses into the very same node as the body of a
    transform, so the caller decides: `block_header` is set when a block is a
    statement of another block and has to be written out.
    """

    def get_code(self, **kwargs) -> str:
        body = []
        if self.animation:
            """
            https://www.renpy.org/doc/html/transforms.html#animation-statement

            atl_animation ::=  "animation"

            image eileen vhappy moving:
                animation
                "eileen vhappy"
                xalign 0.0
                linear 5.0 xalign 1.0
                repeat
            """
            body.append("animation")

        # the header is about this block only, the statements inside it must not
        # inherit the flag
        inner = {key: value for key, value in kwargs.items() if key != "block_header"}

        previous = None
        for statement in self.statements or []:
            if statement is None:
                body.append("pass")
                previous = statement
                continue

            # renpy merges consecutive nodes of these kinds into one, and a
            # `pass` is what keeps two groups apart. Without it the choices,
            # branches or children of two nodes would come back as one.
            if isinstance(statement, MERGED_WHEN_ADJACENT) and type(statement) is type(
                previous
            ):
                body.append("pass")

            if isinstance(statement, RawBlock):
                body.append(util.get_code(statement, **{**inner, "block_header": True}))
            else:
                body.append(util.get_code(statement, **inner))
            previous = statement

        if not body:
            body.append("pass")

        if not kwargs.get("block_header"):
            return "\n".join(body)
        return "block:\n" + util.indent("\n".join(body))


class Block(Statement):
    pass


class RawMultipurpose(RawStatement):
    """
    https://www.renpy.org/doc/html/transforms.html#interpolation-statement

    atl_interp ::=  ((warper simple_expression) | ("warp" simple_expression simple_expression)) (atl_interp_target+ | (":"
                   atl_interp_target+ ))
    atl_interp_target ::=  (atl_property+ ("knot" simple_expression)* )
                        | atl_transform_expression
                        | "clockwise"
                        | "counterclockwise"
                        | ("circles" simple_expression)
    """

    def get_code(self, **kwargs) -> str:
        start = ""
        warp_fun, duration, wrap = self.warp_function, self.duration, self.warper
        if warp_fun and wrap is None:
            # warp {warp_function:expr} {duration:expr}
            start = f"warp {util.get_code(warp_fun, **kwargs)} {util.get_code(duration, **kwargs)}"
        elif not warp_fun and wrap:
            # {wrap} {duration:expr}
            start = f"{wrap} {util.get_code(duration, **kwargs)}"
        elif not warp_fun and not wrap and duration == "0":
            pass

        rv = []

        revolution = self.revolution
        if revolution:
            rv.append(revolution)

        circles = self.circles
        if circles and circles != "0":
            # circles {expression}
            rv.append(f"circles {util.get_code(circles, **kwargs)}")

        for prop, expr in self.properties:
            rv.append(f"{prop} {util.get_code(expr, **kwargs)}")

        for prop, exprs in self.splines:
            last, exprs = exprs[-1], exprs[:-1]
            knots = " ".join(f"knot {util.get_code(expr, **kwargs)}" for expr in exprs)
            rv.append(f"{prop} {util.get_code(last, **kwargs)} {knots}")

        for expr, with_expr in self.expressions:
            if with_expr is None:
                rv.append(str(expr))
                continue
            if isinstance(with_expr, ast.PyExpr):
                valstr = f"with {with_expr}"
            elif isinstance(with_expr, astsupport.PyExpr):
                valstr = f"with {with_expr}"
            else:
                valstr = str(with_expr)
            rv.append(f"{expr} {valstr}")

        if not start:
            return " ".join(rv)
        if not rv:
            # if no properties, return just the warp
            return start
        # targets stay on one line: the indented form means the same thing and
        # is harder to get right
        return start + " " + " ".join(rv)


class RawContainsExpr(RawStatement):
    """
    https://www.renpy.org/doc/html/transforms.html#inline-contains-statement

    atl_contains ::=  "contains" simple_expression
    """

    def get_code(self, **kwargs) -> str:
        """
        Returns the code for a contains expression.
        """
        expression = util.attr(self, "expression")
        if expression:
            return f"contains {util.get_code(expression, **kwargs)}"
        return "contains"


# This allows us to have multiple ATL transforms as children.
class RawChild(RawStatement):
    """
    https://www.renpy.org/doc/html/transforms.html#contains-block-statement

    atl_counts ::=  "contains" ":"
                   atl_block

    Consecutive `contains:` blocks merge into one node, one child each.
    """

    def get_code(self, **kwargs) -> str:
        children = util.attr(self, "children") or []
        rv = []
        for child in children:
            rv.append("contains:")
            rv.append(util.indent(util.get_code(child, **kwargs)))
        if not rv:
            rv = ["contains:", util.indent("pass")]
        return "\n".join(rv)


# This changes the child of this statement, optionally with a transition.
class Child(Statement):
    pass


# This causes interpolation to occur.
class Interpolation(Statement):
    pass


class RawRepeat(RawStatement):
    """
    https://www.renpy.org/doc/html/transforms.html#repeat-statement

    atl_repeat ::=  "repeat" (simple_expression)?
    """

    def get_code(self, **kwargs) -> str:
        if self.repeats:
            return f"repeat {util.get_code(self.repeats, **kwargs)}"
        return "repeat"


class Repeat(Statement):
    pass


class RawParallel(RawStatement):
    """
    https://www.renpy.org/doc/html/transforms.html#parallel-statement

    atl_parallel ::=  ("parallel" ":"
                     atl_block)+

    Consecutive branches are merged into one node, so every block needs its
    own `parallel:` header back.
    """

    def get_code(self, **kwargs) -> str:
        rv = []
        for block in util.attr(self, "blocks") or []:
            rv.append("parallel:")
            rv.append(util.indent(util.get_code(block, **kwargs)))
        if not rv:
            rv = ["parallel:", util.indent("pass")]
        return "\n".join(rv)


class Parallel(Statement):
    pass


class RawChoice(RawStatement):
    """
    https://www.renpy.org/doc/html/transforms.html#choice-statement

    atl_choice ::=  ("choice" (simple_expression)? ":"
                    atl_block)+
    """

    def get_code(self, **kwargs) -> str:
        rv = []
        for chance, block in util.attr(self, "choices") or []:
            # an unwritten weight is stored as 1.0, which is the default
            header = "choice:" if chance in (None, "1.0") else f"choice {chance}:"
            rv.append(header)
            rv.append(util.indent(util.get_code(block, **kwargs)))
        if not rv:
            rv = ["choice:", util.indent("pass")]
        return "\n".join(rv)


class Choice(Statement):
    pass


class RawTime(RawStatement):
    """
    https://www.renpy.org/doc/html/atl.html#time-statement

    atl_time ::=  "time" (simple_expression)?
    """

    def get_code(self, **kwargs) -> str:
        time = util.attr(self, "time")
        if time:
            return f"time {util.get_code(time, **kwargs)}"
        return "time"


class Time(Statement):
    pass


class RawOn(RawStatement):
    """
    https://www.renpy.org/doc/html/transforms.html#on-statement

    atl_on ::=  "on" name [ "," name ] * ":"
      atl_block

    on show:
        alpha 0.0
        linear .5 alpha 1.0
    on hide:
        linear .5 alpha 0.0
    """

    def get_code(self, **kwargs) -> str:
        rv = []
        for text, stmt in self.handlers.items():
            rv.append(f"on {text}:")
            rv.append(util.indent(util.get_code(stmt, **kwargs)))
        return "\n".join(rv)


class On(Statement):
    pass


class RawEvent(RawStatement):
    """
    https://www.renpy.org/doc/html/transforms.html#event-statement

    atl_event ::=  "event" name
    """

    def get_code(self, **kwargs) -> str:
        name = util.attr(self, "name")
        if name:
            return f"event {name}"
        return "event"


class Event(Statement):
    pass


class RawFunction(RawStatement):
    """
    https://www.renpy.org/doc/html/transforms.html#function-statement

    atl_function ::=  "function" simple_expression
    """

    def get_code(self, **kwargs) -> str:
        if self.expr:
            return "function " + str(self.expr)
        else:
            return "function"


class Function(Statement):
    pass


# These merge with the node before them when the parser reads them back, so two
# of them in a row need a `pass` between them to stay two.
MERGED_WHEN_ADJACENT = (RawParallel, RawChoice, RawChild, RawOn)
