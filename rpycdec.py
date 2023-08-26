import argparse
import logging
import os
import pickle
import pickletools
import re
import struct
import time
import zlib
from hashlib import sha256
from typing import Callable

import plyvel
from ratelimit import limits, sleep_and_retry
import requests

import renpy.ast
import renpy.sl2.slast
import renpy.util

# A string at the start of each rpycv2 file.
RPYC2_HEADER = b"RENPY RPC2"

logger = logging.getLogger(__name__)


class GoogleTranslator(object):
    session = requests.Session()

    def __init__(self, src: str = "auto", dest: str = "zh-CN") -> None:
        self.src_lang = src
        self.dest_lang = dest

    @sleep_and_retry
    # limit calls per second
    @limits(calls=5, period=1)
    # google translate api is not free, so use cache
    def translate(self, text: str) -> str:
        if text.strip() == "" or re.match(r"^[0-9\W]+$", text):
            return text
        forms = {
            "client": "gtx",
            "sl": self.src_lang,
            "tl": self.dest_lang,
            "dt": "t",
            "q": text,
        }
        server = "https://translate.google.com"
        resp = self.session.post(f"{server}/translate_a/single", data=forms)
        if resp.status_code != 200:
            raise Exception(f"translate error: {resp.status_code}")
        data = resp.json()
        segments = ""
        for sec in data[0]:
            segments += sec[0]
        return segments


class CachedTranslator(object):
    cache = {}
    _translate: Callable[[str], str]

    def __init__(self, translator: Callable[[str], str], cache_dir=".cache") -> None:
        self._translate = translator
        self.cache = plyvel.DB(cache_dir, create_if_missing=True)

    def translate(self, text: str) -> str:
        start_time = time.time()
        logger.debug(">>> [%s]", text)
        cachekey = sha256(text.encode()).hexdigest().encode()
        cached = self.cache.get(cachekey)
        if cached:
            decoded = cached.decode()
            logger.debug("<-- [%s]", decoded)
            return decoded
        translated = self._translate(text)
        self.cache.put(cachekey, translated.encode())
        cost_time = time.time() - start_time
        logger.debug(f"<<< [{translated}] [cost {cost_time:.2f}s]")
        return translated


class CodeTranslator(object):
    _translator: Callable[[str], str]

    def __init__(self, translator: Callable[[str], str]) -> None:
        """
        Parameters
        ----------
        translator : Callable[[str], str]
            translator function
        """
        self.translator = translator

    def call_translate(self, line) -> str:
        return self.translator(line)

    def trans_placeholder(self, line) -> str:
        """
        1. repalace placeholders with @
        2. translate
        3. replace back @ with placeholders

        To avoid translate chars in placeholders

        eg:

        bad:  {color=#ff0000}hello{/color}  -> {颜色=#ff0000}你好{/颜色}
        good: {color=#ff0000}hello{/color}  -> @你好@ -> {color=#ff0000}你好{/color}
        """
        ph_ch = "@"  # placeholder char
        phs = []
        totranslate = ""
        # {}  []
        braces, squares = [], []
        for i, ch in enumerate(line):
            if i > 0 and line[i - 1] == "\\":
                totranslate += ch
                continue
            match ch:
                case "[":
                    squares.append(i)
                case "]" if squares:
                    end = squares.pop()
                    if squares:
                        continue
                    phs.append(line[end : i + 1])
                    totranslate += ph_ch
                case "{":
                    braces.append(i)
                case "}" if braces:
                    end = braces.pop()
                    if braces:
                        continue
                    phs.append(line[end : i + 1])
                    totranslate += ph_ch
                case _:
                    if not squares and not braces:
                        totranslate += ch

        translated = self.call_translate(totranslate) if totranslate else line
        for p in phs:
            # translate in placeholder
            # e.g. "{#r=hello}"
            m = re.search(r"{#\w=(.+?)}", p)
            if m:
                tp = self.trans_placeholder(m.group(1))
                p = p[: m.start(1)] + tp + p[m.end(1) :]
            translated = translated.replace(ph_ch, p, 1)
        return translated

    def on_text(self, text: str) -> str:
        if text.strip() == "":
            return text
        if text[0] == '"' and text[-1] == '"':
            return '"' + self.on_text(text[1:-1]) + '"'
        if "%" in text:  # format string
            return text
        result = self.trans_placeholder(text)
        result = result.replace("%", "")
        return result

    def on_expr(self, expr: str) -> str:
        prev_end, dquoters = 0, []
        result = ""
        for i, ch in enumerate(expr):
            if i > 0 and expr[i - 1] == "\\":
                continue
            if ch == '"':
                if not dquoters:
                    result += expr[prev_end:i]
                    dquoters.append(i)
                else:
                    result += self.on_text(expr[dquoters.pop() : i + 1])
                    prev_end = i + 1
        else:
            result += expr[prev_end:]
        return result

    def on_block(self, code: str) -> str:
        """
        find strings in python expr and translate it
        """
        results = []
        for text in code.splitlines():
            result = ""
            prev_end = 0
            # match _("hello") 's hello
            for find in re.finditer(r'_\("(.+?)"\)', text):
                start, group, end = find.start(1), find.group(1), find.end(1)
                result += text[prev_end:start] + self.on_text(group)
                prev_end = end
            else:
                result += text[prev_end:]
            results.append(result)
        return "\n".join(results)

    def translate(self, kind, text) -> str:
        match kind:
            case "text":
                text = self.on_text(text)
            case "expr":
                text = self.on_expr(text)
            case "block":
                text = self.on_block(text)
            case _:
                text = self.on_text(text)
        return text


