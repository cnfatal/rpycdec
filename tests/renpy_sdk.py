"""Locate Ren'Py SDKs and compile a game directory headlessly.

Used by the end-to-end round-trip tests. Set ``RPYCDEC_SDKS`` to override SDK
discovery (os.pathsep separated), ``RENPY_SDK_PYTHON`` to override the
interpreter used to run Ren'Py.
"""

import glob
import os
import re
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_VERSION_RE = re.compile(r"^version\s*=\s*u?['\"](\d+(?:\.\d+)+)", re.MULTILINE)
_NAME_RE = re.compile(r"renpy-(\d+(?:\.\d+)+)-sdk")


def find_sdks() -> list[str]:
    """Returns available Ren'Py SDK roots, newest first."""
    override = os.environ.get("RPYCDEC_SDKS")
    candidates = (
        override.split(os.pathsep)
        if override
        else sorted(glob.glob(f"{REPO_ROOT}/sdks/renpy-*"))
    )
    sdks = [os.path.abspath(c) for c in candidates if python_exe(c)]
    return sorted(sdks, key=sdk_version, reverse=True)


def sdk_version(sdk: str) -> tuple[int, ...]:
    """Returns the Ren'Py version of an SDK, `(0,)` when it cannot be told.

    Read from the SDK's own ``renpy/vc_version.py`` (never imported, it lives
    inside the SDK), falling back to the directory name. The build number some
    versions carry is dropped, so a version compares equal to how a fixture
    spells it.
    """
    version_file = os.path.join(sdk, "renpy", "vc_version.py")
    if os.path.exists(version_file):
        with open(version_file, encoding="utf-8", errors="replace") as handle:
            match = _VERSION_RE.search(handle.read())
        if match:
            return tuple(int(part) for part in match.group(1).split("."))[:3]
    match = _NAME_RE.search(os.path.basename(sdk.rstrip(os.sep)))
    if match:
        return tuple(int(part) for part in match.group(1).split("."))[:3]
    return (0,)


def fixture_versions(path: str) -> tuple[tuple[int, ...], tuple[int, ...] | None]:
    """Reads `# min-renpy:` / `# max-renpy:` from a fixture's header.

    Ren'Py only accepts some syntax in some versions -- the two generations of
    `testcase` cannot be compiled by the same SDK -- so a fixture declares the
    range it is written for.
    """
    minimum: tuple[int, ...] = (0,)
    maximum: tuple[int, ...] | None = None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith("#"):
                break
            match = re.match(r"#\s*(min|max)-renpy:\s*(\d+(?:\.\d+)+)", line)
            if not match:
                continue
            version = tuple(int(part) for part in match.group(2).split("."))
            if match.group(1) == "min":
                minimum = version
            else:
                maximum = version
    return minimum, maximum


# SDK layouts differ per platform: macOS ships the interpreter inside the app
# bundle, the linux/windows SDKs ship it under lib/.
_PYTHON_CANDIDATES = (
    "renpy.app/Contents/MacOS/python",
    "lib/py3-linux-x86_64/python",
    "lib/py3-linux-i686/python",
    "lib/py3-windows-x86_64/python.exe",
    "lib/py3-mac-universal/python",
)


def python_exe(sdk: str) -> str | None:
    """Returns the interpreter Ren'Py should be run with, None if not found."""
    override = os.environ.get("RENPY_SDK_PYTHON")
    if override:
        return override if os.path.exists(override) else None
    for candidate in _PYTHON_CANDIDATES:
        path = os.path.join(sdk, candidate)
        if os.path.exists(path):
            return path
    return None


class CompileError(RuntimeError):
    pass


def compile_game(sdk: str, basedir: str, timeout: int = 300) -> list[str]:
    """Compiles every .rpy of ``basedir``/game with the given SDK.

    Returns the list of generated .rpyc files. Raises CompileError including
    Ren'Py's own output, which carries the file and line Ren'Py failed on.
    """
    python = python_exe(sdk)
    if not python:
        raise CompileError(f"no usable interpreter found for SDK {sdk}")
    env = dict(os.environ, SDL_VIDEODRIVER="dummy")
    result = subprocess.run(
        [python, os.path.join(sdk, "renpy.py"), basedir, "compile"],
        cwd=sdk,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise CompileError(
            f"failed to compile {basedir}:\n{result.stdout[-3000:]}{result.stderr[-2000:]}"
        )
    game = os.path.join(basedir, "game")
    return sorted(
        os.path.join(game, f)
        for f in os.listdir(game)
        if f.endswith((".rpyc", ".rpymc"))
    )
