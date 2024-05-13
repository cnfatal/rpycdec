import ast
import random
from .object import Object


class StoreDeleted(object):
    pass


class StoreModule(object):
    pass


class StoreDict(dict):
    pass


class StoreBackup:
    pass


class NoRollback(object):
    pass


class WrapNode(ast.NodeTransformer):
    pass


class CompressedList(object):
    pass


class RevertableList(list):
    pass


class RevertableDict(dict):
    pass


class RevertableSet(set):
    pass


class RevertableObject(object):
    pass


class RollbackRandom(random.Random):
    pass


class DetRandom(random.Random):
    pass


class Rollback(Object):
    pass


class RollbackLog(Object):
    pass


class StoreProxy(object):
    pass


def py_compile(source, mode, filename="<none>", lineno=1, ast_node=False, cache=True):
    pass


def py_eval_bytecode(bytecode, globals=None, locals=None):  # @ReservedAssignment
    pass
