#!/usr/bin/env python3
"""SHA-256 of a folder's contents, in the tree-hash format the release's tree.sha256 uses.

    tree_hash.py <folder>      prints the hash and the file count

The hash is over the sorted lines "relative/path NUL sha256(file) LF" of every file under the folder (staged.json at its root
left out), paths '/'-separated and sorted ordinally. The release carries it as tree.sha256, so a
consumer can pin the unpacked tree as well as the zip. For the package it is computed over the zip's single top folder.
"""
import hashlib
import sys
from pathlib import Path


def tree_hash(folder):
    root = Path(folder)
    entries = {}
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            if rel == "staged.json":
                continue
            entries[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    text = "".join(f"{k}\0{entries[k]}\n" for k in sorted(entries))
    return hashlib.sha256(text.encode("utf-8")).hexdigest(), len(entries)


if __name__ == "__main__":
    digest, count = tree_hash(sys.argv[1])
    print(f"{digest}  {count} files")
