def collapse_stmts(stmts):
    """
    Returns a flat list containing every statement in the tree
    stmts.
    """

    rv = []

    for i in stmts:
        i.get_children(rv.append)

    return rv
