# rpycdec

[![PyPI](https://img.shields.io/pypi/v/rpycdec)](https://pypi.org/project/rpycdec/)
[![Python versions](https://img.shields.io/pypi/pyversions/rpycdec)](https://pypi.org/project/rpycdec/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![tests](https://github.com/cnfatal/rpycdec/actions/workflows/test.yml/badge.svg)](https://github.com/cnfatal/rpycdec/actions/workflows/test.yml)

A tool for decompiling Ren'Py compiled script files (`.rpyc` and `.rpymc`) back
to readable `.rpy` source. It reads scripts compiled by Ren'Py 7 and 8, and is
tested against 7.6.3, 8.2.3, 8.4.1 and 8.5.3.

## Features

| What it does                              | Command                     | Notes                                         |
| ----------------------------------------- | --------------------------- | --------------------------------------------- |
| Decompile a script, or a whole game       | `rpycdec decompile`         | Ren'Py 7.x and 8.x                            |
| Inspect a compiled script, or compare two | `rpycdec dump`              | what the `.rpyc` carries, not just the source |
| Extract an RPA archive, all or part of it | `rpycdec unrpa`             | filter by path expression or suffix           |
| Build an RPA archive                      | `rpycdec rpa`               | files or whole directories                    |
| Pull the game out of an Android APK       | `rpycdec extract-game`      |                                               |
| Write a game's translations out           | `rpycdec extract-translate` | to `tl/<language>/`                           |
| Take a save file apart and put it back    | `rpycdec save`              | `.save` to JSON and back, re-signing included |

The decompiled source is checked by compiling it again and comparing the two
structures, against fixtures and the scripts the Ren'Py SDKs ship: see
[Testing](#testing).

## Installation

Needs Python 3.10 or newer.

```sh
pip install rpycdec
```

To work on rpycdec itself, install it from a clone in editable mode, which
brings the linter along:

```sh
git clone https://github.com/cnfatal/rpycdec.git
cd rpycdec
pip install -e ".[dev]"
```

The wheel also installs the `renpy` and `store` packages the tool uses to
rebuild a script's objects, so keep it out of an environment where the real
Ren'Py is installed.

## Usage

`<required>`, `[optional]`, `...` repeats, `-v` for verbose output.

```sh
# decompile a file, or every .rpyc / .rpymc under a directory
# -o writes somewhere else, -d also prints the pickle disassembly
rpycdec decompile <path>... [-o <dir>] [-d]

# print the structure a compiled script carries, or diff it against another
# file names, line numbers and the like are left out: no decompiler can keep
rpycdec dump <path> [<other>]

# extract an rpa archive, or just the files matching a path
# -e takes a regular expression, -s a suffix; both may be repeated
rpycdec unrpa <archive.rpa> [-o <dir>] [-e <regex>]... [-s <suffix>]...

# build an rpa archive, naming the files inside relative to --base
rpycdec rpa <path>... -o <archive.rpa> [--base <dir>]

# pull the game out of an Android APK
rpycdec extract-game <game.apk> [-o <dir>]

# write a game's translations to tl/<language>/
rpycdec extract-translate <game-dir>... -l <language> [-o <dir>]
rpycdec extract-translate <game-dir> -l Chinese --no-strings --empty

# take a save file apart into JSON, edit it, put it back together
rpycdec save extract <save> [<dir>] [-d] [-V]
rpycdec save restore <dir> [<save>] [-k <security_keys.txt>]
rpycdec save info <save>
rpycdec save genkey [<security_keys.txt>]

# for example
rpycdec decompile /path/to/game/ -o out/
rpycdec dump script.rpyc script.roundtrip.rpyc
rpycdec unrpa archive.rpa -s .rpy .rpyc
```

## Security Warning

This tool processes `.rpyc`, `.rpymc`, `.rpa`, and `.save` files which use Python's `pickle` format internally. rpycdec uses restricted unpicklers with whitelist-based class loading to mitigate arbitrary code execution risks, but **no pickle safeguard is perfect**. Only process files from sources you trust.

Set `RPYCDEC_NO_WARNING=1` to suppress the CLI security warning.

See also: [Python pickle security warning](https://docs.python.org/3/library/pickle.html#module-pickle)

## Troubleshooting

- **Q: Pickle error `ModuleNotFoundError: No module named '...'`**

  A: This means our fake `renpy`/`store` packages don't cover the class your file needs. Please [open an issue](https://github.com/cnfatal/rpycdec/issues) with the Ren'Py version and the file that failed.

- **Q: A statement came out wrong, or as a comment like `# <unrecognized: Foo>`**

  A: Attach the structure of the file to the issue: `rpycdec dump game/script.rpyc`.
  It prints every node with the attributes it carries, including what the
  decompiled script has no way to show, and an `<unrecognized: ...>` names the
  class our fake `renpy` package is missing.

- **Q: The decompiled script looks right, but compiling it again changes something**

  A: `rpycdec dump original.rpyc decompiled.rpyc` prints what differs between
  the two, which is how the tests in this repository check a round trip. Paste
  that, together with the file and the Ren'Py version, into the issue.

## Contributing

Contributions are welcome! Please [open an issue](https://github.com/cnfatal/rpycdec/issues) before submitting major changes so we can discuss the approach.

How the decompiler works, why it ships a fake `renpy` package, and where a
missing node class goes: [DEVELOP.md](DEVELOP.md).

### Testing

`make test` runs the unit tests and the end-to-end fixtures: each fixture in
`tests/fixtures/` is compiled with every Ren'Py SDK found under `sdks/`,
decompiled, compiled again, and both ASTs are compared. Fixtures declare the
version range they are written for with `# min-renpy:` / `# max-renpy:`
headers, and combinations outside that range are skipped.

`make test-corpus` does the same for every game script the SDKs ship (~300
files, it takes a few minutes). Files that do not survive a round trip yet are
listed in `tests/corpus_baseline.json`, each with the kind of failure and what
differs first; a listed file that starts passing fails the test, so the list
stays honest. Regenerate it with
`python3 -m tests.test_corpus --write-baseline`.

The entries left there are the ones no decompiler can fix, because the value
Ren'Py stored was made at compilation time rather than written in the source:

- `say-identifier` — Ren'Py hands out identifiers while generating
  translations; the script itself has no `id` clause to write back.
- `init-offset` — `init offset` is not in the AST at all, it is folded into the
  priorities of the statements around it.

Both need the SDKs, which are not in the repository; tests that need them skip
when `sdks/` is empty. Set `RPYCDEC_SDKS` to point at SDK roots elsewhere.

## Community & Support

- [GitHub Issues](https://github.com/cnfatal/rpycdec/issues) — Bug reports and feature requests
- [Telegram Group](https://t.me/rpycdec) — Community discussion and support

## Alternatives

- [unrpyc](https://github.com/CensoredUsername/unrpyc) - The well-established and widely-used Ren'Py script decompiler
