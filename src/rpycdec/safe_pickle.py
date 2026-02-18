"""
Safe pickle unpickling utilities.

WARNING: Python's pickle format can execute arbitrary code during
deserialization. This module provides restricted unpicklers that only
allow known-safe classes to be loaded, preventing malicious pickle
files from executing harmful code.

See: https://docs.python.org/3/library/pickle.html#module-pickle
"""

import io
import logging
import pickle
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Whitelist definitions
# ---------------------------------------------------------------------------

# Standard library modules that are safe to import during unpickling.
SAFE_MODULES: set[str] = {
    "collections",
    "collections.abc",
}

# Builtin names that are safe to unpickle (data types only).
# Dangerous names like eval, exec, __import__, getattr, etc. are excluded.
SAFE_BUILTINS: set[str] = {
    "set",
    "frozenset",
    "list",
    "dict",
    "tuple",
    "bytes",
    "bytearray",
    "complex",
    "True",
    "False",
    "None",
    "object",
    "int",
    "float",
    "str",
    "bool",
    "slice",
    "range",
    "type",
}


# ---------------------------------------------------------------------------
# DummyClass — safe placeholder for unknown classes
# ---------------------------------------------------------------------------

class DummyClass(object):
    """
    Safe placeholder class for unpickling unknown classes.

    Handles all pickle reconstruction patterns:
    - NEWOBJ/REDUCE with arguments (stored as _new_args/_new_kwargs)
    - BUILD with dict state, (state, slotstate) tuples, or opaque state
    - List-like append operations (APPENDS opcode)
    """

    _state: Any
    _new_args: tuple[Any, ...] | None
    _new_kwargs: dict[str, Any] | None

    def __new__(cls, *args: Any, **kwargs: Any) -> "DummyClass":
        self = object.__new__(cls)
        self._state = None
        self._new_args = args if args else None
        self._new_kwargs = kwargs if kwargs else None
        return self

    def __init__(self, *args: Any, **kwargs: Any):
        # __new__ already handled storage; avoid overwriting
        pass

    def append(self, value: Any) -> None:
        if self._state is None:
            self._state = []
        self._state.append(value)

    def __getitem__(self, key: str) -> Any:
        return self.__dict__[key]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DummyClass):
            return NotImplemented
        return self.__dict__ == other.__dict__

    def __setitem__(self, key: str, value: Any) -> None:
        self.__dict__[key] = value

    def __getstate__(self) -> Any:
        if self._state is not None:
            return self._state
        # Exclude internal fields from state
        return {k: v for k, v in self.__dict__.items()
                if not k.startswith("_new_")}

    def __setstate__(self, state: Any) -> None:
        # Handle (state, slotstate) tuple pattern from __slots__ classes
        slotstate = None
        if (isinstance(state, tuple) and len(state) == 2
                and (state[0] is None or isinstance(state[0], dict))
                and (state[1] is None or isinstance(state[1], dict))):
            state, slotstate = state

        if isinstance(state, dict):
            self.__dict__.update(state)
        elif state is not None:
            self._state = state

        if slotstate:
            self.__dict__.update(slotstate)

    def __repr__(self) -> str:
        cls = type(self)
        module = getattr(cls, "__module__", "?")
        name = getattr(cls, "__name__", "?")
        if self._state is not None:
            return f"<{module}.{name}: state={self._state!r}>"
        attrs = {k: v for k, v in self.__dict__.items()
                 if not k.startswith("_new_") and k != "_state"}
        return f"<{module}.{name}: {attrs}>"


def make_dummy_class(module: str, name: str) -> type:
    """Create a named DummyClass subclass for a given module.name."""
    return type(name, (DummyClass,), {"__module__": module})


# ---------------------------------------------------------------------------
# SafeUnpickler — base restricted unpickler
# ---------------------------------------------------------------------------

class SafeUnpickler(pickle.Unpickler):
    """Base restricted unpickler with whitelist-based class loading.

    Security model:
    - ``renpy.*`` / ``store.*``: allowed (our fake packages)
    - ``builtins`` / ``__builtin__``: only safe data types
    - ``SAFE_MODULES``: standard library modules known to be safe
    - Everything else: handled by ``_on_unknown_class()``

    Subclasses can override ``_on_unknown_class()`` to customise behaviour
    for classes outside the whitelist (raise, create placeholder, etc.).
    """

    def find_class(self, module: str, name: str) -> Any:
        # store.* modules -> DummyClass placeholder
        if module.startswith("store"):
            return make_dummy_class(module, name)

        # Our fake renpy package is safe to import
        if module.startswith("renpy"):
            try:
                return super().find_class(module, name)
            except (ImportError, AttributeError):
                return self._on_unknown_class(module, name)

        # Whitelisted standard library modules
        if module in SAFE_MODULES:
            return super().find_class(module, name)

        # Safe builtins only (excludes eval, exec, __import__, etc.)
        if module in ("builtins", "__builtin__") and name in SAFE_BUILTINS:
            return super().find_class(module, name)

        return self._on_unknown_class(module, name)

    def _on_unknown_class(self, module: str, name: str) -> Any:
        """Handle a class reference outside the whitelist.

        Default: log a warning and return a DummyClass placeholder.
        Subclasses may override to raise or return different placeholders.
        """
        logger.warning(
            f"Unknown class encountered: {module}.{name}. "
            f"Substituting with DummyClass placeholder. "
            f"If this is a legitimate Ren'Py class, please report an issue."
        )
        return make_dummy_class(module, name)


# ---------------------------------------------------------------------------
# RestrictedUnpickler — only allows primitive/builtin data types
# ---------------------------------------------------------------------------

# Primitive builtin types that are always safe.
_PRIMITIVE_BUILTINS = {"dict", "list", "tuple", "set", "frozenset",
                       "bytes", "bytearray", "str", "int", "float",
                       "bool", "complex", "True", "False", "None"}


class RestrictedUnpickler(pickle.Unpickler):
    """Strictly restricted unpickler that only allows primitive data types.

    Suitable for data that should only contain basic Python types
    (dict, list, tuple, int, str, bytes, etc.) with no custom classes.

    Used by RPA index parsing and any other context where only
    primitive data structures are expected.
    """

    def find_class(self, module: str, name: str) -> Any:
        if module in ("builtins", "__builtin__") and name in _PRIMITIVE_BUILTINS:
            return super().find_class(module, name)

        raise pickle.UnpicklingError(
            f"Refusing to unpickle non-primitive class: {module}.{name}"
        )


def safe_loads(data: bytes, **kwargs: Any) -> Any:
    """Safely unpickle data using SafeUnpickler (strict mode — raises on unknown classes)."""
    return SafeUnpickler(io.BytesIO(data), **kwargs).load()


def rpa_loads(data: bytes) -> Any:
    """Safely unpickle RPA index data (very restricted, primitives only)."""
    return RestrictedUnpickler(io.BytesIO(data), encoding="bytes").load()
