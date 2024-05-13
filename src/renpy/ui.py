from .object import Object


class Action(Object):
    pass


class BarValue(Object):
    pass


class Addable(object):
    pass


class Layer(Addable):
    pass


class Many(Addable):
    pass


class One(Addable):
    pass


class Detached(Addable):
    pass


class ChildOrFixed(Addable):
    pass

    def get_code(self, **kwargs) -> str:
        pass


def _hotspot(spot, style="hotspot", **properties):
    pass


def _imagebutton(
    idle_image=None,
    hover_image=None,
    insensitive_image=None,
    activate_image=None,
    selected_idle_image=None,
    selected_hover_image=None,
    selected_insensitive_image=None,
    selected_activate_image=None,
    idle=None,
    hover=None,
    insensitive=None,
    selected_idle=None,
    selected_hover=None,
    selected_insensitive=None,
    image_style=None,
    auto=None,
    **properties,
):
    pass


def _imagemap(
    ground,
    selected,
    hotspots,
    unselected=None,
    overlays=False,
    style="imagemap",
    mouse="imagemap",
    with_none=None,
    **properties,
):
    pass


def _textbutton(
    label,
    clicked=None,
    style=None,
    text_style=None,
    substitute=True,
    scope=None,
    **kwargs,
):
    pass


def _key(key, action=None, activate_sound=None):
    pass


def _label(label, style=None, text_style=None, substitute=True, scope=None, **kwargs):
    pass
