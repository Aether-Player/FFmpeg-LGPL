#!/usr/bin/env python3
"""Check an unpacked FFmpeg package before anything is published.

    verify.py <package-folder> [--configure-out configure.txt]

The package folder is the zip's single top folder (bin/, lib/, include/ ...). Fails (exit 1, every
problem listed) unless:
  * every FFmpeg DLL (av*, sw*, postproc*) carries a configure line, and they are all the same line;
  * that line has none of --enable-chromaprint, --enable-libzvbi, --enable-gpl, --enable-nonfree;
  * no DLL or EXE in bin/ contains "fftw", "chromaprint" or "zvbi" (any case) - the three components
    this build exists to leave out (FFTW is GPL-2.0-or-later and was linked statically through
    Chromaprint; libzvbi has GPL-2.0-only files);
  * every "lib<name> license:" string in the DLLs names an LGPL licence.
The configure line is written to --configure-out for the release notes.
"""
import argparse
import re
import sys
from pathlib import Path

FORBIDDEN_FLAGS = ["--enable-chromaprint", "--enable-libzvbi", "--enable-gpl", "--enable-nonfree"]
FORBIDDEN_WORDS = [b"fftw", b"chromaprint", b"zvbi"]
FFMPEG_DLL = re.compile(r"^(av|sw|postproc)[a-z]*-\d+\.dll$")


def configure_line(data):
    m = re.search(rb"--prefix=[ -~]+", data)
    return m.group(0).decode("ascii") if m else None


def verify(folder):
    """Return (problems, configure_line)."""
    problems = []
    bindir = Path(folder) / "bin"
    dlls = sorted(p for p in bindir.glob("*.dll") if FFMPEG_DLL.match(p.name))
    if not dlls:
        return [f"{bindir} holds no FFmpeg DLLs (av*/sw*-N.dll)"], None
    lines = {}
    for p in dlls:
        data = p.read_bytes()
        line = configure_line(data)
        if line is None:
            problems.append(f"{p.name} carries no configure line")
        else:
            lines[p.name] = line
        for m in re.finditer(rb"lib[a-z]+ license: ([ -~]{3,80})", data):
            lic = m.group(1).decode("ascii")
            if not lic.startswith("LGPL version"):
                problems.append(f"{p.name} is licensed '{lic}'")
    if len(set(lines.values())) > 1:
        problems.append("the FFmpeg DLLs carry different configure lines: " + ", ".join(sorted(lines)))
    conf = next(iter(lines.values()), None)
    if conf:
        for flag in FORBIDDEN_FLAGS:
            if re.search(r"(?<![A-Za-z0-9-])" + re.escape(flag) + r"(?![A-Za-z0-9_-])", conf):
                problems.append(f"the configure line has {flag}")
    for p in sorted(list(bindir.glob("*.dll")) + list(bindir.glob("*.exe"))):
        data = p.read_bytes()
        m = re.search(rb"--prefix=[ -~]+", data)
        if m:   # the configure line is judged by its flags above; a --disable-libzvbi in it is not a library
            data = data[:m.start()] + data[m.end():]
        low = data.lower()
        for w in FORBIDDEN_WORDS:
            n = low.count(w)
            if n:
                problems.append(f"{p.name} contains '{w.decode()}' ({n} times)")
    return problems, conf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--configure-out")
    a = ap.parse_args()
    problems, conf = verify(a.folder)
    if conf and a.configure_out:
        Path(a.configure_out).write_text(conf + "\n", encoding="utf-8", newline="\n")
    if problems:
        print("verify: REFUSED, nothing may be published:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        sys.exit(1)
    print(f"verify: ok - {len(conf.split())} configure words; no forbidden flag, no FFTW/Chromaprint/zvbi string")


if __name__ == "__main__":
    main()
