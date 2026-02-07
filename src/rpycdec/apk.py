"""
APK extraction module for Ren'Py games.

This module provides functionality to extract Ren'Py game resources from Android APK files.
The extraction is done in a streaming fashion to minimize disk I/O and temporary file usage.
"""

import io
import zipfile
import tarfile
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PrependedStream(io.RawIOBase):
    """Wrapper to prepend already-read bytes back to stream."""

    def __init__(self, prepend_data, stream):
        self.prepend_data = prepend_data
        self.stream = stream
        self.prepend_pos = 0

    def readable(self):
        return True

    def read(self, size=-1):
        if size == -1:
            result = self.prepend_data[self.prepend_pos :] + self.stream.read()
            self.prepend_pos = len(self.prepend_data)
            return result

        result = b""
        # First read from prepended data
        if self.prepend_pos < len(self.prepend_data):
            take = min(size, len(self.prepend_data) - self.prepend_pos)
            result = self.prepend_data[self.prepend_pos : self.prepend_pos + take]
            self.prepend_pos += take
            size -= take

        # Then read from underlying stream
        if size > 0:
            result += self.stream.read(size)

        return result

    def readinto(self, b):
        data = self.read(len(b))
        b[: len(data)] = data
        return len(data)


def extract_apk(
    apk_path: str,
    output_dir: Optional[str] = None,
) -> bool:
    """
    Extract Ren'Py game resources from an Android APK file.

    This function directly extracts files from the APK (ZIP) archive,
    renaming them on-the-fly to remove 'x-' prefixes and organizing
    them into a standard Ren'Py structure. The private.mp3 archive
    is extracted in-memory without writing to disk first.

    Args:
        apk_path: Path to the APK file
        output_dir: Output directory (default: APK filename without extension)

    Returns:
        True if extraction was successful, False otherwise
    """
    apk_file = Path(apk_path)

    if not apk_file.exists():
        logger.error(f"APK file not found: {apk_path}")
        return False

    if not zipfile.is_zipfile(apk_path):
        logger.error(f"File is not a valid APK/ZIP file: {apk_path}")
        return False

    # Determine output directory
    if output_dir is None:
        output_path = apk_file.parent / apk_file.stem
    else:
        output_path = Path(output_dir)

    output_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"Extracting APK: {apk_path}")

    with zipfile.ZipFile(apk_path, "r") as apk:
        # Get all relevant files (assets and lib)
        target_files = [f for f in apk.namelist() if f.startswith(("assets/", "lib/"))]

        if not target_files:
            logger.warning("No assets or lib directory found in APK")
            return False

        private_mp3_path = None
        extracted_count = 0

        for file_path in target_files:
            # Skip directories
            if file_path.endswith("/"):
                continue

            if file_path.startswith("assets/"):
                # Remove 'assets/' prefix
                relative_path = file_path[7:]  # len('assets/') = 7

                # Handle private.mp3 specially - remember path for later streaming extraction
                if relative_path == "private.mp3":
                    logger.info("Found private.mp3, will extract via streaming...")
                    private_mp3_path = file_path
                    continue

                # Process path: remove x- prefix and apply mappings
                path_parts = relative_path.split("/")

                # Process all path parts to remove x- prefix
                for i in range(len(path_parts)):
                    # Remove x- prefix from all parts
                    if path_parts[i].startswith("x-"):
                        path_parts[i] = path_parts[i][2:]  # Remove 'x-' prefix

                # Reconstruct path
                dest_path = output_path / "/".join(path_parts)

            elif file_path.startswith("lib/"):
                # User request: extract lib to output/lib/android/
                rel_lib_path = file_path[4:]  # len('lib/') = 4
                dest_path = output_path / "lib" / "android" / rel_lib_path

            else:
                continue

            # Create parent directories
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Extract file directly
            with apk.open(file_path) as src, open(dest_path, "wb") as dst:
                dst.write(src.read())

            extracted_count += 1
            if extracted_count % 100 == 0:
                logger.info(f"Extracted {extracted_count} files...")

        logger.info(f"Extracted {extracted_count} files")

        # Extract private.mp3 via streaming if found
        if private_mp3_path:
            logger.info("Extracting files from private.mp3 archive...")
            # Extract directly to output root (same level as game/)
            private_output = output_path
            private_output.mkdir(parents=True, exist_ok=True)

            with apk.open(private_mp3_path) as private_stream:
                # Read magic bytes to detect gzip format
                magic = private_stream.read(2)

                if not magic.startswith(b"\x1f\x8b"):
                    logger.warning(
                        "private.mp3 is not gzip format, skipping extraction"
                    )
                else:
                    # Create buffered stream with magic bytes prepended
                    wrapped_stream = io.BufferedReader(
                        PrependedStream(magic, private_stream)
                    )

                    with tarfile.open(fileobj=wrapped_stream, mode="r:gz") as tar:
                        tar.extractall(path=private_output)
                        logger.info(
                            f"Extracted {len(tar.getmembers())} files from private.mp3"
                        )

    logger.info(f"Successfully extracted game to: {output_path}")
    return True
