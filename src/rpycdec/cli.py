import argparse
import logging
import os
from rpycdec.decompile import decompile
from rpycdec.rpa import extract_rpa
from rpycdec.save import extract_save, restore_save
from rpycdec.translate import translate


logger = logging.getLogger(__name__)


def decompile_files(srcs: list[str], **kwargs):
    """
    decompile rpyc file or directory.
    """
    for src in srcs:
        decompile(src, dis=kwargs.get("disassemble", False))


def extract_rpa_files(srcs: list[str], **kwargs):
    """
    extract rpa archive.
    """
    for src in srcs:
        with open(src, "rb") as f:
            extract_rpa(f, dir=os.path.dirname(src))


def run_translate(srcs: list[str], source_lang: str, target_lang: str, **kwargs):
    """
    extract translations from rpy files.
    """
    for src in srcs:
        translate(src, source_lang, target_lang, **kwargs)


def main():
    """
    command line tool entry.
    """
    logging.basicConfig(level=logging.INFO)

    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "--verbose", "-v", action="store_true", help="verbose output"
    )
    subparsers = argparser.add_subparsers(
        title="subcommands", dest="command", help="subcommand help"
    )

    decompile_parser = subparsers.add_parser("decompile", help="decompile rpyc file")
    decompile_parser.add_argument("src", nargs=1, help="rpyc file or directory")
    decompile_parser.add_argument(
        "--disassemble", "-d", action="store_true", help="disassemble rpyc file"
    )
    decompile_parser.set_defaults(
        func=lambda args: decompile_files(args.src, **vars(args))
    )

    unrpa_parser = subparsers.add_parser("unrpa", help="extract rpa archive")
    unrpa_parser.add_argument("file", nargs=1, help="rpa archive")
    unrpa_parser.set_defaults(
        func=lambda args: extract_rpa_files(args.file, **vars(args))
    )

    extract_tl_parser = subparsers.add_parser(
        "translate",
        help="""translate files in tl/<language> directory
        rpycdec translate game/tl/None --src en --dest chinese
        """,
    )
    extract_tl_parser.add_argument("--src", help="source language", default="en")
    extract_tl_parser.add_argument("--dest", help="target language", default="zh")
    extract_tl_parser.add_argument("path", nargs=1, help="tl/<language> directory")
    extract_tl_parser.set_defaults(
        func=lambda args: run_translate(args.path, args.src, args.dest)
    )

    save_parser = subparsers.add_parser("save", help="save operations")
    save_subparsers = save_parser.add_subparsers(
        title="save subcommands", dest="save_command", help="save subcommand help"
    )
    save_extract_parser = save_subparsers.add_parser(
        "extract", help="extract save data"
    )
    save_extract_parser.add_argument("path", nargs=1, help="save-file path")
    save_extract_parser.add_argument("dest", nargs="?", help="extract to directory")
    save_extract_parser.set_defaults(
        func=lambda args: extract_save(args.path[0], args.dest, **vars(args))
    )

    save_restore_parser = save_subparsers.add_parser(
        "restore", help="restore save data from extracted directory"
    )
    save_restore_parser.add_argument("path", nargs=1, help="extracted directory")
    save_restore_parser.add_argument("dest", nargs=1, help="restore to save-file")
    save_restore_parser.set_defaults(
        func=lambda args: restore_save(args.path[0], args.dest[0])
    )

    args = argparser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    if not args.command:
        argparser.print_help()
        return
    args.func(args)
