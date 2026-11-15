"""Canonical snapshot of effective repository implementation files."""
from pathlib import Path
import hashlib
import os
import stat
import subprocess


class SnapshotError(Exception):
    """The implementation snapshot could not be computed reliably."""


def snapshot(root: Path) -> str:
    try:
        return _snapshot(root)
    except OSError as exc:
        raise SnapshotError(str(exc)) from exc


def _snapshot(root: Path) -> str:
    root = Path(root).resolve()

    def git(*args):
        result = subprocess.run(['git', '-C', str(root), *args], capture_output=True)
        if result.returncode:
            raise SnapshotError('git ' + ' '.join(args) + ': ' + result.stderr.decode(errors='replace').strip())
        return result.stdout

    top = Path(os.fsdecode(git('rev-parse', '--show-toplevel').strip())).resolve()
    if top != root:
        raise SnapshotError('snapshot requires the Git repository root')
    if git('ls-files', '-u', '-z'):
        raise SnapshotError('unmerged index entries')
    index = git('ls-files', '--stage', '-z')
    branch = git('status', '--porcelain=v2', '--branch', '-z')
    head_tree = b'' if b'# branch.oid (initial)' in branch else git('ls-tree', '-r', '-z', 'HEAD')
    submodules = {}
    gitlinks = set()
    for record in (index + head_tree).split(b'\0'):
        if record.startswith(b'160000 '):
            gitlinks.add(record.split(b'\t', 1)[1])
    for raw in sorted(gitlinks):
        path = os.fsdecode(raw)
        sub = root / path
        if not (sub / '.git').exists():
            raise SnapshotError('uninitialized submodule: ' + path)
        status = subprocess.run(['git', '-C', str(sub), 'status', '--porcelain', '--untracked-files=all'], capture_output=True)
        if status.returncode or status.stdout:
            raise SnapshotError('dirty or unreadable submodule: ' + path)
        head = subprocess.run(['git', '-C', str(sub), 'rev-parse', 'HEAD'], capture_output=True)
        if head.returncode:
            raise SnapshotError('unreadable submodule: ' + path)
        submodules[os.fsencode(path)] = head.stdout.strip()
    def listing():
        return git('ls-files', '--cached', '--others', '--exclude-standard', '-z')

    before = listing()
    head_paths = b''.join(record.split(b'\t', 1)[1] + b'\0' for record in head_tree.split(b'\0') if record)
    paths = sorted(set((before + head_paths).split(b'\0')) - {b''})
    def signature(path):
        try:
            info = path.lstat()
        except (FileNotFoundError, NotADirectoryError):
            return None
        return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    initial = {raw: signature(root / os.fsdecode(raw)) for raw in paths if raw not in submodules}
    observed = {}
    digest = hashlib.sha256()
    try:
        for raw in paths:
            if any(raw.startswith(link + b'/') for link in submodules):
                continue
            if any(raw.startswith(p) for p in (b'docs/features/', b'docs/work-items/', b'docs/superpowers/')):
                continue
            path = root / os.fsdecode(raw)
            if raw in submodules:
                for part in (raw, b's', submodules[raw]):
                    digest.update(len(part).to_bytes(8, 'big'))
                    digest.update(part)
                continue
            try:
                info = path.lstat()
            except (FileNotFoundError, NotADirectoryError):
                observed[raw] = None
                continue
            if stat.S_ISDIR(info.st_mode):
                observed[raw] = signature(path)
                continue
            if stat.S_ISLNK(info.st_mode):
                kind = b'l'
                content = os.fsencode(os.readlink(path))
            elif stat.S_ISREG(info.st_mode):
                kind = b'x' if info.st_mode & 0o111 else b'f'
                content = path.read_bytes()
            else:
                raise SnapshotError('unsupported file type: ' + os.fsdecode(raw))
            after = path.lstat()
            observed[raw] = signature(path)
            if (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_mode, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise SnapshotError('file changed while hashing: ' + os.fsdecode(raw))
            for part in (raw, kind, content):
                digest.update(len(part).to_bytes(8, 'big'))
                digest.update(part)
    except OSError as exc:
        raise SnapshotError(str(exc)) from exc
    for raw, prior in observed.items():
        current = signature(root / os.fsdecode(raw))
        if prior != current or initial[raw] != prior:
            raise SnapshotError('file changed while hashing: ' + os.fsdecode(raw))
    for raw, prior in submodules.items():
        sub = root / os.fsdecode(raw)
        status = subprocess.run(['git', '-C', str(sub), 'status', '--porcelain', '--untracked-files=all'], capture_output=True)
        head = subprocess.run(['git', '-C', str(sub), 'rev-parse', 'HEAD'], capture_output=True)
        if status.returncode or status.stdout or head.returncode or head.stdout.strip() != prior:
            raise SnapshotError('submodule changed while hashing: ' + os.fsdecode(raw))
    if before != listing() or index != git('ls-files', '--stage', '-z') or branch != git('status', '--porcelain=v2', '--branch', '-z'):
        raise SnapshotError('repository changed while hashing')
    return 'impl-v2 sha256:' + digest.hexdigest()
