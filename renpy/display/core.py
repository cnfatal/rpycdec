from .. import object as renpyobject


class IgnoreEvent(Exception):
    pass


class EndInteraction(Exception):
    pass


class absolute(float):
    __slots__ = []


class DisplayableArguments(renpyobject.Object):
    pass


class Displayable(renpyobject.Object):
    pass


class SceneLists(renpyobject.Object):
    pass


class MouseMove(object):
    pass


class Interface(object):
    pass
