import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "feature_docs.py"
SPEC = importlib.util.spec_from_file_location("feature_docs_v2", SCRIPT)
FEATURE_DOCS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = FEATURE_DOCS
SPEC.loader.exec_module(FEATURE_DOCS)


def complete_document(code_basis="no-git; working-tree=unknown"):
    template = (SKILL_ROOT / "assets" / "feature-doc-template.md").read_text(encoding="utf-8")
    replacements = {
        "{{FEATURE_TITLE}}": "示例功能",
        "{{FEATURE_ID}}": "sample-feature",
        "{{FEATURE_ALIASES}}": "",
        "{{LAST_VERIFIED}}": "2026-09-06",
        "{{CODE_BASIS}}": code_basis,
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    template = template.replace(
        "<!-- feature-summary: FEATURE_DOCS:REPLACE -->",
        "<!-- feature-summary: 用于 V2 结构校验测试。 -->",
    )
    template = template.replace(
        "<!-- FEATURE_DOCS:REPLACE | 使用“日期 — 摘要”三级标题，并依次记录状态、变化、原因、兼容性、验证。 -->",
        "### 2026-09-06 — 创建测试档案\n\n"
        "- **状态**：已完成\n- **变化**：创建测试档案。\n- **原因**：测试。\n"
        "- **兼容性**：无。\n- **验证**：单元测试。",
    )
    template = template.replace(
        "<!-- FEATURE_DOCS:REPLACE | 每项使用三级标题，并依次记录决定、原因、取舍、证据；没有时说明不适用。 -->",
        "不适用：测试无长期决策。",
    )
    template = template.replace(
        "<!-- FEATURE_DOCS:REPLACE | 每项使用三级标题，并依次记录影响、当前处理、后续动作；没有时说明不适用。 -->",
        "不适用：测试无已知问题。",
    )
    template = template.replace("- **是否需要用户回归**：FEATURE_DOCS:REPLACE", "- **是否需要用户回归**：否")
    for field in (
        "需更新、部署或重启的服务",
        "无需操作的服务",
        "操作顺序",
        "前置条件",
        "回归步骤与预期结果",
    ):
        template = template.replace(f"- **{field}**：FEATURE_DOCS:REPLACE", f"- **{field}**：不适用：测试。")
    template = re.sub(r"<!-- FEATURE_DOCS:REPLACE.*?-->", "不适用：测试。", template, flags=re.DOTALL)
    return template


def write_repo(text):
    directory = tempfile.TemporaryDirectory()
    repo = Path(directory.name)
    target = repo / "docs" / "features" / "sample-feature.md"
    target.parent.mkdir(parents=True)
    target.write_text(text, encoding="utf-8")
    (target.parent / "index.md").write_text("# 索引\n", encoding="utf-8")
    return directory, repo, target


class FeatureDocsV2Tests(unittest.TestCase):
    def test_rejects_duplicate_metadata(self):
        holder, repo, path = write_repo(
            complete_document().replace(
                "<!-- feature-status: active -->",
                "<!-- feature-status: active -->\n<!-- feature-status: active -->",
            )
        )
        self.addCleanup(holder.cleanup)
        errors = FEATURE_DOCS.validate_document(FEATURE_DOCS.read_document(path), repo)
        self.assertTrue(any("duplicate metadata" in error for error in errors), errors)

    def test_rejects_metadata_outside_header_block(self):
        text = complete_document()
        metadata = "\n".join(line for line in text.splitlines() if line.startswith("<!-- feature-"))
        text = "\n".join(line for line in text.splitlines() if not line.startswith("<!-- feature-"))
        text = text + "\n" + metadata + "\n"
        holder, repo, path = write_repo(text)
        self.addCleanup(holder.cleanup)
        errors = FEATURE_DOCS.validate_document(FEATURE_DOCS.read_document(path), repo)
        self.assertTrue(any("metadata block" in error for error in errors), errors)

    def test_rejects_future_last_verified(self):
        holder, repo, path = write_repo(complete_document().replace("2026-09-06", "2099-12-31"))
        self.addCleanup(holder.cleanup)
        errors = FEATURE_DOCS.validate_document(FEATURE_DOCS.read_document(path), repo)
        self.assertTrue(any("future" in error for error in errors), errors)

    def test_ignores_headings_inside_fenced_code(self):
        text = complete_document().replace(
            "## 业务行为",
            "```markdown\n```python\n## 不应被解析的标题\n```\n\n## 业务行为",
        )
        holder, repo, path = write_repo(text)
        self.addCleanup(holder.cleanup)
        errors = FEATURE_DOCS.validate_document(FEATURE_DOCS.read_document(path), repo)
        self.assertEqual([], errors)

    def test_reports_missing_local_image(self):
        text = complete_document().replace("## 业务行为", "![架构图](missing.png)\n\n## 业务行为")
        holder, repo, path = write_repo(text)
        self.addCleanup(holder.cleanup)
        errors = FEATURE_DOCS.validate_document(FEATURE_DOCS.read_document(path), repo)
        self.assertTrue(any("missing.png" in error for error in errors), errors)

    def test_sync_index_command(self):
        holder, repo, _ = write_repo(complete_document())
        self.addCleanup(holder.cleanup)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "sync-index", "--repo", str(repo)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("sample-feature", (repo / "docs" / "features" / "index.md").read_text())

    def test_init_creates_document_and_managed_index(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "init", "--repo", str(repo), "--id", "sample-feature", "--title", "示例功能", "--aliases", "示例"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((repo / "docs" / "features" / "sample-feature.md").exists())
            self.assertIn("manage-feature-docs:index:start", (repo / "docs" / "features" / "index.md").read_text())

    def test_find_matches_alias_and_returns_not_found_code(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(
                [sys.executable, str(SCRIPT), "init", "--repo", str(repo), "--id", "sample-feature", "--title", "示例功能", "--aliases", "示例别名"],
                check=True,
                capture_output=True,
                text=True,
            )
            found = subprocess.run([sys.executable, str(SCRIPT), "find", "--repo", str(repo), "--query", "示例别名"], capture_output=True, text=True)
            missing = subprocess.run([sys.executable, str(SCRIPT), "find", "--repo", str(repo), "--query", "不存在"], capture_output=True, text=True)
            self.assertEqual(0, found.returncode, found.stderr)
            self.assertIn("sample-feature", found.stdout)
            self.assertEqual(1, missing.returncode)

    def test_reports_missing_local_text_link(self):
        text = complete_document().replace("## 业务行为", "[实现](missing.py)\n\n## 业务行为")
        holder, repo, path = write_repo(text)
        self.addCleanup(holder.cleanup)
        errors = FEATURE_DOCS.validate_document(FEATURE_DOCS.read_document(path), repo)
        self.assertTrue(any("missing.py" in error for error in errors), errors)

    def test_rejects_invalid_change_history_status(self):
        holder, repo, path = write_repo(complete_document().replace("**状态**：已完成", "**状态**：开放"))
        self.addCleanup(holder.cleanup)
        errors = FEATURE_DOCS.validate_document(FEATURE_DOCS.read_document(path), repo)
        self.assertTrue(any("unsupported status" in error for error in errors), errors)

    def test_rejects_future_change_history_date(self):
        holder, repo, path = write_repo(complete_document().replace("2026-09-06 — 创建测试档案", "2099-01-01 — 创建测试档案"))
        self.addCleanup(holder.cleanup)
        errors = FEATURE_DOCS.validate_document(FEATURE_DOCS.read_document(path), repo)
        self.assertTrue(any("change-history date cannot be in the future" in error for error in errors), errors)

    def test_atomic_write_replaces_existing_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "content.md"
            path.write_text("old", encoding="utf-8")
            FEATURE_DOCS.atomic_write_text(path, "new")
            self.assertEqual("new", path.read_text(encoding="utf-8"))

    def test_fresh_mode_rejects_stale_git_basis(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "initial"],
                check=True,
                capture_output=True,
                text=True,
            )
            target = repo / "docs" / "features" / "sample-feature.md"
            target.parent.mkdir(parents=True)
            target.write_text(complete_document("HEAD deadbeefdead; working-tree=clean"), encoding="utf-8")
            (target.parent / "index.md").write_text("# 索引\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "validate", "--repo", str(repo), "--mode", "fresh"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("code-basis", result.stderr)

    def test_fresh_mode_rejects_short_head_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "initial"],
                check=True,
                capture_output=True,
                text=True,
            )
            head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
            path = repo / "docs" / "features" / "sample-feature.md"
            path.parent.mkdir(parents=True)
            path.write_text(complete_document(f"HEAD {head[:8]}; working-tree=clean"), encoding="utf-8")
            document = FEATURE_DOCS.read_document(path)
            errors = FEATURE_DOCS.fresh_git_errors(document, repo)
            self.assertTrue(any("12" in error or "digest" in error for error in errors), errors)

    def test_fresh_mode_accepts_legacy_twelve_char_basis(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "initial"],
                check=True,
                capture_output=True,
                text=True,
            )
            head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
            path = repo / "docs" / "features" / "sample-feature.md"
            path.parent.mkdir(parents=True)
            path.write_text(complete_document(f"HEAD {head[:12]}; working-tree=clean"), encoding="utf-8")
            errors = FEATURE_DOCS.fresh_git_errors(FEATURE_DOCS.read_document(path), repo)
            self.assertEqual([], errors)

    def test_fresh_mode_rejects_legacy_dirty_management_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "initial"],
                check=True,
                capture_output=True,
                text=True,
            )
            head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
            management = repo / "docs" / "features" / "sample-feature.md"
            management.parent.mkdir(parents=True)
            management.write_text(complete_document(f"HEAD {head[:12]}; working-tree=dirty"), encoding="utf-8")
            errors = FEATURE_DOCS.fresh_git_errors(FEATURE_DOCS.read_document(management), repo)
            self.assertTrue(any("legacy dirty" in error for error in errors), errors)

    def test_fresh_mode_rejects_legacy_dirty_basis(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "initial"],
                check=True,
                capture_output=True,
                text=True,
            )
            head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
            path = repo / "docs" / "features" / "sample-feature.md"
            path.parent.mkdir(parents=True)
            path.write_text(complete_document(f"HEAD {head[:12]}; working-tree=dirty"), encoding="utf-8")
            errors = FEATURE_DOCS.fresh_git_errors(FEATURE_DOCS.read_document(path), repo)
            self.assertTrue(any("legacy dirty" in error for error in errors), errors)

    def test_structural_rejects_invalid_code_basis(self):
        holder, repo, path = write_repo(complete_document("totally-invalid-basis"))
        self.addCleanup(holder.cleanup)
        errors = FEATURE_DOCS.validate_document(FEATURE_DOCS.read_document(path), repo)
        self.assertTrue(any("code-basis" in error for error in errors), errors)

    def test_structural_accepts_no_git_code_basis(self):
        holder, repo, path = write_repo(complete_document("no-git; working-tree=unknown"))
        self.addCleanup(holder.cleanup)
        errors = FEATURE_DOCS.validate_document(FEATURE_DOCS.read_document(path), repo)
        self.assertEqual([], errors)

    def test_rejects_last_verified_before_latest_completed_change(self):
        text = complete_document().replace(
            "### 2026-09-06 — 创建测试档案",
            "### 2026-09-10 — 后续完成变更",
        ).replace(
            "2026-09-06",
            "2026-01-01",
            1,
        )
        holder, repo, path = write_repo(text)
        self.addCleanup(holder.cleanup)
        errors = FEATURE_DOCS.validate_document(FEATURE_DOCS.read_document(path), repo)
        self.assertTrue(any("last-verified" in error and "change" in error for error in errors), errors)

    def test_validate_contract_rejects_empty_required_sections(self):
        text = re.sub(r"不适用：测试(?:文档)?。", "", complete_document())
        holder, repo, path = write_repo(text)
        self.addCleanup(holder.cleanup)
        errors = FEATURE_DOCS.validate_contract_document(FEATURE_DOCS.read_document(path), repo)
        self.assertTrue(any("empty section" in error for error in errors), errors)

    def test_validate_contract_accepts_complete_document(self):
        holder, repo, path = write_repo(complete_document())
        self.addCleanup(holder.cleanup)
        errors = FEATURE_DOCS.validate_contract_document(FEATURE_DOCS.read_document(path), repo)
        self.assertEqual([], errors)

    def test_validate_contract_cli_skips_catalog_integrity(self):
        holder, repo, path = write_repo(complete_document())
        self.addCleanup(holder.cleanup)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate-contract", "--repo", str(repo), "--id", "sample-feature"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_invalid_calendar_change_date_reports_error_without_crash(self):
        text = complete_document().replace("### 2026-09-06 — 创建测试档案", "### 2026-02-30 — 非法日期")
        holder, repo, path = write_repo(text)
        self.addCleanup(holder.cleanup)
        errors = FEATURE_DOCS.validate_document(FEATURE_DOCS.read_document(path), repo)
        self.assertTrue(any("invalid change-history date" in error for error in errors), errors)

    def test_invalid_completed_date_does_not_reuse_previous_valid_date(self):
        text = complete_document().replace(
            "### 2026-09-06 — 创建测试档案",
            "### 2026-09-06 — 创建测试档案\n\n- **状态**：已完成\n- **变化**：合法历史。\n- **原因**：测试。\n- **兼容性**：无。\n- **验证**：测试。\n\n### 2026-02-30 — 非法日期",
        )
        holder, repo, path = write_repo(text)
        self.addCleanup(holder.cleanup)
        errors = FEATURE_DOCS.validate_document(FEATURE_DOCS.read_document(path), repo)
        self.assertTrue(any("invalid change-history date" in error for error in errors), errors)

    def test_validate_contract_fresh_cli_rejects_stale_basis(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            implementation = repo / "implementation.py"
            implementation.write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "implementation.py"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-m", "initial"],
                check=True,
                capture_output=True,
                text=True,
            )
            basis = FEATURE_DOCS.git_code_basis(repo)
            path = repo / "docs" / "features" / "sample-feature.md"
            path.parent.mkdir(parents=True)
            path.write_text(complete_document(basis), encoding="utf-8")
            implementation.write_text("value = 2\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "validate-contract", "--repo", str(repo), "--id", "sample-feature", "--mode", "fresh"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("worktree digest", result.stderr)

    def test_fresh_mode_detects_changed_content_with_same_dirty_state(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            implementation = repo / "implementation.py"
            implementation.write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "implementation.py"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-m", "initial"],
                check=True,
                capture_output=True,
                text=True,
            )
            implementation.write_text("value = 2\n", encoding="utf-8")
            basis = FEATURE_DOCS.git_code_basis(repo)
            path = repo / "docs" / "features" / "sample-feature.md"
            path.parent.mkdir(parents=True)
            path.write_text(complete_document(basis), encoding="utf-8")
            implementation.write_text("value = 3\n", encoding="utf-8")
            errors = FEATURE_DOCS.fresh_git_errors(FEATURE_DOCS.read_document(path), repo)
            self.assertTrue(any("digest" in error for error in errors), errors)

    def test_fresh_mode_detects_untracked_nested_file_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "initial"],
                check=True,
                capture_output=True,
                text=True,
            )
            implementation = repo / "src" / "implementation.py"
            implementation.parent.mkdir()
            implementation.write_text("value = 1\n", encoding="utf-8")
            basis = FEATURE_DOCS.git_code_basis(repo)
            path = repo / "docs" / "features" / "sample-feature.md"
            path.parent.mkdir(parents=True)
            path.write_text(complete_document(basis), encoding="utf-8")
            implementation.write_text("value = 2\n", encoding="utf-8")
            errors = FEATURE_DOCS.fresh_git_errors(FEATURE_DOCS.read_document(path), repo)
            self.assertTrue(any("digest" in error for error in errors), errors)

    def test_fresh_mode_detects_non_management_markdown_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "initial"],
                check=True,
                capture_output=True,
                text=True,
            )
            implementation = repo / "schema.md"
            implementation.write_text("version: 1\n", encoding="utf-8")
            basis = FEATURE_DOCS.git_code_basis(repo)
            path = repo / "docs" / "features" / "sample-feature.md"
            path.parent.mkdir(parents=True)
            path.write_text(complete_document(basis), encoding="utf-8")
            implementation.write_text("version: 2\n", encoding="utf-8")
            errors = FEATURE_DOCS.fresh_git_errors(FEATURE_DOCS.read_document(path), repo)
            self.assertTrue(any("digest" in error for error in errors), errors)

    def test_fresh_mode_detects_non_ascii_file_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "initial"],
                check=True,
                capture_output=True,
                text=True,
            )
            implementation = repo / "src" / "模块.py"
            implementation.parent.mkdir(parents=True)
            implementation.write_text("value = 1\n", encoding="utf-8")
            basis = FEATURE_DOCS.git_code_basis(repo)
            path = repo / "docs" / "features" / "sample-feature.md"
            path.parent.mkdir(parents=True)
            path.write_text(complete_document(basis), encoding="utf-8")
            implementation.write_text("value = 2\n", encoding="utf-8")
            errors = FEATURE_DOCS.fresh_git_errors(FEATURE_DOCS.read_document(path), repo)
            self.assertTrue(any("digest" in error for error in errors), errors)

    def test_fresh_mode_detects_renamed_implementation_file(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
            implementation = repo / "implementation.py"
            implementation.write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "implementation.py"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-m", "initial"],
                check=True,
                capture_output=True,
                text=True,
            )
            basis = FEATURE_DOCS.git_code_basis(repo)
            path = repo / "docs" / "features" / "sample-feature.md"
            path.parent.mkdir(parents=True)
            path.write_text(complete_document(basis), encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "mv", "implementation.py", "renamed.py"], check=True)
            errors = FEATURE_DOCS.fresh_git_errors(FEATURE_DOCS.read_document(path), repo)
            self.assertTrue(any("digest" in error for error in errors), errors)

    def test_current_contract_does_not_require_transient_user_regression(self):
        contract = (SKILL_ROOT / "references" / "document-contract.md").read_text(encoding="utf-8")
        testing_section = contract.split("## Evidence and updates", 1)[0]
        self.assertNotIn("用户回归准备", testing_section)
