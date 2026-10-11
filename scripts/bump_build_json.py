#!/usr/bin/env python3
"""Move build.json to new upstream commits. Used by the weekly upstream check; also normalises the file's layout.

    bump_build_json.py build.json [--btbn-commit C] [--ffmpeg-commit C --ffmpeg-describe D]
"""
import argparse
import json
import re
import sys


def bump(pin, btbn_commit=None, ffmpeg_commit=None, ffmpeg_describe=None):
    if btbn_commit:
        if not re.fullmatch(r"[0-9a-f]{40}", btbn_commit):
            raise SystemExit("bump: --btbn-commit is a full 40-hex commit")
        pin["btbn"]["commit"] = btbn_commit
        pin["btbn"].pop("matches_asset_tag", None)   # it named the BtbN autobuild the old commit matched
    if ffmpeg_commit or ffmpeg_describe:
        if not (ffmpeg_commit and ffmpeg_describe):
            raise SystemExit("bump: --ffmpeg-commit and --ffmpeg-describe go together")
        if not re.fullmatch(r"[0-9a-f]{40}", ffmpeg_commit):
            raise SystemExit("bump: --ffmpeg-commit is a full 40-hex commit")
        pin["ffmpeg"]["commit"] = ffmpeg_commit
        pin["ffmpeg"]["describe"] = ffmpeg_describe
    return pin


def dumps(pin):
    return json.dumps(pin, indent=2, ensure_ascii=False) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("build_json")
    ap.add_argument("--btbn-commit")
    ap.add_argument("--ffmpeg-commit")
    ap.add_argument("--ffmpeg-describe")
    a = ap.parse_args()
    with open(a.build_json, encoding="utf-8") as f:
        pin = json.load(f)
    pin = bump(pin, a.btbn_commit, a.ffmpeg_commit, a.ffmpeg_describe)
    with open(a.build_json, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(pin))


if __name__ == "__main__":
    sys.exit(main())
