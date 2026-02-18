"""
Ren'Py Save File Parser and Writer

Ren'Py save files are ZIP archives containing:
- screenshot.png: Save screenshot
- extra_info: UTF-8 encoded save name/description
- json: JSON metadata (version, timestamp, etc.)
- renpy_version: Ren'Py version string
- log: Pickle serialized game state (roots, log)
- signatures: Digital signature for integrity verification

This module provides functionality to:
1. Extract save files to JSON for manual editing
2. Restore edited JSON back to valid save files
"""

import base64
import io
import json
import os
import pickle
import pickletools
import zipfile
from typing import Any, Tuple

from rpycdec.safe_pickle import (
    SafeUnpickler,
    SAFE_MODULES,
)


class DynamicObject:
    """
    A dynamic object that can represent any Ren'Py class during unpickling.
    Stores the original class name and module for JSON round-trip serialization.

    Unlike ``DummyClass`` (safe_pickle.py) which spreads state into ``__dict__``
    for attribute access during decompilation, ``DynamicObject`` keeps state
    as-is in ``_state`` so it can be faithfully serialized to / from JSON.

    Handles all pickle reconstruction patterns:
    - NEWOBJ/REDUCE with arguments
    - BUILD with state (dict or opaque)
    - APPENDS (list-like append)
    - SETITEMS (dict-like __setitem__)
    """

    # Class-level defaults — overridden by type() in _on_unknown_class.
    # Using class attrs ensures they survive even when pickle skips __init__
    # (e.g. the NEWOBJ opcode calls __new__ only).
    _class_name: str = ""
    _module_name: str = ""
    _state: Any
    _items: list[Any] | None
    _new_args: tuple[Any, ...] | None

    def __new__(cls, *args: Any, **kwargs: Any) -> "DynamicObject":
        self = object.__new__(cls)
        self._state = None
        self._items = None
        self._new_args = args if args else None
        return self

    def __init__(self, *args: Any, **kwargs: Any):
        # __new__ already handled initialization; nothing to do.
        pass

    # -- pickle BUILD --

    def __setstate__(self, state: Any) -> None:
        self._state = state

    def __getstate__(self) -> Any:
        return self._state

    # -- pickle APPENDS --

    def append(self, item: Any) -> None:
        if self._items is None:
            self._items = []
        self._items.append(item)

    # -- pickle SETITEMS --

    def __setitem__(self, key: Any, value: Any) -> None:
        if self._state is None:
            self._state = {}
        if isinstance(self._state, dict):
            self._state[key] = value

    # -- re-pickling / repr --

    def __reduce__(self):
        """Support re-pickling by returning the original class info."""
        return (
            _reconstruct_object,
            (self._module_name, self._class_name, self._state),
        )

    def __repr__(self) -> str:
        return f"<{self._module_name}.{self._class_name}: {self._state}>"

    # -- JSON round-trip helpers --

    def to_json_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""
        result: dict[str, Any] = {
            "__class__": self._class_name,
            "__module__": self._module_name,
            "__state__": _to_json_serializable(self._state),
        }
        if self._items:
            result["__items__"] = _to_json_serializable(self._items)
        return result

    @classmethod
    def from_json_dict(cls, data: dict) -> "DynamicObject":
        """Create a DynamicObject from a JSON dictionary."""
        obj = cls()
        obj._class_name = data.get("__class__", "")
        obj._module_name = data.get("__module__", "")
        obj._state = _from_json_serializable(data.get("__state__"))
        items = data.get("__items__")
        if items:
            obj._items = _from_json_serializable(items)
        return obj


# Modules allowed for reconstruction (renpy/store fake packages + safe stdlib)
_RECONSTRUCT_SAFE_PREFIXES = ("renpy.", "store.")


