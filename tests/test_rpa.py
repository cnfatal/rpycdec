import os
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import run

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rpycdec.rpa import create_rpa, extract_rpa

SRC_DIR = str(Path(__file__).resolve().parents[1] / "src")


class RPATests(unittest.TestCase):
    def create_filter_fixture(self, root: Path) -> Path:
        source = root / "game"
        (source / "images").mkdir(parents=True)
        (source / "scripts").mkdir()
        (source / "script.rpy").write_text('label start:\n    "Hello"\n')
        (source / "scripts" / "chapter.RPYC").write_bytes(b"compiled")
        (source / "images" / "bg.png").write_bytes(b"image")
        (source / "notes.txt").write_text("notes")

        archive = root / "archive.rpa"
        create_rpa(str(archive), [str(source)])
        return archive

    def test_create_rpa_round_trips_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "game"
            (source / "images").mkdir(parents=True)
            (source / "script.rpy").write_text('label start:\n    "Hello"\n')
            (source / "images" / "bg.png").write_bytes(b"\x89PNG\r\n\x1a\n")

            archive = root / "archive.rpa"
            create_rpa(str(archive), [str(source)])

            output = root / "out"
            with archive.open("rb") as f:
                extract_rpa(f, str(output))

            self.assertEqual(
                (output / "script.rpy").read_text(), 'label start:\n    "Hello"\n'
            )
            self.assertEqual(
                (output / "images" / "bg.png").read_bytes(), b"\x89PNG\r\n\x1a\n"
            )

    def test_rpa_cli_creates_archive_from_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "00unlock.rpy"
            source.write_text("define unlock = True\n")
            archive = root / "unlock.rpa"
            env = os.environ.copy()
            env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")

            result = run(
                [
                    sys.executable,
                    "-m",
                    "rpycdec",
                    "rpa",
                    "-o",
                    str(archive),
                    str(source),
                ],
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            output = root / "out"
            with archive.open("rb") as f:
                extract_rpa(f, str(output))

            self.assertEqual(
                (output / "00unlock.rpy").read_text(), "define unlock = True\n"
            )

    def test_extract_rpa_filters_by_multiple_suffixes_case_insensitively(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = self.create_filter_fixture(root)
            output = root / "out"

            with archive.open("rb") as f:
                extract_rpa(f, str(output), suffixes=[".rpy", ".rpyc"])

            self.assertTrue((output / "script.rpy").is_file())
            self.assertTrue((output / "scripts" / "chapter.RPYC").is_file())
            self.assertFalse((output / "images" / "bg.png").exists())
            self.assertFalse((output / "notes.txt").exists())

    def test_extract_rpa_accepts_a_single_filter_string(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = self.create_filter_fixture(root)
            output = root / "out"

            with archive.open("rb") as f:
                extract_rpa(f, str(output), suffixes=".rpy")

            self.assertTrue((output / "script.rpy").is_file())
            self.assertFalse((output / "scripts" / "chapter.RPYC").exists())

    def test_extract_rpa_combines_expressions_and_suffixes_with_or(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = self.create_filter_fixture(root)
            output = root / "out"

            with archive.open("rb") as f:
                extract_rpa(
                    f,
                    str(output),
                    expressions=[r"^images/.*\.png$"],
                    suffixes=[".rpy"],
                )

            self.assertTrue((output / "script.rpy").is_file())
            self.assertTrue((output / "images" / "bg.png").is_file())
            self.assertFalse((output / "scripts" / "chapter.RPYC").exists())
            self.assertFalse((output / "notes.txt").exists())

    def test_unrpa_cli_supports_expression_and_multiple_suffixes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = self.create_filter_fixture(root)
            output = root / "out"
            env = os.environ.copy()
            env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")

            result = run(
                [
                    sys.executable,
                    "-m",
                    "rpycdec",
                    "unrpa",
                    str(archive),
                    "-o",
                    str(output),
                    "-e",
                    r"^images/",
                    "-s",
                    ".rpy",
                    ".rpyc",
                ],
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((output / "script.rpy").is_file())
            self.assertTrue((output / "scripts" / "chapter.RPYC").is_file())
            self.assertTrue((output / "images" / "bg.png").is_file())
            self.assertFalse((output / "notes.txt").exists())

    def test_unrpa_cli_rejects_invalid_expression(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")
        result = run(
            [
                sys.executable,
                "-m",
                "rpycdec",
                "unrpa",
                "archive.rpa",
                "-e",
                "[",
            ],
            text=True,
            capture_output=True,
            env=env,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid regular expression", result.stderr)


if __name__ == "__main__":
    unittest.main()
