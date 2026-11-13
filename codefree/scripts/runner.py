#!/usr/bin/env python3
"""Local, evidence-preserving CodeFree-O task runner."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

from events import parse_events


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix='.state-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def state_path(args): return Path(args.record).resolve() / 'state.json'
def load(args): return json.loads(state_path(args).read_text(encoding='utf-8'))
def save(args, state): write_json(state_path(args), state)


def git(project, *args, check=True):
    return subprocess.run(['git', '-C', str(project), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def snapshot(project, target, paths=None):
    target.mkdir(parents=True, exist_ok=False)
    probe = git(project, 'rev-parse', '--show-toplevel', check=False)
    is_git = probe.returncode == 0
    if is_git:
        root = Path(os.fsdecode(probe.stdout.strip())).resolve()
        if root != project: raise ValueError('project must be Git root')
        head = git(project, 'rev-parse', 'HEAD', check=False).stdout.strip().decode('ascii')
        (target/'head').write_text(head)
        (target/'index.diff').write_bytes(git(project, 'diff', '--binary', '--cached').stdout)
        (target/'worktree.diff').write_bytes(git(project, 'diff', '--binary').stdout)
        status = git(project, 'status', '--porcelain=v1', '-z', '--untracked-files=all').stdout
        (target/'status').write_bytes(status)
        raw = (git(project, 'diff', '--name-only', '-z').stdout + git(project, 'diff', '--cached', '--name-only', '-z').stdout + git(project, 'ls-files', '-z', '--others', '--exclude-standard').stdout)
        changed_names = {os.fsdecode(x) for x in raw.split(b'\0') if x}
        raw += git(project, 'ls-files', '-z').stdout
        names = [os.fsdecode(x) for x in raw.split(b'\0') if x]
    else:
        if not paths: raise ValueError('non-Git project requires --paths-file')
        names = Path(paths).read_text(encoding='utf-8').splitlines()
    manifest = {}
    for name in sorted(set(names)):
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts: raise ValueError('unsafe snapshot path')
        src = project / rel
        if any((project / Path(*rel.parts[:i])).is_symlink() for i in range(1, len(rel.parts))): raise ValueError('snapshot path has symlink parent: ' + name)
        if src.is_symlink():
            manifest[name] = {'symlink': os.readlink(str(src))}
        elif src.is_file():
            data = src.read_bytes()
            manifest[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'mode': src.stat().st_mode & 0o777}
            if not is_git or name in changed_names:
                dst = target/'files'/rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)
        elif src.exists():
            raise ValueError('snapshot paths must be files or symlinks: ' + name)
        else: manifest[name] = {'missing': True}
    write_json(target/'manifest.json', manifest)
    digest = hashlib.sha256()
    for item in ('head', 'index.diff', 'worktree.diff', 'status', 'manifest.json'):
        f = target/item
        if f.exists(): digest.update(item.encode()+b'\0'+f.read_bytes())
    return digest.hexdigest()


def normalize(value): return re.sub(r'[^a-z0-9]', '', value.lower())


def resolve_model(cli, requested):
    p = subprocess.run([cli, 'models'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode: raise ValueError('model list failed: ' + p.stderr.strip())
    models = [s.strip() for s in p.stdout.splitlines() if '/' in s and not s.startswith(' ')]
    if requested in models: return requested
    needle = normalize(requested)
    matches = [m for m in models if normalize(m.rsplit('/',1)[-1]).removesuffix('tokenplan') == needle] if hasattr(str, 'removesuffix') else [m for m in models if re.sub('tokenplan$', '', normalize(m.rsplit('/',1)[-1])) == needle]
    if len(matches) != 1: raise ValueError('model unavailable or ambiguous: ' + requested)
    return matches[0]


def alive(pid):
    try: os.kill(pid, 0); return True
    except ProcessLookupError: return False
    except PermissionError: return True


def ensure_idle(state):
    if state.get('process'):
        pid = state['process'].get('pid')
        if pid is None: raise ValueError('launch interrupted; reconcile manually before retry')
        if alive(pid): raise ValueError('process may still be running: ' + str(pid))
        raise ValueError('interrupted process requires manual reconciliation; inspect logs and workspace')


def validate_tasks(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('tasks'), list) or not data['tasks']:
        raise ValueError('tasks must contain a nonempty version 1 task list')
    seen = set()
    for task in data['tasks']:
        if not isinstance(task, dict): raise ValueError('invalid task')
        for key in ('id', 'title', 'goal'):
            if not isinstance(task.get(key), str) or not task[key].strip(): raise ValueError('missing task field: ' + key)
        if task['id'] in seen: raise ValueError('duplicate task id')
        for key in ('targets', 'steps', 'acceptance'):
            if not isinstance(task.get(key), list) or not task[key] or any(not isinstance(x, str) or not x.strip() for x in task[key]): raise ValueError('invalid task field: ' + key)
        deps = task.get('depends_on')
        if not isinstance(deps, list) or any(not isinstance(x, str) or x not in seen for x in deps): raise ValueError('invalid task dependencies')
        checks = task.get('verification')
        if not isinstance(checks, list) or not checks or any(not isinstance(x, dict) or any(not isinstance(x.get(k), str) or not x[k].strip() for k in ('command', 'expected')) for x in checks): raise ValueError('invalid task verification')
        seen.add(task['id'])
    return data


def prepare(args):
    project = Path(args.project).resolve(strict=True)
    record = Path(args.record).resolve()
    if record == project or project in record.parents: raise ValueError('record must be outside project')
    plan = Path(args.plan).read_bytes()
    tasks = validate_tasks(args.tasks_file)
    if state_path(args).exists():
        state = load(args); ensure_idle(state)
        if state.get('version') != 2: raise ValueError('legacy record is read-only')
        if state.get('phase') not in ('ready', 'needs_fix') and not (state.get('phase') == 'blocked' and state.get('last_review')): raise ValueError('task state does not allow plan changes')
        if state['project'] != str(project): raise ValueError('project mismatch')
        if state['title'] != args.title: raise ValueError('task title mismatch')
    else:
        if record.exists() and any(record.iterdir()): raise ValueError('record directory is not empty')
        record.mkdir(parents=True, mode=0o700, exist_ok=True)
        os.chmod(record, 0o700)
        paths_file = None
        if args.paths_file:
            paths_file = str(record/'paths.txt')
            Path(paths_file).write_bytes(Path(args.paths_file).read_bytes())
        digest = snapshot(project, record/'snapshots'/'baseline', paths_file)
        state = dict(version=2, phase='ready', project=str(project), title=args.title, paths_file=paths_file, round=0, session=None, recovery=0, no_progress=0, process=None, expected_snapshot=digest, last_review=None, plan_version=0, model=None)
    state['plan_version'] += 1
    number = state['plan_version']
    planpath = record/'plans'/('plan-%03d.txt' % number)
    planpath.parent.mkdir(parents=True, exist_ok=True)
    planpath.write_bytes(plan)
    write_json(record/'plans'/('tasks-%03d.json' % number), tasks)
    state['tasks_version'] = number
    state.update(plan_sha256=hashlib.sha256(plan).hexdigest(), criteria=args.criteria, authorization=args.authorization, verify=args.verify)
    save(args, state)
    return {'ok': True, 'record': str(record), 'plan_version': number, 'plan_sha256': state['plan_sha256']}


def run(args):
    state = load(args); ensure_idle(state)
    if state.get('version') != 2: raise ValueError('legacy record is read-only')
    if state.get('phase') not in ('ready', 'needs_fix') and not (state.get('phase') == 'blocked' and state.get('last_review') and state.get('last_run', {}).get('issues') and (args.retry or args.rebuild) and args.recovery_evidence): raise ValueError('task state does not allow execution')
    if state.get('tasks_version') != state.get('plan_version'): raise ValueError('prepare a task list before execution')
    if state['no_progress'] >= 3: raise ValueError('three rounds without progress; pause')
    if state.get('last_run', {}).get('issues'):
        if not args.recovery_evidence or not (args.rebuild or args.retry): raise ValueError('previous run failed; review and provide recovery evidence')
        if not state.get('last_review'): raise ValueError('record review before recovery')
        if args.retry and not state['session']: raise ValueError('retry requires a known session ID')
        if args.rebuild:
            state['recovery'] += 1
            state['session'] = None
    elif args.rebuild or args.retry: raise ValueError('recovery requires a failed run')
    if state['round'] and state['last_review'] is None: raise ValueError('record review before next round')
    record = Path(args.record).resolve(); project = Path(state['project'])
    checkdir = record/'snapshots'/('check-%s' % time.time_ns())
    try: current = snapshot(project, checkdir, state['paths_file'])
    finally: shutil.rmtree(checkdir, ignore_errors=True)
    if current != state['expected_snapshot']: raise ValueError('workspace changed since last snapshot; inspect before continuing')
    model = resolve_model(args.cli, args.model or state['model'] or 'glm5.3')
    if state['model'] and model != state['model'] : raise ValueError('model changed; create a new task')
    state['model'] = model
    state['round'] += 1
    n = state['round']; rounddir = record/'rounds'/('%03d' % n)
    extra = Path(args.handoff).read_text(encoding='utf-8')
    context_path = record/'context.txt'
    context = context_path.read_text(encoding='utf-8') if context_path.exists() else extra
    full = not state['session'] or args.rebuild or state.get('last_sent_plan_version') != state['plan_version']
    if full:
        plan = (record/'plans'/('plan-%03d.txt' % state['plan_version'])).read_text(encoding='utf-8')
        tasks_path = record/'plans'/('tasks-%03d.json' % state['plan_version'])
        tasks = validate_tasks(tasks_path)
        handoff = ('按顺序执行以下任务；遇到未决行为问题停止。保护用户已有修改，按验收和验证要求反馈。\n计划:\n' + plan + '\n任务:\n' + json.dumps(tasks, ensure_ascii=False, indent=2) + '\n验收:\n' + state['criteria'] + '\n授权:\n' + state['authorization'] + '\n验证:\n' + state['verify'] + '\n项目规则及原始上下文:\n' + context + ('\n本轮补充:\n' + extra if context != extra else ''))
    else: handoff = extra
    rounddir.mkdir(parents=True)
    if not context_path.exists(): context_path.write_text(context, encoding='utf-8')
    (rounddir/'handoff.txt').write_text(handoff, encoding='utf-8')
    if args.recovery_evidence: (rounddir/'recovery-evidence.txt').write_text(args.recovery_evidence, encoding='utf-8')
    cmd = [args.cli, 'run', '--dir', str(project), '--model', model, '--format', 'json']
    if state['session']: cmd += ['--session', state['session']]
    else: cmd += ['--title', state['title'] + (' · 恢复 %d' % state['recovery'] if state['recovery'] else '')]
    cmd.append('--auto')
    write_json(rounddir/'invocation.json', {'model': model, 'session': state['session'], 'title': cmd[cmd.index('--title')+1] if '--title' in cmd else None, 'auto': True, 'plan_version': state['plan_version']})
    state['phase'] = 'running'
    state['process'] = {'pid': None, 'round': n, 'started': time.time()}
    save(args, state)
    new_session = not state['session']
    requested_title = cmd[cmd.index('--title') + 1] if new_session else None
    with (rounddir/'events.jsonl').open('wb') as out, (rounddir/'errors.txt').open('wb') as err, (rounddir/'handoff.txt').open('rb') as inp:
        proc = subprocess.Popen(cmd, stdin=inp, stdout=out, stderr=err, pass_fds=(args.project_lock_fd,))
        state['process'] = {'pid': proc.pid, 'round': n, 'started': time.time()}; save(args, state)
        rc = proc.wait()
    state['process'] = None
    state['expected_snapshot'] = snapshot(project, record/'snapshots'/('round-%03d' % n), state['paths_file'])
    state['last_review'] = None
    state['phase'] = 'awaiting_review'
    issues = []
    try:
        with (rounddir/'events.jsonl').open(encoding='utf-8') as stream: sid = parse_events(stream, state['session'])
        state['session'] = sid
        if new_session:
            listing = subprocess.run([args.cli, 'session', 'list', '--format', 'json'], cwd=str(project), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                if listing.returncode: raise ValueError('session list failed')
                sessions = json.loads(listing.stdout)
                found = [v for v in sessions if v.get('id') == sid]
                if len(found) != 1 or found[0].get('title') != requested_title: raise ValueError('new session title could not be verified')
            except (ValueError, TypeError, AttributeError) as e: issues.append('title verification: ' + str(e))
    except (ValueError, UnicodeError) as e: issues.append(str(e))
    if rc: issues.append('exit code %d' % rc)
    state['last_run'] = {'exit_code': rc, 'issues': issues, 'round_dir': str(rounddir)}
    state['last_sent_plan_version'] = state['plan_version']
    save(args, state)
    return {'ok': not issues, 'round': n, 'session': state['session'], 'issues': issues, 'evidence': str(rounddir), 'review_required': True}


def review(args):
    state = load(args); ensure_idle(state)
    if state.get('version') != 2: raise ValueError('legacy record is read-only')
    if state.get('phase') != 'awaiting_review': raise ValueError('no unreviewed round')
    if args.result == 'passed' and state.get('last_run', {}).get('issues'): raise ValueError('failed run cannot pass review')
    if not state['round'] or state['last_review'] is not None: raise ValueError('no unreviewed round')
    if not args.baseline_reviewed: raise ValueError('review baseline preservation before recording review')
    record = Path(args.record).resolve()
    checkdir = record/'snapshots'/('review-check-%s' % time.time_ns())
    try: current = snapshot(Path(state['project']), checkdir, state['paths_file'])
    finally: shutil.rmtree(checkdir, ignore_errors=True)
    if current != state['expected_snapshot'] and args.result != 'blocked': raise ValueError('workspace changed since round ended')
    baseline = record/'snapshots'/'baseline'
    manifest = json.loads((baseline/'manifest.json').read_text(encoding='utf-8'))
    missing = [name for name, item in manifest.items() if 'missing' not in item and not (Path(state['project'])/name).exists() and not (Path(state['project'])/name).is_symlink()]
    if missing: raise ValueError('baseline files removed: ' + ', '.join(missing))
    baseline_index = baseline/'index.diff'
    if baseline_index.exists() and baseline_index.stat().st_size:
        current_index = git(Path(state['project']), 'diff', '--binary', '--cached').stdout
        if current_index != baseline_index.read_bytes(): raise ValueError('pre-existing staged changes differ from baseline; inspect before continuing')
    entry = {'baseline_reviewed': True, 'result': args.result, 'evidence': args.evidence, 'progress': args.progress, 'round': state['round']}
    write_json(Path(args.record).resolve()/'rounds'/('%03d' % state['round'])/'review.json', entry)
    entry.update(plan_version=state['plan_version'], model=state['model'])
    state['last_review'] = entry
    state['phase'] = {'passed': 'completed', 'failed': 'needs_fix', 'blocked': 'blocked'}[args.result]
    state['no_progress'] = 0 if args.progress == 'yes' else state['no_progress'] + 1
    if state['no_progress'] >= 3 and state['phase'] == 'needs_fix': state['phase'] = 'paused'
    save(args, state)
    return {'ok': True, 'round': state['round'], 'no_progress': state['no_progress']}


def status(args):
    state = load(args)
    if args.reconcile:
        if state.get('version') != 2: raise ValueError('legacy record is read-only')
        if not args.evidence: raise ValueError('reconciliation requires evidence')
        proc = state.get('process')
        if not proc: raise ValueError('no interrupted process to reconcile')
        if proc.get('pid') and alive(proc['pid']): raise ValueError('process may still be running')
        if not proc.get('pid') and not args.confirmed_no_process: raise ValueError('PID missing: independently confirm no child process and pass --confirmed-no-process')
        n = proc['round']; target = Path(args.record).resolve()/'snapshots'/('reconciled-%03d-%s' % (n, time.time_ns()))
        state['expected_snapshot'] = snapshot(Path(state['project']), target, state['paths_file'])
        state['process'] = None
        state['last_review'] = None
        state['phase'] = 'awaiting_review'
        state['last_run'] = {'round_dir': str(Path(args.record).resolve()/'rounds'/('%03d' % n)), 'issues': ['interrupted: ' + args.evidence]}
        save(args, state)
    return {'ok': True, **state}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--record', required=True); p.add_argument('--project', required=True); p.add_argument('--title', required=True); p.add_argument('--plan', required=True); p.add_argument('--tasks-file', required=True); p.add_argument('--criteria', required=True); p.add_argument('--authorization', required=True); p.add_argument('--verify', required=True); p.add_argument('--paths-file')
    p = sub.add_parser('run'); p.add_argument('--record', required=True); p.add_argument('--handoff', required=True); p.add_argument('--model'); p.add_argument('--cli', default='codefree-o'); p.add_argument('--auto', action='store_true'); recovery = p.add_mutually_exclusive_group(); recovery.add_argument('--rebuild', action='store_true'); recovery.add_argument('--retry', action='store_true'); p.add_argument('--recovery-evidence')
    p = sub.add_parser('record-review'); p.add_argument('--record', required=True); p.add_argument('--result', choices=['passed', 'failed', 'blocked'], required=True); p.add_argument('--evidence', required=True); p.add_argument('--progress', choices=['yes','no'], required=True); p.add_argument('--baseline-reviewed', action='store_true')
    p = sub.add_parser('status'); p.add_argument('--record', required=True); p.add_argument('--reconcile', action='store_true'); p.add_argument('--evidence'); p.add_argument('--confirmed-no-process', action='store_true')
    args = parser.parse_args()
    try:
        record = Path(args.record).resolve()
        lockdir = Path(tempfile.gettempdir()) / ('codefree-locks-%d' % os.getuid())
        lockdir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if lockdir.is_symlink() or lockdir.stat().st_uid != os.getuid(): raise ValueError('unsafe lock directory')
        os.chmod(lockdir, 0o700)
        lockname = hashlib.sha256(os.fsencode(str(record))).hexdigest()
        with contextlib.ExitStack() as stack:
            lock = stack.enter_context((lockdir/lockname).open('a'))
            try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise ValueError('another operation is active for this record')
            if args.command in ('prepare', 'run', 'record-review') or (args.command == 'status' and args.reconcile):
                project = str(Path(args.project).resolve()) if args.command == 'prepare' else load(args)['project']
                project_lock = stack.enter_context((lockdir/('project-' + hashlib.sha256(os.fsencode(project)).hexdigest())).open('a'))
                try: fcntl.flock(project_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError: raise ValueError('another task is active in this project')
                args.project_lock_fd = project_lock.fileno()
            result = {'prepare': prepare, 'run': run, 'record-review': review, 'status': status}[args.command](args)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['ok'] else 1
    except (ValueError, OSError, subprocess.SubprocessError, KeyError) as e:
        print(json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False))
        return 1

if __name__ == '__main__': sys.exit(main())
