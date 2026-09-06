import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "mspm0-ccs" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import check_syscfg


class KeilProjectSelectionTests(unittest.TestCase):
    def test_single_nested_project_retains_build_hint(self):
        with tempfile.TemporaryDirectory(prefix="project space ") as tmp:
            root = Path(tmp)
            project = root / "keil" / "car.uvprojx"
            project.parent.mkdir()
            project.write_text("<Project/>", encoding="utf-8")
            hints = check_syscfg.find_validation_hints(root)
            self.assertIn(str(project), hints["keil_build"])
            self.assertNotIn("keil_project_selection", hints)

    def test_multiple_projects_require_selection_and_print_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("bootloader", "application"):
                project = root / name / "firmware.uvprojx"
                project.parent.mkdir()
                project.write_text("<Project/>", encoding="utf-8")
            messages, details = check_syscfg.check_project(root)
            hints = details["validation_hints"]
            self.assertNotIn("keil_build", hints)
            self.assertIn(".uvprojx", hints["keil_project_selection"])
            self.assertEqual(len(details["keil_projects"]), 2)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                check_syscfg.print_text(root, messages, details)
            self.assertIn("keil_project_selection", output.getvalue())

    def test_no_project_has_no_keil_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            hints = check_syscfg.find_validation_hints(Path(tmp))
        self.assertNotIn("keil_build", hints)
        self.assertNotIn("keil_project_selection", hints)


if __name__ == "__main__":
    unittest.main()
