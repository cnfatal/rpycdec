# rpycdec

A tools for decompiling and translating Ren'py compiled script files (.rpyc and .rpymc).

## How it works

All rpyc files are compiled from rpy files, renpy SDK read every file and parse it to AST object(renpy), and then use pickle to serialize the AST to rpyc file. So we use pickle to deserialize the rpyc file to AST, and then restore the rpy file from AST.

We created a fake "renpy" package(unlikely unrpyc) and it's ast objects to make the pickle can be deserialized correctly.
Another reason to create a fake "renpy" package is that we can separate code generate logic (the `get_code(...)` function) to each AST object, it will be easier to future maintain and for multi-version renpy support.

The most difficult part is generating the rpy file from AST. Different renpy version has different AST structure also different grammar.

## Install

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

Decompile a file:

```sh
rpycdec <path to rpyc file or dir>
```

### Library usage

```python
from rpycdec import decompile, translate

# decompile a file
decompile(input_file, output_file)

# decompile and translate a file
translate(input_file, output_file)
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## FAQ

- **Q: It always raise pickle `import ** \nModuleNotFoundError: No module named '***'` error.**

  A: It's because the our fake packages("renpy","store") is not contains the object you want to decompile. Please open an issue and tell us the renpy version and the rpyc file you want to decompile. Join our telegram group to get help also be better.

## Community

Welcome to join our community to discuss and get help.

- [Telegram Group](https://t.me/rpycdec)
