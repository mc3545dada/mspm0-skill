import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "mspm0-ccs" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import check_syscfg


class InvalidProjectPathTests(unittest.TestCase):
    def run_cli(self, project, *options):
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "check_syscfg.py"), str(project), *options],
            capture_output=True, text=True, encoding="utf-8", timeout=15,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

    def test_missing_directory_returns_structured_json_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli(Path(tmp) / "missing", "--json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        report = json.loads(result.stdout)
        self.assertTrue(any(m["level"] == "error" and "directory" in m["text"] for m in report["messages"]))
        self.assertEqual(report["details"].get("validation_hints", {}), {})

    def test_file_path_returns_structured_json_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "main.c"
            project.write_text("int main(void) { return 0; }", encoding="utf-8")
            result = self.run_cli(project, "--json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout)["messages"][0]["level"], "error")

    def test_text_mode_explains_invalid_directory_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli(Path(tmp) / "missing")
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR", result.stdout)
        self.assertIn("directory", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_invalid_project_does_not_enumerate_probes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "missing"
            with mock.patch.object(sys, "argv", ["check_syscfg.py", str(project), "--probe", "--json"]), \
                 mock.patch.object(check_syscfg, "detect_probes", side_effect=AssertionError("unexpected probe enumeration")), \
                 mock.patch("builtins.print"), mock.patch.object(check_syscfg, "add_probe_check") as probe_check:
                self.assertEqual(check_syscfg.main(), 1)
                probe_check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
