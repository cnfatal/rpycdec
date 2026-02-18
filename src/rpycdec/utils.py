import os
import re


def safe_path(base_dir: str, filename: str) -> str:
    """Resolve *filename* under *base_dir* and guard against path traversal.

    Returns the resolved absolute path.  Raises ``ValueError`` if the
    resulting path escapes *base_dir*.
    """
    root = os.path.realpath(base_dir)
    dest = os.path.realpath(os.path.join(base_dir, filename))
    # dest must be inside root (or equal to root itself)
    if dest != root and not dest.startswith(root + os.sep):
        raise ValueError(f"Path traversal detected: {filename!r}")
    return dest


def write_file(filename: str, data: str):
    """
    write data to file
    """
    dir = os.path.dirname(filename)
    if dir and not os.path.exists(dir):
        os.makedirs(dir)
    with open(filename, "w", encoding="utf-8") as file:
        file.write(data)


def match_files(base_dir: str, pattern: str) -> list[str]:
    """
    match files in dir with regex pattern

    Parameters
    ----------
    base_dir : str
        directory to find in
    pattern : str
        regex pattern

    Returns
    -------
    list[str]
        matched filenames relative to base_dir
    """

    if pattern == "":
        pattern = ".*"
    results = []
    matched = re.compile(pattern)
    for root, _, files in os.walk(base_dir):
        for filename in files:
            filename = os.path.relpath(os.path.join(root, filename), base_dir)
            if matched.match(filename):
                results.append(filename)
    return results
