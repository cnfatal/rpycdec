import collections
import hashlib
import logging
import os
import re
from typing import Callable

import tqdm
from renpy import script
from renpy import ast
import renpy.ast
import renpy.sl2.slast
import renpy.util
from rpycdec import utils, stmts
from renpy.translation import encode_say_string
from renpy.ast import (
    TranslatePython,
    TranslateBlock,
    TranslateEarlyBlock,
    Translate,
    TranslateSay,
)

logger = logging.getLogger(__name__)

PH_CH = "@"  # placeholder char


# Search for identifiers that have been set to the user, and add them
# to self.preexisting_identifiers.
def get_existing_identifiers(self, children: list[renpy.ast.Node]):
    for i in children:
        i.get_children
    for i in script.collapse_stmts(children):
        if isinstance(i, renpy.ast.Say):
            identifier = getattr(i, "identifier", None)
            if identifier is not None:
                self.preexisting_identifiers.add(identifier)


def wrap_translate(stmts, label=None, alternate=None, existing_identifiers=set()):
    translated_nodes = []
    group = []
    for i in stmts:
        if isinstance(i, renpy.ast.Label):
            if not i.hide:
                assert isinstance(i.name, str)
                if i.name.startswith("_"):
                    alternate = i.name
                else:
                    label = i.name
                    alternate = None
        if not isinstance(i, renpy.ast.Translate):
            wrap_translate(i.block, label, alternate, existing_identifiers)
        if isinstance(i, renpy.ast.Say):
            group.append(i)
            tl = create_translate(group)
            translated_nodes.extend(tl)
            group = []
        elif i.translatable:
            group.append(i)
        else:
            if group:
                tl = create_translate(group)
                translated_nodes.extend(tl)
                group = []
            translated_nodes.append(i)
    if group:
        nodes = create_translate(group)
        translated_nodes.extend(nodes)
        group = []
    nodes[:] = translated_nodes


def create_translate(
    nodes: list[renpy.ast.Node],
    label: str | None,
    alternate: str | None,
    existing_identifiers: set = set(),
) -> list[renpy.ast.Node]:
    md5 = hashlib.md5()
    for i in nodes:
        code = i.get_code()
        md5.update((code + "\r\n").encode("utf-8"))
    digest = md5.hexdigest()[:8]
    identifier = unique_identifier(label, digest, existing_identifiers)

    # Take id clause from the block if the last statement is Say statement
    id_identifier = None
    for i in nodes:
        if isinstance(i, ast.Say):
            id_identifier = getattr(i, "identifier", id_identifier)

    if alternate is not None:
        alternate = unique_identifier(alternate, digest, existing_identifiers)
        identifier = id_identifier or identifier
    elif id_identifier is not None:
        alternate = identifier
        identifier = id_identifier
    else:
        alternate = None
    existing_identifiers.add(identifier)
    if alternate is not None:
        existing_identifiers.add(alternate)

    loc = (nodes[0].filename, nodes[0].linenumber)

    tl = ast.Translate(loc, identifier, None, nodes, alternate=alternate)
    tl.name = nodes[0].name + ("translate",)

    ed = renpy.ast.EndTranslate(loc)
    ed.name = nodes[0].name + ("end_translate",)
    return [tl, ed]


def unique_identifier(label: str | None, digest, existing_identifiers: set = set()):
    if label is None:
        base = digest
    else:
        base = label.replace(".", "_") + "_" + digest
    i = 0
    suffix = ""
    while True:
        identifier = base + suffix
        if identifier not in existing_identifiers:
            break
        i += 1
        suffix = "_{0}".format(i)
    return identifier


def encode_placeholder(line: str) -> tuple[str, list[str]]:
    phs = []
    totranslate = ""
    # {}  []
    braces, squares = [], []
    for i, char in enumerate(line):
        if i > 0 and line[i - 1] == "\\":
            totranslate += char
            continue
        match char:
            case "[":
                squares.append(i)
            case "]" if squares:
                end = squares.pop()
                if squares:
                    continue
                phs.append(line[end : i + 1])
                totranslate += PH_CH
            case "{":
                braces.append(i)
            case "}" if braces:
                end = braces.pop()
                if braces:
                    continue
                phs.append(line[end : i + 1])
                totranslate += PH_CH
            case _:
                if not squares and not braces:
                    totranslate += char
    return totranslate, phs


