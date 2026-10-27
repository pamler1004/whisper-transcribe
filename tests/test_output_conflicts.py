import contextlib
import importlib.util
import io
import builtins
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "transcribe.py"
SPEC = importlib.util.spec_from_file_location("transcribe_script", SCRIPT)
TRANSCRIBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRANSCRIBE)


class OutputConflictTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.input = self.directory / "talk.wav"
        self.input.write_bytes(b"synthetic audio placeholder; never decoded")
        self.old_module = sys.modules.get("mlx_whisper")
        sys.modules["mlx_whisper"] = types.SimpleNamespace(transcribe=lambda *a, **k: {
            "segments": [{"text": "synthetic transcript", "start": 0, "end": 1}]
        })

    def tearDown(self):
        if self.old_module is None:
            sys.modules.pop("mlx_whisper", None)
        else:
            sys.modules["mlx_whisper"] = self.old_module
        self.temp.cleanup()

    def run_main(self, *args):
        old_argv = sys.argv
        sys.argv = [str(SCRIPT), str(self.input), *args]
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                try:
                    TRANSCRIBE.main()
                    return 0, stderr.getvalue()
                except SystemExit as exc:
                    return exc.code, stderr.getvalue()
        finally:
            sys.argv = old_argv

    def test_md_and_srt_are_paired_and_existing_files_are_preserved(self):
        (self.directory / "talk.md").write_text("old md", encoding="utf-8")
        (self.directory / "talk.srt").write_text("old srt", encoding="utf-8")
        (self.directory / "talk-2.srt").write_text("old second srt", encoding="utf-8")
        self.run_main("--format", "all")
        self.assertEqual((self.directory / "talk.md").read_text(encoding="utf-8"), "old md")
        self.assertEqual((self.directory / "talk.srt").read_text(encoding="utf-8"), "old srt")
        self.assertEqual((self.directory / "talk-2.srt").read_text(encoding="utf-8"), "old second srt")
        self.assertEqual((self.directory / "talk-3.md").read_text(encoding="utf-8"), "synthetic transcript\n")
        self.assertIn("synthetic transcript", (self.directory / "talk-3.srt").read_text(encoding="utf-8"))

    def test_srt_only_conflict_writes_only_srt(self):
        (self.directory / "talk.srt").write_text("old srt", encoding="utf-8")
        self.run_main("--format", "srt")
        self.assertEqual((self.directory / "talk.srt").read_text(encoding="utf-8"), "old srt")
        self.assertTrue((self.directory / "talk-2.srt").exists())
        self.assertFalse((self.directory / "talk-2.md").exists())

    def test_second_file_race_retains_partial_output_and_reports_conflict(self):
        (self.directory / "talk.md").write_text("old md", encoding="utf-8")
        original_open = Path.open

        def racing_open(path, mode="r", *args, **kwargs):
            if path.name == "talk-2.srt" and mode == "x":
                # Simulate another process creating the second output after the MD
                # was exclusively created by this run.
                with builtins.open(path, "x", encoding="utf-8") as file:
                    file.write("other process")
                raise FileExistsError(path)
            return original_open(path, mode, *args, **kwargs)

        with patch.object(type(self.directory), "open", racing_open):
            code, stderr = self.run_main("--format", "all")
        self.assertEqual(code, 1)
        self.assertEqual((self.directory / "talk.md").read_text(encoding="utf-8"), "old md")
        self.assertEqual((self.directory / "talk-2.srt").read_text(encoding="utf-8"), "other process")
        self.assertTrue((self.directory / "talk-2.md").exists())
        self.assertFalse((self.directory / "talk-3.md").exists())
        self.assertIn("talk-2.md", stderr)
        self.assertIn("没有删除或覆盖文件", stderr)

    def test_explicit_output_directory_and_name_are_respected(self):
        output_dir = self.directory / "requested-output"
        self.run_main("--format", "srt", "--output-dir", str(output_dir), "--output-name", "requested")
        self.assertTrue((output_dir / "requested.srt").exists())
        self.assertFalse((self.directory / "talk.srt").exists())


if __name__ == "__main__":
    unittest.main()
