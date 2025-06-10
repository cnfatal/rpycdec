"""Module for decompiling Ren'Py compiled files (.rpyc) back to source code (.rpy)."""

import logging
import os

import renpy.ast
import renpy.sl2.slast
import renpy.util
from rpycdec import stmts, utils

logger = logging.getLogger(__name__)


def decompile_file(input_file, output_file=None):
    """
    decompile rpyc file into rpy file and write to output.
    """
    if not output_file:
        name, _ = os.path.splitext(input_file)
        output_file = f"{name}.rpy"
    stmt = stmts.load_file(input_file)
    try:
        code = renpy.util.get_code(stmt)
    except Exception as e:
        logger.error("decode file %s failed: %s", input_file, e)
        raise e
    utils.write_file(output_file, code)
    logger.info("decompile %s -> %s", input_file, output_file)


def decompile(input_path, output_path=None):
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
        decompile_file(input_path, output_path)
        return
    if not output_path:
        output_path = input_path
    for filename in utils.match_files(input_path, r".*\.rpym?c$"):
        try:
            decompile_file(
                os.path.join(input_path, filename),
                os.path.join(output_path, filename.removesuffix("c")),
            )
        except Exception as e:
            logger.error("decompile file %s failed: %s", filename, e)
            continue
