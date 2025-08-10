import logging
from . import translation, util


def parse_store_name(name: str) -> str:
    if not name:
        return ""
    if name == "store":
        return ""
    return name.lstrip("store.")


def align_imspec(imspec):
    """
    Align imspec to a tuple of 7 elements.
    """
    if len(imspec) == 7:
        return imspec
    elif len(imspec) == 6:
        return imspec + (None,)
    elif len(imspec) == 3:
        return imspec + (None, None, None, None)
    else:
        raise ValueError(f"Invalid imspec length: {len(imspec)}")


def get_imspec_name(imspec) -> str:
    name, expression, tag, at_list, layer, zorder, behind = align_imspec(imspec)
    if expression:
        return f"expression {expression}"
    return " ".join(name)


def get_imspec_expr(imspec, **kwargs) -> str:
    name, expression, tag, at_list, layer, zorder, behind = align_imspec(imspec)
    rv = []
    if expression:
        rv.append(f"expression {util.get_code(expression, **kwargs)}")
    else:
        rv.append(" ".join(name))

    if layer:
        rv.append(f"onlayer {layer}")

    if at_list:
        at_list = ", ".join([util.get_code(at, **kwargs) for at in at_list])
        rv.append(f"at {at_list}")

    if tag:
        rv.append(f"as {util.get_code(tag, **kwargs)}")

    if zorder:
        rv.append(f"zorder {util.get_code(zorder, **kwargs)}")

    if behind:
        behind = ", ".join([util.get_code(b, **kwargs) for b in behind])
        rv.append(f"behind {behind}")

    return " ".join(rv)


class Node(object):
    pass


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
        if getattr(self, "starred_indexes", None):
            raise NotImplementedError
        if getattr(self, "doublestarred_indexes", None):
            raise NotImplementedError
        if getattr(self, "extrakw", None):
            raise NotImplementedError
        if getattr(self, "extrapos", None):
            raise NotImplementedError
        return "(" + ", ".join(args) + ")"


class PyExpr(object):
    """
    Represents a string containing python code.
    """

    def __new__(cls, s, filename, linenumber, py=3):
        self = str.__new__(cls, s)
        self.filename = filename  # type: ignore
        self.linenumber = linenumber  # type: ignore
        self.py = py  # type: ignore
        return self

    def get_code(self, **kwargs) -> str:
        return self.expr

    def __str__(self):
        return self.expr


class PyCode(object):
    def __getstate__(self):
        return self.state

    def __setstate__(self, state):
        self.state = state

    def get_code(self, **kwargs) -> str:
        return util.get_code(self.state[1])


class Scry(object):
    pass


class Say(Node):
    """
    https://www.renpy.org/doc/html/dialogue.html#say-statement
    """

    def get_code(self, **kwargs) -> str:
        rv = []
        who = util.attr(self, "who")
        if who:
            rv.append(who)

        if getattr(self, "attributes", None):
            rv.extend(self.attributes)

        temporary_attributes = util.attr(self, "temporary_attributes")
        if temporary_attributes:
            rv.append("@")
            rv.extend(temporary_attributes)

        rv.append(translation.encode_say_string(self.what))

        interact = util.attr(self, "interact")
        if interact is False:
            rv.append("nointeract")

        with_ = util.attr(self, "with_")
        if with_:
            rv.append(f"with {with_}")

        id = util.attr(self, "identifier")
        if id:
            rv.append(f"id {id}")

        arguments = util.attr(self, "arguments")
        if arguments:
            rv.append(util.get_code(arguments, **kwargs))

        return " ".join(rv)