def decode_placeholder(line: str, phs: list[str]) -> str:
    for placeholder in phs:
        line = line.replace(PH_CH, placeholder, 1)
    return line


def translate_placeholder(line, fn: Callable[[str], str]) -> str:
    """
    1. repalace placeholders with @
    2. translate
    3. replace back @ with placeholders

    To avoid translate chars in placeholders

    eg:

    bad:  {color=#ff0000}hello{/color}  -> {颜色=#ff0000}你好{/颜色}
    good: {color=#ff0000}hello{/color}  -> @你好@ -> {color=#ff0000}你好{/color}
    """
    totranslate, phs = encode_placeholder(line)
    translated = fn(totranslate) if totranslate else line
    for placeholder in phs:
        # translate in placeholder
        # e.g. "{#r=hello}"
        matched = re.search(r"{#\w=(.+?)}", placeholder)
        if matched:
            translated = translate_placeholder(matched.group(1), fn)
            placeholder = (
                placeholder[: matched.start(1)]
                + translated
                + placeholder[matched.end(1) :]
            )
        translated = translated.replace(PH_CH, placeholder, 1)
    return translated


def walk_node(
    node, callback: Callable[[str, str, str], str], target_lang: str = "None", **kwargs
):
    """
    callback: (kind, old, new) -> translated

    walk ast node and call callback on nodes that contains text/expr/block
    """
    if isinstance(node, renpy.ast.Translate):
        if target_lang:
            node.language = target_lang
    elif isinstance(node, renpy.ast.TranslateString):
        node.new = callback(("text", node.old, node.new))
        if target_lang:
            node.language = target_lang
    elif isinstance(node, renpy.ast.TranslateBlock):
        pass
    elif isinstance(node, renpy.ast.Say):
        node.what = callback(("text", node.what, ""))
    elif isinstance(node, renpy.sl2.slast.SLDisplayable):
        if node.get_name() in ["text", "textbutton"]:
            for i, val in enumerate(node.positional):
                node.positional[i] = callback(("expr", val, ""))
    elif isinstance(node, renpy.ast.Show):
        pass
    elif isinstance(node, renpy.ast.UserStatement):
        pass
    elif isinstance(node, renpy.ast.PyCode):
        state = list(node.state)
        state[1] = callback(("block", state[1], ""))
        node.state = tuple(state)
    elif isinstance(node, renpy.sl2.slast.SLBlock):
        pass
    elif isinstance(node, renpy.sl2.slast.SLUse):
        if node.args:
            for i, (name, val) in enumerate(node.args.arguments):
                val = callback(("block", val, ""))
                node.args.arguments[i] = (name, val)
    elif isinstance(node, renpy.ast.Menu):
        for i, item in enumerate(node.items):
            _li = list(item)
            _li[0] = callback(("text", _li[0], ""))
            node.items[i] = tuple(_li)


def translate_by_model(srcs: list[str], src_lang="en", dest_lang="zh") -> list[str]:
    from transformers import pipeline
    from transformers.pipelines import TranslationPipeline
    from tqdm import tqdm

    # Select appropriate translation model based on target language
    if dest_lang.lower() in ["zh", "chinese"]:
        model = "Helsinki-NLP/opus-mt-en-zh"
    elif dest_lang.lower() in ["ja", "japanese"]:
        model = "Helsinki-NLP/opus-mt-en-ja"
    else:
        model = "Helsinki-NLP/opus-mt-en-zh"
    logger.info("using translation model: %s", model)

    pipe: TranslationPipeline = pipeline("translation", model=model)

    # replace placeholder
    totranslate = []
    phslist = []
    for src in srcs:
        encoded, placeholders = encode_placeholder(src)
        totranslate.append(encoded)
        phslist.append(placeholders)

    translated = []
    batch_size = 8
    for i in tqdm(range(0, len(totranslate), batch_size), desc="Translating"):
        batch_result = pipe(
            totranslate[i : i + batch_size],
            src_lang=src_lang,
            tgt_lang=dest_lang,
            batch_size=batch_size,
        )
        translated.extend([item["translation_text"] for item in batch_result])

    # restore placeholders
    for i, placeholders in enumerate(phslist):
        translated[i] = decode_placeholder(translated[i], placeholders)
    return translated


