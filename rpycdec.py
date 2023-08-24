import argparse
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

# A string at the start of each rpycv2 file.
RPYC2_HEADER = b"RENPY RPC2"

logger = logging.getLogger(__name__)


def noop_translator(text: str) -> str:
    return text


class Translator(object):
    trans_func: Callable[[str], str]
    trans_lang: re.Pattern
    trans_origin: bool = False

    def __init__(
        self,
        trans_func: Callable[[str], str] = noop_translator,
        trans_lang: str = "",
        trans_origin: bool = False,
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
        self.trans_origin = trans_origin

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

    def trans_text(self, text: str) -> str:
        if text.strip() == "":
            return text
        if text[0] == '"' and text[-1] == '"':
            return '"' + self.trans_text(text[1:-1]) + '"'
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

    def trans_expr(self, text: str) -> str:
        prev_end, dquoters = 0, []
        result = ""
        for i, ch in enumerate(text):
            if i > 0 and text[i - 1] == "\\":
                continue
            if ch == '"':
                if not dquoters:
                    result += text[prev_end : i + 1]
                    dquoters.append(i + 1)
                else:
                    result += '"' + self.trans_text(text[dquoters.pop() : i]) + '"'
                    prev_end = i + 1
        else:
            result += text[prev_end:]
        return result

    def trans_python(self, code: str) -> str:
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
                result += text[prev_end:start] + self.trans_text(group)
                prev_end = end
            else:
                result += text[prev_end:]
            results.append(result)
        return "\n".join(results)

    def translate_node(self, node):
        if (
            isinstance(node, renpy.ast.TranslateString)
            and self.trans_lang
            and re.match(self.trans_lang, node.language)
        ):
            node.new = self.trans_text(node.new)

        if self.trans_lang:
            if isinstance(node, renpy.ast.Translate):
                if node.language == self.trans_lang:
                    pass
            elif isinstance(node, renpy.ast.TranslateString):
                if node.language == self.trans_lang:
                    node.new = self.trans_text(node.new)

        if self.trans_origin:
            if isinstance(node, renpy.ast.Say):
                node.what = self.trans_text(node.what)
            elif isinstance(node, renpy.sl2.slast.SLDisplayable):
                if node.get_name() in ["text", "textbutton"]:
                    for i, val in enumerate(node.positional):
                        node.positional[i] = self.trans_expr(val)
            elif isinstance(node, renpy.ast.Show):
                pass
            elif isinstance(node, renpy.ast.UserStatement):
                pass
            elif isinstance(node, renpy.ast.PyCode):
                state = list(node.state)
                state[1] = self.trans_python(state[1])
                node.state = tuple(state)
            elif isinstance(node, renpy.sl2.slast.SLBlock):
                pass
            elif isinstance(node, renpy.sl2.slast.SLUse):
                if node.args:
                    for i, (name, val) in enumerate(node.args.arguments):
                        node.args.arguments[i] = (name, self.trans_python(val))
            elif isinstance(node, renpy.ast.Menu):
                for i, item in enumerate(node.items):
                    li = list(item)
                    li[0] = self.trans_text(li[0])
                    node.items[i] = tuple(li)

    def translate_stmts(self, stmts):
        return renpy.util.get_code(stmts, modifier=self.translate_node)

    def translate_file(self, input_file, output_file=None):
        if not output_file:
            output_file = input_file.rtrim("c")
        # load
        logger.info(f"translating {input_file} to {output_file}")
        stmts = load_file(input_file)
        # trans and generate code
        code = self.translate_stmts(stmts)
        with open(output_file, "wt") as f:
            f.write(code)

    def translate(self, input: str, output: str = None, overwrite: bool = False):
        walk_path(input, output, on_file=self.translate_file, overwrite=overwrite)


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


def decompile_translate(
    input,
    output=None,
    overwrite: bool = False,
    trans_lang: str = "",
    translator: Callable[[str], str] = noop_translator,
):
    Translator(
        trans_func=translator,
        trans_lang=trans_lang,
        trans_origin=True,
    ).translate(input, output, overwrite)


def decompile_file(input_file, output_file=None):
    if not output_file:
        output_file = input_file.removesuffix("c")
    logger.info(f"decompiling {input_file} to {output_file}")
    # unpickle
    stmts = load_file(input_file)
    # decompile
    code = renpy.util.get_code(stmts)
    with open(output_file, "wt") as f:
        f.write(code)


def decompile(input, output=None, overwrite: bool = False):
    walk_path(input, output, on_file=decompile_file, overwrite=overwrite)


def walk_path(
    input,
    output=None,
    overwrite: bool = False,
    on_file: Callable[[str, str], None] = None,
):
    if not output:
        output = input
    if not os.path.isdir(input):
        output_file = output.removesuffix("c")
        if os.path.exists(output_file) and not overwrite:
            raise FileExistsError(f"{output_file} exists")
        if not os.path.exists(os.path.dirname(output_file)):
            os.makedirs(os.path.dirname(output_file))
        on_file(input, output_file)
        return
    if not os.path.exists(output):
        os.makedirs(output)
    for item in pathlib.Path(input).rglob("*"):
        if item.is_dir():
            continue
        filename = str(item.relative_to(input))
        if filename.endswith(".rpyc") or filename.endswith(".rpymc"):
            input_file = os.path.join(input, filename)
            # remove suffix c
            output_file = os.path.join(output, filename.removesuffix("c"))
            if os.path.exists(output_file) and not overwrite:
                raise FileExistsError(f"{output_file} exists")
            if not os.path.exists(os.path.dirname(output_file)):
                os.makedirs(os.path.dirname(output_file))
            on_file(input_file, output_file)


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--force", action="store_true", help="overwrite exists file")
    argparser.add_argument("--dir", "-d", help="output base directory")
    argparser.add_argument("path", nargs="+", help="path to rpyc file or directory")
    args = argparser.parse_args()
    for path in args.path:
        try:
            walk_path(path, args.dir, args.force, decompile_file)
        except FileExistsError as e:
            print(e)


if __name__ == "__main__":
    main()
