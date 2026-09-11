import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "feature_docs", SKILL_ROOT / "scripts" / "feature_docs.py"
)
FEATURE_DOCS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = FEATURE_DOCS
SPEC.loader.exec_module(FEATURE_DOCS)

REGRESSION_FIELDS = (
    "是否需要用户回归",
    "需更新、部署或重启的服务",
    "无需操作的服务",
    "操作顺序",
    "前置条件",
    "回归步骤与预期结果",
)


def base_document_text():
    text = (SKILL_ROOT / "assets" / "feature-doc-template.md").read_text(encoding="utf-8")
    replacements = {
        "{{FEATURE_TITLE}}": "示例功能",
        "{{FEATURE_ID}}": "sample-feature",
        "{{FEATURE_ALIASES}}": "",
        "{{LAST_VERIFIED}}": "2026-08-19",
        "{{CODE_BASIS}}": "no-git; working-tree=unknown",
    }
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    text = text.replace(
        "<!-- feature-summary: FEATURE_DOCS:REPLACE -->",
        "<!-- feature-summary: 用于验证回归交接契约。 -->",
    )
    text = re.sub(
        r"\n### 用户回归准备\n.*?(?=\n## |\Z)",
        "\n",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"<!-- FEATURE_DOCS:REPLACE.*?-->",
        "不适用：测试文档。",
        text,
        flags=re.DOTALL,
    )
    return re.sub(
        r"(## 变更记录\n\n).*\Z",
        r"\1### 2026-08-19 — 创建测试文档\n\n"
        "- **状态**：已完成\n"
        "- **变化**：创建测试文档。\n"
        "- **原因**：验证结构契约。\n"
        "- **兼容性**：无。\n"
        "- **验证**：运行单元测试。\n",
        text,
        flags=re.DOTALL,
    )


def regression_block(values=None, field_order=REGRESSION_FIELDS, extra_lines=()):
    field_values = {
        "是否需要用户回归": "是",
        "需更新、部署或重启的服务": "更新并滚动重启 `refund-worker`。",
        "无需操作的服务": "`refund-api` 无需构建、部署或重启。",
        "操作顺序": "先构建 worker，再滚动重启，最后发送测试事件。",
        "前置条件": "无数据库迁移、配置变更、缓存清理或额外消费者操作。",
        "回归步骤与预期结果": "同一事件发送两次，预期只通知一次。",
    }
    if values:
        field_values.update(values)
    lines = ["### 用户回归准备", ""]
    lines.extend(f"- **{field}**：{field_values[field]}" for field in field_order)
    lines.extend(extra_lines)
    return "\n".join(lines) + "\n\n"


def with_regression_block(text, block):
    return text.replace("## 关键决策", block + "## 关键决策")


def validate_text(text):
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        path = repo / "docs" / "features" / "sample-feature.md"
        path.parent.mkdir(parents=True)
        path.write_text(text, encoding="utf-8")
        document = FEATURE_DOCS.read_document(path)
        return FEATURE_DOCS.validate_document(document, repo)


class RegressionHandoffContractTests(unittest.TestCase):
    def test_legacy_document_without_user_regression_remains_valid(self):
        errors = validate_text(base_document_text())
        self.assertEqual([], errors)

    def test_rejects_unconfirmed_service_actions(self):
        text = with_regression_block(
            base_document_text(),
            regression_block(
                {
                    "需更新、部署或重启的服务": "待确认",
                    "无需操作的服务": "待确认",
                    "操作顺序": "待确认",
                }
            ),
        )
        errors = validate_text(text)
        self.assertTrue(any("未确认内容" in error for error in errors), errors)

    def test_rejects_unresolved_phrase_variants(self):
        phrases = (
            "部署拓扑尚未确定。",
            "部署拓扑待 确认。",
            "部署服务待定。",
            "部署服务需确认。",
            "部署方式有待确认。",
            "部署命令稍后补充。",
            "Deployment is pending confirmation.",
            "Deployment is to be determined.",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                text = with_regression_block(
                    base_document_text(),
                    regression_block({"需更新、部署或重启的服务": phrase}),
                )
                errors = validate_text(text)
                self.assertTrue(any("未确认内容" in error for error in errors), errors)

    def test_accepts_complete_user_regression_preparation(self):
        text = with_regression_block(base_document_text(), regression_block())
        self.assertEqual([], validate_text(text))

    def test_accepts_explicit_no_regression_handoff(self):
        text = with_regression_block(
            base_document_text(),
            regression_block(
                {
                    "是否需要用户回归": "否",
                    "需更新、部署或重启的服务": "无：仅修改文档。",
                    "无需操作的服务": "全部运行时服务均无需操作。",
                    "操作顺序": "不适用：没有运行时变更。",
                    "前置条件": "无数据库迁移、配置变更、缓存清理或消息消费者操作。",
                    "回归步骤与预期结果": "不适用：结构校验已覆盖本次文档修改。",
                }
            ),
        )
        self.assertEqual([], validate_text(text))

    def test_allows_definitive_no_confirmation_phrase(self):
        text = with_regression_block(
            base_document_text(),
            regression_block(
                {
                    "是否需要用户回归": "否",
                    "需更新、部署或重启的服务": "无：无需确认额外服务，部署清单已核验。",
                }
            ),
        )
        self.assertEqual([], validate_text(text))

    def test_rejects_invalid_regression_decision(self):
        text = with_regression_block(
            base_document_text(),
            regression_block({"是否需要用户回归": "可能"}),
        )
        errors = validate_text(text)
        self.assertTrue(any("exactly 是 or 否" in error for error in errors), errors)

    def test_rejects_regression_fields_out_of_order(self):
        order = (
            "是否需要用户回归",
            "无需操作的服务",
            "需更新、部署或重启的服务",
            "操作顺序",
            "前置条件",
            "回归步骤与预期结果",
        )
        text = with_regression_block(
            base_document_text(),
            regression_block(field_order=order),
        )
        errors = validate_text(text)
        self.assertTrue(any("fields are out of order" in error for error in errors), errors)

    def test_rejects_extra_structured_field(self):
        text = with_regression_block(
            base_document_text(),
            regression_block(extra_lines=("- **额外字段**：不应出现。",)),
        )
        errors = validate_text(text)
        self.assertTrue(any("unexpected field" in error for error in errors), errors)

    def test_new_template_omits_transient_user_regression_handoff(self):
        template = (SKILL_ROOT / "assets" / "feature-doc-template.md").read_text(encoding="utf-8")
        self.assertNotIn("### 用户回归准备", template)
        for field in REGRESSION_FIELDS:
            self.assertNotIn(f"**{field}**", template)


if __name__ == "__main__":
    unittest.main()
