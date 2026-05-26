from .. import util


class Signature:
    def get_code(self, **kwargs) -> str:
        rv = []
        parameters = util.attr(self, "parameters")
        if isinstance(parameters, dict):
            for name, value in parameters.items():
                rv.append(util.get_code(value, **kwargs))
        else:
            for value in parameters:
                rv.append(str(value))
        if not rv:
            return ""
        return f"({', '.join(rv)})"


class Parameter:

    (
        POSITIONAL_ONLY,
        POSITIONAL_OR_KEYWORD,
        VAR_POSITIONAL,
        KEYWORD_ONLY,
        VAR_KEYWORD,
    ) = range(5)

    def _variable_or_default(self, name, default):
        return f"{name}={default}" if default is not None else f"{name}"

    def get_code(self, **kwargs) -> str:
        name = util.attr(self, "name")
        kind = util.attr(self, "kind")
        default = util.attr(self, "default")
        if kind == self.POSITIONAL_ONLY:
            return self._variable_or_default(name, default)
        elif kind == self.POSITIONAL_OR_KEYWORD:
            return self._variable_or_default(name, default)
        elif kind == self.VAR_POSITIONAL:
            return f"*{name}"
        elif kind == self.KEYWORD_ONLY:
            return self._variable_or_default(name, default)
        elif kind == self.VAR_KEYWORD:
            return f"**{name}"
        else:
            raise ValueError(f"Unknown parameter kind: {kind}")


class ArgumentInfo:

    def get_code(self, **kwargs) -> str:
        rv = []
        for i, (keyword, expression) in enumerate(self.arguments):
            if i in self.starred_indexes:
                rv.append("*" + expression)
            elif i in self.doublestarred_indexes:
                rv.append("**" + expression)
            elif keyword is not None:
                rv.append("{}={}".format(keyword, expression))
            else:
                rv.append(str(expression))
        return "(" + ", ".join(rv) + ")"
