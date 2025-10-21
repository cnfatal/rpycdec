import os

import renpy


def shorten_filename(filename):
    """
    Shortens a file name. Returns the shortened filename, and a flag that says
    if the filename is in the common directory.
    """

    commondir = os.path.normpath(renpy.config.commondir)  # type: ignore
    gamedir = os.path.normpath(renpy.config.gamedir)

    if filename.startswith(commondir):
        fn = os.path.relpath(filename, commondir)
        common = True

    elif filename.startswith(gamedir):
        fn = os.path.relpath(filename, gamedir)
        common = False

    else:
        fn = os.path.basename(filename)
        common = False

    return fn, common
