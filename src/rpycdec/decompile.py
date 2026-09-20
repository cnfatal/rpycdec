"""Module for decompiling Ren'Py compiled files (.rpyc) back to source code (.rpy)."""

import logging
import os

from renpy import ast, util
from rpycdec import stmts, utils

logger = logging.getLogger(__name__)


def trim_implicit_return(stmts_: list[ast.Node]) -> list[ast.Node]:
    """
    Drops the empty return Ren'Py appends to every parsed script file.

    .. code-block:: python

        # renpy/parser.py parse()
        rv.append(ast.Return((rv[-1].filename, linenumber), None))

    It always ends the top level statement list. Writing it out would make the
    next compilation append another one, so every round trip would gain a
    ``return``. ``util.get_code`` must not do this: inside a block a trailing
    empty return is written by the author.
    """
    if stmts_ and isinstance(stmts_[-1], ast.Return):
        if not util.attr(stmts_[-1], "expression"):
            return stmts_[:-1]
    return stmts_


def decompile_file(input_file, output_path=None, **kwargs):
    """
    decompile rpyc file into rpy file and write to output.
    """
    if not output_path:
        name, _ = os.path.splitext(input_file)
        output_path = f"{name}.rpy"

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    try:
        stmt = trim_implicit_return(stmts.load_file(input_file, **kwargs))
        code = util.get_code(stmt)
    except Exception as e:
        logger.error("decode file %s failed: %s", input_file, e)
        raise
    utils.write_file(output_path, code)
    logger.info("decompile %s -> %s", input_file, output_path)


def decompile(input_path, output_path=None, **kwargs):
    """
    decompile rpyc file or directory into rpy

    Parameters
    ----------
    input_path : str
        path to rpyc file or directory contains rpyc files
    output_path : str, optional
        output path, by default it's same path of input_path.
    """
    if not os.path.isdir(input_path):
        if output_path:
            name, _ = os.path.splitext(os.path.basename(input_path))
            output_path = os.path.join(output_path, f"{name}.rpy")
        decompile_file(input_path, output_path, **kwargs)
        return
    if not output_path:
        output_path = input_path
    for filename in utils.match_files(input_path, r".*\.rpym?c$"):
        decompile_file(
            os.path.join(input_path, filename),
            os.path.join(output_path, filename.removesuffix("c")),
            **kwargs,
        )
