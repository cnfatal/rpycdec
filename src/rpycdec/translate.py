import collections
import hashlib
import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional

import renpy.ast
from rpycdec import utils, stmts

logger = logging.getLogger(__name__)


# ============================================================================
# Translation Extraction Data Structures
# ============================================================================


@dataclass
class DialogueTranslation:
    """Dialogue translation item - generates translate {identifier}: format"""

    identifier: str  # Translation identifier e.g. "start_a1b2c3d4"
    filename: str  # Source file
    linenumber: int  # Line number
    who: Optional[str]  # Speaker
    what: str  # Dialogue content
    code: str  # Original code (for comments)


@dataclass
class StringTranslation:
    """String translation item - generates translate strings: format"""

    filename: str
    linenumber: int
    text: str  # Text to translate
    source: str = "string"  # Source: "menu", "string", "screen", etc.


@dataclass
class TranslationExtractor:
    """Extract translation content from AST"""

    label: Optional[str] = None
    identifiers: set[str] = field(default_factory=set)
    dialogues: list[DialogueTranslation] = field(default_factory=list)
    strings: list[StringTranslation] = field(default_factory=list)
    _seen_strings: set[str] = field(default_factory=set)

    def extract_file(self, filename: str, nodes: list[renpy.ast.Node]) -> None:
        """Extract translations from a single file"""
        for node in self._walk_nodes(nodes):
            self._process_node(node, filename)

    def _walk_nodes(self, nodes: list[renpy.ast.Node]) -> Iterator[renpy.ast.Node]:
        """Recursively walk all nodes"""
        if not nodes:
            return

        for node in nodes:
            yield node

            # Handle different node types - each node type should only be processed once
            if isinstance(node, renpy.ast.If):
                # If node has entries with blocks
                for _, block in node.entries:
                    if block:
                        yield from self._walk_nodes(block)

            elif isinstance(node, renpy.ast.Menu):
                # Menu node has items with blocks
                for _, _, block in node.items:
                    if block:
                        yield from self._walk_nodes(block)

            elif isinstance(node, renpy.ast.UserStatement):
                # UserStatement may have code_block and subparses
                if hasattr(node, "code_block") and node.code_block:
                    yield from self._walk_nodes(node.code_block)
                if hasattr(node, "subparses") and node.subparses:
                    for subparse in node.subparses:
                        if hasattr(subparse, "block") and subparse.block:
                            yield from self._walk_nodes(subparse.block)

            elif hasattr(node, "block") and node.block:
                # Generic block handling for Label, While, Init, Translate, etc.
                yield from self._walk_nodes(node.block)

    def _process_node(self, node: renpy.ast.Node, filename: str) -> None:
        """Process a single node"""
        # Track label
        if isinstance(node, renpy.ast.Label):
            if not getattr(node, "hide", False):
                name = node.get_name() if hasattr(node, "get_name") else getattr(node, "name", None)
                if name and isinstance(name, str) and not name.startswith("_"):
                    self.label = name

        # Say node -> dialogue translation
        if isinstance(node, renpy.ast.Say):
            self._extract_say(node, filename)

        # TranslateSay node - already translated, skip
        elif isinstance(node, renpy.ast.TranslateSay):
            pass  # Already a translation node, no need to extract

        # Menu node -> string translation
        elif isinstance(node, renpy.ast.Menu):
            self._extract_menu(node, filename)

        # UserStatement node -> string translation
        elif isinstance(node, renpy.ast.UserStatement):
            self._extract_user_statement(node, filename)

    def _extract_say(self, node: renpy.ast.Say, filename: str) -> None:
        """Extract Say node"""
        what = getattr(node, "what", None)
        if not what:
            return

        identifier = self._generate_identifier(node)
        who = getattr(node, "who", None)

        self.dialogues.append(
            DialogueTranslation(
                identifier=identifier,
                filename=filename,
                linenumber=node.linenumber,
                who=who,
                what=what,
                code=node.get_code(),
            )
        )

    def _extract_menu(self, node: renpy.ast.Menu, filename: str) -> None:
        """Extract Menu node options"""
        items = getattr(node, "items", [])
        for caption, condition, block in items:
            if caption and caption not in self._seen_strings:
                self._seen_strings.add(caption)
                # Calculate correct line number
                if block:
                    line = block[0].linenumber - 1
                else:
                    line = node.linenumber

                self.strings.append(
                    StringTranslation(
                        filename=filename,
                        linenumber=line,
                        text=caption,
                        source="menu",
                    )
                )

    def _extract_user_statement(self, node: renpy.ast.UserStatement, filename: str) -> None:
        """Extract strings from UserStatement node"""
        try:
            translation_strings = node.get_translation_strings()
            for item in translation_strings:
                if isinstance(item, tuple):
                    line, text = item
                else:
                    line, text = node.linenumber, item

                if text and text not in self._seen_strings:
                    self._seen_strings.add(text)
                    self.strings.append(
                        StringTranslation(
                            filename=filename,
                            linenumber=line,
                            text=text,
                            source="user_statement",
                        )
                    )
        except Exception:
            pass  # Some UserStatements may not implement get_translation_strings

    def _generate_identifier(self, node: renpy.ast.Node) -> str:
        """Generate translation identifier (Ren'Py compatible)"""
        # Check for explicit identifier
        explicit_id = getattr(node, "identifier", None)
        if explicit_id and getattr(node, "explicit_identifier", False):
            if explicit_id not in self.identifiers:
                self.identifiers.add(explicit_id)
                return explicit_id

        # Calculate MD5
        code = node.get_code()
        md5 = hashlib.md5()
        md5.update((code + "\r\n").encode("utf-8"))
        digest = md5.hexdigest()[:8]

        identifier = unique_identifier(self.label, digest, self.identifiers)
        self.identifiers.add(identifier)
        return identifier