def _reconstruct_object(module_name: str, class_name: str, state: Any) -> Any:
    """Reconstruct an object from its module, class name, and state.

    Only allows importing from renpy.*/store.* (our fake packages) and
    whitelisted standard library modules. All other modules fall back
    to DynamicObject.
    """
    # Only allow our fake packages and whitelisted modules
    is_safe = (
        any(module_name.startswith(p) for p in _RECONSTRUCT_SAFE_PREFIXES)
        or module_name in ("renpy", "store")
        or module_name in SAFE_MODULES
    )
    if is_safe:
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            obj = object.__new__(cls)
            if state is not None:
                if hasattr(obj, "__setstate__"):
                    obj.__setstate__(state)
                elif isinstance(state, dict):
                    obj.__dict__.update(state)
            return obj
        except (ImportError, AttributeError):
            pass

    # Fall back to DynamicObject
    obj = DynamicObject()
    obj._class_name = class_name
    obj._module_name = module_name
    obj._state = state
    return obj


class SaveUnpickler(SafeUnpickler):
    """Safe unpickler for Ren'Py save files.

    Extends SafeUnpickler to replace unknown classes with DynamicObject
    instances (instead of raising) so save data can be serialized to JSON.
    """

    def __init__(
        self,
        file,
        *,
        fix_imports: bool = False,
        encoding: str = "ASCII",
        errors: str = "strict",
        verbose: bool = False,
    ):
        super().__init__(
            file, fix_imports=fix_imports, encoding=encoding, errors=errors
        )
        self.verbose = verbose

    def _on_unknown_class(self, module: str, name: str) -> type:
        """Return a DynamicObject subclass instead of raising."""
        if self.verbose:
            print(f"Creating dynamic class: {module}.{name}")
        return type(
            name,
            (DynamicObject,),
            {
                "__module__": module,
                "_class_name": name,
                "_module_name": module,
            },
        )


class SavePickler(pickle.Pickler):
    """
    Custom pickler that handles DynamicObject instances by restoring
    their original class information.
    """

    def reducer_override(self, obj):
        if isinstance(obj, DynamicObject):
            # Return a reduction that will reconstruct the original class
            return (
                _reconstruct_object,
                (obj._module_name, obj._class_name, obj._state),
            )
        # Fall back to default behavior
        return NotImplemented


def _to_json_serializable(obj: Any) -> Any:
    """Convert a Python object to a JSON-serializable structure."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj

    if isinstance(obj, bytes):
        return {"__bytes__": base64.b64encode(obj).decode("ascii")}

    if isinstance(obj, tuple):
        return {"__tuple__": [_to_json_serializable(item) for item in obj]}

    if isinstance(obj, list):
        return [_to_json_serializable(item) for item in obj]

    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            # JSON keys must be strings
            if isinstance(key, str):
                json_key = key
            elif isinstance(key, (int, float, bool)):
                json_key = f"__key_{type(key).__name__}__:{key}"
            elif isinstance(key, tuple):
                json_key = f"__key_tuple__:{json.dumps(_to_json_serializable(key))}"
            else:
                json_key = f"__key_repr__:{repr(key)}"
            result[json_key] = _to_json_serializable(value)
        return result

    if isinstance(obj, set):
        return {"__set__": [_to_json_serializable(item) for item in obj]}

    if isinstance(obj, frozenset):
        return {"__frozenset__": [_to_json_serializable(item) for item in obj]}

    if isinstance(obj, DynamicObject):
        return obj.to_json_dict()

    # For other objects, try to extract state
    if hasattr(obj, "__dict__"):
        return {
            "__class__": obj.__class__.__name__,
            "__module__": obj.__class__.__module__,
            "__state__": _to_json_serializable(obj.__dict__),
        }

    if hasattr(obj, "__getstate__"):
        return {
            "__class__": obj.__class__.__name__,
            "__module__": obj.__class__.__module__,
            "__state__": _to_json_serializable(obj.__getstate__()),
        }

    # Fallback: convert to string representation
    return {"__repr__": repr(obj), "__type__": type(obj).__name__}


def _from_json_serializable(obj: Any) -> Any:
    """Convert a JSON structure back to Python objects."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj

    if isinstance(obj, list):
        return [_from_json_serializable(item) for item in obj]

    if isinstance(obj, dict):
        # Check for special types
        if "__bytes__" in obj:
            return base64.b64decode(obj["__bytes__"])

        if "__tuple__" in obj:
            return tuple(_from_json_serializable(item) for item in obj["__tuple__"])

        if "__set__" in obj:
            return set(_from_json_serializable(item) for item in obj["__set__"])

        if "__frozenset__" in obj:
            return frozenset(
                _from_json_serializable(item) for item in obj["__frozenset__"]
            )

        if "__class__" in obj and "__module__" in obj:
            return DynamicObject.from_json_dict(obj)

        if "__repr__" in obj:
            # Cannot reconstruct, return as-is with warning marker
            return {"__unrecoverable__": obj["__repr__"]}

        # Regular dict with possibly encoded keys
        result = {}
        for key, value in obj.items():
            if key.startswith("__key_int__:"):
                actual_key = int(key.split(":", 1)[1])
            elif key.startswith("__key_float__:"):
                actual_key = float(key.split(":", 1)[1])
            elif key.startswith("__key_bool__:"):
                actual_key = key.split(":", 1)[1] == "True"
            elif key.startswith("__key_tuple__:"):
                actual_key = tuple(
                    _from_json_serializable(json.loads(key.split(":", 1)[1]))
                )
            elif key.startswith("__key_repr__:"):
                # Cannot fully reconstruct, use string
                actual_key = key.split(":", 1)[1]
            else:
                actual_key = key
            result[actual_key] = _from_json_serializable(value)
        return result

    return obj


