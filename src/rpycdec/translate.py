import logging
import os
from typing import Callable
import renpy.ast
import renpy.sl2.slast
import renpy.util
from rpycdec import utils, stmts
from renpy.translation import encode_say_string


logger = logging.getLogger(__name__)


def walk_node(node, callback: Callable[[str, str], str], **kwargs):
    """
    callback: (kind, label, lang, old, new) -> translated

    walk ast node and call callback on nodes that contains text/expr/block
    """
    if isinstance(node, renpy.ast.Translate):
        pass
    elif isinstance(node, renpy.ast.TranslateString):
        pass
    elif isinstance(node, renpy.ast.TranslateBlock):
        pass
    elif isinstance(node, renpy.ast.Say):
        node.what = callback(("text", node.what))
    elif isinstance(node, renpy.sl2.slast.SLDisplayable):
        if node.get_name() in ["text", "textbutton"]:
            for i, val in enumerate(node.positional):
                node.positional[i] = callback(("expr", val))
    elif isinstance(node, renpy.ast.Show):
        pass
    elif isinstance(node, renpy.ast.UserStatement):
        pass
    elif isinstance(node, renpy.ast.PyCode):
        state = list(node.state)
        state[1] = callback(("block", state[1]))
        node.state = tuple(state)
    elif isinstance(node, renpy.sl2.slast.SLBlock):
        pass
    elif isinstance(node, renpy.sl2.slast.SLUse):
        if node.args:
            for i, (name, val) in enumerate(node.args.arguments):
                val = callback(("block", val))
                node.args.arguments[i] = (name, val)
    elif isinstance(node, renpy.ast.Menu):
        for i, item in enumerate(node.items):
            _li = list(item)
            _li[0] = callback(("text", _li[0]))
            node.items[i] = tuple(_li)


def parse_translations(game_dir: str, files: list[str]) -> dict[str, list[(str, str)]]:
    """
    Translate files and return a map of filename and code.
    """

    def _do_collect(meta: tuple, into: dict[str, str]) -> str:
        kind, value = meta
        if kind == "text" and value:
            into[value] = filename
        return value

    # load translations
    stmts_dict: dict[str, list[renpy.ast.Node]] = {}
    # translation -> filename
    translations_dict: dict[str, str] = {}
    for filename in files:
        logger.info("loading %s", filename)
        loaded_stmts = stmts.load_file(os.path.join(game_dir, filename))
        stmts_dict[filename] = loaded_stmts
        renpy.util.get_code(
            loaded_stmts,
            modifier=lambda node, **kwargs: walk_node(
                node,
                lambda meta: _do_collect(meta, translations_dict),
                **kwargs,
            ),
        )
    filename_translations: dict[str, list[(str, str)]] = {}
    for value, filename in translations_dict.items():
        items = filename_translations.setdefault(filename, [])
        if value not in items:
            items.append((value, value))
    return filename_translations


def translate_text(text: list[str], pipeline, **kwargs) -> list[str]:
    result = pipeline(text, **kwargs)
    return [item["translation_text"] for item in result]


def write_translation_strings_file(
    game_dir: str, filename: str, language: str, translations: list[(str, str)]
):
    """
    write translations to a file.
    """
    tlfile = os.path.join(game_dir, "tl", language, filename.removesuffix("c"))
    logger.info("writing translations to %s", tlfile)
    os.makedirs(os.path.dirname(tlfile), exist_ok=True)
    content = f"translate {language} strings:\n"
    for old, new in translations:
        content += renpy.util.indent(f"old {encode_say_string(old)}\n")
        content += renpy.util.indent(f"new {encode_say_string(new)}\n")
        content += "\n"
    utils.write_file(tlfile, content)


def extract_translation(game_dir: str, language: str = "None", **kwargs) -> None:
    """
    extract translations from game directory.
    """
    matches = utils.match_files(game_dir, r".*\.rpym?c$")
    extracted = parse_translations(game_dir, matches)
    logger.info("loaded %d translations", len(extracted))
    if language and language != "None":
        from transformers import pipeline

        # Select appropriate translation model based on target language
        if language.lower() in ["zh", "chinese"]:
            model = "Helsinki-NLP/opus-mt-en-zh"
        elif language.lower() in ["ja", "japanese"]:
            model = "Helsinki-NLP/opus-mt-en-ja"
        else:
            model = "Helsinki-NLP/opus-mt-en-zh"
        logger.info("using translation model: %s", model)
        pipe = pipeline("translation", model=model)

        for filename, translations in extracted.items():
            to_translate = [old for old, new in translations]
            logger.info("translating %d strings in %s", len(to_translate), filename)
            translated = translate_text(to_translate, pipe, **kwargs)
            extracted[filename] = [
                (old, new) for old, new in zip(to_translate, translated)
            ]

    for filename, translations in extracted.items():
        if not translations:
            logger.warning("no translations found in %s", filename)
            continue
        write_translation_strings_file(game_dir, filename, language, translations)
