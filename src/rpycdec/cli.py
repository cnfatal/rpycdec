import argparse
import logging
import os
import sys

from rpycdec.decompile import decompile
from rpycdec.rpa import extract_rpa
from rpycdec.save import extract_save, restore_save, dump_save_info, generate_new_key
from rpycdec.translate import extract_translations
from rpycdec.apk import extract_apk


logger = logging.getLogger(__name__)


def decompile_files(srcs: list[str], **kwargs):
    """
    decompile rpyc file or directory.
    """
    for src in srcs:
        decompile(
            src,
            output_path=kwargs.get("output"),
            dis=kwargs.get("disassemble", False),
        )


def extract_rpa_files(srcs: list[str], **kwargs):
    """
    extract rpa archive.
    """
    for src in srcs:
        with open(src, "rb") as f:
            output_path = kwargs.get("output") or os.path.dirname(src)
            extract_rpa(f, output_dir=output_path)


def run_extract_translations(
    srcs: list[str], language: str, output: str | None = None, **kwargs
):
    """
    extract translations from rpy files.
    """
    for src in srcs:
        # Default output to current directory, extract_translations will create tl/{language}/
        dest = output or "."
        extract_translations(
            game_dir=src,
            output_dir=dest,
            language=language,
            include_dialogues=kwargs.get("include_dialogues", True),
            include_strings=kwargs.get("include_strings", True),
            empty_translation=kwargs.get("empty_translation", False),
        )


def extract_game_from_apk(apk_path: str, **kwargs):
    """
    Extract Ren'Py game from Android APK file.
    """
    extract_apk(
        apk_path=apk_path,
        output_dir=kwargs.get("output"),
    )


SECURITY_WARNING = (
    "\033[33mSecurity Warning: This tool uses a restricted pickle unpickler with "
    "whitelist-based class loading to mitigate arbitrary code execution risks. "
    "However, no safeguard is perfect. Only process files from trusted sources.\033[0m"
)


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
    decompile_parser.add_argument("src", nargs="+", help="rpyc file or directory")
    decompile_parser.add_argument(
        "--output",
        "-o",
        help="output path",
    )
    decompile_parser.add_argument(
        "--disassemble", "-d", action="store_true", help="disassemble rpyc file"
    )
    decompile_parser.set_defaults(
        func=lambda args: decompile_files(args.src, **vars(args))
    )

    unrpa_parser = subparsers.add_parser("unrpa", help="extract rpa archive")
    unrpa_parser.add_argument("file", nargs=1, help="rpa archive")
    unrpa_parser.add_argument(
        "--output",
        "-o",
        help="output path",
    )
    unrpa_parser.set_defaults(
        func=lambda args: extract_rpa_files(args.file, **vars(args))
    )

    extract_game_parser = subparsers.add_parser(
        "extract-game", help="extract Ren'Py game from Android APK file"
    )
    extract_game_parser.add_argument("apk", help="Android APK file path")
    extract_game_parser.add_argument(
        "--output",
        "-o",
        help="output directory (default: APK filename without extension)",
    )
    extract_game_parser.set_defaults(
        func=lambda args: extract_game_from_apk(args.apk, **vars(args))
    )

    extract_translate_parser = subparsers.add_parser(
        "extract-translate",
        help="""extract translations from rpy files and save to tl/<language> directory.""",
    )
    extract_translate_parser.add_argument(
        "src", nargs="+", help="source game directory"
    )
    extract_translate_parser.add_argument(
        "--output",
        "-o",
        help="output directory (default: current directory, creates tl/<language>/)",
    )
    extract_translate_parser.add_argument(
        "--language",
        "-l",
        required=True,
        help="target language code (e.g. chinese, japanese)",
    )
    extract_translate_parser.add_argument(
        "--no-dialogues",
        action="store_true",
        help="skip dialogue translations",
    )
    extract_translate_parser.add_argument(
        "--no-strings",
        action="store_true",
        help="skip string translations",
    )
    extract_translate_parser.add_argument(
        "--empty",
        action="store_true",
        help="generate empty translations (default: copy original)",
    )
    extract_translate_parser.set_defaults(
        func=lambda args: run_extract_translations(
            args.src,
            args.language,
            output=args.output,
            include_dialogues=not args.no_dialogues,
            include_strings=not args.no_strings,
            empty_translation=args.empty,
        )
    )

    save_parser = subparsers.add_parser("save", help="save operations")
    save_subparsers = save_parser.add_subparsers(
        title="save subcommands", dest="save_command", help="save subcommand help"
    )
    save_extract_parser = save_subparsers.add_parser(
        "extract", help="extract save data to JSON files for editing"
    )
    save_extract_parser.add_argument("path", nargs=1, help="save-file path")
    save_extract_parser.add_argument("dest", nargs="?", help="extract to directory")
    save_extract_parser.add_argument(
        "--disassemble", "-d", action="store_true", help="print pickle disassembly"
    )
    save_extract_parser.add_argument(
        "--verbose", "-V", action="store_true", help="verbose class loading output"
    )
    save_extract_parser.set_defaults(
        func=lambda args: extract_save(
            args.path[0],
            args.dest or "",
            dissemble=args.disassemble,
            verbose=getattr(args, "verbose", False),
        )
    )

    save_restore_parser = save_subparsers.add_parser(
        "restore", help="restore save data from extracted JSON directory"
    )
    save_restore_parser.add_argument("path", nargs=1, help="extracted directory")
    save_restore_parser.add_argument("dest", nargs="?", help="restore to save-file")
    save_restore_parser.add_argument(
        "--key", "-k", help="path to security_keys.txt for re-signing"
    )
    save_restore_parser.set_defaults(
        func=lambda args: restore_save(
            args.path[0], args.dest or "", key_file=args.key or ""
        )
    )

    save_info_parser = save_subparsers.add_parser(
        "info", help="show save file information"
    )
    save_info_parser.add_argument("path", nargs=1, help="save-file path")
    save_info_parser.set_defaults(func=lambda args: dump_save_info(args.path[0]))

    save_genkey_parser = save_subparsers.add_parser(
        "genkey", help="generate a new signing key (requires ecdsa library)"
    )
    save_genkey_parser.add_argument(
        "output",
        nargs="?",
        default="security_keys.txt",
        help="output key file path (default: security_keys.txt)",
    )
    save_genkey_parser.set_defaults(func=lambda args: generate_new_key(args.output))

    args = argparser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    if not args.command:
        argparser.print_help()
        return

    # Show security warning for commands that process pickle data
    if args.command in ("decompile", "save", "unrpa") and not os.environ.get(
        "RPYCDEC_NO_WARNING"
    ):
        print(SECURITY_WARNING, file=sys.stderr)

    args.func(args)
