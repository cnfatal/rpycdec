from . import layout, core
from ..text import text
from .. import object as renpyobject, python


class Keymap(layout.Null):
    pass


class RollForward(layout.Null):
    pass


class PauseBehavior(layout.Null):
    pass


class SoundStopBehavior(layout.Null):
    pass


class SayBehavior(layout.Null):
    pass


class Button(layout.Window):
    pass


class ImageButton(Button):
    pass


class HoveredProxy(object):
    pass


class Input(text.Text):  # @UndefinedVariable
    pass


class Adjustment(renpyobject.Object):
    pass


class Bar(core.Displayable):
    pass


class Conditional(layout.Container):
    pass


class TimerState(python.RevertableObject):
    pass


class Timer(layout.Null):
    pass


class MouseArea(core.Displayable):
    pass


class OnEvent(core.Displayable):
    pass
