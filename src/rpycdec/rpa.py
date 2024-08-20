import os
import pickle
import zlib
from io import BufferedIOBase


def read_str(data: BufferedIOBase, eol: int = 0x00) -> bytes:
    content = bytearray()
    while True:
        c = data.read(1)
        if c[0] == eol:
            break
        content += c
    return content


def to_start(start: str | None | bytes) -> bytes:
    if not start:
        return b""
    if isinstance(start, bytes):
        return start
    return start.encode("latin-1")


def extract_rpa(r: BufferedIOBase, dir: str):
    header = read_str(r).decode("utf-8")
    lines = header.splitlines()
    metadata = lines[0].split()
    magic, metadata = metadata[0], metadata[1:]
    index_offset, metadata = int(metadata[0], 16), metadata[1:]
    if magic == "RPA-3.0":
        key, metadata = int(metadata[0], 16), metadata[1:0]
    else:
        raise Exception("magic %s not supported" % magic)

    # read index
    r.seek(index_offset)
    index = pickle.loads(zlib.decompress(r.read()))
    for k, v in index.items():
        index[k] = [
            (offset ^ key, dlen ^ key, b"" if len(left) == 0 else to_start(left[0]))
            for offset, dlen, *left in v
        ]

    for filename, entries in index.items():
        data = bytearray()
        for offset, dlen, start in entries:
            r.seek(offset)
            block = r.read(dlen)
            if start:
                if block.startswith(start):
                    block = block[len(start) :]
                else:
                    print("Warning: %s does not start with %s" % (filename, start))
            data += block

        filename = os.path.join(dir, filename)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "wb") as f:
            print("extracting: ", filename)
            f.write(data)
