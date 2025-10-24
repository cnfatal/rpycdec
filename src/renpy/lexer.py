import os
from typing import NamedTuple

import renpy


class SubParse(object):
    """
    This represents the information about a subparse that can be provided to
    a creator-defined statement.
    """

    def __init__(self, block):
        self.block = block

    def __repr__(self):
        if not self.block:
            return "<SubParse empty>"
        else:
            return "<SubParse {}:{}>".format(
                self.block[0].filename, self.block[0].linenumber
            )


def unelide_filename(fn: str) -> str:
    fn = os.path.normpath(fn)

    if renpy.config.alternate_unelide_path is not None:
        fn0 = os.path.join(renpy.config.alternate_unelide_path, fn)
        if os.path.exists(fn0):
            return fn0

    fn1 = os.path.join(renpy.config.basedir, fn)
    if os.path.exists(fn1):
        return fn1

    fn2 = os.path.join(renpy.config.renpy_base, fn)
    if os.path.exists(fn2):
        return fn2

    return fn


class GroupedLine(NamedTuple):
    # The filename the line is from.
    filename: str
    number: int
    indent: int
    text: str
    block: list["GroupedLine"]