def load_save_zip(file_path: str) -> dict:
    """
    Load all components from a Ren'Py save file.

    Returns a dict with keys:
    - screenshot: bytes or None
    - extra_info: str
    - json: dict (parsed JSON metadata)
    - renpy_version: str
    - log: bytes (raw pickle data)
    - signatures: str
    """
    with zipfile.ZipFile(file_path, "r") as zf:
        result = {
            "screenshot": None,
            "extra_info": "",
            "json": {},
            "renpy_version": "",
            "log": b"",
            "signatures": "",
        }

        namelist = zf.namelist()

        if "screenshot.png" in namelist:
            result["screenshot"] = zf.read("screenshot.png")

        if "extra_info" in namelist:
            result["extra_info"] = zf.read("extra_info").decode("utf-8")

        if "json" in namelist:
            result["json"] = json.loads(zf.read("json").decode("utf-8"))

        if "renpy_version" in namelist:
            result["renpy_version"] = zf.read("renpy_version").decode("utf-8")

        if "log" in namelist:
            result["log"] = zf.read("log")

        if "signatures" in namelist:
            result["signatures"] = zf.read("signatures").decode("utf-8")

        return result


def parse_save_log(log_data: bytes, verbose: bool = False) -> Tuple[Any, Any]:
    """
    Parse the pickle log data from a save file.

    Returns (roots, log) tuple.
    """
    unpickler = SaveUnpickler(
        io.BytesIO(log_data),
        verbose=verbose,
        encoding="utf-8",
        errors="surrogateescape",
    )
    return unpickler.load()


def serialize_save_log(roots: Any, log: Any) -> bytes:
    """
    Serialize roots and log back to pickle format.
    """
    buffer = io.BytesIO()
    pickler = SavePickler(buffer, protocol=2)
    pickler.dump((roots, log))
    return buffer.getvalue()


