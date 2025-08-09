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
    """

    def get_code(self, **kwargs) -> str:
        if (
            not self.animation
            and len(self.statements) == 1
            and isinstance(self.statements[0], RawBlock)
        ):
            return util.get_code(self.statements[0], **kwargs)

        rv = []
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
            rv.append("animation")

        statements = self.statements
        if statements:
            for statement in statements:
                if statement is None:
                    rv.append("pass")
                else:
                    rv.append(util.get_code(statement, **kwargs))
        else:
            rv.append("pass")

        return "\n".join(rv)


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
        if len(rv) < 3:
            # if only few properties, return them in one line
            return start + " " + " ".join(rv)
        return start + ":\n" + util.indent(" ".join(rv))


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
    """

    def get_code(self, **kwargs) -> str:
        children = util.attr(self, "children")
        if not children:
            return "contains:\n    pass"
        rv = ["contains:"]
        rv.append(util.indent(util.get_code(children, **kwargs)))
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
    """

    def get_code(self, **kwargs) -> str:
        rv = ["parallel:"]
        blocks = util.attr(self, "blocks")
        if not blocks:
            rv.append(util.indent("pass"))
        else:
            rv.append(util.indent(util.get_code(blocks, **kwargs)))
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
        for text, stmt in self.choices:
            rv.append(f"choice {text}:")
            rv.append(util.indent(util.get_code(stmt, **kwargs)))
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
