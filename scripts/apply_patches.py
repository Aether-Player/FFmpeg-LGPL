#!/usr/bin/env python3
"""Apply this repository's changes to a checkout of BtbN/FFmpeg-Builds, as build.json describes them.

    apply_patches.py <build.json> <btbn-checkout>

Every edit asserts what it expects to find (an exact count), so a BtbN tree that is not the pinned
one fails here with a message instead of producing a different build. Nothing is fetched.
"""
import json
import re
import sys
from pathlib import Path


def fail(msg):
    print(f"apply_patches: {msg}", file=sys.stderr)
    sys.exit(1)


def edit_lines(path, drop=None, after=None, insert=None, replace=None, count=1):
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    out, hits = [], 0
    for line in lines:
        if drop is not None and re.fullmatch(drop, line):
            hits += 1
            continue
        if replace is not None and re.fullmatch(replace[0], line):
            hits += 1
            out.append(replace[1])
            continue
        out.append(line)
        if after is not None and re.fullmatch(after, line):
            hits += 1
            out.append(insert)
    if hits != count:
        fail(f"{path}: expected {count} matching line(s), found {hits}")
    path.write_text("\n".join(out), encoding="utf-8", newline="\n")


def main():
    if len(sys.argv) != 3:
        fail("usage: apply_patches.py <build.json> <btbn-checkout>")
    pin = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    tree = Path(sys.argv[2])
    if not (tree / "makeimage.sh").is_file() or not (tree / "scripts.d").is_dir():
        fail(f"{tree} is not a BtbN/FFmpeg-Builds checkout")

    removed = list(pin["remove_scripts"])
    for rel in removed:
        p = tree / rel
        if not p.is_file():
            fail(f"{rel} is not in the BtbN tree: the pin and the tree disagree")
        p.unlink()
        print(f"removed {rel}")

    names = [Path(r).stem.split("-", 1)[1] for r in removed]   # 50-chromaprint -> chromaprint
    final = tree / "scripts.d" / "zz-final.sh"
    for name in names:
        # zz-final.sh lists every package in ffbuild_depends; fftw3 is not among them (only chromaprint pulled it in).
        in_final = re.search(rf"^    echo {re.escape(name)}$", final.read_text(encoding="utf-8"), re.M)
        if in_final:
            edit_lines(final, drop=rf"    echo {re.escape(name)}")
            print(f"zz-final.sh: dropped 'echo {name}'")

    edit_lines(tree / "images" / "base" / "Dockerfile",
               replace=(re.escape(pin["images"]["ubuntu"]["ref"].join(["FROM ", ""])),
                        f"FROM {pin['images']['ubuntu']['ref']}@{pin['images']['ubuntu']['digest']}"))
    print("images/base/Dockerfile: Ubuntu pinned by digest")

    edit_lines(tree / "build.sh", after=r"    cd ffmpeg",
               insert=f"    git checkout --detach {pin['ffmpeg']['commit']}")
    print(f"build.sh: FFmpeg checked out at {pin['ffmpeg']['commit']}")

    # Nothing left may name a removed package, apart from rubberband's own (lgpl-disabled) dependency on fftw3.
    left = []
    for p in list(tree.glob("scripts.d/**/*.sh")) + list(tree.glob("variants/*.sh")) + list(tree.glob("addins/*.sh")) + list(tree.glob("util/*.sh")):
        for n, line in enumerate(p.read_text(encoding="utf-8").split("\n"), 1):
            if re.search(r"chromaprint|zvbi", line, re.I) or (re.search(r"fftw", line, re.I) and p.name != "50-rubberband.sh"):
                left.append(f"{p.relative_to(tree)}:{n}: {line.strip()}")
    if left:
        fail("a removed package is still named:\n  " + "\n  ".join(left))
    print("no script still names Chromaprint, FFTW or libzvbi (50-rubberband.sh keeps its fftw3 dependency; it is disabled for every lgpl variant)")


if __name__ == "__main__":
    main()
