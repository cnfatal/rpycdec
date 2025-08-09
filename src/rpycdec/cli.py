import argparse
import logging
from rpycdec.decompile import decompile
from rpycdec.rpa import extract_rpa
from rpycdec.save import extract_save, restore_save
from rpycdec.translate import extract_translation


logger = logging.getLogger(__name__)


def decompile_files(srcs: list[str], **kwargs):
    """
    decompile rpyc file or directory.
    """
    for src in srcs:
        decompile(src, dis=kwargs.get("dissemble", False))


def extract_rpa_files(srcs: list[str], **kwargs):
    """
    extract rpa archive.
    """
    for src in srcs:
        with open(src, "rb") as f:
            extract_rpa(f)


def run_extract_translations(srcs: list[str], language: str = "None"):
    """
    extract translations from rpy files.
    """
    for src in srcs:
        extract_translation(src, language)


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
        "extract_translations", help="extract translations from rpy files"
    )
    extract_tl_parser.add_argument(
        "--language", "-l", default="None", help="translation language"
    )
    extract_tl_parser.add_argument("path", nargs=1, help="rpy file or directory")
    extract_tl_parser.set_defaults(
        func=lambda args: run_extract_translations(args.path, args.language)
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
