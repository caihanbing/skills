import json
import fcntl
import hashlib
import os
import select
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RUNNER = Path(__file__).parents[1] / 'scripts' / 'runner.py'

class RunnerFixture:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / 'project with spaces'
        self.project.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        subprocess.run(['git', '-C', str(self.project), 'config', 'user.email', 'test@example.com'], check=True)
        subprocess.run(['git', '-C', str(self.project), 'config', 'user.name', 'Test'], check=True)
        (self.project / 'tracked').write_text('original\n')
        subprocess.run(['git', '-C', str(self.project), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.project), 'commit', '-qm', 'baseline'], check=True)
        (self.project / 'tracked').write_text('user edit\n')
        (self.project / 'untracked').write_text('user file')
        self.record = self.root / 'record'
        self.plan = self.root / 'plan.txt'
        self.plan.write_text('task plan')
        self.tasks = self.root / 'tasks.json'
        self.tasks.write_text(json.dumps({'version': 1, 'tasks': [{'id': 't1', 'title': '标题', 'goal': '目标', 'targets': ['tracked'], 'depends_on': [], 'steps': ['修改文件'], 'acceptance': ['正确'], 'verification': [{'command': 'test -f tracked', 'expected': '成功'}]}]}, ensure_ascii=False))
        self.handoff = self.root / 'handoff.txt'
        self.handoff.write_text('literal $HOME `test` 中文\n')
        self.fake = self.root / 'fake'
        self.fake.write_text('#!/usr/bin/env python3\nimport sys,json\na=sys.argv[1:]\nif a[0]=="models": print("codefree/GLM-5.3-TokenPlan")\nelif a[0]=="session": print(json.dumps([{ "id":"session-1", "title":"task title"}]))\nelse:\n open(' + repr(str(self.root / 'args')) + ',"w").write(json.dumps(a))\n open(' + repr(str(self.root / 'input')) + ',"w").write(sys.stdin.read())\n print(json.dumps({"type":"text","sessionID":"session-1"}))\n')
        self.fake.chmod(0o755)
    def tearDown(self): self.tmp.cleanup()
    def call(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(RUNNER), *map(str,args)], text=True, capture_output=True)
        if ok: self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        else: self.assertNotEqual(result.returncode, 0, result.stdout)
        return json.loads(result.stdout)
    def prepare(self):
        return self.call('prepare','--record',self.record,'--project',self.project,'--title','task title','--plan',self.plan,'--tasks-file',self.tasks,'--criteria','criteria','--authorization','scope','--verify','test')