# ============================================================================
# Helper Functions
# ============================================================================


def unique_identifier(label: str | None, digest: str, existing_identifiers: set = set()) -> str:
    """Generate a unique translation identifier"""
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


# ============================================================================
# Translation File Generation
# ============================================================================


def quote_unicode(s: str) -> str:
    """Escape special characters in string"""
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\a", "\\a")
    s = s.replace("\b", "\\b")
    s = s.replace("\f", "\\f")
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    s = s.replace("\v", "\\v")
    return s


def elide_filename(filename: str, game_dir: str = "") -> str:
    """Simplify filename for comments"""
    if game_dir and filename.startswith(game_dir):
        filename = filename[len(game_dir) :].lstrip(os.sep)
    # Convert .rpyc to .rpy for display
    if filename.endswith(".rpyc"):
        filename = filename[:-1]
    elif filename.endswith(".rpymc"):
        filename = filename[:-1]
    return filename


def get_translation_filename(source_filename: str) -> str:
    """Generate translation filename from source filename"""
    basename = os.path.basename(source_filename)
    # Remove .rpyc/.rpymc suffix
    if basename.endswith(".rpyc"):
        basename = basename[:-1]
    elif basename.endswith(".rpymc"):
        basename = basename[:-1]
    elif basename.endswith(".rpy"):
        pass
    elif basename.endswith(".rpym"):
        basename = basename[:-1] + ".rpy"
    return basename


def write_dialogue_translations(
    dialogues: list[DialogueTranslation],
    output_dir: str,
    language: str,
    game_dir: str = "",
    empty_translation: bool = True,
    filter_func: Optional[Callable[[str], str]] = None,
) -> dict[str, int]:
    """
    Generate dialogue translation files.

    Returns:
        dict: {filename: count} number of translations written per file
    """
    # Group by source file
    by_file: dict[str, list[DialogueTranslation]] = collections.defaultdict(list)
    for d in dialogues:
        tl_filename = get_translation_filename(d.filename)
        by_file[tl_filename].append(d)

    result = {}

    for tl_filename, items in by_file.items():
        tl_path = os.path.join(output_dir, tl_filename)
        os.makedirs(os.path.dirname(tl_path) if os.path.dirname(tl_path) else output_dir, exist_ok=True)

        with open(tl_path, "w", encoding="utf-8") as f:
            f.write(f"# TODO: Translation updated at {__import__('datetime').datetime.now().isoformat()}\n\n")

            for item in items:
                # Write source file location comment
                elided = elide_filename(item.filename, game_dir)
                f.write(f"# {elided}:{item.linenumber}\n")

                # Write translate block
                f.write(f"translate {language} {item.identifier}:\n\n")

                # Write original code as comment
                f.write(f"    # {item.code}\n")

                # Write translation content
                if empty_translation:
                    new_what = ""
                elif filter_func:
                    new_what = filter_func(item.what)
                else:
                    new_what = item.what

                # Generate translated code
                if item.who:
                    f.write(f'    {item.who} "{quote_unicode(new_what)}"\n')
                else:
                    f.write(f'    "{quote_unicode(new_what)}"\n')

                f.write("\n")

        result[tl_filename] = len(items)
        logger.info(f"Wrote {len(items)} dialogue translations to {tl_path}")

    return result


