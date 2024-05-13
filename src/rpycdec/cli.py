import argparse
import logging
from rpycdec.decompile import decompile


logger = logging.getLogger(__name__)


def main():
    """
    command line tool entry.
    """
    logging.basicConfig(level=logging.INFO)
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "--verbose", "-v", action="store_true", help="verbose output"
    )
    argparser.add_argument("src", nargs=1, help="rpyc file or directory")
    args = argparser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    for src in args.src:
        decompile(src)
