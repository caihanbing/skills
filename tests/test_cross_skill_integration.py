import importlib.util
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
