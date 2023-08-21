from ast import AST
from . import translation
from . import util


def get_imspec_name(imspec) -> str:
    if len(imspec) == 7:
        name, expression, tag, at_list, layer, zorder, behind = imspec
    elif len(imspec) == 6:
        name, expression, tag, at_list, layer, zorder = imspec
        behind = []
    elif len(imspec) == 3:
        name, at_list, layer = imspec
        expression, tag, zorder = None, None, []
    return " ".join(name)


class Node(object):
    __slots__ = [
        "name",
        "filename",
        "linenumber",
        "next",
        "statement_start",
    ]


class ParameterInfo(object):
    def get_code(self, **kwargs) -> str:
        """
        >>> ParameterInfo([("a", 1), ("b", 2)]).get_code()
        '(a=1, b=2)'

        >>> ParameterInfo().get_code()
        '()'
        """
        param_str = []
        positional = list(filter(lambda i: i[0] in self.positional, self.parameters))
        for parameter in positional:
            if parameter[1] is not None:
                param_str.append(f"{parameter[0]}={parameter[1]}")
            else:
                param_str.append(f"{parameter[0]}")

        if self.extrapos:
            param_str.append("*%s" % self.extrapos)

        nameonly = list(filter(lambda i: i not in positional, self.parameters))
        if nameonly:
            if not self.extrapos:
                param_str.append("*")
            for parameter in nameonly:
                if parameter[1] is not None:
                    param_str.append(f"{parameter[0]}={parameter[1]}")
                else:
                    param_str.append(f"{parameter[0]}")

        if self.extrakw:
            param_str.append(f"**{self.extrakw}")

        param = ", ".join(param_str)
        return f"({param})"


class ArgumentInfo(object):
    def get_code(self, **kwargs):
        args = []
        for key, val in self.arguments:
            if key is not None:
                args.append(f"{key}={val}")
            else:
                args.append(val)
        if self.starred_indexes:
            raise NotImplementedError
        if self.doublestarred_indexes:
            raise NotImplementedError
        return "(" + ", ".join(args) + ")"


class PyExpr(str):
    """
    Represents a string containing python code.
    """

    def __new__(cls, s, filename, linenumber, py=int):
        return str.__new__(cls, s)

    def get_code(self, **kwargs) -> str:
        return self


class PyCode(object):
    def __getstate__(self):
        return self.state

    def __setstate__(self, state):
        self.state = state

    def get_code(self, **kwargs) -> str:
        return self.state[1]


class Scry(object):
    pass


class Say(Node):
    __slots__ = [
        "who",
        "who_fast",
        "what",
        "with_",
        "interact",
        "attributes",
        "arguments",
        "temporary_attributes",
        "rollback",
    ]

    def get_code(self, **kwargs) -> str:
        rv = []
        if self.who:
            rv.append(self.who)
        if self.attributes is not None:
            rv.extend(self.attributes)
        if self.temporary_attributes:
            rv.append("@")
            rv.extend(self.temporary_attributes)
        rv.append(translation.encode_say_string(self.what))
        # if not self.interact:
        # rv.append("nointeract")
        if self.with_:
            rv.append("with")
            rv.append(self.with_)
        if self.arguments:
            rv.append(util.get_code(self.arguments))
        return " ".join(rv)


class Init(Node):
    def check_translate_strings(self):
        languages_map = {}
        for item in self.block:
            if not isinstance(item, TranslateString):
                return None
            if item.language not in languages_map:
                languages_map[item.language] = []
            languages_map[item.language].append(item)
        rv = []
        for language, items in languages_map.items():
            rv.append(f"translate {language} strings:")
            for item in items:
                rv.append(util.indent(f"old {translation.encode_say_string(item.old)}"))
                rv.append(util.indent(f"new {translation.encode_say_string(item.new)}"))
                rv.append("")
        return "\n".join(rv)

    def get_code(self, **kwargs) -> str:
        check_translate_strings = self.check_translate_strings()
        if check_translate_strings:
            return check_translate_strings
        if self.priority == -500:  # default priority ?
            return util.get_code(self.block)
        start = "init"
        if self.priority:
            start += f" {self.priority}"
        if len(self.block) == 0:
            raise NotImplementedError
        if len(self.block) == 1:
            return f"{start} {util.get_code(self.block)}"
        rv = [start + ":"]
        rv.append(util.indent(util.get_code(self.block)))
        return "\n".join(rv)