class Init(Node):
    """
    https://www.renpy.org/doc/html/python.html#init-python-statement

    init python:



    https://www.renpy.org/doc/html/lifecycle.html#init-offset-statement

    init offset = 42

    """

    def get_code(self, **kwargs) -> str:
        if len(self.block) == 1:
            next = self.block[0]
            if isinstance(next, Python) or isinstance(next, EarlyPython):
                return f"init {util.get_code(next, **kwargs)}"
            if self.priority == -500 and isinstance(next, Screen):
                return util.get_code(self.block, **kwargs)
            if self.priority == 500 and isinstance(next, Image):
                return util.get_code(next, **kwargs)
            if (
                isinstance(next, Define)
                or isinstance(next, Default)
                or isinstance(next, Transform)
            ):
                return util.get_code(next, **kwargs)

        if self.priority == 0 and all(
            isinstance(item, TranslateString) for item in self.block
        ):
            return util.get_code(self.block, **kwargs)

        start = "init"
        if self.priority:
            start += f" {self.priority}"
        if len(self.block) == 0:
            raise NotImplementedError
        inner_code = util.get_code(self.block, **kwargs)
        if inner_code.count("\n") == 0:
            return f"{start} {inner_code}"
        rv = [start + ":"]
        rv.append(util.indent(inner_code))
        return "\n".join(rv)


class Label(Node):
    """
    https://www.renpy.org/doc/html/label.html

    label sample1:
        "Here is 'sample1' label."

    label sample2(a="default"):
        "Here is 'sample2' label."
        "a = [a]"
    """

    def get_name(self):
        """
        Get the name of the label.
        """
        return util.attr(self, "name") or util.attr(self, "_name")

    def get_code(self, **kwargs) -> str:
        start = "label"
        name = self.get_name()
        if name:
            start += f" {name}"
        parameters = util.attr(self, "parameters")
        if parameters:
            start += f"{util.get_code(parameters, **kwargs)}"
        hide = util.attr(self, "hide")
        if hide:
            start += " hide"
        block = util.attr(self, "block")
        if not block:
            block = Pass()
        return util.label_code(start, block, **kwargs)


class Python(Node):
    """
    # https://www.renpy.org/doc/html/python.html#python-statements


    python:
        flag = True

    $ flag = True
    """

    def get_code(self, **kwargs) -> str:
        inner_code = util.get_code(self.code, **kwargs)
        store = parse_store_name(util.attr(self, "store"))
        hide = util.attr(self, "hide")

        # For single-line Python statements
        # without store or hide attributes, use the $ shorthand
        if not store and not hide and "\n" not in inner_code:
            return f"$ {inner_code}"

        start = "python"
        if store:
            start += f" in {store}"
        if hide:
            start += " hide"
        rv = [start + ":"]
        rv.append(util.indent(f"{inner_code}"))
        return "\n".join(rv)


class EarlyPython(Node):

    def get_code(self, **kwargs) -> str:
        """
        python early:
            flag = True

        $ flag = True
        """
        inner_code = util.get_code(self.code, **kwargs)
        storename = parse_store_name(util.attr(self, "store"))
        if not storename and not self.hide and len(inner_code.split("\n")) == 1:
            return f"$ {inner_code}"
        start = "python early"
        if storename:
            start += f" in {storename}"
        if util.attr(self, "hide"):
            start += " hide"
        return util.label_code(start, util.attr(self, "code"), **kwargs)


class Image(Node):

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
        code = util.attr(self, "code")
        if code:
            return f"{start} = {util.get_code(code,**kwargs)}"
        return util.label_code(start, util.attr(self, "atl"), **kwargs)


class Transform(Node):
    """
    https://www.renpy.org/doc/html/transforms.html#transform-statement

    atl_transform ::=  "transform" qualname ( "(" parameters ")" )? ":"
                      atl_block
    """

    def get_code(self, **kwargs) -> str:
        """
        transform notif_t:
            alpha 0
            ease .2 alpha 1
            pause 2.6
            ease .2 alpha 0 yzoom 0
        """
        start = "transform"
        varname = util.attr(self, "varname")
        if varname:
            start += f" {varname}"
            parameters = util.attr(self, "parameters")
            if parameters:
                start += f"{util.get_code(parameters, **kwargs)}"
        return util.label_code(start, util.attr(self, "atl"), **kwargs)


