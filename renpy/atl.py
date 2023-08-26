from . import util
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
    def get_code(self, **kwargs) -> str:
        if self.animation:
            raise NotImplementedError
        return util.get_code(self.statements, **kwargs)


class Block(Statement):
    pass


class RawMultipurpose(RawStatement):
    def get_code(self, **kwargs) -> str:
        properties = self.properties.copy()
        if self.duration != "0":
            properties = [(self.warper, self.duration)] + properties
        if self.circles != "0":
            raise NotImplementedError
        for k, v in self.expressions:
            if v:
                v = f"with {v}"
            properties.append((k, v))
        if self.splines:
            raise NotImplementedError
        if self.warp_function:
            raise NotImplementedError
        if self.revolution:
            raise NotImplementedError
        return util.get_code_properties(properties)


class RawContainsExpr(RawStatement):
    pass


# This allows us to have multiple ATL transforms as children.
class RawChild(RawStatement):
    def get_code(self, **kwargs) -> str:
        return util.get_code(self.children, **kwargs)


# This changes the child of this statement, optionally with a transition.
class Child(Statement):
    pass


# This causes interpolation to occur.
class Interpolation(Statement):
    pass


# https://www.renpy.org/doc/html/atl.html#repeat-statement
class RawRepeat(RawStatement):
    pass

    # atl_repeat ::=  "repeat" (simple_expression)?
    def get_code(self, **kwargs) -> str:
        if self.repeats:
            return f"repeat {util.get_code(self.repeats, **kwargs)}"
        return "repeat"


class Repeat(Statement):
    pass


# Parallel statement.


class RawParallel(RawStatement):
    def get_code(self, **kwargs) -> str:
        return util.get_code(self.blocks, **kwargs)


class Parallel(Statement):
    pass


class RawChoice(RawStatement):
    def get_code(self, **kwargs) -> str:
        rv = []
        for text, stmt in self.choices:
            rv.append(f"choice {text}:")
            rv.append(util.indent(util.get_code(stmt, **kwargs)))
        return "\n".join(rv)


class Choice(Statement):
    pass


class RawTime(RawStatement):
    pass


class Time(Statement):
    pass


# https://www.renpy.org/doc/html/atl.html#on-statement
class RawOn(RawStatement):
    pass

    # atl_on ::=  "on" name [ "," name ] * ":"
    #   atl_block
    #
    # on show:
    #     alpha 0.0
    #     linear .5 alpha 1.0
    # on hide:
    #     linear .5 alpha 0.0
    def get_code(self, **kwargs) -> str:
        rv = []
        for text, stmt in self.handlers.items():
            rv.append(f"on {text}:")
            rv.append(util.indent(util.get_code(stmt, **kwargs)))
        return "\n".join(rv)


class On(Statement):
    pass


class RawEvent(RawStatement):
    pass


class Event(Statement):
    pass


class RawFunction(RawStatement):
    def get_code(self, **kwargs) -> str:
        return "function " + self.expr


class Function(Statement):
    pass
