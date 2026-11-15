import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dev_work_integration", ROOT / "manage-dev-work" / "scripts" / "dev_work.py")
DEV_WORK = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DEV_WORK
SPEC.loader.exec_module(DEV_WORK)


class CrossSkillIntegrationTests(unittest.TestCase):
    def test_snapshot_cli_agrees_across_both_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
            (repo / "main.py").write_text("value = 1\n", encoding="utf-8")
            scripts = (
                ROOT / "manage-feature-docs/scripts/feature_docs.py",
                ROOT / "manage-dev-work/scripts/dev_work.py",
            )
            def snapshots():
                return [subprocess.run([sys.executable, str(script), "snapshot", "--repo", str(repo)],
                                       check=True, capture_output=True, text=True).stdout.strip()
                        for script in scripts]
            first = snapshots()
            self.assertEqual(first[0], first[1])
            subprocess.run(["git", "-C", str(repo), "add", "main.py"], check=True)
            self.assertEqual(first, snapshots())
            (repo / "main.py").write_text("value = 2\n", encoding="utf-8")
            second = snapshots()
            self.assertEqual(second[0], second[1])
            self.assertNotEqual(first[0], second[0])

    def test_dev_work_uses_sibling_canonical_feature_validator(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            feature = repo / "docs" / "features" / "ghost.md"
            feature.parent.mkdir(parents=True)
            feature.write_text("invalid feature document", encoding="utf-8")
            errors = DEV_WORK.canonical_feature_validation_errors(repo, ("ghost",), None)
            self.assertTrue(errors, errors)
            self.assertTrue(any("Feature Doc ghost" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