def write_string_translations(
    strings: list[StringTranslation],
    output_dir: str,
    language: str,
    game_dir: str = "",
    empty_translation: bool = True,
    filter_func: Optional[Callable[[str], str]] = None,
) -> int:
    """
    Generate string translation file.

    Returns:
        int: number of translations written
    """
    if not strings:
        return 0

    tl_path = os.path.join(output_dir, "strings.rpy")

    with open(tl_path, "w", encoding="utf-8") as f:
        f.write(f"# TODO: Translation updated at {__import__('datetime').datetime.now().isoformat()}\n\n")
        f.write(f"translate {language} strings:\n\n")

        for item in strings:
            # Write source file location comment
            elided = elide_filename(item.filename, game_dir)
            f.write(f"    # {elided}:{item.linenumber}\n")

            # Write old/new
            old_text = quote_unicode(item.text)
            if empty_translation:
                new_text = ""
            elif filter_func:
                new_text = quote_unicode(filter_func(item.text))
            else:
                new_text = old_text

            f.write(f'    old "{old_text}"\n')
            f.write(f'    new "{new_text}"\n\n')

    logger.info(f"Wrote {len(strings)} string translations to {tl_path}")
    return len(strings)


def extract_translations(
    game_dir: str,
    output_dir: str,
    language: str,
    *,
    include_dialogues: bool = True,
    include_strings: bool = True,
    empty_translation: bool = True,
    filter_func: Optional[Callable[[str], str]] = None,
) -> dict:
    """
    Extract translation templates from .rpyc files.

    Args:
        game_dir: Game directory (containing .rpyc files)
        output_dir: Output directory (will create tl/{language}/ structure)
        language: Target language code e.g. "chinese", "japanese"
        include_dialogues: Whether to extract dialogue translations
        include_strings: Whether to extract string translations
        empty_translation: True=new is empty, False=new copies old
        filter_func: Optional text filter/transform function

    Returns:
        dict: Extraction statistics
    """
    # Create output directory tl/{language}/
    tl_output_dir = os.path.join(output_dir, "tl", language)
    os.makedirs(tl_output_dir, exist_ok=True)

    # Find all .rpyc/.rpymc files
    matches = utils.match_files(game_dir, r".*\.rpym?c$")
    logger.info(f"Found {len(matches)} rpyc files in {game_dir}")

    # Create extractor
    extractor = TranslationExtractor()

    # Process all files
    for filename in matches:
        filepath = os.path.join(game_dir, filename)
        logger.info(f"Processing {filename}")

        try:
            loaded_stmts = stmts.load_file(filepath)
            if loaded_stmts:
                extractor.extract_file(filename, loaded_stmts)
        except Exception as e:
            logger.error(f"Failed to process {filename}: {e}")
            continue

    # Statistics
    stats = {
        "files_processed": len(matches),
        "dialogues_found": len(extractor.dialogues),
        "strings_found": len(extractor.strings),
        "dialogues_written": 0,
        "strings_written": 0,
    }

    # Generate translation files
    if include_dialogues and extractor.dialogues:
        dialogue_stats = write_dialogue_translations(
            extractor.dialogues,
            tl_output_dir,
            language,
            game_dir=game_dir,
            empty_translation=empty_translation,
            filter_func=filter_func,
        )
        stats["dialogues_written"] = sum(dialogue_stats.values())
        stats["dialogue_files"] = dialogue_stats

    if include_strings and extractor.strings:
        stats["strings_written"] = write_string_translations(
            extractor.strings,
            tl_output_dir,
            language,
            game_dir=game_dir,
            empty_translation=empty_translation,
            filter_func=filter_func,
        )

    logger.info(
        f"Extraction complete: {stats['dialogues_written']} dialogues, "
        f"{stats['strings_written']} strings written to {tl_output_dir}"
    )

    return stats