class Show(Node):

    def get_code(self, **kwargs) -> str:
        start = "show"
        name = get_imspec_expr(self.imspec)
        if name:
            start += f" {name}"
        return util.label_code(start, util.attr(self, "atl"), **kwargs)


class ShowLayer(Node):
    """
    https://www.renpy.org/doc/html/displaying_images.html#camera-and-show-layer-statements


    show layer <name> at a,b,c :
        atl
    """

    def get_code(self, **kwargs) -> str:
        start = "show layer"
        layer = util.attr(self, "layer")
        if layer:
            start += f" {layer}"
        if not layer:
            start += " master"
            logging.warning(
                "ShowLayer not have a layer name: %s:%s", self.filename, self.linenumber
            )
        at_list = util.attr(self, "at_list")
        if at_list:
            at_list = ", ".join([util.get_code(at, **kwargs) for at in at_list])
            start += f" at {at_list}"
        return util.label_code(start, util.attr(self, "atl"), **kwargs)


class Scene(Node):
    """
    https://www.renpy.org/doc/html/displaying_images.html#scene-statement

    example:
    scene bg room
    """

    def get_code(self, **kwargs) -> str:
        start = "scene"
        imspec = util.attr(self, "imspec")
        layer = util.attr(self, "layer")
        if imspec:
            start += f" {get_imspec_expr(imspec, **kwargs)}"
        elif layer:
            start += f" onlayer {layer}"
        return util.label_code(start, util.attr(self, "atl"), **kwargs)


class Hide(Node):

    def get_code(self, **kwargs) -> str:
        start = "hide"
        name = get_imspec_name(self.imspec)
        if name:
            start += f" {name}"
        return start


class With(Node):

    def get_code(self, **kwargs) -> str:
        paired = util.attr(self, "paired")
        if paired:
            raise Exception("With paired not covered")
        expr = util.attr(self, "expr")
        if isinstance(expr, str):
            return f"with {expr}"
        return f"with {util.get_code(expr, **kwargs)}"


class Call(Node):
    """
    https://www.renpy.org/doc/html/label.html#call-statement

    call subroutine

    call subroutine(2)

    call expression "sub" + "routine" pass (count=3)

    call [expression SIMPLE_EXPRESSION] [pass] [ARGUMENTS] [from LABEL]
    call LABEL [ARGUMENTS]
    """

    def get_code(self, **kwargs) -> str:
        start = "call"

        expression = util.attr(self, "expression")
        if expression:
            if expression == True:
                start += " expression"
            else:
                start += f" expression {util.get_code(expression,**kwargs)}"

        label = util.attr(self, "label")
        if label:
            start += f" {label}"

        arguments = util.attr(self, "arguments")
        if arguments:
            start += f"{util.get_code(arguments,**kwargs)}"

        from_label = kwargs.get("from_label", None)
        if from_label:
            start += f" from {from_label.get_name()}"
        return start


class Return(Node):

    def __new__(cls, *args, **kwargs):
        self = Node.__new__(cls)
        self.expression = None
        return self

    def get_code(self, **kwargs) -> str:
        expression = util.attr(self, "expression")
        if expression:
            return f"return {util.get_code(expression, **kwargs)}"
        else:
            return "return"


