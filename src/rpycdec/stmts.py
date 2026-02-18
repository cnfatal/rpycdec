import io
import logging
from os import path
import pickletools
import struct
import zlib

from renpy.ast import Node
from rpycdec.safe_pickle import SafeUnpickler

logger = logging.getLogger(__name__)

# A string at the start of each rpycv2 file.
RPYC2_HEADER = b"RENPY RPC2"


def read_rpyc_data(file: io.BufferedReader, slot):
    """
    Reads the binary data from `slot` in a .rpyc (v1 or v2) file. Returns
    the data if the slot exists, or None if the slot does not exist.
    """
    header_data = file.read(1024)
    # Legacy path.
    if header_data[: len(RPYC2_HEADER)] != RPYC2_HEADER:
        if slot != 1:
            return None
        file.seek(0)
        data = file.read()
        return zlib.decompress(data)
    # RPYC2 path.
    pos = len(RPYC2_HEADER)
    while True:
        header_slot, start, length = struct.unpack("III", header_data[pos : pos + 12])
        if slot == header_slot:
            break
        if header_slot == 0:
            return None
        pos += 12
    file.seek(start)
    data = file.read(length)
    return zlib.decompress(data)


def load(data: io.BufferedReader, slots: list[int] = [1, 2], **kwargs) -> Node | None:
    # 1 is statements before translation, 2 is after translation.
    for slot in slots:
        try:
            bindata = read_rpyc_data(data, slot)
        except Exception as e:
            logger.warning(f"Failed to read slot {slot}: {e}")
            data.seek(0)
            continue
        if bindata:
            if kwargs.get("dis", False):
                logger.info("Disassembling rpyc file...")
                pickletools.dis(bindata)

            unpickler = SafeUnpickler(
                io.BytesIO(bindata), encoding="utf-8", errors="surrogateescape"
            )
            data, stmts = unpickler.load()

            key = data.get("key", "unlocked")  # type: ignore
            return stmts
    raise Exception("Unsupported file format or invalid file")


def load_file(filename, **kwargs) -> Node | None:
    """
    load renpy code from rpyc file and return ast tree.
    """
    ext = path.splitext(filename)[1]
    if ext in [".rpy", ".rpym"]:
        raise NotImplementedError(
            "unsupport for pase rpy file or use renpy.parser.parse() in renpy's SDK"
        )
    # slot 2 is for pre-translated scripts, slot 1 is for normal scripts
    slots = [2, 1] if kwargs.get("pre_translated", False) else [1, 2]
    with open(filename, "rb") as file:
        return load(file, slots=slots, **kwargs)