def noop_translator(text: str) -> str:
    return text


def walk_node(node, callback, **kwargs):
    p_label, p_lang = kwargs.get("label"), kwargs.get("language")
    if isinstance(node, renpy.ast.Translate):
        pass
    elif isinstance(node, renpy.ast.TranslateString):
        node.new = callback(("text", p_label, node.language, node.old, node.new))
    elif isinstance(node, renpy.ast.TranslateBlock):
        pass
    elif isinstance(node, renpy.ast.Say):
        node.what = callback(("text", p_label, p_lang, node.what, None))
    elif isinstance(node, renpy.sl2.slast.SLDisplayable):
        if node.get_name() in ["text", "textbutton"]:
            for i, val in enumerate(node.positional):
                node.positional[i] = callback(("expr", p_lang, p_label, val, None))
    elif isinstance(node, renpy.ast.Show):
        pass
    elif isinstance(node, renpy.ast.UserStatement):
        pass
    elif isinstance(node, renpy.ast.PyCode):
        state = list(node.state)
        state[1] = callback(("block", p_label, p_lang, state[1], None))
        node.state = tuple(state)
    elif isinstance(node, renpy.sl2.slast.SLBlock):
        pass
    elif isinstance(node, renpy.sl2.slast.SLUse):
        if node.args:
            for i, (name, val) in enumerate(node.args.arguments):
                val = callback(("block", p_label, p_lang, val, None))
                node.args.arguments[i] = (name, val)
    elif isinstance(node, renpy.ast.Menu):
        for i, item in enumerate(node.items):
            li = list(item)
            li[0] = callback(("text", p_label, p_lang, li[0], None))
            node.items[i] = tuple(li)


def do_consume(m: tuple, cache: dict) -> str:
    (kind, label, lang, old, new) = m
    key, val = label or old, new or old
    return cache.get(key) or val


def do_collect(m: tuple, accept_lang: str, into: dict) -> str:
    (kind, label, lang, old, new) = m
    key, val = label or old, new or old
    if accept_lang and lang and lang != accept_lang:
        return val
    if lang or (not lang and key not in into):
        into[key] = (kind, val)
    return val


def walk_callback(stmts, callback) -> str:
    return renpy.util.get_code(
        stmts,
        modifier=lambda node, **kwargs: walk_node(node, callback, **kwargs),
    )


def default_translator() -> Callable[[str], str]:
    return CachedTranslator(GoogleTranslator().translate).translate


def translate_files(
    base_dir: str,
    files: list[str],
    translator: Callable[[str], str],
    include_tl_lang: str = "english",
    concurent: int = 0,
) -> dict[str, str]:
    """
    translate files and return a map of filename and code
    """
    if not translator:
        logger.info("using default translator")
        translator = default_translator()
    stmts_dict = {}
    translations_dict = {}
    # load translations
    for filename in files:
        logger.info("loading %s", filename)
        stmts = load_file(os.path.join(base_dir, filename))
        stmts_dict[filename] = stmts
        walk_callback(
            stmts,
            lambda meta: do_collect(meta, include_tl_lang, translations_dict),
        )
    logger.info("loaded %d translations", len(translations_dict))

    # translate
    logger.info("translating")
    results_dict = {}
    code_translator = CodeTranslator(translator)
    if concurent:
        logger.info(f"translating with {concurent} workers")
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=concurent) as executor:
            results = executor.map(
                lambda item: (
                    item[0],
                    code_translator.translate(item[1][0], item[1][1]),
                ),
                translations_dict.items(),
            )
            for label, result in results:
                results_dict[label] = result
                logger.info(
                    "translated %d/%d", len(results_dict), len(translations_dict)
                )
    else:
        for label, (kind, text) in translations_dict.items():
            results_dict[label] = code_translator.translate(kind, text)
            logger.info("translated %d/%d", len(results_dict), len(translations_dict))

    # generate code
    code_files = {}
    logger.info("generating code")
    for filename, stmts in stmts_dict.items():
        logger.info("gnerating code for %s", filename)
        code_files[filename] = walk_callback(
            stmts, lambda meta: do_consume(meta, results_dict)
        )
    return code_files


