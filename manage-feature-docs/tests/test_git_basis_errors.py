import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'feature_docs.py'
spec = importlib.util.spec_from_file_location('feature_docs_errors', SCRIPT)
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)

class GitBasisErrors(unittest.TestCase):
    def test_corrupt_git_directory_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(['git', '-C', tmp, 'init'], check=True, capture_output=True)
            (Path(tmp) / '.git' / 'HEAD').unlink()
            with self.assertRaises(module.SnapshotError):
                module.git_code_basis(Path(tmp))

    def test_explicit_git_dir_failure_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'GIT_DIR': str(Path(tmp) / 'missing')}):
                with self.assertRaises(module.SnapshotError):
                    module.git_code_basis(Path(tmp))

    def test_plain_directory_keeps_no_git_basis(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual('no-git; working-tree=unknown', module.git_code_basis(Path(tmp)))
