import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "dev_work.py"
SPEC = importlib.util.spec_from_file_location("dev_work", SCRIPT)
DEV_WORK = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DEV_WORK
SPEC.loader.exec_module(DEV_WORK)


class DevWorkTests(unittest.TestCase):
    def _complete_low_risk_item(self, path):
        text = path.read_text(encoding="utf-8").replace("WORK_ITEM:REPLACE", "已完成证据")
        text = text.replace("- [ ] 已完成证据", "- [x] 已完成")
        text = text.replace("**状态**：OPEN", "**状态**：VERIFIED")
        text = text.replace("### VER-001 — 验证项\n\n- **关联需求**：REQ-001\n- **状态**：VERIFIED", "### VER-001 — 验证项\n\n- **关联需求**：REQ-001\n- **状态**：PASS")
        text = text.replace("### DEC-001 — 待决事项\n\n- **状态**：VERIFIED", "### DEC-001 — 待决事项\n\n- **状态**：RESOLVED")
        text = text.replace("### RSK-001 — 风险摘要\n\n- **状态**：VERIFIED", "### RSK-001 — 风险摘要\n\n- **状态**：CLOSED")
        text = text.replace("### REV-001 — 审查结论\n\n- **状态**：VERIFIED", "### REV-001 — 审查结论\n\n- **状态**：PASS")
        for dimension in DEV_WORK.IMPACT_DIMENSIONS:
            text = text.replace(f"| {dimension} | 已完成证据 |", f"| {dimension} | none |")
        text = text.replace("**是否需要用户回归**：已完成证据", "**是否需要用户回归**：否")
        text = text.replace("**用户回归结果**：pending", "**用户回归结果**：not-required")
        path.write_text(text, encoding="utf-8")

    def test_init_creates_work_item_and_index(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "退款去重", "bugfix", "medium", ("order-refund",))
            self.assertTrue(path.exists())
            self.assertIn("WORK-20260906-001", (repo / "docs" / "work-items" / "index.md").read_text())

    def test_clarification_gate_blocks_blocker(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "退款", "feature", "low", ())
            path.write_text(path.read_text(encoding="utf-8").replace("**状态**：OPEN", "**状态**：BLOCKER"), encoding="utf-8")
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "clarified")
            self.assertTrue(any("BLOCKER" in error for error in errors), errors)

    def test_high_risk_handoff_requires_review_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            DEV_WORK.init_work_item(repo, "WORK-20260906-001", "迁移", "change", "high", ())
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "handoff-ready")
            self.assertTrue(any("review" in error.lower() for error in errors), errors)
            self.assertTrue(any("rollback" in error.lower() for error in errors), errors)

    def test_close_requires_completed_user_regression(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            DEV_WORK.init_work_item(repo, "WORK-20260906-001", "退款", "bugfix", "medium", ())
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "closed")
            self.assertTrue(any("regression" in error.lower() for error in errors), errors)

    def test_rejects_jump_over_state_machine(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            DEV_WORK.init_work_item(repo, "WORK-20260906-001", "退款", "feature", "low", ())
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "implementing")
            self.assertTrue(any("invalid transition" in error for error in errors), errors)

    def test_low_risk_item_can_complete_all_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档修订", "change", "low", ())
            self._complete_low_risk_item(path)
            for target in ("clarified", "planned", "implementing", "verifying", "handoff-ready", "closed"):
                self.assertEqual([], DEV_WORK.transition_work_item(repo, "WORK-20260906-001", target))
            self.assertEqual("closed", DEV_WORK.find_work_item(repo, "WORK-20260906-001").metadata["work-status"])

    def test_bugfix_handoff_requires_root_cause_and_regression_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            DEV_WORK.init_work_item(repo, "WORK-20260906-001", "重复退款", "bugfix", "low", ())
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "handoff-ready")
            self.assertTrue(any("根因" in error for error in errors), errors)
            self.assertTrue(any("回归保护" in error for error in errors), errors)

    def test_handoff_rejects_unknown_regression_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8").replace("**是否需要用户回归**：否", "**是否需要用户回归**：可能")
            path.write_text(text, encoding="utf-8")
            for target in ("clarified", "planned", "implementing", "verifying"):
                self.assertEqual([], DEV_WORK.transition_work_item(repo, "WORK-20260906-001", target))
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "handoff-ready")
            self.assertTrue(any("regression decision" in error for error in errors), errors)

    def test_planning_checks_each_requirement_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8").replace(
                "## 变更影响",
                "### REQ-002 — 未完成\n\n- **需求**：WORK_ITEM:REPLACE\n- **验收标准**：WORK_ITEM:REPLACE\n- **实现证据**：WORK_ITEM:REPLACE\n- **验证证据**：WORK_ITEM:REPLACE\n- **状态**：OPEN\n\n## 变更影响",
            )
            path.write_text(text, encoding="utf-8")
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "clarified")
            self.assertEqual([], errors)
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "planned")
            self.assertTrue(any("REQ-002" in error for error in errors), errors)

    def test_high_risk_handoff_requires_release_and_risk_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            DEV_WORK.init_work_item(repo, "WORK-20260906-001", "迁移", "change", "high", ())
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "handoff-ready")
            self.assertTrue(any("release" in error.lower() for error in errors), errors)
            self.assertTrue(any("open risk" in error.lower() for error in errors), errors)

    def test_blocked_item_cannot_resume_at_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            DEV_WORK.init_work_item(repo, "WORK-20260906-001", "退款", "feature", "low", ())
            path = DEV_WORK.find_work_item(repo, "WORK-20260906-001").path
            text = path.read_text(encoding="utf-8").replace("<!-- work-status: intake -->", "<!-- work-status: blocked -->")
            path.write_text(text, encoding="utf-8")
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "handoff-ready")
            self.assertTrue(any("invalid transition" in error for error in errors), errors)

    def test_open_decision_and_risk_require_confirmation_path_at_planning(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8")
            text = text.replace("### DEC-001 — 待决事项\n\n- **状态**：RESOLVED", "### DEC-001 — 待决事项\n\n- **状态**：OPEN")
            text = text.replace("**确认路径**：已完成证据", "**确认路径**：WORK_ITEM:REPLACE", 1)
            path.write_text(text, encoding="utf-8")
            self.assertEqual([], DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "clarified"))
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "planned")
            self.assertTrue(any("confirmation path" in error for error in errors), errors)

    def test_database_impact_requires_high_risk(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "数据变更", "change", "low", ())
            self._complete_low_risk_item(path)
            path.write_text(path.read_text(encoding="utf-8").replace("| Database | none |", "| Database | affected |"), encoding="utf-8")
            self.assertEqual([], DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "clarified"))
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "planned")
            self.assertTrue(any("minimum risk" in error for error in errors), errors)

    def test_empty_plan_and_open_verification_block_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8").replace("- [x] 已完成", "")
            text = text.replace("## 验证\n\n### VER-001", "## 验证\n\n### VER-001").replace("**状态**：VERIFIED", "**状态**：OPEN", 1)
            path.write_text(text, encoding="utf-8")
            for target in ("clarified", "planned"):
                self.assertEqual([], DEV_WORK.transition_work_item(repo, "WORK-20260906-001", target))
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "implementing")
            self.assertTrue(any("plan" in error.lower() for error in errors), errors)

    def test_rejects_duplicate_metadata_and_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            text = path.read_text(encoding="utf-8").replace("<!-- work-status: intake -->", "<!-- work-status: intake -->\n<!-- work-status: closed -->")
            text += "\n## 决策\n\n### DEC-999\n\n- **状态**：BLOCKER\n"
            path.write_text(text, encoding="utf-8")
            errors = DEV_WORK.validate_work_item(repo, "WORK-20260906-001")
            self.assertTrue(any("duplicate metadata" in error for error in errors), errors)
            self.assertTrue(any("duplicate heading" in error for error in errors), errors)
