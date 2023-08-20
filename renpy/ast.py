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


class BaseNode(AST):
    def __new__(cls, *args, **kwargs):
        self = AST.__new__(cls)
        return self


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
    # __slots__ = [
    #     "arguments",
    #     "doublestarred_indexes",
    #     "starred_indexes",
    # ]

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


class PyExpr(BaseNode, str):
    """
    Represents a string containing python code.
    """

    __slots__ = [
        "filename",
        "linenumber",
    ]

    def __new__(cls, s, filename, linenumber, py=int):
        self = str.__new__(cls, s)
        self.filename = filename
        self.linenumber = linenumber
        self.py = py
        return self

    def __set__(self, instance, value):
        instance.__dict__[self._name] = value
        self._set_count += 1


class PyCode(object):
    __slots__ = [
        "source",
        "location",
        "mode",
        "bytecode",
        "hash",
        "py",
    ]

    def __getstate__(self):
        return (1, self.source, self.location, self.mode, self.py)

    def __setstate__(self, state):
        (_, self.source, self.location, self.mode, self.py) = state
        self.bytecode = None

    def get_code(self, **kwargs) -> str:
        return self.source


class Scry(object):
    pass

    # # By default, all attributes are None.
    # def __getattr__(self, name):
    #     return None


class Node(object):
    __slots__ = [
        "name",
        "filename",
        "linenumber",
        "next",
        "statement_start",
    ]
    # items = []
    # lineno = 0
    # col_offset = int
    # end_lineno = None
    # end_col_offset = None
    # type_comment = None
    # body = None


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

    def get_code(self, dialogue_filter=None):
        rv = []

        if self.who:
            rv.append(self.who)

        if self.attributes is not None:
            rv.extend(self.attributes)

        if self.temporary_attributes:
            rv.append("@")
            rv.extend(self.temporary_attributes)

        what = self.what
        if dialogue_filter is not None:
            what = dialogue_filter(what)

        rv.append(translation.encode_say_string(what))

        if not self.interact:
            rv.append("nointeract")

        if self.with_:
            rv.append("with")
            rv.append(self.with_)

        if self.arguments:
            rv.append(self.arguments.get_code())

        return " ".join(rv)


class Init(Node):
    def get_code(self, **kwargs) -> str:
        rv = []
        for item in self.block:
            stmt = util.get_code(item)
            if self.priority:
                stmt = f"init {self.priority} {stmt}"
            rv.append(stmt)
        return "\n".join(rv)


# https://www.renpy.org/doc/html/label.html#labels-control-flow

"""
label subroutine(count=1):

    e "I came here [count] time(s)."
    e "Next, we will return from the subroutine."

    return
"""


class Label(Node):
    _fields = [
        "name",
        "parameters",
        "block",
        "hide",
    ]

    def get_code(self, **kwargs) -> str:
        # inherit label, one useage is with menu
        # menu chapter_1_places:
        if not self.block:
            return self.name
        start = "label"
        if self.name:
            start += f" {self.name}"
        if self.parameters:
            start += f"{util.get_code_parameters(self.parameters)}"
        if self.block:
            start += ":"
        rv = [start]
        for item in self.block:
            rv.append(util.indent(f"{util.get_code(item)}"))
        return "\n".join(rv)


# https://www.renpy.org/doc/html/python.html#python-statements
"""
python:
    flag = True

$ flag = True
"""


class Python(Node):
    def get_code(self, **kwargs) -> str:
        storename = util.parse_store_name(self.store)
        if not storename and not self.hide:
            return f"$ {util.get_code(self.code)}"
        # init -1 python hide:
        start = "python"
        if storename:
            start += f" in {storename}"
        if self.hide:
            start += " hide"
        if self.code:
            start += ":"
        rv = [start]
        if self.code:
            rv.append(util.indent(f"{util.get_code(self.code)}"))
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
    """
    https://www.renpy.org/doc/html/displayables.html#images

    # These two lines are equivalent.
    image logo = "logo.png"
    image logo = Image("logo.png")

    # Using Image allows us to specify a default position as part of
    # an image.
    image logo right = Image("logo.png", xalign=1.0)
    """

    def get_code(self, **kwargs) -> str:
        start = "image"
        if self.imgname:
            start += f" {' '.join(self.imgname)}"
        if self.code or self.atl:
            start += ":"
        rv = [start]
        if self.code:
            rv.append(util.indent(f"{util.get_code(self.code)}"))
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

    """
    transform notif_t:
        alpha 0
        ease .2 alpha 1
        pause 2.6
        ease .2 alpha 0 yzoom 0
    """

    def get_code(self, **kwargs) -> str:
        start = util.get_code_section("transform", self.varname, self.parameters)
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
        rv = [start]
        if self.atl:
            raise NotImplementedError
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
        rv = [start]
        if self.atl:
            raise NotImplementedError
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


# https://www.renpy.org/doc/html/label.html#call-statement
"""
Call Statementlink
The call statement is used to transfer control to the given label. 
It also pushes the next statement onto the call stack,
allowing the return statement to return control to the statement following the call.

If the expression keyword is present, the expression following it is evaluated,
and the string so computed is used as the name of the label to call.
If the expression keyword is not present, the name of the statement to call must be explicitly given.

If the optional from clause is present, it has the effect of including a label statement 
with the given name as the statement immediately following the call statement.
An explicit label helps to ensure that saved games with return stacks can return to the proper place
when loaded on a changed script.

The call statement may take arguments, which are processed as described in PEP 448.

When using a call expression with an arguments list, the pass keyword must be inserted between the expression and the arguments list. Otherwise, the arguments list will be parsed as part of the expression, not as part of the call.


label start:

    e "First, we will call a subroutine."

    call subroutine

    call subroutine(2)

    call expression "sub" + "routine" pass (count=3)

    return
"""


class Call(Node):
    __slots__ = [
        "label",
        "arguments",
        "expression",
    ]

    def get_code(self, **kwargs) -> str:
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


# https://www.renpy.org/doc/html/menus.html#in-game-menus

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

    def get_code(self, **kwargs) -> str:
        start = "menu"
        if self.statement_start:
            if isinstance(self.statement_start, Label):
                start += f" {self.statement_start.name}"
            else:
                if not isinstance(self.statement_start, self.__class__):
                    raise NotImplementedError
        if self.arguments:
            start += f" {util.get_code(self.arguments)}"
        if self.with_:
            raise NotImplementedError
        if self.has_caption:
            raise NotImplementedError
        if self.items or self.set:
            start += ":"
        rv = [start]
        if self.set:
            rv.append(util.indent(f"set {self.set}"))
        for idx, (say, cond, expr) in enumerate(self.items):
            argument = self.item_arguments[idx]
            start = translation.encode_say_string(say)
            if argument:
                start += f" {util.get_code(argument)}"
            if cond:
                start += f" if {util.get_code(cond)}"
            if expr:
                start += ":"
            rv.append(util.indent(start))
            for subitem in expr:
                rv.append(util.indent(util.get_code(subitem), 2))
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
        return ""
        # TODO: check if this is correct
        # may be return "pass" at some cases ?
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
            if index == 0:
                rv.append(f"if {cond}:\n{util.indent(util.get_code(body))}")
                continue
            if index == len(self.entries) - 1:
                rv.append(f"else:\n{util.indent(util.get_code(body))}")
                break
            rv.append(f"elif {cond}:\n{util.indent(util.get_code(body))}")
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
            rv.append(util.indent(util.get_code_properties(properties)))
        return "\n".join(rv)


class Testcase(Node):
    __slots__ = [
        "label",
        "test",
    ]