class RunnerTests(RunnerFixture, unittest.TestCase):
    def test_first_run_title_stdin_and_resume(self):
        self.prepare()
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        args=json.loads((self.root/'args').read_text())
        self.assertEqual(args[args.index('--title')+1], 'task title')
        self.assertIn('task plan', (self.root/'input').read_text())
        self.assertIn('修改文件', (self.root/'input').read_text())
        self.assertIn(self.handoff.read_text(), (self.root/'input').read_text())
        self.call('record-review','--record',self.record,'--result','failed','--evidence','failure','--progress','yes','--baseline-reviewed')
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        args=json.loads((self.root/'args').read_text())
        self.assertEqual(args[args.index('--session')+1], 'session-1')
        self.assertNotIn('--title',args)
    def test_external_change_blocks_next_run(self):
        self.prepare()
        (self.project/'tracked').write_text('concurrent edit')
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)
        self.assertFalse((self.root/'args').exists())

    def test_empty_tasks_rejected_before_dispatch(self):
        self.tasks.write_text('{"version": 1, "tasks": []}')
        self.call('prepare','--record',self.record,'--project',self.project,'--title','task title','--plan',self.plan,'--tasks-file',self.tasks,'--criteria','criteria','--authorization','scope','--verify','test',ok=False)
        self.assertFalse((self.root/'args').exists())

    def test_invalid_task_fields_and_dependencies_are_rejected(self):
        original = json.loads(self.tasks.read_text())
        for mutation in ('missing', 'duplicate', 'dependency'):
            data = json.loads(json.dumps(original))
            if mutation == 'missing': del data['tasks'][0]['steps']
            if mutation == 'duplicate': data['tasks'].append(dict(data['tasks'][0]))
            if mutation == 'dependency': data['tasks'][0]['depends_on'] = ['later']
            self.tasks.write_text(json.dumps(data))
            self.call('prepare','--record',self.record,'--project',self.project,'--title','task title','--plan',self.plan,'--tasks-file',self.tasks,'--criteria','criteria','--authorization','scope','--verify','test',ok=False)

    def test_resume_sends_only_feedback(self):
        self.prepare()
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.call('record-review','--record',self.record,'--result','failed','--evidence','failure','--progress','yes','--baseline-reviewed')
        self.handoff.write_text('T1: fix and retest')
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.assertEqual((self.root/'input').read_text(), 'T1: fix and retest')

    def test_missing_handoff_does_not_consume_round(self):
        self.prepare()
        self.call('run','--record',self.record,'--handoff',self.root/'missing','--cli',self.fake,ok=False)
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)

    def test_changed_plan_keeps_original_context(self):
        self.prepare()
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.call('record-review','--record',self.record,'--result','failed','--evidence','failure','--progress','yes','--baseline-reviewed')
        self.prepare()
        self.handoff.write_text('T1 feedback')
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.assertIn('literal $HOME', (self.root/'input').read_text())
        self.assertIn('T1 feedback', (self.root/'input').read_text())

    def test_runner_emits_only_summary_after_delayed_execution(self):
        self.prepare()
        self.fake.write_text(self.fake.read_text().replace('else:\n open(', 'else:\n import time\n time.sleep(1)\n open('))
        proc = subprocess.Popen([sys.executable, str(RUNNER), 'run', '--record', str(self.record), '--handoff', str(self.handoff), '--cli', str(self.fake)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(select.select([proc.stdout], [], [], 0.4)[0], [])
        stdout, stderr = proc.communicate(timeout=10)
        self.assertEqual(proc.returncode, 0, stderr.decode())
        self.assertTrue(json.loads(stdout)['ok'])
    def test_record_outside_project_and_baseline(self):
        self.prepare()
        state=self.call('status','--record',self.record)
        self.assertEqual(state['round'],0)
        self.assertTrue((self.record/'snapshots'/'baseline'/'files'/'untracked').exists())
        self.call('prepare','--record',self.project/'record','--project',self.project,'--title','x','--plan',self.plan,'--tasks-file',self.tasks,'--criteria','c','--authorization','a','--verify','v',ok=False)
    def test_wrong_session_title_fails(self):
        self.prepare()
        self.fake.write_text(self.fake.read_text().replace('"title":"task title"', '"title":"wrong"'))
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)
        self.assertTrue(self.call('status','--record',self.record)['last_run']['issues'])

    def test_failed_run_blocks_automatic_new_session(self):
        self.prepare()
        self.fake.write_text(self.fake.read_text().replace('print(json.dumps({"type":"text","sessionID":"session-1"}))', 'print(json.dumps({"type":"error","sessionID":"session-1"}))'))
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)
        self.call('record-review','--record',self.record,'--result','blocked','--evidence','error event','--progress','no','--baseline-reviewed')
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)
        self.assertEqual(self.call('status','--record',self.record)['round'], 1)

    def test_model_mismatch_is_not_replaced(self):
        self.prepare()
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,'--model','missing',ok=False)
        self.assertFalse((self.root/'args').exists())

    def test_rebuild_requires_evidence_and_titles_new_session(self):
        self.prepare()
        original = self.fake.read_text()
        self.fake.write_text(original.replace('"title":"task title"', '"title":"wrong"'))
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)
        self.call('record-review','--record',self.record,'--result','blocked','--evidence','wrong title','--progress','no','--baseline-reviewed')
        self.fake.write_text(original.replace('"title":"task title"', '"title":"task title · 恢复 1"'))
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,'--rebuild',ok=False)
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,'--rebuild','--recovery-evidence','session confirmed unavailable')
        args=json.loads((self.root/'args').read_text())
        self.assertEqual(args[args.index('--title')+1], 'task title · 恢复 1')

    def test_failed_resume_can_retry_same_session_after_review(self):
        self.prepare()
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.call('record-review','--record',self.record,'--result','failed','--evidence','needs fix','--progress','yes','--baseline-reviewed')
        original=self.fake.read_text()
        self.fake.write_text(original.replace('print(json.dumps({"type":"text","sessionID":"session-1"}))', 'print(json.dumps({"type":"error","sessionID":"session-1"}))'))
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)
        self.call('record-review','--record',self.record,'--result','blocked','--evidence','temporary failure','--progress','no','--baseline-reviewed')
        self.fake.write_text(original)
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,'--retry','--recovery-evidence','failure cleared')
        args=json.loads((self.root/'args').read_text())
        self.assertEqual(args[args.index('--session')+1], 'session-1')

    def test_user_staged_change_removal_blocks_review(self):
        subprocess.run(['git','-C',str(self.project),'add','tracked'],check=True)
        self.prepare()
        original=self.fake.read_text()
        original=original.replace('else:\n open(', 'else:\n import subprocess\n subprocess.run(["git", "-C", ' + repr(str(self.project)) + ', "reset", "-q", "HEAD", "--", "tracked"], check=True)\n open(')
        self.fake.write_text(original)
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.call('record-review','--record',self.record,'--result','passed','--evidence','ignored stage','--progress','yes','--baseline-reviewed',ok=False)

    def test_user_untracked_deletion_blocks_review(self):
        self.prepare()
        original=self.fake.read_text()
        original=original.replace('else:\n open(', 'else:\n import os\n os.unlink(' + repr(str(self.project/'untracked')) + ')\n open(')
        self.fake.write_text(original)
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.call('record-review','--record',self.record,'--result','passed','--evidence','ignored deletion','--progress','yes','--baseline-reviewed',ok=False)

    def test_project_lock_blocks_other_tasks(self):
        self.prepare()
        lockdir=Path(tempfile.gettempdir()) / ('codefree-locks-%d' % os.getuid())
        lockname='project-' + hashlib.sha256(os.fsencode(str(self.project.resolve()))).hexdigest()
        with (lockdir/lockname).open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)
        self.assertFalse((self.root/'args').exists())

    def test_plan_versions_and_review_gate(self):
        self.prepare()
        self.plan.write_text('revised plan')
        self.prepare()
        self.assertEqual(self.call('status','--record',self.record)['plan_version'], 2)
        self.assertEqual((self.record/'plans'/'plan-001.txt').read_text(), 'task plan')
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.call('record-review','--record',self.record,'--result','passed','--evidence','looks ok','--progress','yes',ok=False)
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)

    def test_staged_and_unstaged_baseline(self):
        subprocess.run(['git','-C',str(self.project),'add','tracked'],check=True)
        (self.project/'tracked').write_text('user edit\nmore user edit\n')
        self.prepare()
        base=self.record/'snapshots'/'baseline'
        self.assertIn(b'user edit', (base/'index.diff').read_bytes())
        self.assertIn(b'more user edit', (base/'worktree.diff').read_bytes())
        self.assertEqual((base/'files'/'tracked').read_text(), 'user edit\nmore user edit\n')

    def test_reconcile_dead_process_requires_evidence(self):
        self.prepare()
        state=json.loads((self.record/'state.json').read_text())
        state['round']=1
        state['process']={'pid': None,'round': 1}
        (self.record/'state.json').write_text(json.dumps(state))
        self.call('status','--record',self.record,'--reconcile',ok=False)
        self.call('status','--record',self.record,'--reconcile','--evidence','confirmed no process','--confirmed-no-process')
        state=self.call('status','--record',self.record)
        self.assertIsNone(state['process'])
        self.assertTrue(state['last_run']['issues'])
        self.assertEqual(state['phase'], 'awaiting_review')
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,'--rebuild','--recovery-evidence','lost',ok=False)

    def test_three_no_progress_stops(self):
        self.prepare()
        for _ in range(3):
            self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
            self.call('record-review','--record',self.record,'--result','failed','--evidence','unchanged','--progress','no','--baseline-reviewed')
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)

