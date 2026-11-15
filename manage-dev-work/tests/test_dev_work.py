import importlib.util
import re
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
FEATURE_SPEC = importlib.util.spec_from_file_location(
    "feature_docs_for_dev_tests", SKILL_ROOT.parent / "manage-feature-docs" / "scripts" / "feature_docs.py"
)
FEATURE_DOCS = importlib.util.module_from_spec(FEATURE_SPEC)
sys.modules[FEATURE_SPEC.name] = FEATURE_DOCS
FEATURE_SPEC.loader.exec_module(FEATURE_DOCS)


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

    def _to_handoff(self, repo, work_id):
        for target in ("clarified", "planned", "implementing", "verifying"):
            self.assertEqual([], DEV_WORK.transition_work_item(repo, work_id, target))
        path = DEV_WORK.find_work_item(repo, work_id).path
        text = path.read_text()
        basis = DEV_WORK.read_work_item(path).metadata.get("verification-basis", "")
        if basis.startswith("impl-v2 "):
            path.write_text(text.replace("**证据基线**：pending", f"**证据基线**：{basis}"))
        return DEV_WORK.transition_work_item(repo, work_id, "handoff-ready")

    def test_rejects_duplicate_record_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8").replace(
                "## 变更影响",
                "### REQ-001 — 重复需求\n\n- **需求**：第二个需求\n- **验收标准**：第二个验收\n- **实现证据**：实现\n- **验证证据**：验证\n- **状态**：VERIFIED\n\n## 变更影响",
            )
            path.write_text(text, encoding="utf-8")
            errors = DEV_WORK.validate_work_item(repo, "WORK-20260906-001")
            self.assertTrue(any("duplicate REQ ID" in error for error in errors), errors)

    def test_rejects_orphan_ver_requirement(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            path.write_text(
                path.read_text(encoding="utf-8").replace("**关联需求**：REQ-001", "**关联需求**：REQ-999"),
                encoding="utf-8",
            )
            errors = self._to_handoff(repo, "WORK-20260906-001")
            self.assertTrue(any("unknown requirement REQ-999" in error for error in errors), errors)

    def test_checks_every_verification_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            orphan = (
                "### VER-002 — 孤立验证\n\n- **关联需求**：REQ-999\n"
                "- **状态**：PASS\n- **证据**：孤立。\n\n"
            )
            path.write_text(
                path.read_text(encoding="utf-8").replace("## 验证\n\n### VER-001", "## 验证\n\n" + orphan + "### VER-001"),
                encoding="utf-8",
            )
            errors = self._to_handoff(repo, "WORK-20260906-001")
            self.assertTrue(any("unknown requirement REQ-999" in error for error in errors), errors)

    def test_missing_verification_blocks_without_parser_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            text = re.sub(r"### VER-001.*?(?=^## 代码审查)", "", path.read_text(encoding="utf-8"), flags=re.MULTILINE | re.DOTALL)
            path.write_text(text, encoding="utf-8")
            errors = self._to_handoff(repo, "WORK-20260906-001")
            self.assertTrue(any("requires a PASS VER" in error for error in errors), errors)

    def test_rejects_verification_without_requirement_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            path.write_text(
                path.read_text(encoding="utf-8").replace("**关联需求**：REQ-001", "**关联需求**："),
                encoding="utf-8",
            )
            errors = self._to_handoff(repo, "WORK-20260906-001")
            self.assertTrue(any("unknown requirement" in error for error in errors), errors)

    def test_rejects_deferred_requirement_with_missing_references(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8").replace(
                "- **状态**：VERIFIED\n- **延期依据**：不适用：未延期。\n- **后续工作**：不适用：未延期。",
                "- **状态**：DEFERRED\n- **延期依据**：DEC-999\n- **后续工作**：WORK-20990101-999",
                1,
            )
            path.write_text(text, encoding="utf-8")
            errors = self._to_handoff(repo, "WORK-20260906-001")
            self.assertTrue(any("decision DEC-999" in error for error in errors), errors)
            self.assertTrue(any("follow-up work WORK-20990101-999" in error for error in errors), errors)

    def test_deferred_requirement_requires_resolved_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8").replace(
                "- **状态**：VERIFIED\n- **延期依据**：不适用：未延期。\n- **后续工作**：不适用：未延期。",
                "- **状态**：DEFERRED\n- **延期依据**：DEC-001\n- **后续工作**：WORK-20260907-001",
                1,
            ).replace(
                "### DEC-001 — 待决事项\n\n- **状态**：RESOLVED",
                "### DEC-001 — 待决事项\n\n- **状态**：OPEN",
            )
            follow_up = repo / "docs" / "work-items" / "WORK-20260907-001.md"
            follow_up.write_text("placeholder", encoding="utf-8")
            path.write_text(text, encoding="utf-8")
            errors = DEV_WORK.gate_errors(DEV_WORK.read_work_item(path), "handoff-ready", repo)
            self.assertTrue(any("decision DEC-001" in error and "resolved" in error for error in errors), errors)

    def test_rejects_close_with_missing_feature_doc(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(
                repo, "WORK-20260906-001", "文档", "change", "low", ("missing-feature",)
            )
            self._complete_low_risk_item(path)
            errors = self._to_handoff(repo, "WORK-20260906-001")
            self.assertEqual([], errors)
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "closed")
            self.assertTrue(any("Feature Doc missing-feature" in error for error in errors), errors)

    def test_rejects_close_with_duplicate_feature_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            feature = repo / "docs" / "features" / "missing-feature.md"
            feature.parent.mkdir(parents=True)
            feature.write_text(
                "<!-- feature-id: missing-feature -->\n<!-- feature-id: missing-feature -->\n",
                encoding="utf-8",
            )
            path = DEV_WORK.init_work_item(
                repo, "WORK-20260906-001", "文档", "change", "low", ("missing-feature",)
            )
            self._complete_low_risk_item(path)
            self.assertEqual([], self._to_handoff(repo, "WORK-20260906-001"))
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "closed")
            self.assertTrue(any("duplicate metadata" in error for error in errors), errors)

    def test_rejects_close_with_fenced_fake_feature_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            feature = repo / "docs" / "features" / "missing-feature.md"
            feature.parent.mkdir(parents=True)
            feature.write_text("```markdown\n<!-- feature-id: missing-feature -->\n```\n", encoding="utf-8")
            path = DEV_WORK.init_work_item(
                repo, "WORK-20260906-001", "文档", "change", "low", ("missing-feature",)
            )
            self._complete_low_risk_item(path)
            self.assertEqual([], self._to_handoff(repo, "WORK-20260906-001"))
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "closed")
            self.assertTrue(any("Feature Doc missing-feature" in error and "feature ID not found" in error for error in errors), errors)

    def test_close_rejects_stale_feature_doc_in_git_repo(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            import subprocess

            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
            implementation = repo / "implementation.py"
            implementation.write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "implementation.py"], check=True)
            subprocess.run(
                [
                    "git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com",
                    "commit", "-m", "initial",
                ],
                check=True,
                capture_output=True,
            )
            feature = repo / "docs" / "features" / "sample-feature.md"
            feature.parent.mkdir(parents=True)
            feature.write_text(self._valid_feature_doc(FEATURE_DOCS.git_code_basis(repo)), encoding="utf-8")
            path = DEV_WORK.init_work_item(
                repo, "WORK-20260906-001", "文档", "change", "low", ("sample-feature",)
            )
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8").replace("**Feature Docs**：已完成证据", "**Feature Docs**：sample-feature")
            path.write_text(text, encoding="utf-8")
            implementation.write_text("value = 2\n", encoding="utf-8")
            self.assertEqual([], self._to_handoff(repo, "WORK-20260906-001"))
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "closed")
            self.assertTrue(any("worktree digest" in error for error in errors), errors)

    def _valid_feature_doc(self, basis):
        metadata = [
            "<!-- feature-id: sample-feature -->", "<!-- feature-title: 示例功能 -->", "<!-- feature-aliases:  -->",
            "<!-- feature-status: active -->", "<!-- feature-summary: 示例功能。 -->", "<!-- last-verified: 2026-09-11 -->",
            f"<!-- code-basis: {basis} -->",
        ]
        sections = {
            "快速上下文": "当前功能上下文。",
            "目标与边界": "### 目标\n功能目标。\n\n### 范围内\n当前范围。\n\n### 范围外\n无。\n\n### 不变量\n必须稳定。",
            "业务行为": "业务行为。", "架构与代码地图": "代码地图。", "API、事件与任务": "无。",
            "数据模型与迁移": "无。", "核心流程": "流程。", "异常与边界条件": "无。",
            "并发与幂等": "无。", "安全与权限": "无。", "配置与依赖": "无。", "可观测性与运维": "无。",
            "测试与验证": "### 已执行\n测试通过。\n\n### 未执行\n无。",
            "关键决策": "不适用：无长期决策。", "已知问题与后续工作": "不适用：无已知问题。",
            "变更记录": "### 2026-09-11 — 创建档案\n\n- **状态**：已完成\n- **变化**：创建。\n- **原因**：测试。\n- **兼容性**：无。\n- **验证**：测试。",
        }
        return "# 示例功能\n\n" + "\n".join(metadata) + "\n\n" + "\n\n".join(f"## {heading}\n\n{body}" for heading, body in sections.items()) + "\n"

    def test_ignores_heading_inside_fenced_code(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "## 实施记录", "```markdown\n```python\n## 风险\n```\n\n## 实施记录"
                ),
                encoding="utf-8",
            )
            errors = DEV_WORK.validate_work_item(repo, "WORK-20260906-001")
            self.assertEqual([], errors)

    def test_rejects_future_or_inverted_work_item_dates(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            text = path.read_text(encoding="utf-8")
            text = re.sub(r"<!-- created: .*? -->", "<!-- created: 2099-12-31 -->", text, count=1)
            text = re.sub(r"<!-- updated: .*? -->", "<!-- updated: 2026-01-01 -->", text, count=1)
            path.write_text(text, encoding="utf-8")
            errors = DEV_WORK.validate_work_item(repo, "WORK-20260906-001")
            self.assertTrue(any("created" in error and "future" in error for error in errors), errors)
            self.assertTrue(any("created" in error and "updated" in error for error in errors), errors)

    def test_rejects_stale_work_item_index(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            index = repo / "docs" / "work-items" / "index.md"
            index.write_text(index.read_text(encoding="utf-8").replace("文档", "旧标题"), encoding="utf-8")
            errors = DEV_WORK.validate_work_item(repo, "WORK-20260906-001")
            self.assertTrue(any("index is stale" in error for error in errors), errors)

    def test_rejects_work_item_metadata_outside_header(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            lines = path.read_text(encoding="utf-8").splitlines()
            metadata = [line for line in lines if line.startswith("<!-- ")]
            body = [line for line in lines if line not in metadata]
            path.write_text("\n".join(body + metadata) + "\n", encoding="utf-8")
            errors = DEV_WORK.validate_work_item(repo, "WORK-20260906-001")
            self.assertTrue(any("metadata block" in error for error in errors), errors)

    def test_resolved_decision_requires_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8")
            text = re.sub(
                r"### DEC-001.*?(?=^## 风险)",
                "### DEC-001 — 已定决策\n\n- **状态**：RESOLVED\n- **确认路径**：\n- **决定**：\n- **原因**：\n- **取舍**：\n- **证据**：\n\n",
                text,
                flags=re.MULTILINE | re.DOTALL,
            )
            path.write_text(text, encoding="utf-8")
            errors = self._to_handoff(repo, "WORK-20260906-001")
            self.assertTrue(any("decision" in error and "requires" in error for error in errors), errors)

    def test_pass_verification_requires_own_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            text = re.sub(
                r"(### VER-001.*?- \*\*证据\*\*)：已完成证据",
                r"\1：",
                path.read_text(encoding="utf-8"),
                count=1,
                flags=re.DOTALL,
            )
            path.write_text(text, encoding="utf-8")
            errors = self._to_handoff(repo, "WORK-20260906-001")
            self.assertTrue(any("VER-001" in error and "evidence" in error for error in errors), errors)

    def test_pass_review_requires_scope_and_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "medium", ())
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8")
            text = re.sub(r"### REV-001.*?(?=^## 发布与回滚)", "### REV-001 — 审查结论\n\n- **状态**：PASS\n- **范围**：\n- **证据**：\n\n", text, flags=re.MULTILINE | re.DOTALL)
            path.write_text(text, encoding="utf-8")
            errors = self._to_handoff(repo, "WORK-20260906-001")
            self.assertTrue(any("review" in error and "requires" in error for error in errors), errors)

    def test_rejects_duplicate_impact_dimension(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8").replace("| Database | none |", "| Database | none |\n| Database | affected |", 1)
            path.write_text(text, encoding="utf-8")
            self.assertEqual([], DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "clarified"))
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "planned")
            self.assertTrue(any("Database" in error and "exactly once" in error for error in errors), errors)

    def test_deferred_follow_up_must_be_a_valid_work_item(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8").replace(
                "- **状态**：VERIFIED\n- **延期依据**：不适用：未延期。\n- **后续工作**：不适用：未延期。",
                "- **状态**：DEFERRED\n- **延期依据**：DEC-001\n- **后续工作**：WORK-20260907-001",
                1,
            )
            text = text.replace("### DEC-001 — 待决事项\n\n- **状态**：RESOLVED", "### DEC-001 — 待决事项\n\n- **状态**：RESOLVED", 1)
            follow_up = repo / "docs" / "work-items" / "WORK-20260907-001.md"
            follow_up.write_text("not a work item", encoding="utf-8")
            path.write_text(text, encoding="utf-8")
            errors = DEV_WORK.gate_errors(DEV_WORK.read_work_item(path), "handoff-ready", repo)
            self.assertTrue(any("follow-up work" in error and "valid" in error for error in errors), errors)

    def test_work_item_requires_h1_title_and_matching_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            text = path.read_text(encoding="utf-8").replace("# 文档", "# 其他标题", 1)
            wrong_path = path.with_name("WORK-20260906-001-renamed.md")
            path.unlink()
            wrong_path.write_text(text, encoding="utf-8")
            errors = DEV_WORK.validate_work_item(repo, "WORK-20260906-001")
            self.assertTrue(any("filename" in error for error in errors), errors)
            self.assertTrue(any("title" in error for error in errors), errors)

    def test_work_item_requires_level_one_title(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            path.write_text(path.read_text(encoding="utf-8").replace("# 文档\n", "", 1), encoding="utf-8")
            errors = DEV_WORK.validate_work_item(repo, "WORK-20260906-001")
            self.assertTrue(any("missing level-one title" in error for error in errors), errors)

    def test_rejects_invalid_or_duplicate_feature_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            with self.assertRaises(DEV_WORK.DevWorkError):
                DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ("Bad_ID",))
            with self.assertRaises(DEV_WORK.DevWorkError):
                DEV_WORK.init_work_item(repo, "WORK-20260906-002", "文档", "change", "low", ("same", "same"))

    def test_close_requires_feature_docs_evidence_to_match_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            feature = repo / "docs" / "features" / "sample-feature.md"
            feature.parent.mkdir(parents=True)
            feature.write_text("<!-- feature-id: sample-feature -->\n", encoding="utf-8")
            path = DEV_WORK.init_work_item(
                repo, "WORK-20260906-001", "文档", "change", "low", ("sample-feature",)
            )
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8").replace("**Feature Docs**：已完成证据", "**Feature Docs**：other-feature")
            path.write_text(text, encoding="utf-8")
            self.assertEqual([], self._to_handoff(repo, "WORK-20260906-001"))
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "closed")
            self.assertTrue(any("Feature Docs evidence" in error for error in errors), errors)

    def test_close_rejects_invalid_feature_doc_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            feature = repo / "docs" / "features" / "sample-feature.md"
            feature.parent.mkdir(parents=True)
            feature.write_text("invalid doc", encoding="utf-8")
            path = DEV_WORK.init_work_item(
                repo, "WORK-20260906-001", "文档", "change", "low", ("sample-feature",)
            )
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8").replace("**Feature Docs**：已完成证据", "**Feature Docs**：sample-feature")
            path.write_text(text, encoding="utf-8")
            self.assertEqual([], self._to_handoff(repo, "WORK-20260906-001"))
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "closed")
            self.assertTrue(any("Feature Doc sample-feature" in error and "feature ID not found" in error for error in errors), errors)

    def test_close_rejects_empty_feature_doc_without_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            feature = repo / "docs" / "features" / "sample-feature.md"
            feature.parent.mkdir(parents=True)
            metadata = [
                "<!-- feature-id: sample-feature -->", "<!-- feature-title: 示例功能 -->", "<!-- feature-aliases:  -->",
                "<!-- feature-status: active -->", "<!-- feature-summary: 示例。 -->", "<!-- last-verified: 2026-09-11 -->",
                "<!-- code-basis: no-git; working-tree=unknown -->",
            ]
            headings = [
                "快速上下文", "目标与边界", "业务行为", "架构与代码地图", "API、事件与任务", "数据模型与迁移",
                "核心流程", "异常与边界条件", "并发与幂等", "安全与权限", "配置与依赖", "可观测性与运维",
                "测试与验证", "关键决策", "已知问题与后续工作", "变更记录",
            ]
            feature.write_text("# 示例功能\n\n" + "\n".join(metadata) + "\n\n" + "\n\n".join(f"## {heading}" for heading in headings), encoding="utf-8")
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ("sample-feature",))
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8").replace("**Feature Docs**：已完成证据", "**Feature Docs**：sample-feature")
            path.write_text(text, encoding="utf-8")
            self.assertEqual([], self._to_handoff(repo, "WORK-20260906-001"))
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "closed")
            self.assertTrue(any("empty section" in error for error in errors), errors)

    def test_close_rejects_feature_doc_with_empty_required_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            feature = repo / "docs" / "features" / "sample-feature.md"
            feature.parent.mkdir(parents=True)
            metadata = [
                "<!-- feature-id: sample-feature -->", "<!-- feature-title: 示例功能 -->", "<!-- feature-aliases:  -->",
                "<!-- feature-status: active -->", "<!-- feature-summary: 示例。 -->", "<!-- last-verified: 2026-09-11 -->",
                "<!-- code-basis: no-git; working-tree=unknown -->",
            ]
            headings = [
                "快速上下文", "目标与边界", "业务行为", "架构与代码地图", "API、事件与任务", "数据模型与迁移",
                "核心流程", "异常与边界条件", "并发与幂等", "安全与权限", "配置与依赖", "可观测性与运维",
                "测试与验证", "关键决策", "已知问题与后续工作", "变更记录",
            ]
            feature.write_text("# 示例功能\n\n" + "\n".join(metadata) + "\n\n" + "\n\n".join(f"## {heading}" for heading in headings), encoding="utf-8")
            path = DEV_WORK.init_work_item(
                repo, "WORK-20260906-001", "文档", "change", "low", ("sample-feature",)
            )
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8").replace("**Feature Docs**：已完成证据", "**Feature Docs**：sample-feature")
            path.write_text(text, encoding="utf-8")
            self.assertEqual([], self._to_handoff(repo, "WORK-20260906-001"))
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "closed")
            self.assertTrue(any("empty section" in error for error in errors), errors)

    def test_latest_failed_review_blocks_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "medium", ())
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8").replace(
                "## 发布与回滚",
                "### REV-002 — 复审\n\n- **状态**：FAIL\n- **范围**：实现\n- **证据**：发现阻断问题。\n\n## 发布与回滚",
            )
            path.write_text(text, encoding="utf-8")
            errors = self._to_handoff(repo, "WORK-20260906-001")
            self.assertTrue(any("latest review" in error for error in errors), errors)

    def test_accepted_risk_requires_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            text = path.read_text(encoding="utf-8").replace(
                "### RSK-001 — 风险摘要\n\n- **状态**：CLOSED\n- **确认路径**：已完成证据\n- **概率**：已完成证据\n- **影响**：已完成证据\n- **缓解措施**：已完成证据\n- **验证**：已完成证据",
                "### RSK-001 — 风险摘要\n\n- **状态**：ACCEPTED\n- **确认路径**：\n- **概率**：\n- **影响**：\n- **缓解措施**：\n- **验证**：",
            )
            path.write_text(text, encoding="utf-8")
            errors = self._to_handoff(repo, "WORK-20260906-001")
            self.assertTrue(any("status ACCEPTED" in error for error in errors), errors)

    def test_rejects_stale_verification_basis(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            import subprocess

            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
            (repo / "implementation.py").write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "implementation.py"], check=True)
            subprocess.run(
                [
                    "git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com",
                    "commit", "-m", "initial",
                ],
                check=True,
                capture_output=True,
            )
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            for target in ("clarified", "planned", "implementing", "verifying"):
                self.assertEqual([], DEV_WORK.transition_work_item(repo, "WORK-20260906-001", target))
            (repo / "implementation.py").write_text("value = 2\n", encoding="utf-8")
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "handoff-ready")
            self.assertTrue(any("verification basis" in error for error in errors), errors)

    def test_rejects_stale_basis_when_untracked_nested_file_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            import subprocess

            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
            subprocess.run(
                [
                    "git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com",
                    "commit", "--allow-empty", "-m", "initial",
                ],
                check=True,
                capture_output=True,
            )
            implementation = repo / "src" / "implementation.py"
            implementation.parent.mkdir()
            implementation.write_text("value = 1\n", encoding="utf-8")
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            for target in ("clarified", "planned", "implementing", "verifying"):
                self.assertEqual([], DEV_WORK.transition_work_item(repo, "WORK-20260906-001", target))
            implementation.write_text("value = 2\n", encoding="utf-8")
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "handoff-ready")
            self.assertTrue(any("verification basis" in error for error in errors), errors)

    def test_non_management_markdown_changes_invalidate_basis(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            import subprocess

            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
            subprocess.run(
                [
                    "git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com",
                    "commit", "--allow-empty", "-m", "initial",
                ],
                check=True,
                capture_output=True,
            )
            implementation = repo / "schema.md"
            implementation.write_text("version: 1\n", encoding="utf-8")
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            for target in ("clarified", "planned", "implementing", "verifying"):
                self.assertEqual([], DEV_WORK.transition_work_item(repo, "WORK-20260906-001", target))
            implementation.write_text("version: 2\n", encoding="utf-8")
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "handoff-ready")
            self.assertTrue(any("verification basis" in error for error in errors), errors)

    def test_rejects_stale_basis_when_non_ascii_file_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            import subprocess

            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
            subprocess.run(
                [
                    "git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com",
                    "commit", "--allow-empty", "-m", "initial",
                ],
                check=True,
                capture_output=True,
            )
            implementation = repo / "src" / "模块.py"
            implementation.parent.mkdir()
            implementation.write_text("value = 1\n", encoding="utf-8")
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            self._complete_low_risk_item(path)
            for target in ("clarified", "planned", "implementing", "verifying"):
                self.assertEqual([], DEV_WORK.transition_work_item(repo, "WORK-20260906-001", target))
            implementation.write_text("value = 2\n", encoding="utf-8")
            errors = DEV_WORK.transition_work_item(repo, "WORK-20260906-001", "handoff-ready")
            self.assertTrue(any("verification basis" in error for error in errors), errors)

    def test_legacy_work_item_without_verification_basis_remains_structural(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, "WORK-20260906-001", "文档", "change", "low", ())
            text = re.sub(r"\n<!-- verification-basis: pending -->", "", path.read_text(encoding="utf-8"))
            path.write_text(text, encoding="utf-8")
            errors = DEV_WORK.validate_work_item(repo, "WORK-20260906-001")
            self.assertEqual([], errors)

