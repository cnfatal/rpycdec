# rpycdec

A tools for decompiling and translating Ren'py compiled script files (.rpyc and .rpymc).

## Features

- Decompile for Ren'py compiled script files .rpyc to .rpy files.
- Automatic scan translations in scripts and translate to target language (default using Google Translate).

## Usage

Install with pip:

```sh
pip install rpypcdec
```

Decompile a file or directory:

```sh
rpycdec [--force] <path to rpyc file or dir>
```

Decompile and translate a file or directory:

```sh
rpycdec --translate <path to rpyc file or dir>
```

### Library usage

```python
import rpycdec

rpycdec.decompile(filename)
```

## Development  

Use pipenv to manage dependencies:

```sh
pipenv install --dev
```

## Community

- [Telegram Group](https://t.me/rpycdec)
