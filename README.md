# rpycdec

A tool for decompiling Ren'py compiled script files (.rpyc and .rpymc).

## Features

- Decompile `.rpyc` and `.rpymc` files to readable Ren'Py script code
- Extract RPA archives
- Extract and edit Ren'Py save files (`.save` → JSON → `.save`)
- Extract Ren'Py games from Android APK files
- Extract translations from compiled scripts to `tl/{language}/` directories
- Support for multiple Ren'Py versions (7.x, 8.x)

## Installation

Install with pip:

```sh
pip install rpycdec
```

Or install from source:

```sh
git clone https://github.com/cnfatal/rpycdec.git
cd rpycdec
pip install .
```

## Usage

### Command Line Interface

Decompile a single file:

```sh
rpycdec decompile script.rpyc
```

Decompile all files in a directory:

```sh
rpycdec decompile /path/to/game/
```

Extract RPA archive:

```sh
rpycdec unrpa archive.rpa
```

Extract Ren'Py game from Android APK:

```sh
rpycdec extract-game game.apk
```

Extract translations:

```sh
rpycdec extract-translate /path/to/game/ -l Chinese
```

## Security Warning

This tool processes `.rpyc`, `.rpymc`, `.rpa`, and `.save` files which use Python's `pickle` format internally. rpycdec uses restricted unpicklers with whitelist-based class loading to mitigate arbitrary code execution risks, but **no pickle safeguard is perfect**. Only process files from sources you trust.

Set `RPYCDEC_NO_WARNING=1` to suppress the CLI security warning.

See also: [Python pickle security warning](https://docs.python.org/3/library/pickle.html#module-pickle)

## Troubleshooting

- **Q: Pickle error `ModuleNotFoundError: No module named '...'`**

  A: This means our fake `renpy`/`store` packages don't cover the class your file needs. Please [open an issue](https://github.com/cnfatal/rpycdec/issues) with the Ren'Py version and the file that failed.

## Contributing

Contributions are welcome! Please [open an issue](https://github.com/cnfatal/rpycdec/issues) before submitting major changes so we can discuss the approach.

## Community & Support

- [GitHub Issues](https://github.com/cnfatal/rpycdec/issues) — Bug reports and feature requests
- [Telegram Group](https://t.me/rpycdec) — Community discussion and support

## Alternative

- [unrpyc](https://github.com/CensoredUsername/unrpyc) - The well-established and widely-used Ren'Py script decompiler
