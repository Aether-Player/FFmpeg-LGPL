#!/usr/bin/env python3
"""Decide what a workflow run builds and what it is called. Writes key=value lines to $GITHUB_OUTPUT.

    plan.py <build.json> [--revision R] [--exists true|false]

tag      ffmpeg-<ffmpeg describe>-btbn-<7 hex of the BtbN commit>[-r<R>]
         (the namespace is ours alone: nothing else in this repository matches "ffmpeg-*")
asset    ffmpeg-<describe>-<target>-<variant>-<addins joined by '-'>   (the zip BtbN's build.sh names it, without .zip)
"""
import argparse
import json
import os
import re
import sys


def plan(pin, revision=""):
    describe = pin["ffmpeg"]["describe"]
    short = pin["btbn"]["commit"][:7]
    if not re.fullmatch(r"[0-9a-f]{40}", pin["btbn"]["commit"]) or not re.fullmatch(r"[0-9a-f]{40}", pin["ffmpeg"]["commit"]):
        raise SystemExit("plan: btbn.commit and ffmpeg.commit must be full 40-hex commits")
    if not re.fullmatch(r"n[0-9][0-9A-Za-z.\-]*-g[0-9a-f]{7,}", describe):
        raise SystemExit(f"plan: ffmpeg.describe '{describe}' is not a `git describe` of a release tag")
    if not pin["ffmpeg"]["commit"].startswith(describe.rsplit("-g", 1)[1]):
        raise SystemExit("plan: ffmpeg.describe does not end in the ffmpeg.commit's hash")
    if revision and not re.fullmatch(r"[0-9]{1,3}", revision):
        raise SystemExit("plan: revision is a small number")
    tag = f"ffmpeg-{describe}-btbn-{short}" + (f"-r{revision}" if revision else "")
    asset = "-".join(["ffmpeg", describe, pin["target"], pin["variant"]] + list(pin["addins"]))
    return {"tag": tag, "asset": asset, "btbn_commit": pin["btbn"]["commit"], "ffmpeg_commit": pin["ffmpeg"]["commit"],
            "ffmpeg_describe": describe}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("build_json")
    ap.add_argument("--revision", default="")
    a = ap.parse_args()
    with open(a.build_json, encoding="utf-8") as f:
        out = plan(json.load(f), a.revision)
    lines = [f"{k}={v}" for k, v in out.items()]
    print("\n".join(lines))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
