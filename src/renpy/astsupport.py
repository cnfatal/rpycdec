class PyExpr(object):

    def __new__(
        cls,
        expr: str,
        filename: str,
        linenumber: int,
        py: int,
        hashcode: str,
        column: int = 0,
    ):
        self = object.__new__(cls)
        self.expr = expr
        self.filename = filename
        self.linenumber = linenumber
        self.py = py
        self.hashcode = hashcode
        self.column = column
