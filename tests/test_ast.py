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


class TestStyleGetCode(unittest.TestCase):
    """Tests for Style.get_code()"""

    def _make_node(self, name, **attrs):
        node = ast.Style()
        node.style_name = name
        node.properties = {}
        for key, value in attrs.items():
            setattr(node, key, value)
        return node

    def test_clear(self):
        """`clear` is a clause, not a property, see issue #25."""
        node = self._make_node("big_red", clear=True, properties={"size": "40"})
        self.assertEqual(node.get_code(), "style big_red clear size 40")

    def test_clear_in_block(self):
        """clauses stay on the header when properties go to a block."""
        node = self._make_node(
            "big_red",
            clear=True,
            properties={"size": "40", "color": '"#f00"', "bold": "True"},
        )
        self.assertEqual(
            node.get_code(),
            'style big_red clear:\n    size 40\n    color "#f00"\n    bold True',
        )

    def test_clauses(self):
        """parent, clear, take, del and variant are all clauses."""
        node = self._make_node(
            "big_red",
            parent="default",
            clear=True,
            take="small_red",
            delattr=["bold", "italic"],
            variant='"touch"',
            properties={"size": "40"},
        )
        self.assertEqual(
            node.get_code(),
            "style big_red is default clear take small_red del bold del italic"
            ' variant "touch" size 40',
        )

    def test_no_properties(self):
        """a style without properties is just its clauses."""
        node = self._make_node("big_red", parent="default", clear=True)
        self.assertEqual(node.get_code(), "style big_red is default clear")


class TestParseStoreName(unittest.TestCase):
    """`python in X` stores are spelled `store.X` in the AST."""

    def test_plain_store(self):
        self.assertEqual(ast.parse_store_name("store.mystore"), "mystore")

    def test_store_named_like_a_prefix(self):
        """`store.editor` is not `ditor`: lstrip would eat the leading chars."""
        self.assertEqual(ast.parse_store_name("store.editor"), "editor")
        self.assertEqual(ast.parse_store_name("store.test"), "test")
        self.assertEqual(ast.parse_store_name("store.style"), "style")

    def test_the_default_store_has_no_name(self):
        self.assertEqual(ast.parse_store_name("store"), "")
        self.assertEqual(ast.parse_store_name(""), "")
        self.assertEqual(ast.parse_store_name(None), "")


class TestIfGetCode(unittest.TestCase):
    """Only a trailing `True` entry is an else clause."""

    def _make_node(self, conditions):
        node = ast.If(("script.rpy", 1))
        node.entries = [
            (condition, [ast.Pass(("script.rpy", 1))]) for condition in conditions
        ]
        return node

    def test_if_elif(self):
        """An if chain without an else ends in a plain elif."""
        node = self._make_node(['result == "a"', 'result == "b"'])
        self.assertEqual(
            node.get_code(),
            'if result == "a":\n    pass\nelif result == "b":\n    pass',
        )

    def test_if_else(self):
        """An else clause is stored as a trailing `True`."""
        node = self._make_node(['result == "a"', "True"])
        self.assertEqual(
            node.get_code(), 'if result == "a":\n    pass\nelse:\n    pass'
        )

    def test_if_true(self):
        """`if True:` on its own stays an if."""
        node = self._make_node(["True"])
        self.assertEqual(node.get_code(), "if True:\n    pass")


class TestLabelGetCode(unittest.TestCase):
    """A label is allowed to have no body at all."""

    def _make_node(self, name, block):
        node = ast.Label(("script.rpy", 1))
        node.name = name
        node.block = block
        return node

    def test_label_without_block(self):
        """`label foo:` with nothing after it is a jump target."""
        self.assertEqual(self._make_node("foo", []).get_code(), "label foo:")

    def test_label_with_block(self):
        node = self._make_node("foo", [ast.Pass(("script.rpy", 1))])
        self.assertEqual(node.get_code(), "label foo:\n    pass")


if __name__ == "__main__":
    unittest.main()
