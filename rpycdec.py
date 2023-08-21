import argparse
import os
import pathlib
import pickle
import pickletools
import struct
import zlib
from renpy import util

# A string at the start of each rpycv2 file.
RPYC2_HEADER = b"RENPY RPC2"


def read_rpyc_data(f, slot):
    """
    Reads the binary data from `slot` in a .rpyc (v1 or v2) file. Returns
    the data if the slot exists, or None if the slot does not exist.
    """
    f.seek(0)
    header_data = f.read(1024)
    # Legacy path.
    if header_data[: len(RPYC2_HEADER)] != RPYC2_HEADER:
        if slot != 1:
            return None
        f.seek(0)
        data = f.read()
        return zlib.decompress(data)
    # RPYC2 path.
    pos = len(RPYC2_HEADER)
    while True:
        header_slot, start, length = struct.unpack("III", header_data[pos : pos + 12])
        if slot == header_slot:
            break
        if header_slot == 0:
            return None
        pos += 12
    f.seek(start)
    data = f.read(length)
    return zlib.decompress(data)


def load_file(fn, disasm: bool = False):
    if fn.endswith(".rpy") or fn.endswith(".rpym"):
        if os.path.exists(fn):
            print(
                "not support for rpy file, to parse statement use renpy.parser.parse() in renpy's SDK "
            )
            return None
        fn += "c"
    if fn.endswith(".rpyc") or fn.endswith(".rpymc"):
        with open(fn, "rb") as f:
            for slot in [1, 2]:
                bindata = read_rpyc_data(f, slot)
                if bindata:
                    if disasm:
                        disasm_file = fn + ".disasm"
                        with open(disasm_file, "wt") as disasm_f:
                            pickletools.dis(bindata, out=disasm_f)
                    data, stmts = pickle.loads(bindata)
                    return stmts
                f.seek(0)
    return None


def decompile_file(input_file, output_file=None, overwrite: bool = False):
    if not output_file:
        output_file = input_file.replace(".rpyc", ".rpy").replace(".rpymc", ".rpym")
    if os.path.exists(output_file) and not overwrite:
        print(f"skip exists output file {output_file}")
        return
    print(f"decompiling {input_file} to {output_file}")
    # unpickle
    stmts = load_file(input_file)
    # decompile
    code = util.get_code(stmts)
    with open(output_file, "wt") as f:
        f.write(code)


def decompile_dir(input_dir, output_dir=None, overwrite: bool = False):
    if not output_dir:
        output_dir = input_dir
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in pathlib.Path(input_dir).rglob("*"):
        if filename.is_dir():
            continue
        filename = str(filename.relative_to(input_dir))
        if filename.endswith(".rpyc") or filename.endswith(".rpymc"):
            input_file = os.path.join(input_dir, filename)
            output_file = os.path.join(
                output_dir,
                filename.replace(".rpyc", ".rpy").replace(".rpymc", ".rpym"),
            )
            decompile_file(input_file, output_file, overwrite=overwrite)


def decompile(input, output=None, overwrite=False):
    if os.path.isdir(input):
        decompile_dir(input, output, overwrite)
    else:
        decompile_file(input, output, overwrite)


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--force", action="store_true", help="overwrite exists file")
    argparser.add_argument("--dir", "-d", help="output base directory")
    argparser.add_argument("path", nargs="+", help="path to rpyc file or directory")
    args = argparser.parse_args()
    for path in args.path:
        if not os.path.exists(path):
            print("path %s not exists", path)
            return
        decompile(path, args.dir, overwrite=args.force)


if __name__ == "__main__":
    main()
