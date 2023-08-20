import ast

# Three levels of constness.
GLOBAL_CONST = 2  # Expressions that are const everywhere.
LOCAL_CONST = 1  # Expressions that are const with regard to a screen + parameters.
NOT_CONST = 0  # Expressions that are not const.


class Control(object):
    pass


class Analysis(object):
    pass


class PyAnalysis(ast.NodeVisitor):
    pass


class CompilerCache(object):
    pass


ccache = CompilerCache()
