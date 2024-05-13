class Object(object):
    __version__ = 0

    nosave = []

    def __getstate__(self):
        rv = vars(self).copy()

        for f in self.nosave:
            if f in rv:
                del rv[f]

        rv["__version__"] = self.__version__

        return rv

    # None, to prevent this from being called when unnecessary.
    after_setstate = None

    def __setstate__(self, new_dict):
        version = new_dict.pop("__version__", 0)

        self.__dict__.update(new_dict)

        if version != self.__version__:
            self.after_upgrade(version)  # E1101

        if self.after_setstate:
            self.after_setstate()  # E1102


class Sentinel(object):
    pass
