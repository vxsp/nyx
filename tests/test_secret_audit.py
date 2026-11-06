import importlib.util
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest


spec = importlib.util.spec_from_file_location("secret_audit", Path(__file__).resolve().parents[1] / "scripts" / "check-secrets.py")
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


class SecretAuditTests(unittest.TestCase):
    def test_removed_secret_in_history_still_blocks(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
            git("init", "-b", "main")
            (root / ".gitignore").write_text(".env\n", encoding="utf-8")
            (root / "config").mkdir()
            (root / "config" / ".env").write_text("NAVIDROME_PASSWORD=local-test-value\n", encoding="utf-8")
            (root / "source.txt").write_text("ghp_" + "A" * 36, encoding="utf-8")
            git("add", ".gitignore", "source.txt")
            git("-c", "user.name=Nyx Test", "-c", "user.email=nyx@example.com", "commit", "-m", "synthetic history")
            (root / "source.txt").write_text("clean current contents", encoding="utf-8")
            git("add", "source.txt")
            findings, _ = audit_module.audit(root)
            self.assertTrue(any("history:" in item and "provider token" in item for item in findings))
            self.assertFalse(any("local-test-value" in item for item in findings))

    def test_private_files_block_but_environment_example_is_allowed(self):
        self.assertTrue(audit_module.private_path("config/.env"))
        self.assertTrue(audit_module.private_path("config/projects.local.json"))
        self.assertTrue(audit_module.private_path("reports/Navidrome/report.md"))
        self.assertFalse(audit_module.private_path("config/.env.example"))
        self.assertFalse(audit_module.private_path("reports/.gitkeep"))

    def test_configuration_credentials_are_not_limited_to_current_password(self):
        self.assertTrue(audit_module.credential_assignments("config/.env.example", b"NAVIDROME_PASSWORD=retired-value\n"))
        self.assertTrue(audit_module.credential_assignments("config/settings.json", b'{"nested":{"api_key":"retired-value"}}'))
        self.assertFalse(audit_module.credential_assignments("config/.env.example", b"NAVIDROME_PASSWORD=\n"))
        self.assertFalse(audit_module.credential_assignments("config/settings.json", b'{"api_key":"your_api_key"}'))

    def test_historical_private_path_cannot_hide_behind_shared_empty_blob(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
            git("init", "-b", "main")
            (root / ".gitignore").write_text(".env\n", encoding="utf-8")
            (root / "config").mkdir()
            (root / "config" / ".env.example").write_text("NAVIDROME_PASSWORD=retired-value\n", encoding="utf-8")
            (root / "a.txt").write_text("NAVIDROME_PASSWORD=retired-value\n", encoding="utf-8")
            (root / "config" / "exposed.local.json").write_text("", encoding="utf-8")
            (root / "empty.txt").write_text("", encoding="utf-8")
            git("add", ".gitignore", "config/.env.example", "config/exposed.local.json", "empty.txt", "a.txt")
            git("-c", "user.name=Nyx Test", "-c", "user.email=nyx@example.com", "commit", "-m", "synthetic historical configuration")
            (root / "config" / ".env.example").write_text("NAVIDROME_PASSWORD=\n", encoding="utf-8")
            git("rm", "--", "config/exposed.local.json")
            git("add", "config/.env.example")
            findings, _ = audit_module.audit(root)
            self.assertTrue(any("history:config/exposed.local.json" in item for item in findings))
            self.assertTrue(any("history:config/.env.example" in item and "non-placeholder" in item for item in findings))
