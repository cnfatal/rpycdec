import argparse
from concurrent.futures import ProcessPoolExecutor
import logging
import os
import pathlib
import pickle
import pickletools
import re
import struct
from typing import Callable
import zlib
import renpy.util
import renpy.ast
import renpy.sl2.slast
import glob


# A string at the start of each rpycv2 file.
RPYC2_HEADER = b"RENPY RPC2"

logger = logging.getLogger(__name__)


def noop_translator(text: str) -> str:
    return text


class Translator(object):
    trans_func: Callable[[str], str]
    trans_lang: re.Pattern
    translations_map = {}
    translated_map = {}

    def __init__(
        self,
        trans_func: Callable[[str], str] = noop_translator,
        trans_lang: str = "english",
    ) -> None:
        """
        Parameters
        ----------
        trans_func : Callable[[str], str]
            translate function that accept a string and return a string as translated result

        trans_lang : str
            translate on exists translate string, skip if not set
        """
        self.trans_func = trans_func
        self.trans_lang = trans_lang

    def trans_call(self, line) -> str:
        return self.trans_func(line)

    def trans_placeholder(self, line) -> str:
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
                    phs.append(line[squares.pop() : i + 1])
                    totranslate += ph_ch
                case "{":
                    braces.append(i)
                case "}" if braces:
                    phs.append(line[braces.pop() : i + 1])
                    totranslate += ph_ch
                case _:
                    if not squares and not braces:
                        totranslate += ch

        translated = self.trans_call(totranslate) if totranslate else line
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
        if re.match(r"^[a-z0-9_\(\)\[\]]+$", text):
            return text
        # only contains upper case
        if re.match(r"^[A-Z]+$", text):
            return text
        result = self.trans_placeholder(text)
        # rmeove % in result
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

    def on_translate(self, kind, text) -> str:
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

    def do_collect(self, label: str, lang: str, item: (str, str)) -> str:
        label = label or item[1]
        if lang or (not lang and label not in self.translations_map):
            self.translations_map[label] = item
        return item[1]

    def do_translate(self, label: str, lang: str, item: (str, str)) -> str:
        return (self.translated_map.get(label or item[1]) or item)[1]

    def walk_node(self, node, callback, **kwargs) -> bool:
        parent_label, parent_lang = kwargs.get("label"), kwargs.get("language")
        if isinstance(node, renpy.ast.Translate):
            if node.language and node.language != self.trans_lang:
                return False
        elif isinstance(node, renpy.ast.TranslateString):
            if node.language and node.language != self.trans_lang:
                return False
            # use node.old as key
            node.new = callback(node.old, node.language, ("text", node.new))
        elif isinstance(node, renpy.ast.Say):
            if parent_lang and parent_lang != self.trans_lang:
                return False
            node.what = callback(parent_label, parent_lang, ("text", node.what))
        elif isinstance(node, renpy.sl2.slast.SLDisplayable):
            if node.get_name() in ["text", "textbutton"]:
                for i, val in enumerate(node.positional):
                    val = callback(parent_label, parent_lang, ("expr", val))
                    node.positional[i] = val
        elif isinstance(node, renpy.ast.Show):
            pass
        elif isinstance(node, renpy.ast.UserStatement):
            pass
        elif isinstance(node, renpy.ast.PyCode):
            state = list(node.state)
            state[1] = callback(parent_label, parent_lang, ("block", state[1]))
            node.state = tuple(state)
        elif isinstance(node, renpy.sl2.slast.SLBlock):
            pass
        elif isinstance(node, renpy.sl2.slast.SLUse):
            if node.args:
                for i, (name, val) in enumerate(node.args.arguments):
                    val = callback(parent_label, parent_lang, ("block", val))
                    node.args.arguments[i] = (name, val)
        elif isinstance(node, renpy.ast.Menu):
            for i, item in enumerate(node.items):
                li = list(item)
                li[0] = callback(parent_label, parent_lang, ("text", li[0]))
                node.items[i] = tuple(li)
        return True

    def walk_callback(self, stmts, callback) -> str:
        return renpy.util.get_code(
            stmts,
            modifier=lambda node, **kwargs: self.walk_node(node, callback, **kwargs),
        )

    def translate_file(self, input_file, output_file=None):
        if not output_file:
            output_file = input_file.rtrim("c")
        stmts = load_file(input_file)
        code = self.walk_callback(stmts, self.do_translate)
        write_file(output_file, code)

    def translate_dir(
        self,
        input: str,
        output: str = None,
        concurent: int = os.cpu_count(),
    ):
        if not output:
            output = input
        files = glob_files(input, "*.rpyc")
        stmts_map = {}
        # load translations
        logger.info("loading translations")
        for file in files:
            stmts = load_file(os.path.join(input, file))
            stmts_map[file] = stmts
            self.walk_callback(stmts, self.do_collect)
        # translate
        logger.info("loaded %d translations", len(self.translations_map))
        logger.info("translating")

        results = {}
        for label, (kind, text) in self.translations_map.items():
            results[label] = (kind, self.on_translate(kind, text))
            logger.info("translated %d/%d", len(results), len(self.translations_map))
        self.translated_map = results
        # generate code
        logger.info("generating code")
        for filename, stmts in stmts_map.items():
            code = self.walk_callback(stmts, self.do_translate)
            output_file = os.path.join(output, filename.removesuffix("c"))
            write_file(output_file, code)

    def translate(self, input, output=None):
        if os.path.isfile(input):
            return self.translate_file(input, output)
        return self.translate_dir(input, output)


def write_file(f, data):
    if not os.path.exists(os.path.dirname(f)):
        os.makedirs(os.path.dirname(f))
    with open(f, "w") as f:
        f.write(data)


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


def decompile_translate(input, output=None, translator=noop_translator):
    Translator(trans_func=translator).translate(input, output)


def decompile_file(input_file, output_file=None):
    if not output_file:
        output_file = input_file.removesuffix("c")
    stmts = load_file(input_file)
    code = renpy.util.get_code(stmts)
    write_file(output_file, code)


def decompile(input, output=None):
    walk_path(input, output, on_file=decompile_file)


def glob_files(dir: str, pattern: str) -> list[str]:
    return [os.path.relpath(f, dir) for f in glob.glob(os.path.join(dir, pattern))]


def walk_path(input, output=None, on_file: Callable[[str, str], None] = None):
    if not os.path.isdir(input):
        if not output:
            output_file = input.removesuffix("c")
        on_file(input, output_file)
        return
    if not output:
        output = input
    for item in pathlib.Path(input).rglob("*"):
        if item.is_dir():
            continue
        filename = str(item.relative_to(input))
        if filename.endswith(".rpyc") or filename.endswith(".rpymc"):
            input_file = os.path.join(input, filename)
            # remove suffix c
            output_file = os.path.join(output, filename.removesuffix("c"))
            on_file(input_file, output_file)


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--dir", "-d", help="output base directory")
    argparser.add_argument("path", nargs="+", help="path to rpyc file or directory")
    args = argparser.parse_args()
    for path in args.path:
        decompile(path, args.dir)


if __name__ == "__main__":
    main()
