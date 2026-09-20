"""Corpus round-trip tests: decompile a compiled script, compile the result
again, and require the two ASTs to match.

Instead of hand written fixtures this walks the game scripts the Ren'Py SDKs
ship, which is where the odd corners live -- the SDKs carry ~300 of them, from
two line examples to the launcher.

Every file costs a Ren'Py start, so this is opt-in:

    make test-corpus

`tests/corpus_baseline.json` lists the files known not to survive a round trip
yet, with the kind of failure and, for the AST ones, what differs first. A file
listed there that starts passing fails the test, so the baseline has to stay
honest. Regenerate it with:

    python3 -m tests.test_corpus --write-baseline
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _path in (os.path.join(_ROOT, "src"), _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from rpycdec.astdump import (  # noqa: E402
    canonical,
    diff,
    dump_file,
    first_difference,
)
from rpycdec.decompile import decompile_file  # noqa: E402
from tests import renpy_sdk  # noqa: E402

BASELINE = os.path.join(_HERE, "corpus_baseline.json")
ENABLED = "RPYCDEC_CORPUS"


def corpus_files() -> list:
    """(sdk, path) for every game script the SDKs ship.

    Only the projects' own `game/` scripts: Ren'Py always loads its own
    `renpy/common/*.rpyc` on startup, so a decompiled copy of one of those
    cannot be compiled back -- the two collide on every label they define.
    """
    found = []
    for sdk in renpy_sdk.find_sdks():
        for project in sorted(os.listdir(sdk)):
            game = os.path.join(sdk, project, "game")
            if not os.path.isdir(game):
                continue
            found += [
                (sdk, os.path.join(game, name))
                for name in sorted(os.listdir(game))
                if name.endswith(".rpyc")
            ]
    return found


def _is_package(path: str) -> bool:
    """True for a directory holding python, e.g. the launcher's `gui7`."""
    if not os.path.isdir(path):
        return False
    return any(name.endswith(".py") for name in os.listdir(path))


def _copy_project(game_dir: str, game: str, skip: str) -> None:
    """Copies a project's game directory, minus the file being tested.

    Files, and the directories that hold python (a game can ship modules its
    scripts import). Assets, `cache/` and `tl/` are left out: compiling does
    not need them and `tl/` alone is megabytes per project.
    """
    for entry in os.listdir(game_dir):
        source = os.path.join(game_dir, entry)
        if entry == skip or entry in ("cache", "saves"):
            continue
        if os.path.isfile(source):
            shutil.copy2(source, os.path.join(game, entry))
        elif _is_package(source):
            shutil.copytree(source, os.path.join(game, entry))


# What the first difference means, for the note in the baseline.
REASONS = (
    ("Init.priority", "init-offset: `init offset` shifts priorities at parse time"),
    ("identifier", "say-identifier: renpy generates these while translating"),
    ("PyCode", "python-indentation: how renpy recorded the block"),
    ("UserStatement.block", "user-statement-source: the text renpy recorded"),
)


def reason_for(detail: str) -> str:
    for marker, reason in REASONS:
        if marker in detail:
            return reason
    return ""


def check(sdk: str, source: str) -> tuple:
    """Round trips one file, returns ("", "") when its AST survives.

    The file goes back into its own project, with the project's other compiled
    scripts alongside: game scripts use statements the project registers and
    labels their siblings define, so a lone file would not even parse.
    """
    game_dir = os.path.dirname(source)
    name = os.path.basename(source)
    with tempfile.TemporaryDirectory() as work:
        game = os.path.join(work, "game")
        os.makedirs(game)
        _copy_project(game_dir, game, name)
        target = os.path.join(game, name.replace(".rpyc", ".rpy"))
        try:
            decompile_file(source, target)
            compiled = renpy_sdk.compile_game(sdk, work)
        except Exception:
            return "recompile-error", ""
        again = next(path for path in compiled if os.path.basename(path) == name)
        golden, again_dump = dump_file(source), dump_file(again)
        if diff(golden, again_dump, "compiled", "roundtrip"):
            # locate the difference the way the comparison sees it: on the
            # canonical form, where positions are already gone
            return "ast-mismatch", first_difference(
                canonical(golden), canonical(again_dump)
            )
    return "", ""


def relative(path: str) -> str:
    return os.path.relpath(path, _ROOT)


def load_baseline() -> dict:
    if not os.path.exists(BASELINE):
        return {}
    with open(BASELINE, encoding="utf-8") as handle:
        return json.load(handle)


class TestCorpus(unittest.TestCase):
    """The scripts the SDK ships must survive a decompile round trip."""

    def setUp(self):
        if not os.environ.get(ENABLED):
            self.skipTest(f"set {ENABLED}=1 to run the corpus round trip")

    def test_corpus(self):
        if not renpy_sdk.find_sdks():
            self.skipTest("no Ren'Py SDK found under sdks/")
        baseline = load_baseline()
        unexpected = []
        stale = []
        for sdk, path in corpus_files():
            name = relative(path)
            with self.subTest(name):
                failure, _ = check(sdk, path)
                if failure and name not in baseline:
                    unexpected.append(f"{name}: {failure}")
                elif not failure and name in baseline:
                    stale.append(f"{name}: passes now, drop it from the baseline")
        self.assertEqual(stale, [], "the baseline is out of date")
        self.assertEqual(unexpected, [], f"{len(unexpected)} files do not round trip")


def write_baseline() -> None:
    entries = {}
    for sdk, path in corpus_files():
        failure, detail = check(sdk, path)
        if failure:
            entries[relative(path)] = {
                "kind": failure,
                "reason": reason_for(detail),
            }
            print(f"{failure:16s} {relative(path)}")
    with open(BASELINE, "w", encoding="utf-8") as handle:
        json.dump(dict(sorted(entries.items())), handle, indent=2)
        handle.write("\n")
    print(f"\n{len(entries)} known failures written to {BASELINE}")


if __name__ == "__main__":
    if "--write-baseline" in sys.argv:
        write_baseline()
    else:
        unittest.main()
