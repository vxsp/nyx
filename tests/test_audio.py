import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import wave

from jobs import audio
from nyx.config import ConfigurationError

try:
    from mutagen import File
except ImportError:
    File = None


class AudioTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"NYX_REPORT_DIR": ""})
        environment.start()
        self.addCleanup(environment.stop)

    def config(self, root, **changes):
        return {"roots": [root], "max_entries": 1000, "max_seconds": 30, "large_export_mb": 1, **changes}

    def test_inventory_candidates_are_read_only_and_flp_usage_unavailable(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "a").mkdir()
            (root / "b").mkdir()
            paths = [root / "a" / "Track  Demo.mp3", root / "b" / "track  demo.MP3", root / "session.flp"]
            for path in paths:
                path.write_bytes(b"synthetic bytes")
            before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
            result = audio.inventory(self.config(root))
            self.assertTrue(result["complete"])
            self.assertEqual(result["audio_files"], 2)
            self.assertEqual(result["fl_studio_projects"], 1)
            self.assertEqual(len(result["duplicate_candidates"]), 1)
            self.assertIn("unavailable", result["fl_studio_sample_usage"])
            self.assertEqual(before, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths})

    def test_entry_limit_is_explicitly_partial(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            for number in range(5):
                (root / f"{number}.wav").write_bytes(b"synthetic")
            result = audio.inventory(self.config(root, max_entries=2))
            self.assertFalse(result["complete"])
            self.assertEqual(result["entries_visited"], 2)

    def test_overlapping_roots_do_not_double_count(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            child = root / "sub"
            child.mkdir()
            (child / "demo.mp3").write_bytes(b"synthetic")
            result = audio.inventory(self.config(root, roots=[root, child]))
            self.assertEqual(result["audio_files"], 1)

    def test_unavailable_metadata_is_not_reported_as_missing_tags(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "corrupt.mp3"
            path.write_bytes(b"not audio")
            result = audio.metadata(path, lambda *args, **kwargs: None)
            self.assertEqual(result["status"], "unavailable")
            self.assertNotIn("missing", result)

    @unittest.skipIf(File is None, "Install requirements-audio.txt for real parser check")
    def test_real_wav_metadata_read_keeps_original_bytes(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.wav"
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(8000)
                handle.writeframes(b"\0\0" * 80)
            original = path.read_bytes()
            result = audio.metadata(path, File)
            self.assertEqual(result["status"], "read")
            self.assertIn("artist", result["missing"])
            self.assertEqual(path.read_bytes(), original)

    def test_private_configuration_and_invalid_limits(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config").mkdir()
            config = root / "config" / "audio.local.json"
            config.write_text(json.dumps({"roots": ["."], "max_entries": 0}), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                audio.configuration(root, {})
            config.write_text(json.dumps({"roots": ["."]}), encoding="utf-8")
            self.assertEqual(audio.configuration(root, {})["roots"], [root.resolve()])

    def test_no_configuration_reports_no_scan_and_large_export_candidates(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            report = audio.run_audio_report(root, {})
            self.assertIn("No directories configured", report.read_text())
            sample = root / "large.wav"
            with sample.open("wb") as handle:
                handle.truncate(2 * 1024**2)
            result = audio.inventory(self.config(root))
            self.assertIn(str(sample), result["large_exports"])


if __name__ == "__main__":
    unittest.main()
