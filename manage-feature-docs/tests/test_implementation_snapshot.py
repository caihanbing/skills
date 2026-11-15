import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'implementation_snapshot.py'

class SnapshotTests(unittest.TestCase):
    def test_staging_and_commit_preserve_snapshot_and_deletion_changes_it(self):
        spec = importlib.util.spec_from_file_location('implementation_snapshot', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                subprocess.run(['git', '-C', tmp, *args], check=True, capture_output=True)
            git('init')
            git('config', 'user.email', 'test@example.com')
            git('config', 'user.name', 'Test')
            (root / 'a').write_text('hello')
            first = module.snapshot(root)
            git('add', 'a')
            self.assertEqual(first, module.snapshot(root))
            git('commit', '-m', 'initial')
            self.assertEqual(first, module.snapshot(root))
            (root / 'a').unlink()
            self.assertNotEqual(first, module.snapshot(root))

    def test_detects_earlier_file_changed_while_hashing_later_file(self):
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('snapshot_race', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', '-C', tmp, 'init'], check=True, capture_output=True)
            (root / 'a').write_text('old')
            (root / 'b').write_text('other')
            original = Path.read_bytes
            def read(path):
                data = original(path)
                if path.name == 'b':
                    (root / 'a').write_text('new')
                return data
            with patch.object(Path, 'read_bytes', read):
                with self.assertRaises(module.SnapshotError):
                    module.snapshot(root)

    def test_staged_deleted_ignored_file_still_in_head_snapshot(self):
        spec = importlib.util.spec_from_file_location('snapshot_head', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                subprocess.run(['git', '-C', tmp, *args], check=True, capture_output=True)
            git('init')
            git('config', 'user.email', 'test@example.com')
            git('config', 'user.name', 'Test')
            (root / '.gitignore').write_text('a\n')
            (root / 'a').write_text('content')
            git('add', '-f', 'a')
            git('add', '.gitignore')
            git('commit', '-m', 'initial')
            before = module.snapshot(root)
            git('rm', '--cached', 'a')
            self.assertEqual(before, module.snapshot(root))

    def test_git_failure_is_reported(self):
        spec = importlib.util.spec_from_file_location('snapshot_error', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(module.SnapshotError):
                module.snapshot(Path(tmp))

    def test_modes_symlinks_and_rename_change_snapshot(self):
        spec = importlib.util.spec_from_file_location('snapshot_files', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', '-C', tmp, 'init'], check=True, capture_output=True)
            file = root / 'a'
            file.write_text('content')
            original = module.snapshot(root)
            file.chmod(0o755)
            executable = module.snapshot(root)
            self.assertNotEqual(original, executable)
            file.rename(root / 'b')
            renamed = module.snapshot(root)
            self.assertNotEqual(executable, renamed)
            (root / 'link').symlink_to('b')
            self.assertNotEqual(renamed, module.snapshot(root))

    def test_uninitialized_and_dirty_submodule_rejected(self):
        spec = importlib.util.spec_from_file_location('snapshot_submodule', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'main'
            sub = Path(tmp) / 'sub'
            root.mkdir()
            sub.mkdir()
            def git(path, *args):
                subprocess.run(['git', '-C', str(path), *args], check=True, capture_output=True)
            for path in (root, sub):
                git(path, 'init')
                git(path, 'config', 'user.name', 'Test')
                git(path, 'config', 'user.email', 'test@example.com')
            (sub / 'file').write_text('content')
            git(sub, 'add', 'file')
            git(sub, 'commit', '-m', 'initial')
            git(root, '-c', 'protocol.file.allow=always', 'submodule', 'add', str(sub), 'child')
            module.snapshot(root)
            (root / 'child' / 'file').write_text('dirty')
            with self.assertRaises(module.SnapshotError):
                module.snapshot(root)
            git(root, 'submodule', 'deinit', '-f', 'child')
            with self.assertRaises(module.SnapshotError):
                module.snapshot(root)

    def test_tracked_file_removed_after_preflight_is_rejected(self):
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('snapshot_removed', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', '-C', tmp, 'init'], check=True, capture_output=True)
            (root / 'a').write_text('content')
            subprocess.run(['git', '-C', tmp, 'add', 'a'], check=True, capture_output=True)
            original = Path.lstat
            calls = [0]
            def lstat(path):
                if path.name == 'a':
                    calls[0] += 1
                    if calls[0] == 2:
                        path.unlink()
                return original(path)
            with patch.object(Path, 'lstat', lstat):
                with self.assertRaises(module.SnapshotError):
                    module.snapshot(root)

    def test_tracked_directory_replaced_by_file(self):
        spec = importlib.util.spec_from_file_location('snapshot_directory', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                subprocess.run(['git', '-C', tmp, *args], check=True, capture_output=True)
            git('init')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.com')
            (root / 'a').mkdir()
            (root / 'a' / 'b').write_text('old')
            git('add', '.')
            git('commit', '-m', 'initial')
            (root / 'a' / 'b').unlink()
            (root / 'a').rmdir()
            (root / 'a').write_text('new')
            git('add', '-A')
            self.assertTrue(module.snapshot(root).startswith('impl-v2 sha256:'))

    def test_tracked_file_replaced_by_directory(self):
        spec = importlib.util.spec_from_file_location('snapshot_replaced', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                subprocess.run(['git', '-C', tmp, *args], check=True, capture_output=True)
            git('init')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.com')
            (root / 'a').write_text('old')
            git('add', '.')
            git('commit', '-m', 'initial')
            (root / 'a').unlink()
            (root / 'a').mkdir()
            (root / 'a' / 'b').write_text('new')
            git('add', '-A')
            self.assertTrue(module.snapshot(root).startswith('impl-v2 sha256:'))

    def test_staged_deleted_head_submodule_still_checks_dirty_directory(self):
        spec = importlib.util.spec_from_file_location('snapshot_old_submodule', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root, sub = Path(tmp) / 'main', Path(tmp) / 'sub'
            root.mkdir()
            sub.mkdir()
            def git(path, *args):
                subprocess.run(['git', '-C', str(path), *args], check=True, capture_output=True)
            for path in (root, sub):
                git(path, 'init')
                git(path, 'config', 'user.name', 'Test')
                git(path, 'config', 'user.email', 'test@example.com')
            (sub / 'file').write_text('clean')
            git(sub, 'add', '.')
            git(sub, 'commit', '-m', 'initial')
            git(root, '-c', 'protocol.file.allow=always', 'submodule', 'add', str(sub), 'child')
            git(root, 'commit', '-am', 'submodule')
            before = module.snapshot(root)
            git(root, 'rm', '--cached', 'child')
            self.assertEqual(before, module.snapshot(root))
            (root / 'child' / 'file').write_text('dirty')
            with self.assertRaises(module.SnapshotError):
                module.snapshot(root)

    def test_sparse_config_and_skip_worktree_are_rejected(self):
        for script in (SCRIPT, SCRIPT.parents[2] / 'manage-dev-work/scripts/implementation_snapshot.py'):
            spec = importlib.util.spec_from_file_location('sparse_snapshot', script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with tempfile.TemporaryDirectory() as tmp:
                def git(*args):
                    subprocess.run(['git', '-C', tmp, *args], check=True, capture_output=True)
                git('init')
                (Path(tmp) / 'a').write_text('a')
                git('add', 'a')
                git('config', 'core.sparseCheckout', 'true')
                with self.assertRaises(module.SnapshotError): module.snapshot(Path(tmp))
                git('config', 'core.sparseCheckout', 'false')
                git('update-index', '--skip-worktree', 'a')
                with self.assertRaises(module.SnapshotError): module.snapshot(Path(tmp))

    def test_sparse_index_linked_worktree_and_config_error(self):
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('sparse_linked', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'repo'
            root.mkdir()
            def git(*args):
                subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)
            git('init')
            git('config', 'user.email', 'test@example.com')
            git('config', 'user.name', 'Test')
            for name in ('one/a', 'two/b'):
                path = root / name
                path.parent.mkdir(exist_ok=True)
                path.write_text(name)
            git('add', '.')
            git('commit', '-m', 'init')
            linked = Path(tmp) / 'linked'
            git('worktree', 'add', '-b', 'linked', str(linked))
            subprocess.run(['git', '-C', str(linked), 'sparse-checkout', 'init', '--cone', '--sparse-index'], check=True, capture_output=True)
            subprocess.run(['git', '-C', str(linked), 'sparse-checkout', 'set', 'one'], check=True, capture_output=True)
            with self.assertRaises(module.SnapshotError): module.snapshot(linked)
            original = module.subprocess.run
            def fail_config(args, **kwargs):
                if 'config' in args:
                    return subprocess.CompletedProcess(args, 3, b'', b'error')
                return original(args, **kwargs)
            with patch.object(module.subprocess, 'run', side_effect=fail_config):
                with self.assertRaises(module.SnapshotError): module.snapshot(root)

    def test_submodule_skip_worktree_is_rejected(self):
        spec = importlib.util.spec_from_file_location('snapshot_sub_sparse', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'root'
            child = Path(tmp) / 'source'
            root.mkdir(); child.mkdir()
            def git(path, *args):
                subprocess.run(['git', '-C', str(path), *args], check=True, capture_output=True)
            for path in (root, child):
                git(path, 'init')
                git(path, 'config', 'user.name', 'Test')
                git(path, 'config', 'user.email', 'test@example.com')
            (child / 'f').write_text('original')
            git(child, 'add', '.')
            git(child, 'commit', '-m', 'initial')
            git(root, '-c', 'protocol.file.allow=always', 'submodule', 'add', str(child), 'sub')
            git(root, 'commit', '-am', 'submodule')
            module.snapshot(root)
            git(root / 'sub', 'update-index', '--skip-worktree', 'f')
            (root / 'sub' / 'f').write_text('changed')
            with self.assertRaises(module.SnapshotError): module.snapshot(root)

    def test_submodule_assume_unchanged_is_rejected(self):
        spec = importlib.util.spec_from_file_location('snapshot_sub_assume', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root, child = Path(tmp) / 'root', Path(tmp) / 'child'
            root.mkdir(); child.mkdir()
            def git(path, *args):
                subprocess.run(['git', '-C', str(path), *args], check=True, capture_output=True)
            for path in (root, child):
                git(path, 'init'); git(path, 'config', 'user.name', 'Test'); git(path, 'config', 'user.email', 'test@example.com')
            (child / 'f').write_text('original')
            git(child, 'add', '.'); git(child, 'commit', '-m', 'initial')
            git(root, '-c', 'protocol.file.allow=always', 'submodule', 'add', str(child), 'sub')
            git(root, 'commit', '-am', 'submodule')
            git(root / 'sub', 'update-index', '--assume-unchanged', 'f')
            (root / 'sub' / 'f').write_text('changed')
            with self.assertRaises(module.SnapshotError): module.snapshot(root)

    def test_staged_deleted_submodule_still_checked_for_sparse_flags(self):
        spec = importlib.util.spec_from_file_location('snapshot_deleted_sub_sparse', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root, child = Path(tmp) / 'root', Path(tmp) / 'child'
            root.mkdir(); child.mkdir()
            def git(path, *args):
                subprocess.run(['git', '-C', str(path), *args], check=True, capture_output=True)
            for path in (root, child):
                git(path, 'init'); git(path, 'config', 'user.name', 'Test'); git(path, 'config', 'user.email', 'test@example.com')
            (child / 'f').write_text('original')
            git(child, 'add', '.'); git(child, 'commit', '-m', 'initial')
            git(root, '-c', 'protocol.file.allow=always', 'submodule', 'add', str(child), 'sub')
            git(root, 'commit', '-am', 'submodule')
            git(root, 'rm', '--cached', 'sub')
            git(root / 'sub', 'update-index', '--skip-worktree', 'f')
            (root / 'sub' / 'f').write_text('changed')
            with self.assertRaises(module.SnapshotError): module.snapshot(root)
