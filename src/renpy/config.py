from typing import Optional

# Do we use old text substitutions?
old_substitutions = True

# An alternate path to use when uneliding. (Mostly used by the launcher to enable
# the style inspector.)
alternate_unelide_path = None

# Various directories.
gamedir = ""
basedir = ""
renpy_base = ""
commondir = None  # type: Optional[str]
logdir = None  # type: Optional[str] # Where log and error files go.
