import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "package_skill.py"
SPEC = importlib.util.spec_from_file_location("package_skill", SCRIPT)
PACKAGE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PACKAGE
SPEC.loader.exec_module(PACKAGE)


class PackageSkillTests(unittest.TestCase):
    def test_excludes_local_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "demo-skill"
            (root / ".git").mkdir(parents=True)
            (root / "__MACOSX").mkdir()
            (root / "__pycache__").mkdir()
            (root / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n", encoding="utf-8")
            (root / ".DS_Store").write_text("ignored", encoding="utf-8")
            (root / ".git" / "config").write_text("ignored", encoding="utf-8")
            (root / "__MACOSX" / "meta").write_text("ignored", encoding="utf-8")
            (root / "__pycache__" / "demo.pyc").write_text("ignored", encoding="utf-8")
            output = Path(directory) / "demo.zip"
            PACKAGE.package(root, output)
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
            self.assertEqual(["demo-skill/SKILL.md"], names)

    def test_excludes_symlink_to_external_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "demo-skill"
            root.mkdir()
            external = Path(directory) / "external.txt"
            external.write_text("sensitive", encoding="utf-8")
            (root / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n", encoding="utf-8")
            (root / "external-link.txt").symlink_to(external)
            output = Path(directory) / "demo.zip"
            PACKAGE.package(root, output)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(["demo-skill/SKILL.md"], archive.namelist())

    def test_rejects_output_inside_skill_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "demo-skill"
            root.mkdir()
            (root / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                PACKAGE.package(root, root / "release.zip")