class Label(Node):
    _fields = [
        "name",
        "parameters",
        "block",
        "hide",
    ]

    def get_code(self, **kwargs) -> str:
        start = "label"
        if self.name:
            start += f" {self.name}"
        if self.parameters:
            start += f"{util.get_code_parameters(self.parameters)}"
        start += ":"  # label always has colon
        rv = [start]
        rv.append(util.indent(f"{util.get_code(self.block)}"))
        return "\n".join(rv)


class Python(Node):
    # https://www.renpy.org/doc/html/python.html#python-statements
    def get_code(self, **kwargs) -> str:
        """
        python:
            flag = True

        $ flag = True
        """
        inner_code = util.get_code(self.code)
        storename = util.parse_store_name(self.store)
        if not storename and not self.hide and len(inner_code.split("\n")) == 1:
            return f"$ {inner_code}"
        start = "python"
        if storename:
            start += f" in {storename}"
        if self.hide:
            start += " hide"
        if self.code:
            start += ":"
        rv = [start]
        if self.code:
            rv.append(util.indent(f"{inner_code}"))
        return "\n".join(rv)


class EarlyPython(Node):
    __slots__ = [
        "hide",
        "code",
        "store",
    ]


class Image(Node):
    _filds = [
        "imgname",
        "code",
        "atl",
    ]

    def get_code(self, **kwargs) -> str:
        """
        https://www.renpy.org/doc/html/displayables.html#images

        # These two lines are equivalent.
        image logo = "logo.png"
        image logo = Image("logo.png")

        # Using Image allows us to specify a default position as part of
        # an image.
        image logo right = Image("logo.png", xalign=1.0)
        """
        start = "image"
        if self.imgname:
            start += f" {' '.join(self.imgname)}"
        if self.code and self.atl:
            raise NotImplementedError
        if self.code:
            return f"{start} = {util.get_code(self.code)}"
        if self.atl:
            start += ":"
        rv = [start]
        if self.atl:
            rv.append(util.indent(f"{util.get_code(self.atl)}"))
        return "\n".join(rv)


class Transform(Node):
    __slots__ = [
        # The name of the transform.
        "varname",
        # The block of ATL associated with the transform.
        "atl",
        # The parameters associated with the transform, if any.
        "parameters",
    ]

    def get_code(self, **kwargs) -> str:
        """
        transform notif_t:
            alpha 0
            ease .2 alpha 1
            pause 2.6
            ease .2 alpha 0 yzoom 0
        """
        start = "transform"
        if self.varname:
            start += f" {self.varname}"
            if self.parameters:
                start += f"{util.get_code(self.parameters)}"
        if self.atl:
            start += ":"
        rv = [start]
        if self.atl:
            rv.append(util.indent(util.get_code(self.atl)))
        return "\n".join(rv)


class Show(Node):
    __slots__ = [
        "imspec",
        "atl",
    ]

    def get_code(self, **kwargs) -> str:
        start = "show"
        name = get_imspec_name(self.imspec)
        if name:
            start += f" {name}"
        if self.atl:
            start += ":"
        rv = [start]
        if self.atl:
            rv.append(util.indent(util.get_code(self.atl)))
        return "\n".join(rv)


class ShowLayer(Node):
    __slots__ = [
        "layer",
        "at_list",
        "atl",
    ]


class Scene(Node):
    __slots__ = [
        "imspec",
        "layer",
        "atl",
    ]

    def get_code(self, **kwargs) -> str:
        start = "scene"
        name = get_imspec_name(self.imspec)
        if name:
            start += f" {name}"
        if self.layer:
            raise NotImplementedError
        if self.atl:
            start += ":"
        rv = [start]
        if self.atl:
            rv.append(util.indent(util.get_code(self.atl)))
        return "\n".join(rv)


class Hide(Node):
    __slots__ = [
        "imspec",
    ]

    def get_code(self, **kwargs) -> str:
        start = "hide"
        name = get_imspec_name(self.imspec)
        if name:
            start += f" {name}"
        return start


class With(Node):
    __slots__ = [
        "expr",
        "paired",
    ]

    def get_code(self, **kwargs) -> str:
        start = "with"
        if self.paired:
            start += f" {util.get_code(self.paired)}"
        if self.expr and self.expr != "None":
            start += f" {util.get_code(self.expr)}"
        return start


