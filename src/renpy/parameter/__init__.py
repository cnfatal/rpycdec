class Signature:
    def get_code(self, **kwargs) -> str:
        ret = ""
        if hasattr(self, "parameters"):
            params = ", ".join(self.parameters)
            ret += f"({params})"
        return ret


class Parameter:
    def get_code(self, **kwargs) -> str:
        raise NotImplementedError
