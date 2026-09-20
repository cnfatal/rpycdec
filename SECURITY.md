# Security Policy

## What this tool does with untrusted input

rpycdec reads `.rpyc`, `.rpymc`, `.rpa` and `.save` files, and all of them are
`pickle` streams. Unpickling a stream with Python's own `pickle` runs whatever
the stream asks for, so a crafted file can execute code. Every unpickler in
this project is therefore restricted (`src/rpycdec/safe_pickle.py`):

- classes from our own fake `renpy` and `store` packages are allowed, and only
  those: the lookup resolves to the modules shipped in the wheel,
- builtins are limited to data types (`dict`, `list`, `str`, ...) and never
  `eval`, `exec`, `__import__` or `getattr`,
- `collections` and `collections.abc` are allowed, nothing else,
- any other class becomes an inert placeholder that keeps what it carried
  instead of running anything.

Save files go through `SaveUnpickler`, which does the same and turns unknown
classes into plain objects (`src/rpycdec/save.py`), and the RPA index reader is
stricter still, accepting primitive types only. Paths taken from an archive or
an APK are resolved under the output directory, and an entry that would escape
it is refused (`rpycdec.utils.safe_path`).

The CLI prints a warning before it touches a file. `RPYCDEC_NO_WARNING=1`
silences the message; it does not change what the unpicklers allow.

## Reporting a vulnerability

Please report privately rather than in a public issue:

- **GitHub**: the *Security* tab, *Report a vulnerability* — a private advisory,
  where the file can be attached. If that button is not there, the repository
  has not turned private reporting on; use the address below instead.
- **email**: cnfatal@gmail.com

Include the version (`pip show rpycdec`), how it was installed, the command you
ran, its output, and the file that triggered it. Attach the file to the
advisory instead of posting it publicly, and say how it was made if you can.

You will get an answer within a few days, and credit in the advisory and the
release notes unless you would rather stay anonymous.

## What counts as a security issue

In scope:

- a file that makes rpycdec execute code, write or delete files, open a network
  connection, or import anything outside the whitelist,
- a way around the whitelist in `safe_pickle.py`, including through the
  `renpy.*` / `store.*` import path,
- a crafted archive, save file or APK that writes outside the output
  directory.

Not a security issue — please [open a normal
issue](https://github.com/cnfatal/rpycdec/issues) instead:

- a crash, a traceback, or a wrong decompilation on a malformed or unsupported
  file: that is a bug, and a welcome one,
- running out of memory or time on a huge or pathological file; the tool reads
  whatever the file says it holds,
- what the file contains. Undoing the obfuscation of a game is what rpycdec is
  for; whether you may do it is a licensing question, not a security one.

## Supported versions

The latest release. Fixes land on `main` and ship in the next release; older
releases are not patched. If you are not sure a file can be trusted, run the
tool inside a container or a virtual machine.