class NewContractTests(unittest.TestCase):
    def test_empty_title_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(DEV_WORK.DevWorkError):
                DEV_WORK.init_work_item(directory, None, '  ', 'feature', 'low', ())

    def test_reversed_index_markers_are_reported(self):
        with self.assertRaises(DEV_WORK.DevWorkError):
            DEV_WORK.render_index([], DEV_WORK.INDEX_END + '\n' + DEV_WORK.INDEX_START)

    def test_missing_h1_does_not_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = DEV_WORK.init_work_item(directory, None, 'title', 'feature', 'low', ())
            path.write_text(path.read_text().replace('# title', '# '))
            self.assertTrue(DEV_WORK.structural_errors(DEV_WORK.read_work_item(path)))

    def test_changed_snapshot_invalidates_old_pass_and_regression(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            implementation = repo / 'app.py'
            implementation.write_text('one')
            path = DEV_WORK.init_work_item(repo, None, 'title', 'feature', 'low', ())
            helper = DevWorkTests()
            helper._complete_low_risk_item(path)
            work_id = DEV_WORK.read_work_item(path).work_id
            for state in ('clarified', 'planned', 'implementing', 'verifying'):
                self.assertEqual([], DEV_WORK.transition_work_item(repo, work_id, state))
            basis = DEV_WORK.read_work_item(path).metadata['verification-basis']
            text = path.read_text().replace('**证据基线**：pending', f'**证据基线**：{basis}').replace('**用户回归结果**：not-required', '**用户回归结果**：passed')
            path.write_text(text)
            self.assertEqual([], DEV_WORK.transition_work_item(repo, work_id, 'implementing'))
            implementation.write_text('two')
            self.assertEqual([], DEV_WORK.transition_work_item(repo, work_id, 'verifying'))
            text = path.read_text()
            self.assertNotIn('**状态**：PASS', text)
            self.assertIn('**用户回归结果**：pending', text)
            self.assertNotEqual(basis, DEV_WORK.read_work_item(path).metadata['verification-basis'])

    def test_migrate_legacy_implementing_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, None, 'title', 'feature', 'low', ())
            text = path.read_text().replace('work-status: intake', 'work-status: implementing')
            text = re.sub(r'^<!-- verification-basis:.*\n', '', text, flags=re.MULTILINE)
            text = re.sub(r'^- \*\*证据基线\*\*：.*\n', '', text, flags=re.MULTILINE)
            path.write_text(text.replace('**状态**：OPEN\n- **证据**', '**状态**：PASS\n- **证据**'))
            work_id = DEV_WORK.read_work_item(path).work_id
            DEV_WORK.migrate_work_item(repo, work_id)
            migrated = path.read_text()
            DEV_WORK.migrate_work_item(repo, work_id)
            self.assertEqual(migrated, path.read_text())
            self.assertIn('verification-basis: pending', migrated)
            self.assertEqual(2, migrated.count('**证据基线**：pending'))

    def test_broken_git_repository_fails_closed(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            (repo / '.git' / 'HEAD').unlink()
            with self.assertRaises(DEV_WORK.DevWorkError):
                DEV_WORK.verification_basis(repo)

    def test_nested_unchecked_plan_item_allows_implementation(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, None, 'title', 'feature', 'low', ())
            DevWorkTests()._complete_low_risk_item(path)
            text = path.read_text().replace('- [x] 已完成', '- [x] 已完成\n  - [ ] critical')
            path.write_text(text)
            errors = DEV_WORK.gate_errors(DEV_WORK.read_work_item(path), 'implementing')
            self.assertFalse(any('plan is incomplete' in error for error in errors), errors)
            errors = DEV_WORK.gate_errors(DEV_WORK.read_work_item(path), 'verifying')
            self.assertTrue(any('plan is incomplete' in error for error in errors), errors)

    def test_invalid_nested_checkbox_blocks_implementation(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, None, 'title', 'feature', 'low', ())
            DevWorkTests()._complete_low_risk_item(path)
            path.write_text(path.read_text().replace('- [x] 已完成', '- [x] 已完成\n  - [maybe] critical'))
            errors = DEV_WORK.gate_errors(DEV_WORK.read_work_item(path), 'implementing')
            self.assertTrue(any('plan is incomplete' in error for error in errors), errors)

    def test_init_records_canonical_git_code_basis(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            (repo / 'app.py').write_text('implementation')
            path = DEV_WORK.init_work_item(repo, None, 'title', 'feature', 'low', ())
            self.assertEqual(DEV_WORK.verification_basis(repo), DEV_WORK.read_work_item(path).metadata['code-basis'])

    def test_index_escapes_valid_title(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            DEV_WORK.init_work_item(repo, None, r'path\name <tag>', 'feature', 'low', ())
            index = (repo / 'docs/work-items/index.md').read_text()
            self.assertIn(r'path\\name &lt;tag&gt;', index)

    def test_index_rejects_invalid_item_instead_of_skipping(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, None, 'title', 'feature', 'low', ())
            path.write_text(path.read_text().replace('work-id: WORK-', 'work-id: INVALID-'))
            with self.assertRaises(DEV_WORK.DevWorkError):
                DEV_WORK.sync_index(repo)

    def test_init_rolls_back_if_index_markers_reversed(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            directory_path = repo / 'docs/work-items'
            directory_path.mkdir(parents=True)
            index = directory_path / 'index.md'
            original = DEV_WORK.INDEX_END + '\n' + DEV_WORK.INDEX_START
            index.write_text(original)
            with self.assertRaises(DEV_WORK.DevWorkError):
                DEV_WORK.init_work_item(repo, 'WORK-20260906-001', 'title', 'feature', 'low', ())
            self.assertFalse((directory_path / 'WORK-20260906-001.md').exists())
            self.assertEqual(original, index.read_text())

    def test_transition_rolls_back_when_index_write_fails(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, None, 'title', 'feature', 'low', ())
            original = path.read_text()
            original_write = DEV_WORK.atomic_write
            def fail_index(target, text):
                if target.name == 'index.md':
                    raise OSError('simulated index failure')
                return original_write(target, text)
            with patch.object(DEV_WORK, 'atomic_write', side_effect=fail_index):
                with self.assertRaises(OSError):
                    DEV_WORK.transition_work_item(repo, DEV_WORK.read_work_item(path).work_id, 'clarified')
            self.assertEqual(original, path.read_text())

    def test_migrate_rolls_back_when_index_write_fails(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, None, 'title', 'feature', 'low', ())
            path.write_text(path.read_text().replace('work-status: intake', 'work-status: implementing').replace('<!-- verification-basis: pending -->\n', ''))
            original = path.read_text()
            original_write = DEV_WORK.atomic_write
            def fail_index(target, text):
                if target.name == 'index.md':
                    raise OSError('simulated index failure')
                return original_write(target, text)
            with patch.object(DEV_WORK, 'atomic_write', side_effect=fail_index):
                with self.assertRaises(OSError):
                    DEV_WORK.migrate_work_item(repo, DEV_WORK.read_work_item(path).work_id)
            self.assertEqual(original, path.read_text())

class PreservationTests(unittest.TestCase):
    def test_atomic_write_preserves_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'item'
            path.write_text('old')
            path.chmod(0o644)
            DEV_WORK.atomic_write(path, 'new')
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)

    def test_invalidate_preserves_fenced_examples_and_crlf(self):
        text = '### VER-001\r\n- **状态**：PASS\r\n```\r\n- **状态**：PASS\r\n- **证据基线**：example\r\n```\r\n- **证据基线**：old\r\n'
        expected = text.replace('PASS\r\n```', 'OPEN\r\n```').replace('：old', '：pending')
        self.assertEqual(DEV_WORK.invalidate_evidence(text), expected)

    def test_invalidate_only_user_regression_section(self):
        text = '## 其他\n- **用户回归结果**：passed\n## 用户回归\n- **用户回归结果**：passed\n'
        self.assertEqual(DEV_WORK.invalidate_evidence(text), text.rsplit('passed', 1)[0] + 'pending\n')

    def test_atomic_new_file_is_private_and_failure_preserves_original(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'item'
            DEV_WORK.atomic_write(path, 'old')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.chmod(0o640)
            with patch.object(DEV_WORK.os, 'replace', side_effect=OSError('failed')):
                with self.assertRaises(OSError):
                    DEV_WORK.atomic_write(path, 'new')
            self.assertEqual(path.read_text(), 'old')
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_migration_preserves_fenced_examples_and_crlf(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            path = DEV_WORK.init_work_item(repo, 'WORK-20260906-001', '标题', 'feature', 'low', ())
            text = path.read_text().replace('work-status: intake', 'work-status: implementing')
            text = re.sub(r'^<!-- verification-basis:.*\n', '', text, flags=re.MULTILINE)
            text = re.sub(r'^- \*\*证据基线\*\*：.*\n', '', text, flags=re.MULTILINE)
            sample = '```\n### VER-999 — 示例\n- **状态**：PASS\n- **证据基线**：example\n```\n'
            text = text.replace('### VER-001', sample + '### VER-001').replace('\n', '\r\n')
            path.write_bytes(text.encode())
            DEV_WORK.migrate_work_item(repo, 'WORK-20260906-001')
            result = path.read_bytes().decode()
            self.assertIn(sample.replace('\n', '\r\n'), result)
            self.assertNotIn('\n', result.replace('\r\n', ''))
            self.assertIn('<!-- verification-basis: pending -->', result)
            first = result
            DEV_WORK.migrate_work_item(repo, 'WORK-20260906-001')
            self.assertEqual(path.read_bytes().decode(), first)

    def test_crlf_git_reentry_preserves_examples_and_invalidates_real_records(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            code = repo / 'app.py'
            code.write_text('one\n')
            work_id = 'WORK-20260906-001'
            path = DEV_WORK.init_work_item(repo, work_id, '标题', 'feature', 'low', ())
            DevWorkTests()._complete_low_risk_item(path)
            text = path.read_text().replace('\n', '\r\n')
            path.write_bytes(text.encode())
            for target in ('clarified', 'planned', 'implementing', 'verifying'):
                self.assertEqual([], DEV_WORK.transition_work_item(repo, work_id, target))
            text = path.read_bytes().decode()
            sample = '```\r\n- **状态**：PASS\r\n- **证据基线**：example\r\n- **用户回归结果**：passed\r\n```\r\n'
            text = text.replace('### VER-001', sample + '### VER-001', 1)
            pos = text.index('\r\n', text.index('### VER-001')) + 2
            text = text[:pos] + sample + text[pos:]
            text = text.replace('**用户回归结果**：not-required', '**用户回归结果**：passed')
            path.write_bytes(text.encode())
            self.assertEqual([], DEV_WORK.transition_work_item(repo, work_id, 'implementing'))
            code.write_text('two\n')
            self.assertEqual([], DEV_WORK.transition_work_item(repo, work_id, 'verifying'))
            result = path.read_bytes().decode()
            self.assertEqual(result.count(sample), 2)
            self.assertNotIn('\n', result.replace('\r\n', ''))
            self.assertIn('- **状态**：OPEN', result[result.index('### VER-001'):])
            self.assertIn('- **用户回归结果**：pending', result)

    def test_atomic_write_uses_literal_newlines_and_portable_chmod(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'item'
            path.write_bytes(b'old')
            path.chmod(0o640)
            named = DEV_WORK.tempfile.NamedTemporaryFile
            chmod = DEV_WORK.os.chmod
            with patch.object(DEV_WORK.tempfile, 'NamedTemporaryFile', wraps=named) as create, \
                 patch.object(DEV_WORK.os, 'chmod', wraps=chmod) as set_mode:
                DEV_WORK.atomic_write(path, 'a\r\nb\n')
            self.assertEqual(create.call_args.kwargs['newline'], '')
            set_mode.assert_called_once()
            self.assertEqual(path.read_bytes(), b'a\r\nb\n')
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)
