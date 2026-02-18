import logging
import os
import zlib
from io import BufferedIOBase

from rpycdec.safe_pickle import rpa_loads
from rpycdec.utils import safe_path

logger = logging.getLogger(__name__)


def read_until(data: BufferedIOBase, delimiter: int = 0x00) -> bytes:
    """Read bytes from stream until delimiter is found.

    Raises ValueError on unexpected EOF.
    """
    content = bytearray()
    while True:
        c = data.read(1)
        if not c:
            raise ValueError("Unexpected EOF while reading stream")
        if c[0] == delimiter:
            break
        content += c
    return content


def start_to_bytes(left: list | None) -> bytes:
    if not left:
        return b""
    if isinstance(left[0], bytes):
        return left[0]
    return left[0].encode("latin-1")


def extract_rpa(r: BufferedIOBase, output_dir: str | None = None):
    output_dir = output_dir or "."
    magic = read_until(r, 0x20)
    if magic != b"RPA-3.0":
        raise ValueError("Not a Ren'Py RPA-3.0 archive.")
    index_offset = int(read_until(r, 0x20), 16)
    key = int(read_until(r, 0x0A).decode(), 16)

    # read index
    r.seek(index_offset)
    index = rpa_loads(zlib.decompress(r.read()))

    for k, v in index.items():
        index[k] = [
            (offset ^ key, dlen ^ key, start_to_bytes(left))
            for offset, dlen, *left in v
        ]

    for filename, entries in index.items():
        # Handle bytes filenames from Python 2 era archives
        if isinstance(filename, bytes):
            filename = filename.decode("utf-8", errors="surrogateescape")

        data = bytearray()
        for offset, dlen, start in entries:
            r.seek(offset)
            block = r.read(dlen)
            if start:
                if block.startswith(start):
                    block = block[len(start) :]
                else:
                    logger.warning(
                        "%s does not start with expected prefix %s", filename, start
                    )
            data += block

        # Path traversal protection
        try:
            dest = safe_path(output_dir, filename)
        except ValueError:
            logger.warning("Skipping path traversal attempt: %s", filename)
            continue

        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            logger.info("extracting: %s", dest)
            f.write(data)
