# FFmpeg-LGPL

An LGPL FFmpeg for Windows (win64, shared), built on GitHub-hosted runners from
[BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds)' scripts at a pinned commit, **minus Chromaprint, FFTW and libzvbi**.

Why: BtbN's `win64-lgpl-shared` build statically links Chromaprint, which links FFTW (GPL-2.0-or-later), and libzvbi (some
files GPL-2.0-only). FFmpeg is LGPL only if nothing GPL is compiled in. Chromaprint is an audio-fingerprint muxer and libzvbi
is DVB teletext; this repository builds the same FFmpeg without them and checks, before
every release, that none of the three is in the result.

## What a release contains

Tag `ffmpeg-<FFmpeg describe>-btbn-<BtbN short commit>` (for example `ffmpeg-n9.0.1-11-ge47273f4d9-btbn-8267213`; a rebuild of the
same pin adds `-r2`). Assets:

| File | What |
|---|---|
| `ffmpeg-<describe>-win64-lgpl-shared-9.0.zip` | the package: `bin/` (DLLs and tools), `lib/`, `include/`, `LICENSE.txt` |
| `<zip>.sha256`, `SHA256SUMS` | SHA-256 of the zip and of every asset |
| `tree.sha256` | a SHA-256 over the package's files (`scripts/tree_hash.py`) |
| `configure.txt` | the configure line compiled into the DLLs |
| `capabilities.txt` | the sorted lists of `ffmpeg -decoders -encoders -demuxers -muxers -protocols -filters -bsfs -hwaccels` (run under Wine in the build image) |
| `build.json` | the pin the release was built from |
| `source-ffmpeg.tar.xz` | FFmpeg's source at the built commit |
| `source-btbn-scripts.tar.xz`, `build.patch` | BtbN's scripts at the built commit, and the change this repository makes to them |
| `source-build-files.tar.xz` | this repository's build files at the release |
| `source-components.tar.part-NN`, `components.txt` | the source of every library compiled in, as the build fetched it (`cat source-components.tar.part-* \| tar -x`), and the pinned repository and commit of each |

**The source offer.** Each release carries the corresponding source of everything in its zip: the FFmpeg source, the build scripts
and patch, and the source of each library the build links. The release notes say how to rebuild. Not captured: what a library's own
build downloads while it compiles (Rust crates); the lock files that name them are inside the component tarballs.

## What the build checks before it publishes

`scripts/verify.py`: every FFmpeg DLL has a configure line and they are all the same; that line has none of `--enable-chromaprint`,
`--enable-libzvbi`, `--enable-gpl`, `--enable-nonfree`; no DLL or EXE contains `fftw`, `chromaprint` or `zvbi`; every `lib... license:`
string is LGPL. If any check fails nothing is published.

## How it runs

- `build.json` is the one pin: the BtbN commit, the FFmpeg commit, target and variant, the scripts removed, the edits made to BtbN's files,
  and the Ubuntu image digest the toolchain is built from. Everything else is derived.
- `.github/workflows/build.yml` runs on a push to `main` that changes `build.json`, or on a manual dispatch. It checks BtbN out at the pin,
  applies `scripts/apply_patches.py` (removes the three scripts, drops them from BtbN's entry script, pins the Ubuntu image by digest,
  checks FFmpeg out at the pinned commit), builds the toolchain images and the package with BtbN's own `makeimage.sh` and `build.sh`,
  verifies, assembles the files, and a second job with `contents: write` (the only one) creates the release. A dispatch from a branch other
  than `main` is a dry run: it builds and verifies and publishes nothing. The very first push to `main` (this repository's first commit)
  builds nothing: the first release is a deliberate dispatch of *Build FFmpeg* on `main`. A tag that already has a release is not built
  again; dispatch with `revision` set to `2` (and so on) to rebuild the same pin as `<tag>-r2`.
- `.github/workflows/upstream.yml` runs weekly (and on dispatch). It compares BtbN's default branch and FFmpeg's `release/9.0` with the pin.
  If either moved it opens a pull request that bumps `build.json`; it builds nothing, publishes nothing and never pushes to `main`. A dry
  run on the pull request's branch checks the bump; merging it publishes the release.
- No secret is used. `pull_request_target` is never used and no `pull_request` trigger exists, so a pull request from a fork builds nothing.
  Every action is pinned by commit SHA.

## Images

BtbN's own toolchain images (`ghcr.io/btbn/ffmpeg-builds/...`) are rebuilt daily under a moving `:latest` tag and their cleanup deletes
untagged older versions, so a digest of theirs stops resolving within days. The toolchain is therefore built from scratch in the job from
BtbN's Dockerfiles at the pinned commit, `FROM` the Ubuntu index digest in `build.json`. The apt, rustup and crosstool-ng inputs of those
Dockerfiles are not pinned (BtbN's are not either): a release is the same scripts and sources, not the same bytes. The zip's SHA-256 is the
pin the consumer uses.

## Settings this repository needs

Set by the owner, because a workflow cannot set them:

- **Actions > General > Fork pull request workflows**: require approval for all outside collaborators. (No workflow here has a
  `pull_request` trigger, so a fork's pull request runs nothing anyway; the setting keeps it so if one is added.)
- **Actions > General > Workflow permissions**: read repository contents by default, and tick *Allow GitHub Actions to create and approve
  pull requests* (`upstream.yml` opens the bump pull request with the repository's own token).
- **A branch ruleset on `main`**: require a pull request, block force pushes and deletion, and require the *Tests* check if one is added.
  The release job creates the tag with the repository's token; a tag ruleset on `ffmpeg-*` that allows only that job (or the owner) to create
  them keeps the namespace ours.

## Tests

`python -I -m unittest discover -s tests` (the build job runs it): the verification against fixture DLLs, the pin, planning, bumping, the patch
against a fixture tree, the capability parser, and the rules the workflows keep (SHA-pinned actions, no `pull_request_target`, empty top-level
permissions, `contents: write` only on the release and propose jobs).

## Licence

MIT, as BtbN's scripts are (`LICENSE`): the scripts, patch and workflows here are under the same licence. The FFmpeg in a release is
LGPL-3.0-or-later (`--enable-version3`), with the licences of the libraries it links in `LICENSE.txt` and in their source tarballs.
