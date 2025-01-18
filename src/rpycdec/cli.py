import argparse
import logging
from rpycdec.decompile import decompile
from rpycdec.rpa import extract_rpa


logger = logging.getLogger(__name__)


def decompile_files(srcs: list[str]):
    """
    decompile rpyc file or directory.
    """
    for src in srcs:
        decompile(src)


def extract_rpa_files(srcs: list[str]):
    """
    extract rpa archive.
    """
    for src in srcs:
        with open(src, "rb") as f:
            extract_rpa(f)


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
    decompile_parser.set_defaults(func=decompile_files)

    unrpa_parser = subparsers.add_parser("unrpa", help="extract rpa archive")
    unrpa_parser.add_argument("src", nargs=1, help="rpa archive")
    unrpa_parser.set_defaults(func=extract_rpa_files)

    args = argparser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    if not args.command:
        argparser.print_help()
        return
    args.func(args.src)
