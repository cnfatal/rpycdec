from renpy.ast import ParameterInfo
from ..ui import Addable
from .. import util
from operator import itemgetter


class SLContext(Addable):
    pass


class SLNode(object):
    pass


class SLBlock(SLNode):
    def get_code(self, **kwargs) -> str:
        rv = []
        for child in self.children:
            rv.append(util.get_code(child))
        return "\n".join(rv)


class SLCache(object):
    pass


"""
# https://www.renpy.org/doc/html/screens.html#add-statement

screen add_test():
    add "logo.png" xalign 1.0 yalign 0.0

screen python_screen:
    python:
        test_name = "Test %d" % test_number

        
https://www.renpy.org/doc/html/screens.html#use
"""


class SLDisplayable(SLBlock):
    """
    `displayable`
        A function that, when called with the positional and keyword
        arguments, causes the displayable to be displayed.

    `scope`
        If true, the scope is supplied as an argument to the displayable.

    `child_or_fixed`
        If true and the number of children of this displayable is not one,
        the children are added to a Fixed, and the Fixed is added to the
        displayable.

    `style`
        The base name of the main style.

    `pass_context`
        If given, the context is passed in as the first positonal argument
        of the displayable.

    `imagemap`
        True if this is an imagemap, and should be handled as one.

    `hotspot`
        True if this is a hotspot that depends on the imagemap it was
        first displayed with.

    `replaces`
        True if the object this displayable replaces should be
        passed to it.

    `default_keywords`
        The default keyword arguments to supply to the displayable.

    `variable`
        A variable that the main displayable is assigned to.
    """

    def get_code(self, **kwargs) -> str:
        start = self.name
        # if scope      add:
        # if not scope  add():
        # if not self.scope:
        # start += "()"
        if self.positional:
            if len(self.positional) == 1:
                start += f" {self.positional[0]}"
            else:
                raise NotImplementedError
        # default_keywords
        # if self.default_keywords:
        #     start += f" {util.get_code_keyword(self.default_keywords)}"
        # keywords
        if self.keyword:
            start += f" {util.get_code_properties(self.keyword)}"

        # unhandled attributes
        if self.hotspot:
            pass
        if self.replaces:
            pass
        if self.pass_context:
            pass
        if self.unique:
            pass
        if self.child_or_fixed:
            pass
        if self.imagemap:
            pass
        if self.variable:
            pass

        # children
        if self.children:
            start += ":"
        rv = [start]
        for child in self.children:
            rv.append(util.indent(f"{util.get_code(child)}"))
        return "\n".join(rv)


class SLIf(SLNode):
    def get_code(self, **kwargs) -> str:
        rv = []
        for index, (cond, body) in enumerate(self.entries):
            if index == 0:
                rv.append(f"if {cond}:\n{util.indent(util.get_code(body))}")
                continue
            if index == len(self.entries) - 1:
                rv.append(f"else:\n{util.indent(util.get_code(body))}")
                break
            rv.append(f"elif {cond}:\n{util.indent(util.get_code(body))}")
        return "\n".join(rv)


class SLShowIf(SLNode):
    pass


class SLFor(SLBlock):
    pass


class SLPython(SLNode):
    def get_code(self, **kwargs) -> str:
        return f"$ {util.get_code(self.code)}"


class SLPass(SLNode):
    pass


# https://www.renpy.org/doc/html/python.html#default-statement
class SLDefault(SLNode):
    pass

    def get_code(self, **kwargs) -> str:
        return f"default {self.variable} {self.expression}"


class SLUse(SLNode):
    pass

    def get_code(self, **kwargs) -> str:
        return f"use {self.target}{util.get_code(self.args)}"


# https://www.renpy.org/doc/html/screens.html#use-and-transclude
"""
screen movable_frame(pos):
    drag:
        pos pos

        frame:
            background Frame("movable_frame.png", 10, 10)
            top_padding 20

            transclude
"""


class SLTransclude(SLNode):
    def get_code(self, **kwargs) -> str:
        return "transclude"


# https://www.renpy.org/doc/html/screens.html#screen-statement
class SLScreen(SLBlock):
    parameters: ParameterInfo
    keyword: list

    def get_code(self, **kwargs) -> str:
        start = "screen"
        if self.name:
            start += f" {self.name}"
            if self.parameters:
                start += f"{util.get_code(self.parameters)}"
        if self.keyword or self.children:
            start += ":"
        rv = [start]
        # keyword
        if self.keyword:
            rv.append(util.indent(util.get_code_properties(self.keyword, newline=True)))
        # children
        for child in self.children:
            rv.append(util.indent(util.get_code(child)))
        return "\n".join(rv)


class ScreenCache(object):
    pass
