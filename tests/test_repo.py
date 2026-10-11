"""Tests of the pin, the planning and bumping scripts, the patch, the capability parser and the workflows' rules.

    python -I -m unittest discover -s tests
"""
import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import bump_build_json  # noqa: E402
import capabilities  # noqa: E402
import plan  # noqa: E402
import tree_hash  # noqa: E402

PIN = json.loads((ROOT / "build.json").read_text(encoding="utf-8"))


class Plan(unittest.TestCase):
    def test_tag_and_asset_follow_the_pin(self):
        p = plan.plan(PIN)
        self.assertEqual(p["tag"], "ffmpeg-n9.0.1-11-ge47273f4d9-btbn-8267213")
        self.assertEqual(p["asset"], "ffmpeg-n9.0.1-11-ge47273f4d9-win64-lgpl-shared-9.0")

    def test_revision_suffix(self):
        self.assertTrue(plan.plan(PIN, "2")["tag"].endswith("-btbn-8267213-r2"))
        with self.assertRaises(SystemExit):
            plan.plan(PIN, "2; rm -rf")

    def test_a_describe_that_does_not_match_its_commit_is_refused(self):
        bad = copy.deepcopy(PIN)
        bad["ffmpeg"]["describe"] = "n9.0.1-11-gaaaaaaaaaa"
        with self.assertRaises(SystemExit):
            plan.plan(bad)

    def test_a_short_commit_is_refused(self):
        bad = copy.deepcopy(PIN)
        bad["btbn"]["commit"] = "8267213"
        with self.assertRaises(SystemExit):
            plan.plan(bad)

    def test_the_tag_namespace_is_ffmpeg_only(self):
        self.assertRegex(plan.plan(PIN)["tag"], r"^ffmpeg-n[0-9]")


class TreeHash(unittest.TestCase):
    def test_matches_the_reference_value(self):
        # The expected value is the reference implementation's hash over the same tree (a.txt "alpha CRLF", sub/b.bin 00 01 02 03 ff, a staged.json
        # that is left out), computed on 2026-10-11.
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "sub").mkdir()
            (Path(d) / "a.txt").write_bytes(b"alpha" + bytes([13, 10]))
            (Path(d) / "sub" / "b.bin").write_bytes(bytes([0, 1, 2, 3, 255]))
            (Path(d) / "staged.json").write_text("x")
            self.assertEqual(tree_hash.tree_hash(d), ("4eb16e049ec5329ec65538660de8c478baf00c0835387be535e9a0a85393ef4e", 2))


class Bump(unittest.TestCase):
    def test_bump_moves_the_commits_and_drops_the_stale_autobuild_tag(self):
        pin = bump_build_json.bump(copy.deepcopy(PIN), "a" * 40, "b" * 40, "n9.0.2-25-g" + "b" * 10)
        self.assertEqual(pin["btbn"]["commit"], "a" * 40)
        self.assertNotIn("matches_asset_tag", pin["btbn"])
        self.assertEqual(plan.plan(pin)["ffmpeg_commit"], "b" * 40)

    def test_ffmpeg_commit_and_describe_go_together(self):
        with self.assertRaises(SystemExit):
            bump_build_json.bump(copy.deepcopy(PIN), None, "b" * 40, None)

    def test_the_committed_build_json_is_in_the_scripts_own_layout(self):
        self.assertEqual((ROOT / "build.json").read_text(encoding="utf-8"), bump_build_json.dumps(PIN))


class Patch(unittest.TestCase):
    def tree(self, d):
        t = Path(d)
        (t / "scripts.d").mkdir()
        (t / "images" / "base").mkdir(parents=True)
        (t / "makeimage.sh").write_text("#!/bin/bash\n")
        for rel in PIN["remove_scripts"]:
            (t / rel).write_text("#!/bin/bash\n")
        (t / "scripts.d" / "zz-final.sh").write_text("ffbuild_depends() {\n    echo aom\n    echo chromaprint\n    echo zvbi\n}\n")
        (t / "images" / "base" / "Dockerfile").write_text("FROM ubuntu:26.04\n\nARG X\n")
        (t / "build.sh").write_text("    git clone x ffmpeg\n    cd ffmpeg\n\n    ./configure\n")
        return t

    def apply(self, t):
        import subprocess
        return subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "apply_patches.py"), str(ROOT / "build.json"), str(t)],
                              capture_output=True, text=True)

    def test_patch_applies_and_pins(self):
        with tempfile.TemporaryDirectory() as d:
            t = self.tree(d)
            r = self.apply(t)
            self.assertEqual(r.returncode, 0, r.stderr)
            for rel in PIN["remove_scripts"]:
                self.assertFalse((t / rel).exists())
            self.assertEqual((t / "scripts.d" / "zz-final.sh").read_text(), "ffbuild_depends() {\n    echo aom\n}\n")
            self.assertIn("FROM ubuntu:26.04@sha256:", (t / "images" / "base" / "Dockerfile").read_text())
            self.assertIn("git checkout --detach " + PIN["ffmpeg"]["commit"], (t / "build.sh").read_text())

    def test_a_tree_that_is_not_the_pinned_one_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = self.tree(d)
            (t / "images" / "base" / "Dockerfile").write_text("FROM ubuntu:27.04\n")
            r = self.apply(t)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("expected 1 matching line", r.stderr)

    def test_a_script_that_still_names_a_removed_package_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = self.tree(d)
            (t / "scripts.d" / "50-other.sh").write_text("ffbuild_depends() {\n    echo zvbi\n}\n")
            r = self.apply(t)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("still named", r.stderr)