class Call(Node):
    __slots__ = [
        "label",
        "arguments",
        "expression",
    ]

    # https://www.renpy.org/doc/html/label.html#call-statement
    def get_code(self, **kwargs) -> str:
        """
        label start:
        e "First, we will call a subroutine."
        call subroutine
        call subroutine(2)
        call expression "sub" + "routine" pass (count=3)
        return
        """
        start = "call"
        if self.label:
            start += f" {self.label}"
        if self.expression:
            start += f" expression {util.get_code(self.expression)} pass "
        if self.arguments:
            start += f"({util.get_code_parameters(self.arguments)})"
        return start


class Return(Node):
    __slots__ = [
        "expression",
    ]

    def __new__(cls, *args, **kwargs):
        self = Node.__new__(cls)
        self.expression = None
        return self

    def get_code(self, **kwargs) -> str:
        rv = ["return"]
        if self.expression:
            rv.append(f" {util.get_code(self.expression)}")
        return "".join(rv)


class Menu(Node):
    __slots__ = [
        "items",
        "set",
        "with_",
        "has_caption",
        "arguments",
        "item_arguments",
        "rollback",
    ]

    # https://www.renpy.org/doc/html/menus.html#in-game-menus
    def get_code(self, **kwargs) -> str:
        """
        default menuset = set()
        menu chapter_1_places:
            set menuset
            "Where should I go?"
            "Dallas, TX" (150, sale=True):
                jump dallas
            "Go to class." if True:
                jump go_to_class
            "Go to the bar.":
                jump go_to_bar
            "Go to jail.":
                jump go_to_jail
        """
        start = "menu"
        if self.statement_start:
            if isinstance(self.statement_start, Label):
                start += f" {self.statement_start.name}"
        if self.arguments:
            start += f" {util.get_code(self.arguments)}"
        if self.with_:
            raise NotImplementedError
        # if self.has_caption:
        #     raise NotImplementedError
        if self.items or self.set:
            start += ":"
        rv = [start]
        if self.statement_start and not isinstance(self.statement_start, (Label, Menu)):
            if not self.has_caption:
                raise NotImplementedError
            rv.append(util.indent(util.get_code(self.statement_start)))
        if self.set:
            rv.append(util.indent(f"set {self.set}"))
        for idx, (say, cond, expr) in enumerate(self.items):
            argument = self.item_arguments[idx]
            start = translation.encode_say_string(say)
            if argument:
                start += f"{util.get_code(argument)}"
            if cond and cond != "True":
                start += f" if {util.get_code(cond)}"
            if expr:
                start += ":"
            rv.append(util.indent(start))
            if expr:
                rv.append(util.indent(util.get_code(expr), 2))
        return "\n".join(rv)


class Jump(Node):
    __slots__ = [
        "target",
        "expression",
    ]

    def get_code(self, **kwargs) -> str:
        rv = ["jump"]
        if self.expression:
            rv.append(f" {util.get_code(self.expression)}")
        if self.target:
            rv.append(f" {self.target}")
        return "".join(rv)


class Pass(Node):
    __slots__ = []

    def get_code(self, **kwargs) -> str:
        # return ""
        # TODO: check if this is correct
        # may be return "pass" or "" at cases ?
        return "pass"


class While(Node):
    __slots__ = [
        "condition",
        "block",
    ]


class If(Node):
    __slots__ = ["entries"]

    def get_code(self, **kwargs) -> str:
        rv = []
        for index, (cond, body) in enumerate(self.entries):
            body_code = util.indent(util.get_code(body))
            if index == 0:
                rv.append(f"if {cond}:\n{body_code}")
                continue
            if cond and cond != "True":
                rv.append(f"elif {cond}:\n{body_code}")
            else:
                rv.append(f"else:\n{body_code}")
                break
        return "\n".join(rv)


class UserStatement(Node):
    __slots__ = [
        "line",
        "parsed",
        "block",
        "translatable",
        "code_block",
        "translation_relevant",
        "rollback",
        "subparses",
    ]

    def __new__(cls, *args, **kwargs):
        self = Node.__new__(cls)
        self.block = []
        self.code_block = None
        self.translatable = False
        self.translation_relevant = False
        self.rollback = "normal"
        self.subparses = []
        return self

    def get_code(self, **kwargs) -> str:
        start = self.line
        if self.block:
            start += ":\n"
        rv = [start]
        for item in self.block:
            raise NotImplementedError
            rv.append(util.indent(f"{util.get_code(item)}"))
        return "\n".join(rv)


