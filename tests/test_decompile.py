"""Tests for the file level decoding steps in rpycdec.decompile"""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "src"))

import renpy.ast as ast  # noqa: E402
from rpycdec.decompile import trim_implicit_return  # noqa: E402


def make_return(expression=None):
    node = ast.Return(("script.rpy", 1))
    node.expression = expression
    return node


class TestTrimImplicitReturn(unittest.TestCase):
    """Ren'Py appends an empty return to every parsed file, we must not emit it."""

    def test_trailing_empty_return_is_dropped(self):
        say = ast.Say()
        say.what = "hi"
        self.assertEqual(trim_implicit_return([say, make_return()]), [say])

    def test_return_with_expression_is_kept(self):
        node = make_return("flag")
        self.assertEqual(trim_implicit_return([node]), [node])

    def test_return_inside_block_is_kept(self):
        inner = make_return()
        label = ast.Label()
        label.block = [inner]
        trimmed = trim_implicit_return([label])
        self.assertEqual(trimmed, [label])
        self.assertEqual(trimmed[0].block, [inner])

    def test_empty_input(self):
        self.assertEqual(trim_implicit_return([]), [])


if __name__ == "__main__":
    unittest.main()
