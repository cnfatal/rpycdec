"""End-to-end tests: compile fixtures with the Ren'Py SDK, decompile them
with rpycdec, recompile the result, and compare the two ASTs semantically.

These tests need a Ren'Py SDK under ``sdks/`` (gitignored). They are skipped
when no SDK is present. Point ``RPYCDEC_SDKS`` at SDK roots to override, e.g.
``RPYCDEC_SDKS=sdks/renpy-8.5.3-sdk`` to only run against one version.
"""

import logging
import os
import shutil
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
for _path in (os.path.join(os.path.dirname(_HERE), "src"), _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from rpycdec.astdump import diff, dump_file  # noqa: E402
from rpycdec.decompile import decompile_file  # noqa: E402
from tests import renpy_sdk  # noqa: E402

FIXTURES = os.path.join(_HERE, "fixtures")

logger = logging.getLogger(__name__)


class UnknownClassCollector(logging.Handler):
    """Collects 'Unknown class' warnings emitted while decompiling."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.classes = set()

    def emit(self, record):
        msg = record.getMessage()
        if msg.startswith("Unknown class"):
            self.classes.add(msg.split(":")[1].strip().rstrip("."))


def roundtrip(sdk: str, fixture: str) -> dict:
    """Compile -> decompile -> compile, returns both AST dumps for comparison.

    Everything happens in a temporary tree, so only the in-memory results are
    returned; the compiled files themselves are throwaway.
    """
    name = os.path.basename(fixture)
    with tempfile.TemporaryDirectory() as workdir:
        golden_dir = os.path.join(workdir, "golden")
        os.makedirs(os.path.join(golden_dir, "game"), exist_ok=True)
        shutil.copy(fixture, os.path.join(golden_dir, "game", name))
        golden_rpyc = renpy_sdk.compile_game(sdk, golden_dir)[0]

        recompiled_dir = os.path.join(workdir, "recompiled")
        os.makedirs(os.path.join(recompiled_dir, "game"), exist_ok=True)
        source = os.path.join(recompiled_dir, "game", name)
        collector = UnknownClassCollector()
        safe_pickle_log = logging.getLogger("rpycdec.safe_pickle")
        safe_pickle_log.addHandler(collector)
        try:
            decompile_file(golden_rpyc, source)
        finally:
            safe_pickle_log.removeHandler(collector)
        recompiled_rpyc = renpy_sdk.compile_game(sdk, recompiled_dir)[0]

        return {
            "unknown_classes": collector.classes,
            "golden": dump_file(golden_rpyc),
            "recompiled": dump_file(recompiled_rpyc),
        }


class TestRoundTrip(unittest.TestCase):
    """Every fixture must survive compile -> decompile -> compile unchanged."""

    def test_fixtures(self):
        sdks = renpy_sdk.find_sdks()
        if not sdks:
            self.skipTest("no Ren'Py SDK found under sdks/")
        fixtures = sorted(f for f in os.listdir(FIXTURES) if f.endswith(".rpy"))
        self.assertTrue(fixtures, "no fixtures found")
        for name in fixtures:
            path = os.path.join(FIXTURES, name)
            minimum, maximum = renpy_sdk.fixture_versions(path)
            for sdk in sdks:
                label = f"{name} @ {os.path.basename(sdk)}"
                with self.subTest(label):
                    version = renpy_sdk.sdk_version(sdk)
                    if version < minimum:
                        self.skipTest(
                            f"{label}: needs Ren'Py >= {minimum}, this SDK is {version}"
                        )
                    if maximum and version > maximum:
                        self.skipTest(
                            f"{label}: needs Ren'Py <= {maximum}, this SDK is {version}"
                        )
                    result = roundtrip(sdk, path)
                    self.assertEqual(result["unknown_classes"], set(), label)
                    mismatch = diff(
                        result["golden"],
                        result["recompiled"],
                        fromfile=f"compiled {label}",
                        tofile=f"roundtrip {label}",
                    )
                    if mismatch:
                        self.fail(f"{label} AST mismatch:\n{mismatch}")


if __name__ == "__main__":
    unittest.main()
