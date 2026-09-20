"""Tests for the AST comparison oracle in rpycdec.astdump"""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "src"))

from renpy.util import string_continuation_lines  # noqa: E402
from rpycdec.astdump import canonical, normalize_python  # noqa: E402


class TestCanonical(unittest.TestCase):
    """What the round trip comparison treats as 'the same script'."""

    def test_location_attributes_go(self):
        dumped = {"Say": {"what": "hi", "filename": "game/x.rpy", "linenumber": 3}}
        self.assertEqual(canonical(dumped), {"Say": {"what": "hi"}})

    def test_label_names_stay(self):
        """`_name` is the author's name for a label, not an identity tuple."""
        self.assertEqual(
            canonical({"Label": {"_name": "start"}}), {"Label": {"_name": "start"}}
        )
        self.assertEqual(
            canonical({"Say": {"_name": ["game/x.rpy", 1, 2]}}), {"Say": {}}
        )

    def test_source_rows_lose_their_position(self):
        dumped = {
            "UserStatement": {
                "block": [["game/x.rpy", 14, "define e = 1", []]],
            }
        }
        self.assertEqual(
            canonical(dumped),
            {"UserStatement": {"block": [["<file>", "<line>", "define e = 1", []]]}},
        )

    def test_user_statement_derived_names_are_normalized(self):
        """The parser names a statement after the line it sits on."""
        dumped = {
            "UserStatement": {
                "block": [["game/x.rpy", 14, "code", []]],
                "parsed": [
                    ["example"],
                    {
                        "filename": "game/x.rpy",
                        "number": 14,
                        "name": "example_game/x.rpy_14",
                        "names": ["example_game/x.rpy_14"],
                        "large": False,
                    },
                ],
            }
        }
        self.assertEqual(
            canonical(dumped),
            {
                "UserStatement": {
                    "block": [["<file>", "<line>", "code", []]],
                    "parsed": [
                        ["example"],
                        {
                            "number": "<line>",
                            "name": "example_game/x.rpy_<line>",
                            "names": ["example_game/x.rpy_<line>"],
                            "large": False,
                        },
                    ],
                }
            },
        )

    def test_other_two_element_lists_are_left_alone(self):
        self.assertEqual(canonical([["a", 1]]), [["a", 1]])
        self.assertEqual(
            canonical(["game/x.rpy", "not a line"]), ["game/x.rpy", "not a line"]
        )


class TestNormalizePython(unittest.TestCase):
    """Python blocks compare by what they mean, not how they are laid out."""

    def test_layout_does_not_matter(self):
        self.assertEqual(
            normalize_python("a = 1\n\nb = 2\n"), normalize_python("\na = 1\nb = 2\n")
        )

    def test_code_does_matter(self):
        self.assertNotEqual(normalize_python("a = 1"), normalize_python("a = 2"))


class TestStringContinuationLines(unittest.TestCase):
    """Which lines of a python block renpy recorded as they were written."""

    def test_stored_as_written(self):
        """Closing quotes deeper than the opening ones: the file's indentation."""
        source = 'def f():\n    """\n    doc\n        """\n'
        self.assertEqual(string_continuation_lines(source), {3, 4})

    def test_dedented_by_renpy(self):
        """Quotes at the same level: the indentation is the string's own."""
        source = 'def f():\n    """\n    doc\n    """\n'
        self.assertEqual(string_continuation_lines(source), set())

    def test_blank_line_forces_it(self):
        source = 'def f():\n    """\n    doc\n\n    more\n    """\n'
        self.assertEqual(string_continuation_lines(source), {3, 4, 5, 6})


if __name__ == "__main__":
    unittest.main()
