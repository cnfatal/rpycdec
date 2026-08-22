import logging
import os
import pickle
import re
import zlib
from collections.abc import Iterable
from io import BufferedIOBase
from pathlib import Path

from rpycdec.safe_pickle import rpa_loads
from rpycdec.utils import safe_path

logger = logging.getLogger(__name__)

RPA3_KEY = 0x42424242
RPA3_PADDING = b"Made with Ren'Py."
RPA3_HEADER_PLACEHOLDER = b"RPA-3.0 XXXXXXXXXXXXXXXX XXXXXXXX\n"


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
    return bytes(content)


def start_to_bytes(left: list | None) -> bytes:
    if not left:
        return b""
    if isinstance(left[0], bytes):
        return left[0]
    return left[0].encode("latin-1")


def normalize_archive_name(name: str) -> str:
    return name.replace(os.sep, "/")


def collect_rpa_files(
    sources: list[str],
    base_dir: str | None = None,
    output_path: str | None = None,
) -> list[tuple[str, str]]:
    """Collect files to add to an archive.

    Returns ``(archive_name, filesystem_path)`` tuples. Directories contribute
    all nested files, with deterministic sorting.
    """
    if not sources:
        raise ValueError("No source files were provided.")

    paths = [Path(src) for src in sources]
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(path)
        if not path.is_file() and not path.is_dir():
            raise ValueError(f"Unsupported source path: {path}")

    if base_dir is not None:
        base = Path(base_dir).resolve()
    elif len(paths) == 1 and paths[0].is_dir():
        base = paths[0].resolve()
    else:
        parents = [
            path.resolve().parent if path.is_file() else path.resolve()
            for path in paths
        ]
        base = Path(os.path.commonpath([str(parent) for parent in parents]))

    output = Path(output_path).resolve() if output_path else None
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()

    for path in sorted(paths, key=lambda p: str(p)):
        resolved = path.resolve()
        candidates = [resolved]
        if resolved.is_dir():
            candidates = sorted(
                (p for p in resolved.rglob("*") if p.is_file()),
                key=lambda p: str(p),
            )

        for file_path in candidates:
            if output is not None and file_path.resolve() == output:
                logger.info("skipping output archive: %s", file_path)
                continue

            try:
                archive_name = normalize_archive_name(
                    str(file_path.resolve().relative_to(base))
                )
            except ValueError as exc:
                raise ValueError(
                    f"{file_path} is not under base directory {base}"
                ) from exc

            if archive_name in ("", "."):
                archive_name = file_path.name

            if archive_name in seen:
                raise ValueError(f"Duplicate archive path: {archive_name}")

            seen.add(archive_name)
            entries.append((archive_name, str(file_path)))

    return entries


def create_rpa(
    output_path: str,
    sources: list[str],
    base_dir: str | None = None,
    key: int = RPA3_KEY,
):
    """Create a Ren'Py RPA-3.0 archive from files or directories."""
    entries = collect_rpa_files(sources, base_dir=base_dir, output_path=output_path)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    index: dict[str, list[tuple[int, int, bytes]]] = {}

    with open(output_path, "wb") as archive:
        archive.write(RPA3_HEADER_PLACEHOLDER)

        for archive_name, file_path in entries:
            archive.write(RPA3_PADDING)
            offset = archive.tell()
            size = os.path.getsize(file_path)

            with open(file_path, "rb") as source:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    archive.write(chunk)

            index[archive_name] = [(offset ^ key, size ^ key, b"")]
            logger.info("adding: %s", archive_name)

        index_offset = archive.tell()
        archive.write(zlib.compress(pickle.dumps(index, pickle.HIGHEST_PROTOCOL)))

        archive.seek(0)
        archive.write(b"RPA-3.0 %016x %08x\n" % (index_offset, key))


def _compile_file_filters(
    expressions: str | Iterable[str] | None,
    suffixes: str | Iterable[str] | None,
) -> tuple[list[re.Pattern[str]], tuple[str, ...]]:
    expression_values = (expressions,) if isinstance(expressions, str) else expressions
    suffix_values = (suffixes,) if isinstance(suffixes, str) else suffixes
    patterns = [re.compile(expression) for expression in expression_values or ()]
    normalized_suffixes = tuple(suffix.casefold() for suffix in suffix_values or ())
    if any(not suffix for suffix in normalized_suffixes):
        raise ValueError("RPA file suffixes must not be empty.")
    return patterns, normalized_suffixes


def _matches_file_filters(
    filename: str,
    patterns: list[re.Pattern[str]],
    suffixes: tuple[str, ...],
) -> bool:
    if not patterns and not suffixes:
        return True

    # RPA paths conventionally use forward slashes. Normalize legacy archives
    # so expressions behave consistently on every host platform.
    archive_path = filename.replace("\\", "/")
    return any(pattern.search(archive_path) for pattern in patterns) or (
        bool(suffixes) and archive_path.casefold().endswith(suffixes)
    )


def extract_rpa(
    r: BufferedIOBase,
    output_dir: str | None = None,
    expressions: str | Iterable[str] | None = None,
    suffixes: str | Iterable[str] | None = None,
):
    """Extract files from an RPA archive.

    When *expressions* or *suffixes* are provided, a file is extracted when
    its normalized archive path matches any regular expression or suffix.
    Regular expressions use :func:`re.search`; suffix matching ignores case.
    """
    output_dir = output_dir or "."
    patterns, normalized_suffixes = _compile_file_filters(expressions, suffixes)
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

        if not _matches_file_filters(filename, patterns, normalized_suffixes):
            logger.debug("skipping filtered file: %s", filename)
            continue

        # Path traversal protection. Resolve the destination before reading
        # the payload so rejected entries do not consume unnecessary memory.
        try:
            dest = safe_path(output_dir, filename)
        except ValueError:
            logger.warning("Skipping path traversal attempt: %s", filename)
            continue

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

        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            logger.info("extracting: %s", dest)
            f.write(data)
