"""Fixture tests for scripts/verify.py: python -I -m unittest discover -s tests"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import verify  # noqa: E402

GOOD = "--prefix=/ffbuild/prefix --enable-version3 --disable-debug --enable-shared --disable-static --enable-libdav1d"


def package(root, configure=GOOD, extra=b"", licence=b"LGPL version 3 or later"):
    bindir = Path(root) / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    for name in ("avutil-60.dll", "avcodec-62.dll"):
        (bindir / name).write_bytes(b"junk libavutil license: " + licence + b"\0" + configure.encode() + b"\0" + extra)
    return root


class Verify(unittest.TestCase):
    def run_case(self, **kw):
        with tempfile.TemporaryDirectory() as d:
            return verify.verify(package(d, **kw))

    def test_clean_package_passes(self):
        problems, conf = self.run_case()
        self.assertEqual(problems, [])
        self.assertEqual(conf, GOOD)

    def test_each_forbidden_flag_is_refused(self):
        for flag in verify.FORBIDDEN_FLAGS:
            with self.subTest(flag=flag):
                problems, _ = self.run_case(configure=GOOD + " " + flag)
                self.assertTrue(any(flag in p for p in problems), problems)

    def test_disable_of_a_forbidden_flag_is_not_a_problem(self):
        problems, _ = self.run_case(configure=GOOD + " --disable-gpl --disable-libzvbi")
        self.assertEqual(problems, [])

    def test_fftw_string_anywhere_is_refused(self):
        problems, _ = self.run_case(extra=b"fftw-3.3.11 fftw_plan_dft")
        self.assertTrue(any("fftw" in p for p in problems), problems)

    def test_chromaprint_and_zvbi_strings_are_refused(self):
        for word in (b"Chromaprint", b"libzvbi"):
            with self.subTest(word=word):
                problems, _ = self.run_case(extra=word)
                self.assertTrue(problems)

    def test_gpl_licence_string_is_refused(self):
        problems, _ = self.run_case(licence=b"GPL version 3 or later")
        self.assertTrue(any("licensed" in p for p in problems), problems)

    def test_missing_configure_line_and_missing_dlls(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bin").mkdir()
            (Path(d) / "bin" / "avutil-60.dll").write_bytes(b"nothing")
            problems, _ = verify.verify(d)
            self.assertTrue(any("no configure line" in p for p in problems))
        with tempfile.TemporaryDirectory() as d:
            problems, _ = verify.verify(d)
            self.assertTrue(any("no FFmpeg DLLs" in p for p in problems))

    def test_two_different_configure_lines_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            package(d)
            (Path(d) / "bin" / "avcodec-62.dll").write_bytes(b"x\0" + (GOOD + " --enable-libopus").encode())
            problems, _ = verify.verify(d)
            self.assertTrue(any("different configure lines" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
