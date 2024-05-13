import os
import re


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