class ConstraintTests(RunnerFixture, unittest.TestCase):
    def test_completed_task_cannot_run_again(self):
        self.prepare()
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.call('record-review','--record',self.record,'--result','passed','--evidence','ok','--progress','yes','--baseline-reviewed')
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)

    def test_unreviewed_plan_cannot_change(self):
        self.prepare()
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.call('prepare','--record',self.record,'--project',self.project,'--title','task title','--plan',self.plan,'--tasks-file',self.tasks,'--criteria','x','--authorization','x','--verify','x',ok=False)

    def test_review_rejects_external_change(self):
        self.prepare()
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        (self.project/'tracked').write_text('external change')
        self.call('record-review','--record',self.record,'--result','passed','--evidence','ok','--progress','yes','--baseline-reviewed',ok=False)

    def test_tampered_plan_is_rejected(self):
        self.prepare()
        (self.record / 'plans' / 'plan-001.txt').write_text('tampered')
        self.call('run', '--record', self.record, '--handoff', self.handoff, '--cli', self.fake, ok=False)
        self.assertFalse((self.root / 'args').exists())

    def test_tampered_tasks_are_rejected(self):
        self.prepare()
        path = self.record / 'plans' / 'tasks-001.json'
        data = json.loads(path.read_text())
        data['tasks'][0]['steps'] = ['tampered']
        path.write_text(json.dumps(data))
        self.call('run', '--record', self.record, '--handoff', self.handoff, '--cli', self.fake, ok=False)
        self.assertFalse((self.root / 'args').exists())

    def test_disabled_auto_refuses_dispatch(self):
        self.call('prepare', '--record', self.record, '--project', self.project, '--title', 'task title', '--plan', self.plan, '--tasks-file', self.tasks, '--criteria', 'criteria', '--authorization', 'scope', '--verify', 'test', '--no-auto-approve')
        self.call('run', '--record', self.record, '--handoff', self.handoff, '--cli', self.fake, ok=False)
        self.assertFalse((self.root / 'args').exists())

    def test_unblock_allows_reviewed_blocked_task_to_resume(self):
        self.prepare()
        self.call('run', '--record', self.record, '--handoff', self.handoff, '--cli', self.fake)
        self.call('record-review', '--record', self.record, '--result', 'blocked', '--evidence', 'waiting', '--progress', 'no', '--baseline-reviewed')
        self.call('unblock', '--record', self.record, '--evidence', 'resolved')
        self.call('run', '--record', self.record, '--handoff', self.handoff, '--cli', self.fake)

    def test_outside_target_rejected(self):
        data = json.loads(self.tasks.read_text())
        data['tasks'][0]['targets'] = ['../../outside']
        self.tasks.write_text(json.dumps(data))
        self.call('prepare', '--record', self.record, '--project', self.project, '--title', 'task title', '--plan', self.plan, '--tasks-file', self.tasks, '--criteria', 'criteria', '--authorization', 'scope', '--verify', 'test', ok=False)

    def test_protected_ignored_file_change_blocks_pass(self):
        (self.project/'.gitignore').write_text('secret.env\n')
        (self.project/'secret.env').write_text('original secret')
        paths = self.root/'protected.txt'
        paths.write_text('secret.env\n')
        self.call('prepare','--record',self.record,'--project',self.project,'--title','task title','--plan',self.plan,'--tasks-file',self.tasks,'--criteria','c','--authorization','a','--verify','v','--protect-paths-file',paths)
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        (self.project/'secret.env').write_text('changed secret')
        self.call('record-review','--record',self.record,'--result','passed','--evidence','review','--progress','yes','--baseline-reviewed',ok=False)
        self.call('record-review','--record',self.record,'--result','blocked','--evidence','changed','--progress','no','--baseline-reviewed')
        self.assertNotIn('original secret', '\n'.join(p.read_text(errors='ignore') for p in self.record.rglob('*') if p.is_file()))

    def test_ignored_target_is_snapshotted_without_contents(self):
        (self.project/'.gitignore').write_text('local/\n')
        (self.project/'local').mkdir()
        (self.project/'local'/'config').write_text('sensitive')
        data=json.loads(self.tasks.read_text()); data['tasks'][0]['targets']=['local']
        self.tasks.write_text(json.dumps(data))
        self.prepare()
        manifest=json.loads((self.record/'snapshots'/'baseline'/'manifest.json').read_text())
        self.assertIn('local/config', manifest)
        self.assertFalse((self.record/'snapshots'/'baseline'/'files'/'local'/'config').exists())
        (self.project/'local'/'config').write_text('changed')
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)

    def test_version_files_are_never_overwritten(self):
        self.prepare()
        path=self.record/'plans'/'plan-002.txt'
        path.write_text('existing')
        result=self.call('prepare','--record',self.record,'--project',self.project,'--title','task title','--plan',self.plan,'--tasks-file',self.tasks,'--criteria','c','--authorization','a','--verify','v')
        self.assertEqual(path.read_text(),'existing')
        self.assertEqual(result['plan_version'],3)

    def test_protected_tracked_file_not_copied(self):
        (self.project/'secret').write_text('private content')
        subprocess.run(['git','-C',str(self.project),'add','secret'],check=True)
        protected=self.root/'protect'; protected.write_text('secret\n')
        self.call('prepare','--record',self.record,'--project',self.project,'--title','task title','--plan',self.plan,'--tasks-file',self.tasks,'--criteria','c','--authorization','a','--verify','v','--protect-paths-file',protected)
        for path in self.record.rglob('*'):
            if path.is_file(): self.assertNotIn(b'private content', path.read_bytes())

    def test_launch_failure_can_be_reviewed(self):
        self.prepare()
        self.fake.write_text(self.fake.read_text().replace('else:\n open(', 'else:\n open('))
        # A valid models command followed by an invalid interpreter on launch.
        self.fake.write_text(self.fake.read_text().replace('else:\n open(', 'else:\n import os\n os.unlink(__file__)\n open('))
        # Remove the executable only after model discovery.
        content=self.fake.read_text().replace('if a[0]=="models": print("codefree/GLM-5.3-TokenPlan")', 'if a[0]=="models":\n print("codefree/GLM-5.3-TokenPlan")\n import os\n os.unlink(__file__)')
        self.fake.write_text(content)
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)
        state=self.call('status','--record',self.record)
        self.assertEqual(state['phase'],'awaiting_review')
        self.assertIsNone(state['process'])
        self.call('record-review','--record',self.record,'--result','blocked','--evidence','launch failed','--progress','no','--baseline-reviewed')

    def test_protected_file_restored_can_unblock(self):
        (self.project/'secret').write_text('original')
        subprocess.run(['git','-C',str(self.project),'add','secret'],check=True)
        protected=self.root/'protect'; protected.write_text('secret\n')
        self.call('prepare','--record',self.record,'--project',self.project,'--title','task title','--plan',self.plan,'--tasks-file',self.tasks,'--criteria','c','--authorization','a','--verify','v','--protect-paths-file',protected)
        self.fake.write_text(self.fake.read_text().replace('else:\n open(', 'else:\n open('+repr(str(self.project/'secret'))+',"w").write("changed")\n open('))
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.call('record-review','--record',self.record,'--result','blocked','--evidence','changed','--progress','no','--baseline-reviewed')
        (self.project/'secret').write_text('original')
        self.call('unblock','--record',self.record,'--evidence','restored')

    def test_blocked_review_records_staged_change(self):
        subprocess.run(['git','-C',str(self.project),'add','tracked'],check=True)
        self.prepare()
        self.fake.write_text(self.fake.read_text().replace('else:\n open(', 'else:\n import subprocess\n subprocess.run(["git","-C",'+repr(str(self.project))+',"reset","-q","HEAD","--","tracked"],check=True)\n open('))
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.call('record-review','--record',self.record,'--result','blocked','--evidence','stage changed','--progress','no','--baseline-reviewed')

    def test_reconcile_retains_snapshot_failure_evidence(self):
        self.prepare()
        state=json.loads((self.record/'state.json').read_text())
        state['round']=1; state['process']={'pid':None,'round':1}
        state['last_run']={'round_dir':str(self.record.resolve()/'rounds'/'001'),'exit_code':4,'issues':['snapshot failed: example']}
        (self.record/'state.json').write_text(json.dumps(state))
        self.call('status','--record',self.record,'--reconcile','--evidence','confirmed','--confirmed-no-process')
        state=self.call('status','--record',self.record)
        self.assertEqual(state['last_run']['exit_code'],4)
        self.assertIn('snapshot failed: example',state['last_run']['issues'])

    def test_initial_prepare_failure_leaves_no_partial_record(self):
        self.tasks.write_text(json.dumps({'version':1,'tasks':[{'id':'1','title':'x','goal':'x','targets':['tracked'],'depends_on':[],'steps':['x'],'acceptance':['x'],'verification':[{'command':'x','expected':'x'}]}]}))
        protected=self.root/'protect'; protected.write_text('directory\n')
        (self.project/'directory').mkdir()
        self.call('prepare','--record',self.record,'--project',self.project,'--title','task title','--plan',self.plan,'--tasks-file',self.tasks,'--criteria','c','--authorization','a','--verify','v','--protect-paths-file',protected,ok=False)
        self.assertFalse(self.record.exists())
        self.prepare()

    def test_new_protection_preserves_staged_baseline_comparison(self):
        (self.project/'secret').write_text('secret')
        subprocess.run(['git','-C',str(self.project),'add','secret'],check=True)
        self.prepare()
        protected=self.root/'protect'; protected.write_text('secret\n')
        self.call('prepare','--record',self.record,'--project',self.project,'--title','task title','--plan',self.plan,'--tasks-file',self.tasks,'--criteria','c','--authorization','a','--verify','v','--protect-paths-file',protected)
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.call('record-review','--record',self.record,'--result','passed','--evidence','ok','--progress','yes','--baseline-reviewed')

    def test_snapshot_failure_preserves_exit_and_reconciles(self):
        self.prepare()
        self.fake.write_text(self.fake.read_text().replace('else:\n open(', 'else:\n import os\n os.unlink('+repr(str(self.project/'tracked'))+')\n os.mkdir('+repr(str(self.project/'tracked'))+')\n open('))
        result=self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)
        self.assertTrue(result['reconcile_required'])
        state=self.call('status','--record',self.record)
        self.assertEqual(state['last_run']['exit_code'],0)
        (self.project/'tracked').rmdir()
        (self.project/'tracked').write_text('user edit\n')
        self.call('status','--record',self.record,'--reconcile','--evidence','restored')
        state=self.call('status','--record',self.record)
        self.assertTrue(any('snapshot failed:' in x for x in state['last_run']['issues']))

    def test_tampered_artifacts_block_review_and_prepare(self):
        for name in ('plan-001.txt', 'tasks-001.json'):
            with self.subTest(name=name):
                if self.record.exists():
                    import shutil; shutil.rmtree(self.record)
                self.prepare()
                self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
                (self.record/'plans'/name).write_text('tampered')
                self.call('record-review','--record',self.record,'--result','passed','--evidence','ok','--progress','yes','--baseline-reviewed',ok=False)
                self.call('record-review','--record',self.record,'--result','blocked','--evidence','tampered','--progress','no','--baseline-reviewed')
                self.call('unblock','--record',self.record,'--evidence','fixed',ok=False)
                self.call('prepare','--record',self.record,'--project',self.project,'--title','task title','--plan',self.plan,'--tasks-file',self.tasks,'--criteria','c','--authorization','a','--verify','v',ok=False)

    def test_incremental_target_symlink_rejected(self):
        data=json.loads(self.tasks.read_text()); data['tasks'][0]['targets']=['future/new']; self.tasks.write_text(json.dumps(data))
        self.prepare()
        code='else:\n import os\n os.symlink('+repr(str(self.root))+','+repr(str(self.project/'future'))+')\n open('
        original=self.fake.read_text(); self.fake.write_text(original.replace('else:\n open(',code))
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.call('record-review','--record',self.record,'--result','passed','--evidence','ok','--progress','yes','--baseline-reviewed',ok=False)
        self.call('record-review','--record',self.record,'--result','failed','--evidence','bad target','--progress','yes','--baseline-reviewed')
        self.fake.write_text(original)
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)
        self.assertEqual(self.call('status','--record',self.record)['round'],1)

    def test_legacy_without_tasks_digest_can_reprepare(self):
        self.prepare()
        path=self.record/'state.json'; state=json.loads(path.read_text()); del state['tasks_sha256']; path.write_text(json.dumps(state))
        self.prepare()
        state=self.call('status','--record',self.record)
        self.assertEqual(state['plan_version'],2)
        self.assertTrue(state['migration_history'])
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)

    def test_symlink_plan_artifact_is_rejected(self):
        self.prepare()
        path=self.record/'plans'/'plan-001.txt'; path.unlink(); path.symlink_to(self.plan)
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)
        self.assertFalse((self.root/'args').exists())

    def test_fifo_plan_artifact_is_rejected_without_hanging(self):
        self.prepare()
        path=self.record/'plans'/'plan-001.txt'; path.unlink(); os.mkfifo(str(path))
        result=subprocess.run([sys.executable,str(RUNNER),'run','--record',str(self.record),'--handoff',str(self.handoff),'--cli',str(self.fake)],capture_output=True,text=True,timeout=5)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.root/'args').exists())

    def test_blocked_review_records_unsafe_target_snapshot(self):
        import shutil
        directory=self.project/'directory'; directory.mkdir(); (directory/'file').write_text('tracked')
        subprocess.run(['git','-C',str(self.project),'add','directory/file'],check=True)
        data=json.loads(self.tasks.read_text()); data['tasks'][0]['targets']=['directory/file']; self.tasks.write_text(json.dumps(data))
        self.prepare()
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        shutil.rmtree(directory); directory.symlink_to(self.root, target_is_directory=True)
        self.call('record-review','--record',self.record,'--result','blocked','--evidence','unsafe','--progress','no','--baseline-reviewed')
        state=self.call('status','--record',self.record)
        self.assertIn('snapshot_error',state['last_review'])

    def test_auto_is_default(self):
        self.prepare()
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.assertIn('--auto',json.loads((self.root/'args').read_text()))

if __name__ == '__main__': unittest.main()