class PostUserStatement(Node):
    __slots__ = [
        "parent",
    ]


class StoreNamespace(object):
    pass


# https://www.renpy.org/doc/html/python.html#define-statement
"""
define -2 gui.accent_color = '#ffdd1e'
"""


class Define(Node):
    __slots__ = [
        "varname",
        "code",
        "store",
        "index",
        "operator",
    ]

    def get_code(self, **kwargs) -> str:
        start = "define"
        varname = self.varname
        store_name = util.parse_store_name(self.store)
        if store_name:
            varname = f"{store_name}.{varname}"
        return f"{start} {varname} {self.operator} {util.get_code(self.code)}"


# All the default statements, in the order they were registered.
default_statements = []


class Default(Node):
    __slots__ = [
        "varname",
        "code",
        "store",
    ]

    def get_code(self, **kwargs) -> str:
        varname = self.varname
        # trim store or store. prefix
        st = self.store.lstrip("store.")
        if st and st != "store":
            varname = f"{st}.{varname}"
        return f"default {varname} = {util.get_code(self.code)}"


# https://www.renpy.org/doc/html/screens.html#screen-language
class Screen(Node):
    __slots__ = [
        "screen",
    ]

    def get_code(self, **kwargs) -> str:
        return util.get_code(self.screen)


class Translate(Node):
    __slots__ = [
        "identifier",
        "alternate",
        "language",
        "block",
        "after",
    ]
    """
    translate arabic python:
        gui.REGULAR_FONT = "DejaVuSans.ttf"
        gui.LIGHT_FONT = "DejaVuSans.ttf"
        gui.FONT_SCALE = .9
        gui.REGULAR_BOLD = True
    """

    def get_code(self, **kwargs) -> str:
        start = f"translate {self.language} {self.identifier}"
        if self.alternate:
            start += f" alternate {self.alternate}"
        if self.block:
            start += ":"
        rv = [start]
        for item in self.block:
            rv.append(util.indent(util.get_code(item)))
        return "\n".join(rv)


class EndTranslate(Node):
    def get_code(self, **kwargs) -> str:
        return ""


class TranslateString(Node):
    __slots__ = [
        "language",
        "old",
        "new",
        "newloc",
    ]

    """
    https://www.renpy.org/doc/html/translating_renpy.html#language-specific-translations

    translate french strings:
        old "OK"
        new ""
    """

    def get_code(self, **kwargs) -> str:
        rv = []
        rv.append(f"translate {self.language} strings:")
        rv.append(util.indent(f"old {translation.encode_say_string(self.old)}"))
        rv.append(util.indent(f"new {translation.encode_say_string(self.new)}"))
        return "\n".join(rv)


class TranslatePython(Node):
    __slots__ = [
        "language",
        "code",
    ]


class TranslateBlock(Node):
    __slots__ = [
        "block",
        "language",
    ]


class TranslateEarlyBlock(TranslateBlock):
    pass


class Style(Node):
    __slots__ = [
        "style_name",
        "parent",
        "properties",
        "clear",
        "take",
        "delattr",
        "variant",
    ]

    """
    # https://www.renpy.org/doc/html/style.html#defining-styles-style-statement
    # Creates a new style, inheriting from default.
    style big_red:
        size 40

    # Updates the style.
    style big_red color "#f00"

    # Takes the properties of label_text from big_red, but only if we're
    # on a touch system.

    style label_text:
        variant "touch"
        take big_red

    # Style a has all the properties of style c, except that when not present
    # in c, the properties are taken from b or b's parents.
    style a is b:
        take c
    """

    def get_code(self, **kwargs) -> str:
        properties = self.properties.copy()
        start = f"style {self.style_name}"
        if self.parent:
            start += f" is {self.parent}"
        if self.variant:
            properties["variant"] = self.variant
        if self.clear:
            properties["clear"] = None
        if self.take:
            properties["take"] = self.take
        if self.delattr:
            raise NotImplementedError
        if properties:
            start += ":"
        rv = [start]
        if properties:
            rv.append(util.indent(util.get_code_properties(properties, newline=True)))
        return "\n".join(rv)


class Testcase(Node):
    __slots__ = [
        "label",
        "test",
    ]
