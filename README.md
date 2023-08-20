# rpycdec

Decompiler for Ren'py compiled script files (.rpyc and .rpymc).

## Usage

```sh
pip install rpypcdec
rpycdec [--force] <path to rpyc file or dir>
```

### Library usage

```python
import rpycdec

rpycdec.decompile(filename)
```
