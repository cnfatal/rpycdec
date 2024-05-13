from . import core, layout
from .. import python


class Drag(core.Displayable, python.RevertableObject):
    pass


class DragGroup(layout.MultiBox):
    pass
