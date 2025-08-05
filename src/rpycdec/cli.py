import argparse
import logging
from rpycdec.decompile import decompile
from rpycdec.rpa import extract_rpa
from rpycdec.translate import extract_translation


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


def run_extract_translation(srcs: list[str], language: str = "None"):
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
    decompile_parser.set_defaults(func=decompile_files)

    unrpa_parser = subparsers.add_parser("unrpa", help="extract rpa archive")
    unrpa_parser.add_argument("src", nargs=1, help="rpa archive")
    unrpa_parser.set_defaults(func=extract_rpa_files)

    extract_translation_parser = subparsers.add_parser(
        "extract_translation", help="extract translations from rpy files"
    )
    extract_translation_parser.add_argument(
        "--language", "-l", default="None", help="translation language"
    )
    extract_translation_parser.add_argument(
        "src", nargs=1, help="rpy file or directory"
    )
    extract_translation_parser.set_defaults(func=run_extract_translation)

    args = argparser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    if not args.command:
        argparser.print_help()
        return
    args.func(args.src)