def translate(
    input,
    output=None,
    translator: Callable[[str], str] = None,
    include_tl_lang: str = "english",
    concurent: int = 0,
):
    if os.path.isfile(input):
        if not output:
            output = input.removesuffix("c")
        (_, code) = translate_files(
            "",
            [input],
            translator=translator,
        ).popitem()
        logger.info("writing %s", output)
        write_file(output, code)
        return

    if not output:
        output = input
    matches = match_files(input, ".*\.rpym?c$")
    file_codes = translate_files(
        input,
        matches,
        translator=translator,
        include_tl_lang=include_tl_lang,
        concurent=concurent,
    )
    for filename, code in file_codes.items():
        output_file = os.path.join(output, filename.removesuffix("c"))
        logger.info("writing %s", output_file)
        write_file(output_file, code)


def write_file(f, data):
    if not os.path.exists(os.path.dirname(f)):
        os.makedirs(os.path.dirname(f))
    with open(f, "w") as f:
        f.write(data)


def match_files(dir: str, pattern: str) -> list[str]:
    if pattern == "":
        pattern = ".*"
    result = []
    m = re.compile(pattern)
    for root, dirs, files in os.walk(dir):
        result.extend(
            filter(
                lambda f: m.match(f),
                map(lambda f: os.path.relpath(os.path.join(root, f), dir), files),
            )
        )
    return result


def read_rpyc_data(f, slot):
    """
    Reads the binary data from `slot` in a .rpyc (v1 or v2) file. Returns
    the data if the slot exists, or None if the slot does not exist.
    """
    f.seek(0)
    header_data = f.read(1024)
    # Legacy path.
    if header_data[: len(RPYC2_HEADER)] != RPYC2_HEADER:
        if slot != 1:
            return None
        f.seek(0)
        data = f.read()
        return zlib.decompress(data)
    # RPYC2 path.
    pos = len(RPYC2_HEADER)
    while True:
        header_slot, start, length = struct.unpack("III", header_data[pos : pos + 12])
        if slot == header_slot:
            break
        if header_slot == 0:
            return None
        pos += 12
    f.seek(start)
    data = f.read(length)
    return zlib.decompress(data)


def load_file(filename, disasm: bool = False):
    ext = os.path.splitext(filename)[1]
    if ext in [".rpy", ".rpym"]:
        raise NotImplementedError(
            "unsupport for pase rpy file or use renpy.parser.parse() in renpy's SDK"
        )
    if ext in [".rpyc", ".rpymc"]:
        with open(filename, "rb") as f:
            for slot in [1, 2]:
                bindata = read_rpyc_data(f, slot)
                if bindata:
                    if disasm:
                        disasm_file = filename + ".disasm"
                        with open(disasm_file, "wt") as disasm_f:
                            pickletools.dis(bindata, out=disasm_f)
                    data, stmts = pickle.loads(bindata)
                    return stmts
                f.seek(0)
    return None


def decompile_file(input_file, output_file=None):
    if not output_file:
        output_file = input_file.removesuffix("c")
    if not output_file.endswith(".rpy"):
        output_file = os.path.join(
            output_file, os.path.basename(input_file).removesuffix("c")
        )
    stmts = load_file(input_file)
    code = renpy.util.get_code(stmts)
    logger.info("writing %s", output_file)
    write_file(output_file, code)


def decompile(input, output=None):
    if not os.path.isdir(input):
        decompile_file(input, output)
        return
    if not output:
        output = input
    for filename in match_files(input, ".*\.rpym?c$"):
        decompile_file(
            os.path.join(input, filename),
            os.path.join(output, filename.removesuffix("c")),
        )


def main():
    logging.basicConfig(level=logging.INFO)
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "--concurent", "-n", type=int, default=0, help="concurent translate"
    )
    argparser.add_argument(
        "--include-lang",
        "-i",
        default=None,
        help="add items in tl/<lang> dir to translations",
    )
    argparser.add_argument(
        "--verbose", "-v", action="store_true", help="verbose output"
    )
    argparser.add_argument(
        "--translate", action="store_true", help="decompile and translate"
    )
    argparser.add_argument("src", nargs=1, help="rpyc file or directory")
    argparser.add_argument("dest", nargs="?", help="output file or directory")
    args = argparser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    if args.translate:
        translate(
            args.src[0],
            args.dest,
            concurent=args.concurent,
            include_tl_lang=args.include_lang,
        )
    else:
        decompile(args.src[0], args.dest)


if __name__ == "__main__":
    main()