class Menu(Node):
    """
    https://www.renpy.org/doc/html/menus.html#in-game-menus
    """

    def _is_caption(item):
        label, condition, block = item
        return condition == "True" and block is None

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
        label = util.attr(kwargs, "menu_label")
        if label:
            if isinstance(label, Label):
                start += f" {label.get_name()}"
            else:
                start += f" {label}"

        # if statement_start:
        #     if isinstance(statement_start, Label):
        #         start += f" {statement_start.get_name()}"
        arguments = util.attr(self, "arguments")
        if arguments:
            start += f" {util.get_code(arguments,**kwargs)}"

        rv = [start + ":"]

        with_ = util.attr(self, "with_")
        if with_:
            rv.append(util.indent(f"with {with_}"))

        attrset = util.attr(self, "set")
        if attrset:
            rv.append(util.indent(f"set {attrset}"))

        say = util.attr(kwargs, "menu_say")
        if say:
            rv.append(util.indent(util.get_code(say, **kwargs)))

        items = util.attr(self, "items")
        item_arguments = util.attr(self, "item_arguments")
        for idx, (say, cond, expr) in enumerate(items):
            sel = translation.encode_say_string(say)
            if item_arguments:
                argument = item_arguments[idx]
                # argument may None
                if argument:
                    sel += f"{util.get_code(argument,**kwargs)}"
            if cond and cond != "True":
                sel += f" if {util.get_code(cond,**kwargs)}"
            # a empty expr means a caption
            rv.append(util.indent(util.label_code(sel, expr, **kwargs)))
        if len(rv) == 1:
            rv.append("pass")  # if no items, add a pass statement
        return "\n".join(rv)


class Jump(Node):
    """
    https://www.renpy.org/doc/html/label.html#jump-statement
    """

    def get_code(self, **kwargs) -> str:
        rv = "jump"
        expression = util.attr(self, "expression")
        if expression is True:
            rv += " expression"
        elif expression:  # maybe backward compatibility?
            rv += f" {util.get_code(expression, **kwargs)}"
        target = util.attr(self, "target")
        if target:
            rv += f" {target}"
        return rv


class Pass(Node):
    """
    pass
    """

    def get_code(self, **kwargs) -> str:
        # return ""
        # TODO: check if this is correct
        # may be return "pass" or "" at cases ?
        return "pass"


class While(Node):
    """
    https://www.renpy.org/doc/html/conditional.html#while-statement

    while lines: # evaluates to True as long as the list is not empty
        play sound lines.pop(0) # removes the first element
        pause

    while True:
        "This is the song that never terminates."
        "It goes on and on, my compatriots."
    """

    def get_code(self, **kwargs) -> str:
        start = f"while {self.condition}"
        return util.label_code(start, util.attr(self, "block"), **kwargs)


class If(Node):

    def get_code(self, **kwargs) -> str:
        rv = []
        entries = util.attr(self, "entries")
        for index, (cond, body) in enumerate(entries):
            if cond is None:
                logging.warning(
                    "Unexpected None condition in if statement at %s:%s",
                    self.filename,
                    self.linenumber,
                )
            block = util.indent(util.get_code(body, **kwargs))
            if index == 0:
                rv.append(f"if {cond}:\n{block}")
                continue
            if index == len(entries) - 1:
                rv.append(f"else:\n{block}")
                continue
            rv.append(f"elif {cond}:\n{block}")
        return "\n".join(rv)


class UserStatement(Node):
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
        rv = [start]
        if self.block:
            rv.append(util.indent(util.get_block_code(self.block, **kwargs)))
        return "\n".join(rv)


class PostUserStatement(Node):
    pass


class StoreNamespace(object):
    pass


# https://www.renpy.org/doc/html/python.html#define-statement
"""
define -2 gui.accent_color = '#ffdd1e'
"""


class Define(Node):

    def get_code(self, **kwargs) -> str:

        start = "define"
        priority = util.attr(self, "priority")
        if priority:
            start += f" {priority}"
        store_name = parse_store_name(util.attr(self, "store"))
        if store_name:
            start += f" {store_name}"
        varname = util.attr(self, "varname")
        operator = "="
        if getattr(self, "operator", None):
            operator = self.operator
        return f"{start} {varname} {operator} {util.get_code(self.code,**kwargs)}"


# All the default statements, in the order they were registered.
default_statements = []


class Default(Node):

    def get_code(self, **kwargs) -> str:
        # trim store or store. prefix
        st = parse_store_name(util.attr(self, "store"))
        return f"default {st}.{self.varname} = {util.get_code(self.code,**kwargs)}"


