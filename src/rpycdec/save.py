import io
import json
import os
import pickle
import pickletools
import zipfile


class DynamicClass(object):

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        instance._state = None
        return instance

    def __setstate__(self, state):
        self._state = state

    def __getstate__(self):
        return self._state

    def __setitem__(self, key, value):
        if self._state is None:
            self._state = {}
        self._state[key] = value

    def append(self, value):
        if self._state is None:
            self._state = []
        self._state.append(value)


class DynamicClassUnpickler(pickle.Unpickler):

    def find_class(self, module: str, name: str):
        if module == "builtins":
            return super().find_class(module, name)
        # if module.startswith("renpy.revertable"):
        # return super().find_class(module, name)
        print(f"find_class: {module}.{name}")
        cls = type(
            name,
            (DynamicClass,),
            {
                "__module__": module,
                "__class__": name,
                "__real_class__": f"{module}.{name}",
            },
        )
        return cls


def load_save_data(data: io.BytesIO) -> tuple[bytes, str]:
    """
    Load save data from a save file

    return the data and signatures
    """
    with zipfile.ZipFile(data, "r") as zf:
        log = zf.read("log")
        try:
            token = zf.read("signatures").decode("utf-8")
        except:
            token = ""
        return log, token


def load_save(file_path: str) -> dict:
    with open(file_path, "rb") as f:
        log, signatures = load_save_data(f)
    roots, log = pickle.loads(log, encoding="utf-8", errors="surrogateescape")


def extract_save(file_path: str, extracted_dir: str = "", **kwargs):
    if not extracted_dir:
        extracted_dir = file_path + ".extracted"
    with open(file_path, "rb") as f:
        log, signatures = load_save_data(f)
    if kwargs.get("dissemble", False):
        pickletools.dis(log)

    loaded = DynamicClassUnpickler(io.BytesIO(log)).load()
    root, log = loaded

    os.makedirs(extracted_dir, exist_ok=True)
    with open(extracted_dir + "/root.json", "wb") as root_file:
        json.dump(root, root_file, indent=4)
    with open(extracted_dir + "/log.json", "wb") as log_file:
        json.dump(log, log_file, indent=4)
    with open(extracted_dir + "/signatures.json", "wb") as sig_file:
        json.dump(signatures, sig_file, indent=4)


def restore_save(extracted_dir: str, into_file: str = "", **kwargs):
    if not into_file:
        into_file = extracted_dir + ".restored"
    with open(into_file, "wb") as f:
        save_data = io.BytesIO()
        with zipfile.ZipFile(save_data, "w") as zf:
            zf.writestr("log", pickle.dumps(kwargs.get("log", b"")))
            zf.writestr("signatures", kwargs.get("signatures", "").encode("utf-8"))
        f.write(save_data.getvalue())
