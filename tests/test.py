import logging
import unittest

from rpycdec import decompile, translate


class TestRpycDec(unittest.TestCase):
    def test_decode(self):
        input_file = "tests/script.rpyc"
        output_file = "tests/script-decoded.rpy"
        desired_file = "tests/script.rpy"
        decompile(input_file, output_file)
        self.assertTrue(file_compare(output_file, desired_file))

    def test_translate(self):
        input_file = "tests/script.rpyc"
        output_file = "tests/script-translated.rpy"
        translate(input_file, output_file)


def file_compare(file1, file2):
    with open(file1, "r") as f:
        file1content = f.read()
    with open(file2, "r") as f:
        file2content = f.read()
    return file1content == file2content


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
