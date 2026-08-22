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


class TestPythonGetCode(unittest.TestCase):
    """Tests for Python.get_code() keyword order and correctness."""

    def _make_node(self, code_str, store=None, hide=None):
        node = ast.Python(loc=("script.rpyc", 1))
        node.code = make_pycode(code_str)
        if store is not None:
            node.store = store
        if hide is not None:
            node.hide = hide
        return node

    def test_single_line_shorthand(self):
        """Single-line Python without store/hide uses $ shorthand."""
        node = self._make_node("flag = True")
        self.assertEqual(node.get_code(), "$ flag = True")

    def test_hide_before_store(self):
        """'hide' must appear before 'in <store>' per Ren'Py grammar."""
        node = self._make_node("flag = True", hide=True, store="store.mystore")
        result = node.get_code()
        self.assertIn("python hide in mystore:", result)

    def test_hide_only(self):
        """python hide: block without store."""
        node = self._make_node("flag = True", hide=True)
        result = node.get_code()
        self.assertTrue(result.startswith("python hide:"))

    def test_store_only(self):
        """python in <store>: block without hide."""
        node = self._make_node("flag = True", store="store.mystore")
        result = node.get_code()
        self.assertTrue(result.startswith("python in mystore:"))

    def test_multiline(self):
        """Multiline code produces a python: block."""
        node = self._make_node("flag = True\nother = False")
        result = node.get_code()
        self.assertIn("python:", result)


class TestEarlyPythonGetCode(unittest.TestCase):
    """Tests for EarlyPython.get_code() — keyword order and missing-attribute safety."""

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
        self.assertEqual(node.get_code(), "$ flag = True")

    def test_single_line_hide_false(self):
        """EarlyPython with hide=False should use $ shorthand."""
        node = self._make_node("flag = True", hide=False)
        self.assertEqual(node.get_code(), "$ flag = True")

    def test_hide_before_store(self):
        """'hide' must appear before 'in <store>' per Ren'Py grammar."""
        node = self._make_node("flag = True", hide=True, store="store.mystore")
        result = node.get_code()
        self.assertIn("python early hide in mystore:", result)

    def test_hide_only(self):
        """python early hide: block without store."""
        node = self._make_node("flag = True", hide=True)
        result = node.get_code()
        self.assertTrue(result.startswith("python early hide:"))

    def test_store_only(self):
        """python early in <store>: block without hide."""
        node = self._make_node("flag = True", store="store.mystore")
        result = node.get_code()
        self.assertTrue(result.startswith("python early in mystore:"))

    def test_multiline(self):
        """Multiline code should emit 'python early:' block."""
        node = self._make_node("flag = True\nother = False")
        result = node.get_code()
        self.assertIn("python early:", result)


if __name__ == "__main__":
    unittest.main()