# https://www.renpy.org/doc/html/screens.html#screen-language
class Screen(Node):

    def get_code(self, **kwargs) -> str:
        return util.get_code(self.screen, **kwargs)


class Translate(Node):
    """
    translate arabic python:
        gui.REGULAR_FONT = "DejaVuSans.ttf"
        gui.LIGHT_FONT = "DejaVuSans.ttf"
        gui.FONT_SCALE = .9
        gui.REGULAR_BOLD = True
    """

    def get_code(self, **kwargs) -> str:
        language = util.attr(self, "language")
        identifier = util.attr(self, "identifier")
        alternate = util.attr(self, "alternate")
        if not language and not identifier:
            return ""
        start = f"translate {language} {identifier}"
        if alternate:
            start += f" alternate {alternate}"
        if self.block:
            start += ":"
        rv = [start]
        for item in self.block:
            callkwargs = kwargs.copy()
            # inject translate language and label to all children
            callkwargs.update({"language": language, "label": identifier})
            rv.append(util.indent(util.get_code(item, **callkwargs)))
        return "\n".join(rv)


class EndTranslate(Node):
    def get_code(self, **kwargs) -> str:
        return ""


class TranslateString(Node):
    """
    https://www.renpy.org/doc/html/translating_renpy.html#language-specific-translations

    translate french strings:
        old "OK"
        new ""
    """

    language: str
    old: str
    new: str

    def get_code(self, **kwargs) -> str:
        language = util.attr(self, "language")
        if not language:
            language = "None"
        return (
            f"translate {language} strings:\n"
            f"{util.indent(f'old {translation.encode_say_string(self.old)}')} \n"
            f"{util.indent(f'new {translation.encode_say_string(self.new)}')}"
        )


class TranslatePython(Node):
    pass


class TranslateBlock(Node):

    def get_code(self, **kwargs) -> str:
        return util.get_code(self.block, **kwargs)


class TranslateSay(Node):
    """
    translate say:
        "Hello" "Bonjour"
    """

    def get_code(self, **kwargs) -> str:
        old, new = util.attr(self, "old"), util.attr(self, "new")
        if old or new:
            return f'translate say:\n{util.indent(f"{self.old} {self.new}")}'
        return ""


class TranslateEarlyBlock(TranslateBlock):
    def get_code(self, **kwargs) -> str:
        for item in self.block:
            kwargs.update({"language": self.language})
            return util.get_code(item, **kwargs)


class Style(Node):
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
        start = f"style {self.style_name}"
        properties = self.properties.copy()

        parent = util.attr(self, "parent")
        if parent:
            start += f" is {parent}"
        clear = util.attr(self, "clear")
        if clear:
            properties["clear"] = None
        take = util.attr(self, "take")
        if take:
            properties["take"] = take
        delattr = util.attr(self, "delattr")
        if delattr:
            for d in delattr:
                properties["delattr"] = d

        variant = util.attr(self, "variant")
        if variant:
            properties["variant"] = variant

        if not properties:
            return start
        if len(properties) < 3:
            return f"{start} {util.get_code_properties(properties)}"
        rv = [start + ":"]
        rv.append(util.indent(util.get_code_properties(properties, newline=True)))
        return "\n".join(rv)


class Testcase(Node):
    pass


class Camera(Node):
    """
    https://www.renpy.org/doc/html/3dstage.html#using-the-3d-stage

    # Enabling the 3D stage for the background layer.
    camera background:
        perspective True

    camera master at a,b,c:
        atl
    """

    def get_code(self, **kwargs) -> str:
        start = "camera"
        if self.layer:
            start += f" {self.layer}"
        if self.at_list:
            start += f" at {util.get_code(self.at_list,**kwargs)}"
        return util.label_code(start, util.attr(self, "atl"), **kwargs)
