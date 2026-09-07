import io
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rpycdec.apk import extract_apk


class APKTests(unittest.TestCase):
    def create_apk(self, root: Path, private_archive: io.BytesIO) -> Path:
        apk_path = root / "game.apk"
        with zipfile.ZipFile(apk_path, "w") as apk:
            apk.writestr("assets/private.mp3", private_archive.getvalue())
        return apk_path

    def test_extract_apk_streams_large_private_archive(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            private_data = bytes(range(256)) * 32_768

            private_archive = io.BytesIO()
            with tarfile.open(fileobj=private_archive, mode="w:gz") as tar:
                member = tarfile.TarInfo("game/large.bin")
                member.size = len(private_data)
                tar.addfile(member, io.BytesIO(private_data))

            apk_path = self.create_apk(root, private_archive)
            output_path = root / "out"

            self.assertTrue(extract_apk(str(apk_path), str(output_path)))
            self.assertEqual(
                (output_path / "game" / "large.bin").read_bytes(), private_data
            )

    def test_extract_apk_skips_unsafe_private_archive_members(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            private_archive = io.BytesIO()
            with tarfile.open(fileobj=private_archive, mode="w:gz") as tar:
                safe_data = b"safe"
                safe_member = tarfile.TarInfo("game/safe.txt")
                safe_member.size = len(safe_data)
                tar.addfile(safe_member, io.BytesIO(safe_data))

                unsafe_member = tarfile.TarInfo("game/escape")
                unsafe_member.type = tarfile.SYMTYPE
                unsafe_member.linkname = "../../outside"
                tar.addfile(unsafe_member)

            apk_path = self.create_apk(root, private_archive)
            output_path = root / "out"

            with self.assertLogs("rpycdec.apk", level="WARNING") as logs:
                self.assertTrue(extract_apk(str(apk_path), str(output_path)))

            self.assertEqual((output_path / "game" / "safe.txt").read_bytes(), b"safe")
            self.assertFalse((output_path / "game" / "escape").is_symlink())
            self.assertIn("Skipping unsafe tar member game/escape", logs.output[0])


if __name__ == "__main__":
    unittest.main()
