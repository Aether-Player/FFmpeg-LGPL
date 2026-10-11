#!/bin/bash
# The corresponding source of one release (the LGPL source offer): FFmpeg at the built commit, BtbN's scripts at the built
# commit with the patch this repository applies, this repository's build files, and the source of every component the build
# compiled in, as BtbN's download.sh fetched it (a tarball of each pinned git clone or archive).
#
#   source_bundle.sh <btbn-checkout (patched, after the build)> <ffmpeg-clone> <this-repo-checkout> <build.json> <out-dir>
#
# Writes into <out-dir>: source-ffmpeg.tar.xz, source-btbn-scripts.tar.xz, build.patch, source-build-files.tar.xz,
# components.txt, source-components.tar.part-NN (the components' tarballs in one tar, cut into parts under GitHub's 2 GiB
# asset limit: cat the parts, then tar -xf).
#
# Not captured: what a component's own build downloads while it compiles (Rust crates for rav1e and similar, language package
# managers). Those come from the registries the component's lock file names; the lock files are inside the tarballs.
set -euo pipefail
BTBN="$1"; FFSRC="$2"; REPO="$3"; PIN="$4"
mkdir -p "$5"
OUT="$(cd "$5" && pwd)"   # absolute: some commands below run after a cd
FFCOMMIT="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["ffmpeg"]["commit"])' "$PIN")"
FFDESC="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["ffmpeg"]["describe"])' "$PIN")"
BCOMMIT="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["btbn"]["commit"])' "$PIN")"

git -C "$FFSRC" archive --format=tar --prefix="ffmpeg-$FFDESC/" "$FFCOMMIT" | xz -T0 -9 > "$OUT/source-ffmpeg.tar.xz"
git -C "$BTBN" archive --format=tar --prefix="FFmpeg-Builds-${BCOMMIT:0:7}/" "$BCOMMIT" | xz -T0 -9 > "$OUT/source-btbn-scripts.tar.xz"
git -C "$BTBN" diff --no-color > "$OUT/build.patch"
test -s "$OUT/build.patch" || { echo "source_bundle: the BtbN tree has no patch applied" >&2; exit 1; }
(cd "$REPO" && tar -cJf "$OUT/source-build-files.tar.xz" LICENSE README.md build.json scripts .github/workflows)

# The stages the generated Dockerfile builds (generate.sh writes one ENV line per enabled stage).
DL="$BTBN/.cache/downloads"
: > "$OUT/components.txt"
STAGES="$(grep -o 'STAGENAME="[^"]*"' "$BTBN/Dockerfile" | sed 's/STAGENAME="\(.*\)"/\1/' | sort -u)"
LIST="$(mktemp)"
for s in $STAGES; do
    script="$(ls "$BTBN"/scripts.d/??-"$s".sh "$BTBN"/scripts.d/??-"$s"/*.sh 2>/dev/null | head -n 1 || true)"
    files="$(cd "$DL" && ls "${s}"_*.tar.xz 2>/dev/null || true)"
    {
        echo "== $s"
        [ -n "$script" ] && grep -H -E '^SCRIPT_(REPO|COMMIT|REV|BRANCH|TAGFILTER|SUBDIR)[0-9A-Z_]*=' "$script" | sed "s|^$BTBN/||" || true
        if [ -n "$files" ]; then echo "source tarball: $files"; else echo "source tarball: none (the stage downloads nothing, or builds from the toolchain image)"; fi
    } >> "$OUT/components.txt"
    for f in $files; do echo "$f" >> "$LIST"; done
done
test -s "$LIST" || { echo "source_bundle: no component tarballs found in $DL" >&2; exit 1; }
(cd "$DL" && tar -cf - -T "$LIST") | split -b 1900M -d -a 2 - "$OUT/source-components.tar.part-"
rm -f "$LIST"
ls -la "$OUT"
