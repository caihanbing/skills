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
            "```markdown\n## 不应被解析的标题\n```\n\n## 业务行为",
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
