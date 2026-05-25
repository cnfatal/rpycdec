import os
import sys
import tempfile
import unittest
from subprocess import run
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rpycdec.rpa import create_rpa, extract_rpa

SRC_DIR = str(Path(__file__).resolve().parents[1] / "src")


class RPATests(unittest.TestCase):
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
            source.write_text('define unlock = True\n')
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
                (output / "00unlock.rpy").read_text(), 'define unlock = True\n'
            )


if __name__ == "__main__":
    unittest.main()
