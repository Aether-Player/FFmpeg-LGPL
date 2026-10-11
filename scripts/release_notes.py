#!/usr/bin/env python3
"""The body of a release: what it is, what it was built from, how it was checked, how to verify and rebuild it.

    release_notes.py <build.json> <dist-folder> <tag> <asset>
"""
import json
import sys
from pathlib import Path


def main():
    pin = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    dist, tag, asset = Path(sys.argv[2]), sys.argv[3], sys.argv[4]
    configure = (dist / "configure.txt").read_text(encoding="utf-8").strip()
    sums = (dist / "SHA256SUMS").read_text(encoding="utf-8").strip()
    removed = ", ".join(Path(p).stem.split("-", 1)[1] for p in pin["remove_scripts"])
    print(f"""An LGPL-3.0-or-later build of FFmpeg: BtbN/FFmpeg-Builds' `{pin['target']}-{pin['variant']}` scripts with {removed} removed (Chromaprint and FFTW, which brings GPL code into the DLLs, and libzvbi).

| | |
|---|---|
| FFmpeg | `{pin['ffmpeg']['describe']}`, commit `{pin['ffmpeg']['commit']}` of `{pin['ffmpeg']['branch']}` |
| BtbN/FFmpeg-Builds | commit `{pin['btbn']['commit']}` |
| Package | `{asset}.zip` |

### Checked before this release was published
No `--enable-chromaprint`, `--enable-libzvbi`, `--enable-gpl` or `--enable-nonfree` in the configure line of any FFmpeg DLL; no `fftw`, `chromaprint` or `zvbi` string in any DLL or EXE; every DLL's licence string is LGPL. `capabilities.txt` lists what the build can decode, encode, demux, mux, filter and hardware-accelerate.

### Configure line
```
{configure}
```

### SHA-256
```
{sums}
```

### Source (the LGPL source offer)
`source-ffmpeg.tar.xz` is FFmpeg at the commit above. `source-btbn-scripts.tar.xz` is BtbN's build scripts at their commit, `build.patch` is the change this repository makes to them, and `source-build-files.tar.xz` is this repository's own build files. `source-components.tar.part-NN` is the source of every library compiled in, as the build fetched it (`cat source-components.tar.part-* | tar -x`); `components.txt` names each library's pinned repository and commit. Rebuild: check out this repository at tag `{tag}` and run `.github/workflows/build.yml`'s steps (see README.md). A component that downloads packages while it compiles (Rust crates) takes them from the registry its lock file names; the lock files are in the tarballs.
""")


if __name__ == "__main__":
    main()