def extract_save(
    file_path: str,
    extracted_dir: str = "",
    dissemble: bool = False,
    verbose: bool = False,
    **kwargs,
):
    """
    Extract a Ren'Py save file to a directory with JSON files for editing.

    Creates:
    - metadata.json: Contains extra_info, json metadata, renpy_version, signatures
    - roots.json: The game state roots (variables, etc.)
    - log.json: The game log/history
    - screenshot.png: The save screenshot (if present)

    Args:
        file_path: Path to the .save file
        extracted_dir: Output directory (default: {file_path}.extracted)
        dissemble: If True, print pickle disassembly to stdout
        verbose: If True, print verbose class loading info
    """
    if not extracted_dir:
        extracted_dir = file_path + ".extracted"

    print(f"Extracting save file: {file_path}")
    print(f"Output directory: {extracted_dir}")

    # Load the save file
    save_data = load_save_zip(file_path)

    if dissemble:
        print("\n=== Pickle Disassembly ===")
        pickletools.dis(save_data["log"])
        print("=== End Disassembly ===\n")

    # Parse the log data
    roots, log = parse_save_log(save_data["log"], verbose=verbose)

    # Create output directory
    os.makedirs(extracted_dir, exist_ok=True)

    # Save metadata
    metadata = {
        "extra_info": save_data["extra_info"],
        "json": save_data["json"],
        "renpy_version": save_data["renpy_version"],
        "signatures": save_data["signatures"],
    }
    metadata_path = os.path.join(extracted_dir, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"  Saved: metadata.json")

    # Save roots
    roots_path = os.path.join(extracted_dir, "roots.json")
    with open(roots_path, "w", encoding="utf-8") as f:
        json.dump(_to_json_serializable(roots), f, indent=2, ensure_ascii=False)
    print(f"  Saved: roots.json")

    # Save log
    log_path = os.path.join(extracted_dir, "log.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(_to_json_serializable(log), f, indent=2, ensure_ascii=False)
    print(f"  Saved: log.json")

    # Save screenshot if present
    if save_data["screenshot"]:
        screenshot_path = os.path.join(extracted_dir, "screenshot.png")
        with open(screenshot_path, "wb") as f:
            f.write(save_data["screenshot"])
        print(f"  Saved: screenshot.png")

    print(f"\nExtraction complete!")
    print(f"Edit roots.json or log.json, then use 'restore' to create a new save file.")


def restore_save(
    extracted_dir: str,
    output_file: str = "",
    key_file: str = "",
    **kwargs,
):
    """
    Restore a Ren'Py save file from extracted JSON files.

    Reads:
    - metadata.json: Contains extra_info, json metadata, renpy_version, signatures
    - roots.json: The game state roots
    - log.json: The game log/history
    - screenshot.png: The save screenshot (optional)

    Args:
        extracted_dir: Directory containing extracted JSON files
        output_file: Output save file path (default: {extracted_dir}.save)
        key_file: Path to security_keys.txt for re-signing (optional)
    """
    if not output_file:
        output_file = extracted_dir.rstrip("/").removesuffix(".extracted") + ".restored.save"

    print(f"Restoring save file from: {extracted_dir}")
    print(f"Output file: {output_file}")

    # Load metadata
    metadata_path = os.path.join(extracted_dir, "metadata.json")
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    print(f"  Loaded: metadata.json")

    # Load roots
    roots_path = os.path.join(extracted_dir, "roots.json")
    with open(roots_path, "r", encoding="utf-8") as f:
        roots_json = json.load(f)
    roots = _from_json_serializable(roots_json)
    print(f"  Loaded: roots.json")

    # Load log
    log_path = os.path.join(extracted_dir, "log.json")
    with open(log_path, "r", encoding="utf-8") as f:
        log_json = json.load(f)
    log = _from_json_serializable(log_json)
    print(f"  Loaded: log.json")

    # Load screenshot if present
    screenshot = None
    screenshot_path = os.path.join(extracted_dir, "screenshot.png")
    if os.path.exists(screenshot_path):
        with open(screenshot_path, "rb") as f:
            screenshot = f.read()
        print(f"  Loaded: screenshot.png")

    # Serialize the game state
    log_data = serialize_save_log(roots, log)

    # Handle signatures
    if key_file:
        print(f"  Re-signing with key: {key_file}")
        signatures = sign_data(log_data, key_file)
        print(f"  Generated new signature")
    else:
        # Keep original signatures (will be invalid for modified saves)
        signatures = metadata.get("signatures", "")

    # Create the save file
    output_file_tmp = output_file + ".tmp"
    with zipfile.ZipFile(output_file_tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        # Screenshot
        if screenshot:
            zf.writestr("screenshot.png", screenshot)

        # Extra info
        zf.writestr("extra_info", metadata.get("extra_info", "").encode("utf-8"))

        # JSON metadata
        zf.writestr("json", json.dumps(metadata.get("json", {})).encode("utf-8"))

        # Ren'Py version
        zf.writestr("renpy_version", metadata.get("renpy_version", "").encode("utf-8"))

        # Log data
        zf.writestr("log", log_data)

        # Signatures
        zf.writestr("signatures", signatures.encode("utf-8"))

    # Atomic rename
    if os.path.exists(output_file):
        os.unlink(output_file)
    os.rename(output_file_tmp, output_file)

    print(f"\nRestore complete!")
    print(f"Save file created: {output_file}")

    if not key_file:
        print(
            f"\nNote: No signing key provided. Original signatures preserved but invalid."
        )
        print(f"Use --key to provide security_keys.txt for valid signatures.")
        print(f"Some games with strict signature checking may reject modified saves.")


def sign_data(log_data: bytes, key_file: str) -> str:
    """
    Sign log data using ECDSA keys from a Ren'Py security_keys.txt file.

    The key file is typically located at:
    <game_save_dir>/tokens/security_keys.txt

    Args:
        log_data: The pickle-serialized game state (log) data
        key_file: Path to security_keys.txt containing the signing key

    Returns:
        Signature string in Ren'Py format
    """
    try:
        import ecdsa
    except ImportError:
        raise ImportError(
            "ecdsa library required for signing. Install with: pip install ecdsa"
        )

    def encode_line(kind: str, key: bytes, sig: bytes = b"") -> str:
        """Encode a signature line in Ren'Py format."""
        key_b64 = base64.b64encode(key).decode("ascii")
        if sig:
            sig_b64 = base64.b64encode(sig).decode("ascii")
            return f"{kind} {key_b64} {sig_b64}\n"
        return f"{kind} {key_b64}\n"

    def decode_line(line: str) -> Tuple[str, bytes, bytes]:
        """Decode a signature line from Ren'Py format."""
        parts = line.strip().split()
        if len(parts) < 2:
            return "", b"", b""
        kind = parts[0]
        key = base64.b64decode(parts[1])
        sig = base64.b64decode(parts[2]) if len(parts) > 2 else b""
        return kind, key, sig

    signatures = ""

    with open(key_file, "r") as f:
        for line in f:
            kind, key_der, _ = decode_line(line)
            if kind == "signing-key":
                try:
                    sk = ecdsa.SigningKey.from_der(key_der)
                    if sk is not None and sk.verifying_key is not None:
                        sig = sk.sign(log_data)
                        signatures += encode_line(
                            "signature", sk.verifying_key.to_der(), sig
                        )
                except Exception as e:
                    print(f"Warning: Failed to sign with key: {e}")

    return signatures


def generate_new_key(key_file: str) -> str:
    """
    Generate a new ECDSA signing key and save to file.

    This creates a new security_keys.txt that can be used to sign saves.
    Note: Saves signed with this key will trigger a trust dialog in the game.

    Args:
        key_file: Path to save the new security_keys.txt

    Returns:
        Path to the created key file
    """
    try:
        import ecdsa
    except ImportError:
        raise ImportError("ecdsa library required. Install with: pip install ecdsa")

    sk = ecdsa.SigningKey.generate(curve=ecdsa.NIST256p)
    vk = sk.verifying_key

    if vk is not None:
        sk_b64 = base64.b64encode(sk.to_der()).decode("ascii")
        vk_b64 = base64.b64encode(vk.to_der()).decode("ascii")
        line = f"signing-key {sk_b64} {vk_b64}\n"

        os.makedirs(os.path.dirname(key_file) or ".", exist_ok=True)
        with open(key_file, "w") as f:
            f.write(line)

        print(f"Generated new signing key: {key_file}")
        return key_file

    raise RuntimeError("Failed to generate signing key")


def dump_save_info(file_path: str):
    """
    Print summary information about a save file.
    """
    save_data = load_save_zip(file_path)

    print(f"Save file: {file_path}")
    print(f"\n=== Metadata ===")
    print(f"Extra info: {save_data['extra_info']}")
    print(f"Ren'Py version: {save_data['renpy_version']}")
    print(f"\n=== JSON Metadata ===")
    for key, value in save_data["json"].items():
        print(f"  {key}: {value}")

    print(f"\n=== Contents ===")
    print(f"Screenshot: {'Yes' if save_data['screenshot'] else 'No'}")
    print(f"Log data size: {len(save_data['log'])} bytes")
    print(f"Has signatures: {'Yes' if save_data['signatures'] else 'No'}")
