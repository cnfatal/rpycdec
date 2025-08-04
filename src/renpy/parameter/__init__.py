from .. import util


class Signature:
    def get_code(self, **kwargs) -> str:
        rv = []
        parameters = util.attr(self, "parameters")
        if type(parameters) is dict:
            for name, value in parameters.items():
                valuecode = value.get_code(**kwargs)
                if not valuecode:
                    continue
                rv.append(f"{name}={valuecode}")
        else:
            for value in parameters:
                rv.append(str(value))
        if not rv:
            return ""
        return f"({', '.join(rv)})"


class Parameter:
    def get_code(self, **kwargs) -> str:
        name = util.attr(self, "name")
        kind = util.attr(self, "kind")
        default = util.attr(self, "default")
        if not default:
            return None
        return str(default)


class ArgumentInfo:
    def get_code(self, **kwargs) -> str:
        arguments = util.attr(self, "arguments")
        return util.get_code_properties(arguments)
