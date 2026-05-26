"""Tests for renpy.ast node code generation"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import renpy.ast as ast


def make_pycode(code_str):
    """Create a PyCode object with the given source string."""
    pycode = ast.PyCode()
    pycode.state = (None, code_str, None, None, None)
    return pycode


class TestEarlyPythonGetCode(unittest.TestCase):
    """Tests for EarlyPython.get_code() - regression for AttributeError on missing 'hide'"""

    def _make_node(self, code_str, store=None, hide=None):
        node = ast.EarlyPython(loc=("script.rpyc", 1))
        node.code = make_pycode(code_str)
        if store is not None:
            node.store = store
        if hide is not None:
            node.hide = hide
        return node

    def test_single_line_no_hide_attr(self):
        """EarlyPython without 'hide' attribute should not raise AttributeError."""
        node = self._make_node("flag = True")
        result = node.get_code()
        self.assertEqual(result, "$ flag = True")

    def test_single_line_hide_false(self):
        """EarlyPython with hide=False should use $ shorthand."""
        node = self._make_node("flag = True", hide=False)
        result = node.get_code()
        self.assertEqual(result, "$ flag = True")

    def test_hide_true(self):
        """EarlyPython with hide=True should emit 'python early hide:' block."""
        node = self._make_node("flag = True", hide=True)
        result = node.get_code()
        self.assertIn("python early", result)
        self.assertIn("hide", result)

    def test_with_store(self):
        """EarlyPython with store should emit 'python early in <store>:' block."""
        node = self._make_node("flag = True", store="store.mystore")
        result = node.get_code()
        self.assertIn("python early", result)
        self.assertIn("in mystore", result)

    def test_multiline(self):
        """EarlyPython with multiline code should emit 'python early:' block."""
        node = self._make_node("flag = True\nother = False")
        result = node.get_code()
        self.assertIn("python early", result)


if __name__ == "__main__":
    unittest.main()
