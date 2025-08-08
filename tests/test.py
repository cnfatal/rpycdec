import io
import logging
import unittest
import zipfile
import requests
import os
import re
import subprocess
import shutil


from rpycdec import decompile


def download_renpy_sdk(version: str, dir: str) -> str:
    """
    Download Ren'Py SDK from GitHub releases.
    :param version: Ren'Py version, e.g. "8.3.0"
    :param into: Directory to download the SDK into.
    """
    os.makedirs(dir, exist_ok=True)
    sdk_path = f"renpy-{version}-sdk"
    full_sdk_path = os.path.join(dir, sdk_path)
    if os.path.exists(full_sdk_path):
        logging.info(f"Ren'Py SDK {version} already exists at {full_sdk_path}")
        return full_sdk_path
    url = f"https://www.renpy.org/dl/{version}/renpy-{version}-sdk.zip"
    logging.info(f"Downloading and extracting Ren'Py SDK {version} from {url}")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    tmp_dir = os.path.join(dir, f"renpy-{version}-sdk-tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
        # zip_ref.extractall(tmp_dir)
        for file in zip_ref.namelist():
            zip_ref.extract(file, tmp_dir)
            perm = zip_ref.getinfo(file).external_attr >> 16
            if perm:
                # Set file permissions if available
                os.chmod(os.path.join(tmp_dir, file), perm)
    # move extracted files to the final directory
    os.rename(os.path.join(tmp_dir, sdk_path), full_sdk_path)
    shutil.rmtree(tmp_dir, ignore_errors=True)
    logging.info(f"Ren'Py SDK {version} extracted to {full_sdk_path}")
    return full_sdk_path


def compile_game(sdk_path, game_path):
    """Compile the game using the Ren'Py SDK.
    :param sdk_path: Path to the Ren'Py SDK.
    :param game_path: Path to the game directory containing .rpy files.
    """
    renpy_script = os.path.join(sdk_path, "renpy.sh")
    if not os.path.exists(renpy_script):
        raise FileNotFoundError(f"renpy.sh not found in SDK: {renpy_script}")

    if not os.path.exists(game_path):
        logging.info(f"Game path does not exist: {game_path}, skipping compilation.")
        return

    abs_game_path = os.path.abspath(game_path)

    cmd = ["bash", renpy_script, abs_game_path, "compile"]
    logging.info(f"Compiling game with command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=sdk_path)
    if result.returncode != 0:
        logging.error(f"Compilation failed: {result.stderr}")
        raise Exception(f"Compile game error: {result.stdout}")
    logging.info(f"Game compiled successfully: {game_path}")


class TestRpycDec(unittest.TestCase):

    def setUp(self):
        self.test_dir = os.path.dirname(__file__)
        self.sdks_dir = os.path.join(os.path.dirname(self.test_dir), "sdks")

    def find_test_versions(self):
        """
        Find all Ren'Py versions in the test directory.
        :return: List of tuples (version, path) for each found version.
        """
        return [
            (match.group(1), os.path.join(self.test_dir, item))
            for item in os.listdir(self.test_dir)
            if os.path.isdir(os.path.join(self.test_dir, item))
            and (match := re.match(r"renpy-(\d+\.\d+\.\d+)", item))
        ]

    def decompile_and_compare(self, game_path):
        decompile_dir = os.path.join(
            os.path.dirname(game_path), os.path.basename(game_path) + f"_decompiled"
        )
        if os.path.exists(decompile_dir):
            shutil.rmtree(decompile_dir)
        os.makedirs(decompile_dir)
        rpyc_files = []
        for root, dirs, files in os.walk(game_path):
            for file in files:
                if file.endswith(".rpyc"):
                    rpyc_files.append(os.path.join(root, file))

        if not rpyc_files:
            logging.warning(f"No .rpyc files found in {game_path}")
            return True
        for rpyc_file in rpyc_files:
            rpy_file = rpyc_file.replace(".rpyc", ".rpy")
            output_file = os.path.join(
                decompile_dir, os.path.relpath(rpy_file, game_path)
            )
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            logging.info(f"Decompiling {rpyc_file} to {output_file}")
            decompile(rpyc_file, output_file)

            # 检查是否成功生成了输出文件
            if not os.path.exists(output_file):
                logging.error(
                    f"Decompilation failed: output file not created: {output_file}"
                )
                return False
            # todo: compare with original .rpy file if exists
        return True

    def test_decompile(self):
        """
        Test decompilation of Ren'Py games for all versions found in the test directory.
        """
        version_games = [
            ("8.4.1", "tests/renpy8/game"),
        ]
        for version, game_path in version_games:
            with self.subTest(version=version):
                logging.info(f"Testing Ren'Py version {version} with game: {game_path}")
                sdk_path = download_renpy_sdk(version, self.sdks_dir)
                compile_game(sdk_path, game_path)
                success = self.decompile_and_compare(game_path)
                self.assertTrue(
                    success, f"Decompilation test failed for version {version}"
                )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