def parse_and_translate(
    game_dir: str, files: list[str], output_dir: str, **kwargs
) -> None:
    """
    Translate files
    """

    def _do_collect(meta: tuple, into: dict[str, str]) -> str:
        kind, old, new = meta
        if kind == "text" and old:
            into[old] = new
        return old

    # load translations
    stmts_dict: dict[str, list[renpy.ast.Node]] = {}
    translations = {}
    for filename in files:
        logger.info("loading %s", filename)
        loaded_stmts = stmts.load_file(os.path.join(game_dir, filename))
        stmts_dict[filename] = loaded_stmts
        renpy.util.get_code(
            loaded_stmts,
            modifier=lambda node, **kwargs: walk_node(
                node,
                lambda meta: _do_collect(meta, translations),
                **kwargs,
            ),
        )
    source_list = list(translations.keys())
    logger.info("loaded %d translations", len(source_list))
    translated = translate_by_model(source_list, src_lang=src_lang, dest_lang=dest_lang)
    translated_map = dict(zip(source_list, translated))

    def _do_translate(meta: tuple, translations: dict[str, str]) -> str:
        kind, old, new = meta
        if kind == "text" and old in translations:
            return translations[old]
        return old

    for filename, loaded_stmts in stmts_dict.items():
        code = renpy.util.get_code(
            loaded_stmts,
            modifier=lambda node, **kwargs: walk_node(
                node,
                lambda meta: _do_translate(meta, translated_map),
                **kwargs,
            ),
        )
        dest = os.path.join(output_dir, filename.removesuffix("c"))
        logger.info("writing %s", dest)
        utils.write_file(dest, code)


def take_translates(self, nodes: list[renpy.ast.Node]) -> object:
    """
    Takes the translates out of the flattened list of statements, and stores
    them into the dicts above.
    """

    if not nodes:
        return

    filename = os.path.normpath(os.path.abspath(filename))

    label = None
    languages = set()
    default_translates = {}
    file_translates = collections.defaultdict(list)
    additional_strings = collections.defaultdict(list)
    for n in nodes:
        if not n.translation_relevant:
            continue

        if isinstance(n.name, str):
            label = n.name

        if isinstance(n, TranslatePython):
            if n.language is not None:
                languages.add(n.language)

        elif isinstance(n, TranslateEarlyBlock):
            if n.language is not None:
                languages.add(n.language)

        elif isinstance(n, TranslateBlock):
            if n.language is not None:
                languages.add(n.language)

        elif isinstance(n, (Translate, TranslateSay)):
            if n.language is None:
                if n.identifier in default_translates:
                    old_node = default_translates[n.identifier]
                    continue

                default_translates[n.identifier] = n
                file_translates[filename].append((label, n))
            else:
                languages.add(n.language)
                self.language_translates[n.identifier, n.language] = n
                self.chain_worklist.append((n.identifier, n.language))

        else:
            for line in n.get_translation_strings():
                additional_strings[filename].append(line)
    return {
        "languages": languages,
        "default_translates": default_translates,
        "file_translates": file_translates,
        "additional_strings": additional_strings,
    }


def extract_translate(game_dir: str, src_lang: str, dest_lang: str, **kwargs) -> None:
    """
    extract translations from game directory.
    """
    matches = utils.match_files(game_dir, r".*\.rpym?c$")

    # load translations
    stmts_dict: dict[str, list[renpy.ast.Node]] = {}
    translations = {}

    def do_collect(meta: tuple, into: dict[str, str]) -> str:
        kind, old, new = meta
        if kind == "text" and old:
            into[old] = new
        return old

    for filename in matches:
        logger.info("loading %s", filename)
        loaded_stmts = stmts.load_file(os.path.join(game_dir, filename))
        stmts_dict[filename] = loaded_stmts
        renpy.util.get_code(
            loaded_stmts,
            modifier=lambda node, **kwargs: walk_node(
                node,
                lambda meta: do_collect(meta, translations),
                **kwargs,
            ),
        )
