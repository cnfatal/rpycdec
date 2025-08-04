from .. import ast, ui, util


class SLContext(ui.Addable):
    pass


class SLNode(object):
    pass


class SLBlock(SLNode):
    def get_code(self, **kwargs) -> str:
        rv = []
        if self.keyword:
            rv.append(util.get_code_properties(self.keyword, newline=True))
        if self.children:
            rv.append(util.get_code(self.children, **kwargs))
        return "\n".join(rv)


class SLCache(object):
    pass


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

    https://www.renpy.org/doc/html/screens.html#add-statement
    https://www.renpy.org/doc/html/screens.html#use
    https://www.renpy.org/doc/html/screens.html#has
    """

    def get_name(self) -> str:
        # higher version use style instead of name
        name = getattr(self, "name", None)
        displable = getattr(self, "displayable", None)
        start = ""
        if name:
            start = name
        elif displable:
            # displayable function named sl2xxx like sl2vbar , sl2viewport
            displable_name = displable.__name__.lower()
            if displable_name.startswith("sl2"):
                start = displable_name.replace("sl2", "")
            elif displable_name == "onevent":
                start = "on"
            else:
                start = displable_name.replace("_", "")
        else:
            raise Exception("displayable not found")
        if self.style:
            match start:
                case "multibox":
                    start = self.style
                case "window":
                    start = self.style
        return start

    def get_code(self, **kwargs) -> str:
        # higher version use style instead of name
        start = self.get_name()
        if not start:
            raise Exception("displayable not found")

        # if scope      add:
        # if not scope  add():
        # if not self.scope:
        # start += "()"
        positional = util.attr(self, "positional")
        positional = [x for x in positional if x is not None]
        if positional:
            start += f" {' '.join(positional)}"
        # unhandled attributes
        hotspot = util.attr(self, "hotspot")
        replaces = util.attr(self, "replaces")
        pass_context = util.attr(self, "pass_context")
        imagemap = util.attr(self, "imagemap")
        variable = util.attr(self, "variable")
        default_keywords = util.attr(self, "default_keywords")
        child_or_fixed = util.attr(self, "child_or_fixed")
        # keywords
        keyword = util.attr(self, "keyword")
        children = util.attr(self, "children")
        if not children:
            if keyword:
                start += f" {util.get_code_properties(keyword)}"
            return start
        # children
        start += ":"
        rv = [start]
        if keyword:
            rv.append(util.indent(util.get_code_properties(keyword, newline=True)))
        rv.append(util.indent(util.get_code(children, **kwargs)))
        return "\n".join(rv)


class SLIf(SLNode):
    def get_code(self, **kwargs) -> str:
        rv = []
        for index, (cond, body) in enumerate(self.entries):
            body_code = util.get_code(body, **kwargs)
            if not body_code:
                body_code = "pass"
            body_code = util.indent(body_code)
            if index == 0:
                rv.append(f"if {cond}:\n{body_code}")
                continue
            if cond and cond != "True":
                rv.append(f"elif {cond}:\n{body_code}")
            else:
                rv.append(f"else:\n{body_code}")
                break
        return "\n".join(rv)


class SLShowIf(SLNode):
    """
    https://www.renpy.org/doc/html/screens.html#showif-statement

    showif n == 3:
        text "Three" size 100 at cd_transform
    elif n == 2:
        text "Two" size 100 at cd_transform
    elif n == 1:
        text "One" size 100 at cd_transform
    else:
        text "Liftoff!" size 100 at cd_transform
    """

    def get_code(self, **kwargs) -> str:
        rv = []
        for index, (cond, body) in enumerate(self.entries):
            body_code = util.get_code(body, **kwargs)
            if not body_code:
                body_code = "pass"
            body_code = util.indent(body_code)
            if index == 0:
                rv.append(f"showif {cond}:\n{body_code}")
                continue
            if cond and cond != "True":
                rv.append(f"elif {cond}:\n{body_code}")
            else:
                rv.append(f"else:\n{body_code}")
                break
        return "\n".join(rv)


class SLFor(SLBlock):
    pass

    """
    screen five_buttons():
        vbox:
            for i, numeral index numeral in enumerate(numerals):
                textbutton numeral action Return(i + 1)
    """

    def get_code(self, **kwargs) -> str:
        start = f"for {self.variable} in {self.expression}:"
        return util.label_code(start, self.children, **kwargs)


class SLPython(SLNode):
    def get_code(self, **kwargs) -> str:
        inner_code = util.get_code(self.code, **kwargs)
        if not inner_code:
            return ""
        if len(inner_code.splitlines()) == 1:
            return f"$ {inner_code}"
        return f"python:\n{util.indent(inner_code)}"


class SLPass(SLNode):
    pass


# https://www.renpy.org/doc/html/python.html#default-statement
class SLDefault(SLNode):
    def get_code(self, **kwargs) -> str:
        return f"default {self.variable} = {self.expression}"


class SLUse(SLNode):
    def get_code(self, **kwargs) -> str:
        start = "use"
        if self.target:
            if isinstance(self.target, ast.PyExpr):
                start += f" expression {util.get_code(self.target, **kwargs)}"
            else:
                start += f" {self.target}"
        if self.args:
            start += f"{util.get_code(self.args, **kwargs)}"
        if self.block:
            return util.label_code(start, self.block, **kwargs)
        if self.ast:
            return util.label_code(start, self.ast, **kwargs)
        return start


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
    """
    screen name(parameters):
        [style_prefix ["pref"|"pref_vbox"|"pref_button"|None]]
    """

    parameters: ast.ParameterInfo
    keyword: list

    def get_code(self, **kwargs) -> str:
        start = "screen"
        if self.name:
            start += f" {self.name}"
            if self.parameters:
                start += f"{util.get_code(self.parameters, **kwargs)}"

        properties = self.keyword.copy()
        tag = util.attr(self, "tag")
        if tag:
            properties.append(("tag", tag))
        layer = util.attr(self, "layer")
        if layer != "'screens'" and layer != "None":
            properties.append(("layer", layer))
        children = util.attr(self, "children")
        if properties or children:
            start += ":"

        rv = [start]
        # keyword
        if properties:
            rv.append(util.indent(util.get_code_properties(properties, newline=True)))
        # children
        rv.append(util.indent(util.get_code(children, **kwargs)))
        return "\n".join(rv)


class ScreenCache(object):
    pass


class SLContinue(SLNode):
    def get_code(self, **kwargs) -> str:
        return "continue"
