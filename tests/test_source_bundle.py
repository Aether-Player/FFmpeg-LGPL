"""scripts/source_bundle.sh on fixture repositories: the corresponding-source bundle of a release.

    python -I -m unittest discover -s tests

Skipped where bash, git, xz or split is missing. The fixture is a BtbN-like checkout with one commit and one uncommitted change (the
patch), an FFmpeg-like repository with the pinned commit, a repository of this project's files, and a download cache with two stages.
"""
import json
import os
import shutil
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "source_bundle.sh"


def find_bash():
    """A bash that is not Windows' WSL launcher (the System32 bash.exe answers 'no such file' to a script of ours): Git for Windows' own."""
    found = shutil.which("bash")
    if found and "system32" not in found.lower():
        return found
    git_exe = shutil.which("git")
    if git_exe:
        for parent in Path(git_exe).resolve().parents:
            cand = parent / "bin" / "bash.exe"
            if cand.is_file():
                return str(cand)
    return None


BASH = find_bash()
TOOLS = bool(BASH) and all(shutil.which(t) for t in ("git", "xz", "split", "tar"))


def with_python3(d):
    """An environment whose `python3` is this interpreter (on Windows `python3` is the Store's shim; on the runner it is the real one)."""
    bindir = Path(d) / "pybin"
    bindir.mkdir()
    exe = sys.executable.replace(chr(92), "/")
    with open(bindir / "python3", "w", encoding="utf-8", newline="\n") as f:
        f.write("#!/bin/sh\nexec \"" + exe + "\" \"$@\"\n")
    env = dict(os.environ)
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    return env


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "core.autocrlf=false", *args],
                          check=True, capture_output=True, text=True).stdout.strip()


@unittest.skipUnless(TOOLS, "bash, git, xz, split and tar are needed")
class Bundle(unittest.TestCase):
    def test_a_bundle_holds_the_sources_the_patch_and_the_components(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            btbn = d / "btbn"
            (btbn / "scripts.d").mkdir(parents=True)
            (btbn / "scripts.d" / "50-aom.sh").write_text('SCRIPT_REPO="https://example.org/aom.git"\nSCRIPT_COMMIT="abc123"\n')
            (btbn / "scripts.d" / "50-chromaprint.sh").write_text("x\n")
            (btbn / "build.sh").write_text("cd ffmpeg\n")
            git(btbn, "init", "-q")
            git(btbn, "add", ".")
            git(btbn, "commit", "-q", "-m", "btbn")
            bcommit = git(btbn, "rev-parse", "HEAD")
            (btbn / "scripts.d" / "50-chromaprint.sh").unlink()          # the patch: a removal and an edit
            (btbn / "build.sh").write_text("cd ffmpeg\ngit checkout --detach X\n")
            (btbn / "Dockerfile").write_text('ENV SELF="scripts.d/50-aom.sh" STAGENAME="aom"\n')
            dl = btbn / ".cache" / "downloads"
            dl.mkdir(parents=True)
            (dl / "aom_0123.tar.xz").write_bytes(b"aom source")
            ff = d / "ffmpeg"
            ff.mkdir()
            (ff / "configure").write_text("#!/bin/sh\n")
            git(ff, "init", "-q")
            git(ff, "add", ".")
            git(ff, "commit", "-q", "-m", "ff")
            fcommit = git(ff, "rev-parse", "HEAD")
            repo = d / "lgpl"
            (repo / ".github" / "workflows").mkdir(parents=True)
            (repo / "scripts").mkdir()
            for n in ("LICENSE", "README.md"):
                (repo / n).write_text(n)
            (repo / ".github" / "workflows" / "build.yml").write_text("name: x\n")
            pin = repo / "build.json"
            pin.write_text(json.dumps({"btbn": {"commit": bcommit}, "ffmpeg": {"commit": fcommit, "describe": "n9.0.1-1-gabcdef1"}}))
            out = d / "dist"
            # a relative output folder, as the workflow passes it
            r = subprocess.run([BASH, str(SCRIPT), "btbn", "ffmpeg", "lgpl", "lgpl/build.json", "dist"], cwd=d, env=with_python3(d), capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            names = sorted(p.name for p in out.iterdir())
            self.assertEqual(names, ["build.patch", "components.txt", "source-btbn-scripts.tar.xz", "source-build-files.tar.xz",
                                     "source-components.tar.part-00", "source-ffmpeg.tar.xz"])
            patch = (out / "build.patch").read_text()
            self.assertIn("deleted file mode", patch)
            self.assertIn("git checkout --detach X", patch)
            comp = (out / "components.txt").read_text()
            self.assertIn("== aom", comp)
            self.assertIn('SCRIPT_COMMIT="abc123"', comp)
            self.assertIn("source tarball: aom_0123.tar.xz", comp)
            listing = subprocess.run(["tar", "-tf", str(out / "source-components.tar.part-00")], capture_output=True, text=True).stdout
            self.assertIn("aom_0123.tar.xz", listing)
            self.assertIn("ffmpeg-n9.0.1-1-gabcdef1/configure", subprocess.run(["tar", "-tJf", str(out / "source-ffmpeg.tar.xz")], capture_output=True, text=True).stdout)

    def test_a_tree_with_no_patch_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            btbn = d / "btbn"
            btbn.mkdir()
            (btbn / "a").write_text("a")
            git(btbn, "init", "-q")
            git(btbn, "add", ".")
            git(btbn, "commit", "-q", "-m", "x")
            (btbn / "Dockerfile").write_text("")
            ff = d / "ff"
            ff.mkdir()
            (ff / "a").write_text("a")
            git(ff, "init", "-q")
            git(ff, "add", ".")
            git(ff, "commit", "-q", "-m", "x")
            repo = d / "lgpl"
            repo.mkdir()
            (repo / "LICENSE").write_text("l")
            (repo / "README.md").write_text("r")
            (repo / "build.json").write_text(json.dumps({"btbn": {"commit": git(btbn, "rev-parse", "HEAD")},
                                                         "ffmpeg": {"commit": git(ff, "rev-parse", "HEAD"), "describe": "n1-1-gabcdef1"}}))
            r = subprocess.run([BASH, str(SCRIPT), "btbn", "ff", "lgpl", "lgpl/build.json", "dist"], cwd=d, env=with_python3(d), capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("no patch applied", r.stderr)


if __name__ == "__main__":
    unittest.main()
