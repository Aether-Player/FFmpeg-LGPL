#!/usr/bin/env python3
"""Write FFmpeg's capability lists as one sorted text file (capabilities.txt, ffmpeg-capabilities/1).

    capabilities.py --ffmpeg "<command that runs ffmpeg>" --out capabilities.txt

The command is split like a shell line, so "wine /pkg/bin/ffmpeg.exe" and "C:/x/ffmpeg.exe" both work.
It runs `ffmpeg -hide_banner <list>` for -decoders -encoders -demuxers -muxers -protocols -filters -bsfs
-hwaccels. Each list becomes a [section] of sorted lines; descriptions are dropped (they are prose and
change between versions), flags and names are kept. Two files from two builds are compared with diff, so a
change in what a build can do shows line by line.
"""
import argparse
import re
import shlex
import subprocess
import sys

LISTS = ["decoders", "encoders", "demuxers", "muxers", "protocols", "filters", "bsfs", "hwaccels"]


def after_separator(lines, pattern):
    for i, line in enumerate(lines):
        if re.fullmatch(pattern, line.strip()):
            return lines[i + 1:]
    raise SystemExit("capabilities: the list has no separator line; ffmpeg's output format changed")


def keys(name, text):
    lines = text.replace("\r\n", "\n").split("\n")
    out = set()
    if name in ("decoders", "encoders"):
        for line in after_separator(lines, r"-+"):
            m = re.match(r"\s*([VASDT.][.F][.S][.X][.B][.D])\s+(\S+)", line)
            if m:
                out.add(f"{m.group(1)} {m.group(2)}")
    elif name in ("demuxers", "muxers"):
        for line in after_separator(lines, r"-+"):
            m = re.match(r" ([D ])([E ])([d ]) (\S+)", line)
            if m:
                flags = "".join(c if c != " " else "." for c in m.group(1, 2, 3))
                out.add(f"{flags} {m.group(4)}")
    elif name == "filters":
        for line in after_separator(lines, r"-+"):
            m = re.match(r" ([T.][S.][C.]?)\s+(\S+)\s+(\S+)", line)
            if m:
                out.add(f"{m.group(1)} {m.group(2)} {m.group(3)}")
    elif name == "protocols":
        side = None
        for line in lines:
            if line.strip() in ("Input:", "Output:"):
                side = line.strip()[:-1].lower()
            elif side and line.strip():
                out.add(f"{side} {line.strip()}")
    else:  # bsfs, hwaccels: a header line, then one name per line
        header = "Bitstream filters:" if name == "bsfs" else "Hardware acceleration methods:"
        seen = False
        for line in lines:
            if line.strip() == header:
                seen = True
            elif seen and line.strip():
                out.add(line.strip())
    if not out:
        raise SystemExit(f"capabilities: no entries parsed for -{name}")
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ffmpeg", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cmd = shlex.split(a.ffmpeg, posix=("\\" not in a.ffmpeg))
    version = subprocess.run(cmd + ["-hide_banner", "-version"], capture_output=True, check=True).stdout.decode("utf-8", "replace").split("\n")[0].strip()
    lines = ["# ffmpeg-capabilities/1: the sorted lists of `ffmpeg -hide_banner -<list>`, descriptions dropped", f"# {version}"]
    for name in LISTS:
        r = subprocess.run(cmd + ["-hide_banner", f"-{name}"], capture_output=True)
        if r.returncode != 0:
            sys.exit(f"capabilities: ffmpeg -{name} exited {r.returncode}: {r.stderr.decode('utf-8', 'replace')[-400:]}")
        lines.append(f"[{name}]")
        lines += keys(name, r.stdout.decode("utf-8", "replace"))
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"capabilities: wrote {a.out} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
