# rpycdec

A tool for decompiling Ren'py compiled script files (.rpyc and .rpymc).

## Features

- Decompile .rpyc and .rpymc files to readable Python code
- Extract RPA archives
- Parse translations from .rpyc and .rpymc files to `tl/{language}/` directories
- Support for multiple Ren'py versions (7.x, 8.x)

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

Extract translations:

```sh
rpycdec extract-translate /path/to/game/ -l Chinese
```

### Library Usage

```python
from rpycdec import decompile, extract_rpa

# decompile a file
with open('script.rpyc', 'rb') as input_file, open('script.rpy', 'wb') as output_file:
    decompile(input_file, output_file)

# Extract RPA archive
with open('archive.rpa', 'rb') as f:
    extract_rpa(f, './extracted/')
```

## Troubleshooting

- **Q: It always raise pickle `import ** \nModuleNotFoundError: No module named '**\*'` error.**

  A: It's because the our fake packages("renpy","store") is not contains the object you want to decompile. Please open an issue and tell us the renpy version and the rpyc file you want to decompile. Join our telegram group to get help also be better.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## Community & Support

- [GitHub Issues](https://github.com/cnfatal/rpycdec/issues) - Bug reports and feature requests
- [Telegram Group](https://t.me/rpycdec) - Community discussion and help
