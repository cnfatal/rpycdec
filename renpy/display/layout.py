from ..display import core, layout
from .. import object as renpyobject


class Null(core.Displayable):
    pass


class Container(core.Displayable):
    pass


class Position(layout.Container):
    pass


class Grid(Container):
    pass


class IgnoreLayers(Exception):
    pass


class MultiBox(layout.Container):
    pass


class SizeGroup(renpyobject.Object):
    pass


class Window(Container):
    pass


class DynamicDisplayable(core.Displayable):
    pass


def ConditionSwitch(*args, **kwargs):
    pass


class IgnoresEvents(Container):
    pass


def Crop(rect, child, **properties):
    pass


LiveCrop = Crop


class Side(Container):
    pass


class Alpha(core.Displayable):
    pass


class AdjustTimes(Container):
    pass


class Tile(Container):
    pass


LiveTile = Tile


class Flatten(Container):
    pass


class AlphaMask(Container):
    pass
