# Development Guide

## How decompilation works

All rpyc files are compiled from rpy files, renpy SDK read every file and parse it to AST object(renpy), and then use pickle to serialize the AST to rpyc file. So we use pickle to deserialize the rpyc file to AST, and then restore the rpy file from AST.

We created a fake "renpy" package(unlikely unrpyc) and it's ast objects to make the pickle can be deserialized correctly.
Another reason to create a fake "renpy" package is that we can separate code generate logic (the `get_code(...)` function) to each AST object, it will be easier to future maintain and for multi-version renpy support.

The most difficult part is generating the rpy file from AST. Different renpy version has different AST structure also different grammar.
