"""Tests for rpycdec.translate module"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import renpy.ast
from rpycdec.translate import (
    TranslationExtractor,
    DialogueTranslation,
    StringTranslation,
    get_translation_filename,
    elide_filename,
    quote_unicode,
    unique_identifier,
    write_dialogue_translations,
    write_string_translations,
)


class TestGetTranslationFilename(unittest.TestCase):
    """Tests for get_translation_filename()"""

    def test_rpyc_to_rpy(self):
        self.assertEqual(get_translation_filename("script.rpyc"), "script.rpy")

    def test_rpymc_to_rpym(self):
        self.assertEqual(get_translation_filename("script.rpymc"), "script.rpym")

    def test_subdirectory_preserved(self):
        """Directory structure should be preserved (was a bug: basename stripped dirs)"""
        self.assertEqual(
            get_translation_filename("sub/intro.rpyc"), "sub/intro.rpy"
        )

    def test_nested_subdirectory_preserved(self):
        self.assertEqual(
            get_translation_filename("a/b/c/script.rpyc"), "a/b/c/script.rpy"
        )

    def test_rpym_unchanged(self):
        self.assertEqual(get_translation_filename("script.rpym"), "script.rpym")

    def test_rpy_unchanged(self):
        self.assertEqual(get_translation_filename("script.rpy"), "script.rpy")


class TestElideFilename(unittest.TestCase):
    def test_strips_game_dir(self):
        result = elide_filename("/game/script.rpyc", "/game")
        self.assertEqual(result, "script.rpy")

    def test_rpymc_to_rpym(self):
        result = elide_filename("/game/script.rpymc", "/game")
        self.assertEqual(result, "script.rpym")

    def test_no_game_dir(self):
        result = elide_filename("script.rpyc")
        self.assertEqual(result, "script.rpy")


class TestQuoteUnicode(unittest.TestCase):
    def test_backslash(self):
        self.assertEqual(quote_unicode("a\\b"), "a\\\\b")

    def test_double_quote(self):
        self.assertEqual(quote_unicode('say "hi"'), 'say \\"hi\\"')

    def test_newline(self):
        self.assertEqual(quote_unicode("line1\nline2"), "line1\\nline2")

    def test_plain_string(self):
        self.assertEqual(quote_unicode("hello"), "hello")


class TestUniqueIdentifier(unittest.TestCase):
    def test_no_label(self):
        result = unique_identifier(None, "abcd1234")
        self.assertEqual(result, "abcd1234")

    def test_with_label(self):
        result = unique_identifier("start", "abcd1234")
        self.assertEqual(result, "start_abcd1234")

    def test_label_dot_replaced(self):
        result = unique_identifier("chapter.one", "abcd1234")
        self.assertEqual(result, "chapter_one_abcd1234")

    def test_collision_appends_index(self):
        existing = {"start_abcd1234"}
        result = unique_identifier("start", "abcd1234", existing)
        self.assertEqual(result, "start_abcd1234_1")

    def test_multiple_collisions(self):
        existing = {"start_abcd1234", "start_abcd1234_1"}
        result = unique_identifier("start", "abcd1234", existing)
        self.assertEqual(result, "start_abcd1234_2")


class TestTranslationExtractor(unittest.TestCase):
    def _make_say_node(self, who, what, filename="script.rpyc", linenumber=1):
        node = renpy.ast.Say(loc=(filename, linenumber))
        node.who = who
        node.what = what
        node.interact = True
        node.identifier = None
        node.explicit_identifier = False
        node.attributes = None
        node.temporary_attributes = None
        node.arguments = None
        node.with_ = None
        return node

    def test_extract_say_dialogue(self):
        extractor = TranslationExtractor()
        node = self._make_say_node("e", "Hello world.")
        extractor.extract_file("script.rpyc", [node])
        self.assertEqual(len(extractor.dialogues), 1)
        d = extractor.dialogues[0]
        self.assertEqual(d.who, "e")
        self.assertEqual(d.what, "Hello world.")
        self.assertEqual(d.filename, "script.rpyc")

    def test_extract_say_no_speaker(self):
        extractor = TranslationExtractor()
        node = self._make_say_node(None, "A narrator line.")
        extractor.extract_file("script.rpyc", [node])
        self.assertEqual(len(extractor.dialogues), 1)
        self.assertIsNone(extractor.dialogues[0].who)

    def test_no_say_no_dialogue(self):
        extractor = TranslationExtractor()
        extractor.extract_file("script.rpyc", [])
        self.assertEqual(len(extractor.dialogues), 0)
        self.assertEqual(len(extractor.strings), 0)

    def test_identifier_generated(self):
        extractor = TranslationExtractor()
        node = self._make_say_node("e", "Hello.")
        extractor.extract_file("script.rpyc", [node])
        self.assertIsNotNone(extractor.dialogues[0].identifier)
        self.assertIsInstance(extractor.dialogues[0].identifier, str)


class TestWriteDialogueTranslations(unittest.TestCase):
    def test_writes_dialogue_file(self):
        dialogues = [
            DialogueTranslation(
                identifier="start_abcd1234",
                filename="script.rpyc",
                linenumber=5,
                who="e",
                what="Hello.",
                code='e "Hello."',
            )
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            result = write_dialogue_translations(
                dialogues, tmpdir, "chinese", empty_translation=False
            )
            tl_file = os.path.join(tmpdir, "script.rpy")
            self.assertTrue(os.path.exists(tl_file))
            with open(tl_file) as f:
                content = f.read()
            self.assertIn("translate chinese start_abcd1234:", content)
            self.assertIn('e "Hello."', content)

    def test_preserves_subdirectory_structure(self):
        """Translation files should mirror the source directory structure"""
        dialogues = [
            DialogueTranslation(
                identifier="intro_abcd1234",
                filename="sub/intro.rpyc",
                linenumber=3,
                who=None,
                what="Welcome.",
                code='"Welcome."',
            )
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            write_dialogue_translations(
                dialogues, tmpdir, "chinese", empty_translation=False
            )
            tl_file = os.path.join(tmpdir, "sub", "intro.rpy")
            self.assertTrue(
                os.path.exists(tl_file),
                f"Expected {tl_file} to exist (subdirectory structure not preserved)",
            )

    def test_empty_translation(self):
        dialogues = [
            DialogueTranslation(
                identifier="start_abcd1234",
                filename="script.rpyc",
                linenumber=1,
                who="e",
                what="Hello.",
                code='e "Hello."',
            )
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            write_dialogue_translations(
                dialogues, tmpdir, "chinese", empty_translation=True
            )
            with open(os.path.join(tmpdir, "script.rpy")) as f:
                content = f.read()
            self.assertIn('e ""', content)


class TestWriteStringTranslations(unittest.TestCase):
    def test_writes_strings_file(self):
        strings = [
            StringTranslation(filename="script.rpyc", linenumber=2, text="Play")
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            count = write_string_translations(
                strings, tmpdir, "chinese", empty_translation=False
            )
            self.assertEqual(count, 1)
            tl_file = os.path.join(tmpdir, "strings.rpy")
            self.assertTrue(os.path.exists(tl_file))
            with open(tl_file) as f:
                content = f.read()
            self.assertIn("translate chinese strings:", content)
            self.assertIn('old "Play"', content)
            self.assertIn('new "Play"', content)

    def test_empty_strings_not_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            count = write_string_translations([], tmpdir, "chinese")
            self.assertEqual(count, 0)
            self.assertFalse(os.path.exists(os.path.join(tmpdir, "strings.rpy")))


class TestCLIExtractTranslate(unittest.TestCase):
    """Integration tests for the extract-translate CLI command"""

    def test_language_argument_recognized(self):
        """The --language argument must be recognized by the CLI parser"""
        from rpycdec.cli import main

        with tempfile.TemporaryDirectory() as tmpdir:
            sys.argv = [
                "rpycdec",
                "extract-translate",
                tmpdir,
                "--language",
                "chinese",
            ]
            # Should not raise SystemExit with non-zero code (unrecognized arguments)
            try:
                main()
            except SystemExit as e:
                if e.code != 0:
                    self.fail(f"CLI raised SystemExit({e.code}) - --language may not be recognized")

    def test_language_short_flag(self):
        """The -l short flag must also work"""
        from rpycdec.cli import main

        with tempfile.TemporaryDirectory() as tmpdir:
            sys.argv = ["rpycdec", "extract-translate", tmpdir, "-l", "japanese"]
            try:
                main()
            except SystemExit as e:
                if e.code != 0:
                    self.fail(f"CLI raised SystemExit({e.code}) - -l flag may not be recognized")

    def test_creates_tl_directory(self):
        """extract-translate must create tl/<language>/ directory in output"""
        from rpycdec.cli import main

        with tempfile.TemporaryDirectory() as game_dir:
            with tempfile.TemporaryDirectory() as out_dir:
                sys.argv = [
                    "rpycdec",
                    "extract-translate",
                    game_dir,
                    "--language",
                    "chinese",
                    "--output",
                    out_dir,
                ]
                main()
                tl_dir = os.path.join(out_dir, "tl", "chinese")
                self.assertTrue(
                    os.path.isdir(tl_dir),
                    f"Expected tl/chinese/ directory at {tl_dir}",
                )


if __name__ == "__main__":
    unittest.main()