class Capabilities(unittest.TestCase):
    def test_decoders_and_hwaccels_and_protocols(self):
        dec = "Decoders:\n V..... = Video\n ------\n V....D h264                 H.264\n S..... libzvbi_teletextdec  Libzvbi\n"
        self.assertEqual(capabilities.keys("decoders", dec), ["S..... libzvbi_teletextdec", "V....D h264"])
        self.assertEqual(capabilities.keys("hwaccels", "Hardware acceleration methods:\ncuda\nd3d12va\n\n"), ["cuda", "d3d12va"])
        prot = "Supported file protocols:\nInput:\n  file\n  http\nOutput:\n  file\n"
        self.assertEqual(capabilities.keys("protocols", prot), ["input file", "input http", "output file"])

    def test_formats_keep_the_demux_mux_device_flags(self):
        out = "Formats:\n D.. = Demuxing\n ---\n D   mov  QuickTime\n  E  chromaprint  Chromaprint\n DE  mp4  MP4\n D d dshow  DirectShow\n"
        self.assertEqual(capabilities.keys("muxers", out), [".E. chromaprint", "D.. mov", "D.d dshow", "DE. mp4"])

    def test_filters(self):
        out = "Filters:\n  T.. = Timeline\n  ------\n TS aap  AA->A  Apply\n .. abench  A->A  Bench\n"
        self.assertEqual(capabilities.keys("filters", out), [".. abench A->A", "TS aap AA->A"])

    def test_a_list_with_no_entries_fails(self):
        with self.assertRaises(SystemExit):
            capabilities.keys("bsfs", "Bitstream filters:\n")


class Workflows(unittest.TestCase):
    """Rules every workflow here keeps: the lint a public repository's workflows need."""

    files = sorted((ROOT / ".github" / "workflows").glob("*.yml"))

    def test_there_are_workflows(self):
        self.assertGreaterEqual(len(self.files), 2)

    def test_every_action_is_pinned_by_commit_sha(self):
        for f in self.files:
            for line in f.read_text(encoding="utf-8").splitlines():
                m = re.match(r"\s*-?\s*uses:\s*(\S+)", line)
                if m:
                    self.assertRegex(m.group(1), r"^[\w./-]+@[0-9a-f]{40}$", f"{f.name}: {line}")

    def test_no_pull_request_target_and_no_pull_request_trigger(self):
        for f in self.files:
            text = f.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"(?m)^\s*(pull_request_target|pull_request)\s*:", f.name)

    def test_permissions_are_empty_at_the_top_and_write_is_named_per_job(self):
        for f in self.files:
            text = f.read_text(encoding="utf-8")
            self.assertRegex(text, r"(?m)^permissions: \{\}$", f.name)
            for m in re.finditer(r"(?m)^    permissions:\n((?:      .+\n)+)", text):
                block = m.group(1)
                if "write" in block:
                    job = re.findall(r"(?m)^  (\w+):$", text[: m.start()])[-1]
                    self.assertIn(job, ("release", "propose"), f"{f.name}: write permission in job '{job}'")

    def test_no_secret_other_than_the_github_token_is_used(self):
        for f in self.files:
            for m in re.finditer(r"\$\{\{\s*secrets\.(\w+)", f.read_text(encoding="utf-8")):
                self.fail(f"{f.name} reads secrets.{m.group(1)}")

    def test_the_first_push_to_main_builds_nothing(self):
        text = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
        self.assertIn('[ "$BEFORE" = "0000000000000000000000000000000000000000" ]', text)

    def test_the_upstream_check_pushes_only_a_bump_branch_and_never_releases(self):
        text = (ROOT / ".github" / "workflows" / "upstream.yml").read_text(encoding="utf-8")
        pushes = re.findall(r"(?m)^\s*git push .*$", text)
        self.assertEqual([p.strip() for p in pushes], ['git push origin "$branch"'])
        self.assertIn('branch="bump/', text)
        self.assertNotRegex(text, r"gh release|--force|git tag|git push --tags|git push origin main")

    def test_every_job_has_a_timeout(self):
        for f in self.files:
            text = f.read_text(encoding="utf-8")
            jobs = re.findall(r"(?m)^    runs-on:", text)
            self.assertGreaterEqual(len(jobs), 1, f.name)
            self.assertEqual(len(re.findall(r"(?m)^    timeout-minutes:", text)), len(jobs), f.name)

    def test_only_hosted_runners_are_used(self):
        for f in self.files:
            for m in re.finditer(r"(?m)^\s+runs-on:\s*(.+)$", f.read_text(encoding="utf-8")):
                self.assertRegex(m.group(1).strip(), r"^ubuntu-24\.04$", f.name)

    def test_only_the_release_job_holds_contents_write_in_build_yml(self):
        text = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"contents: write", text)), 1)
        self.assertLess(text.index("contents: write"), len(text))
        self.assertGreater(text.index("contents: write"), text.index("  release:"))


if __name__ == "__main__":
    unittest.main()
