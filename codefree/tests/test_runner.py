import json
import fcntl
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RUNNER = Path(__file__).parents[1] / 'scripts' / 'runner.py'

class RunnerTests(unittest.TestCase):
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
        return self.call('prepare','--record',self.record,'--project',self.project,'--title','task title','--plan',self.plan,'--criteria','criteria','--authorization','scope','--verify','test')
    def test_first_run_title_stdin_and_resume(self):
        self.prepare()
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        args=json.loads((self.root/'args').read_text())
        self.assertEqual(args[args.index('--title')+1], 'task title')
        self.assertEqual((self.root/'input').read_text(), self.handoff.read_text())
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
    def test_record_outside_project_and_baseline(self):
        self.prepare()
        state=self.call('status','--record',self.record)
        self.assertEqual(state['round'],0)
        self.assertTrue((self.record/'snapshots'/'baseline'/'files'/'untracked').exists())
        self.call('prepare','--record',self.project/'record','--project',self.project,'--title','x','--plan',self.plan,'--criteria','c','--authorization','a','--verify','v',ok=False)
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

    def test_three_no_progress_stops(self):
        self.prepare()
        for _ in range(3):
            self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
            self.call('record-review','--record',self.record,'--result','failed','--evidence','unchanged','--progress','no','--baseline-reviewed')
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)

if __name__ == '__main__': unittest.main()

class ConstraintTests(RunnerTests):
    def test_completed_task_cannot_run_again(self):
        self.prepare()
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.call('record-review','--record',self.record,'--result','passed','--evidence','ok','--progress','yes','--baseline-reviewed')
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake,ok=False)

    def test_unreviewed_plan_cannot_change(self):
        self.prepare()
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.call('prepare','--record',self.record,'--project',self.project,'--title','task title','--plan',self.plan,'--criteria','x','--authorization','x','--verify','x',ok=False)

    def test_review_rejects_external_change(self):
        self.prepare()
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        (self.project/'tracked').write_text('external change')
        self.call('record-review','--record',self.record,'--result','passed','--evidence','ok','--progress','yes','--baseline-reviewed',ok=False)

    def test_auto_is_default(self):
        self.prepare()
        self.call('run','--record',self.record,'--handoff',self.handoff,'--cli',self.fake)
        self.assertIn('--auto',json.loads((self.root/'args').read_text()))
