#!/usr/bin/env python3
"""Create, find, and structurally validate repository feature documents."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote


FEATURE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
METADATA_RE = re.compile(
    r"^<!--\s*(feature-id|feature-title|feature-aliases|feature-status|feature-summary|last-verified|code-basis):\s*(.*?)\s*-->$",
    re.MULTILINE,
)
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
INDEX_START = "<!-- manage-feature-docs:index:start -->"
INDEX_END = "<!-- manage-feature-docs:index:end -->"
ALLOWED_STATUSES = {"planned", "active", "deprecated", "retired"}
REQUIRED_METADATA = (
    "feature-id",
    "feature-title",
    "feature-aliases",
    "feature-status",
    "feature-summary",
    "last-verified",
    "code-basis",
)
REQUIRED_HEADINGS = (
    "## 快速上下文",
    "## 目标与边界",
    "## 业务行为",
    "## 架构与代码地图",
    "## API、事件与任务",
    "## 数据模型与迁移",
    "## 核心流程",
    "## 异常与边界条件",
    "## 并发与幂等",
    "## 安全与权限",
    "## 配置与依赖",
    "## 可观测性与运维",
    "## 测试与验证",
    "## 关键决策",
    "## 已知问题与后续工作",
    "## 变更记录",
)
REQUIRED_SUBHEADINGS = {
    "## 目标与边界": ("### 目标", "### 范围内", "### 范围外", "### 不变量"),
    "## 测试与验证": ("### 已执行", "### 未执行"),
}
CHANGE_FIELDS = ("状态", "变化", "原因", "兼容性", "验证")
USER_REGRESSION_FIELDS = (
    "是否需要用户回归",
    "需更新、部署或重启的服务",
    "无需操作的服务",
    "操作顺序",
    "前置条件",
    "回归步骤与预期结果",
)
STRUCTURED_SECTION_FIELDS = {
    "## 关键决策": ("决定", "原因", "取舍", "证据"),
    "## 已知问题与后续工作": ("影响", "当前处理", "后续动作"),
}
CHANGE_STATUSES = {"已完成", "部分完成", "已回滚"}
CHINESE_UNRESOLVED_REGRESSION_RE = re.compile(
    r"待确认|待定|(?<![无不])需(?:要)?确认|尚未确定|未确定|"
    r"稍后(?:补充|确认)|后续(?:补充|确认)|尚不(?:明确|清楚)|未知|不清楚|不明确"
)
ENGLISH_UNRESOLVED_REGRESSION_RE = re.compile(
    r"\b(?:todo|tbd|unknown|pending confirmation|to be confirmed|to be determined|"
    r"not yet determined|fill in later)\b",
    re.IGNORECASE,
)
PLACEHOLDER_PATTERNS = (
    re.compile(r"FEATURE_DOCS:REPLACE"),
    re.compile(r"\{\{[A-Z0-9_]+\}\}"),
    re.compile(r"\[(?:TODO|TBD)\]", re.IGNORECASE),
)


class FeatureDocsError(Exception):
    """A user-actionable feature-document error."""


@dataclass(frozen=True)
class FeatureDocument:
    path: Path
    text: str
    scan_text: str
    metadata: dict[str, str]

    @property
    def feature_id(self) -> str:
        return self.metadata.get("feature-id", "")

    @property
    def title(self) -> str:
        return self.metadata.get("feature-title", "")

    @property
    def aliases(self) -> tuple[str, ...]:
        value = self.metadata.get("feature-aliases", "")
        return tuple(part.strip() for part in value.split(",") if part.strip())


def parse_metadata(text: str) -> dict[str, str]:
    return {match.group(1): match.group(2).strip() for match in METADATA_RE.finditer(text)}


def mask_fenced_blocks(text: str) -> str:
    """Hide fenced-code contents while preserving newlines and offsets."""
    lines = text.splitlines(keepends=True)
    masked: list[str] = []
    fence: tuple[str, int] | None = None
    for line in lines:
        marker = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})", line)
        if fence is None and marker:
            fence = (marker.group(1)[0], len(marker.group(1)))
            masked.append(" " * (len(line.rstrip("\r\n"))) + line[len(line.rstrip("\r\n")) :])
            continue
        if fence is not None:
            if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= fence[1]:
                fence = None
            masked.append(" " * (len(line.rstrip("\r\n"))) + line[len(line.rstrip("\r\n")) :])
            continue
        masked.append(line)
    return "".join(masked)


def read_document(path: Path) -> FeatureDocument:
    text = path.read_text(encoding="utf-8")
    scan_text = mask_fenced_blocks(text)
    return FeatureDocument(path=path, text=text, scan_text=scan_text, metadata=parse_metadata(scan_text))


def atomic_write_text(path: Path, text: str) -> None:
    """Replace a text file atomically while preserving safe default permissions."""
    mode = (path.stat().st_mode & 0o777) if path.exists() else 0o644
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_name, mode)
        os.replace(temporary_name, path)
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


def feature_directory(repo: Path) -> Path:
    return repo / "docs" / "features"


def discover_documents(repo: Path) -> list[FeatureDocument]:
    directory = feature_directory(repo)
    if not directory.exists():
        return []
    return [
        read_document(path)
        for path in sorted(directory.glob("*.md"))
        if path.name.casefold() != "index.md"
    ]


def ensure_repo(value: str) -> Path:
    repo = Path(value).expanduser().resolve()
    if not repo.is_dir():
        raise FeatureDocsError(f"repository directory does not exist: {repo}")
    return repo


def reject_unsafe_metadata(label: str, value: str) -> None:
    if "\n" in value or "\r" in value or "-->" in value or "|" in value:
        raise FeatureDocsError(f"{label} cannot contain newlines, '|', or '-->'")


def git_code_basis(repo: Path) -> str:
    def run_git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            check=False,
            capture_output=True,
            text=True,
        )

    inside = run_git("rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return "no-git; working-tree=unknown"
    head = run_git("rev-parse", "--short=12", "HEAD")
    sha = head.stdout.strip() if head.returncode == 0 else "unborn"
    status = run_git("status", "--porcelain")
    state = "dirty" if status.returncode != 0 or status.stdout.strip() else "clean"
    return f"HEAD {sha}; working-tree={state}"


def fresh_git_errors(document: FeatureDocument, repo: Path) -> list[str]:
    """Compare document evidence with the current implementation worktree."""
    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "-C", str(repo), *args], check=False, capture_output=True, text=True)

    if git("rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
        return ["fresh validation requires a Git repository"]
    basis = document.metadata.get("code-basis", "")
    match = re.fullmatch(r"HEAD\s+([0-9a-fA-F]+|unborn);\s*working-tree=(clean|dirty)(?:\s*\([^)]*\))?", basis)
    if not match:
        return ["code-basis must use 'HEAD <sha>; working-tree=<clean|dirty>' for fresh validation"]
    actual_head = git("rev-parse", "--short=12", "HEAD").stdout.strip() or "unborn"
    errors: list[str] = []
    if not actual_head.startswith(match.group(1)):
        errors.append("code-basis HEAD does not match current HEAD")
    status_lines = git("status", "--porcelain").stdout.splitlines()
    implementation_dirty = False
    for line in status_lines:
        path = line[3:].split(" -> ")[-1] if len(line) > 3 else ""
        if not path.startswith(("docs/features/", "docs/work-items/")):
            implementation_dirty = True
            break
    documented_dirty = match.group(2) == "dirty"
    if documented_dirty != implementation_dirty:
        errors.append("code-basis working-tree state does not match implementation changes")
    return errors


def escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def build_index_block(documents: Iterable[FeatureDocument]) -> str:
    lines = [
        INDEX_START,
        "| 功能 ID | 标题 | 别名 | 状态 | 简述 | 最后核验 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    ordered = sorted(documents, key=lambda doc: (doc.feature_id, doc.path.name))
    for doc in ordered:
        metadata = doc.metadata
        feature_id = metadata.get("feature-id", "待确认")
        title = metadata.get("feature-title", "待确认")
        aliases = metadata.get("feature-aliases", "") or "—"
        status = metadata.get("feature-status", "待确认")
        summary = metadata.get("feature-summary", "待确认")
        verified = metadata.get("last-verified", "待确认")
        lines.append(
            "| "
            + " | ".join(
                (
                    f"[`{escape_table_cell(feature_id)}`]({doc.path.name})",
                    escape_table_cell(title),
                    escape_table_cell(aliases),
                    escape_table_cell(status),
                    escape_table_cell(summary),
                    escape_table_cell(verified),
                )
            )
            + " |"
        )
    lines.append(INDEX_END)
    return "\n".join(lines)


def render_index(existing: str | None, documents: Iterable[FeatureDocument]) -> str:
    block = build_index_block(documents)
    if existing is None:
        return "# 功能技术档案索引\n\n本索引用于跨会话定位稳定功能档案。\n\n" + block + "\n"

    start_count = existing.count(INDEX_START)
    end_count = existing.count(INDEX_END)
    if start_count != end_count or start_count > 1:
        raise FeatureDocsError("index contains mismatched or duplicate managed-block markers")
    if start_count == 1:
        start = existing.index(INDEX_START)
        end = existing.index(INDEX_END, start) + len(INDEX_END)
        return existing[:start] + block + existing[end:]

    separator = "" if existing.endswith("\n\n") else "\n" if existing.endswith("\n") else "\n\n"
    return existing + separator + "## 功能档案索引\n\n" + block + "\n"


def template_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "feature-doc-template.md"


def command_init(args: argparse.Namespace) -> int:
    repo = ensure_repo(args.repo)
    feature_id = args.feature_id
    if not FEATURE_ID_RE.fullmatch(feature_id):
        raise FeatureDocsError("feature ID must be lowercase kebab-case")
    reject_unsafe_metadata("title", args.title)
    aliases = tuple(dict.fromkeys(alias.strip() for alias in args.aliases if alias.strip()))
    for alias in aliases:
        reject_unsafe_metadata("alias", alias)

    directory = feature_directory(repo)
    target = directory / f"{feature_id}.md"
    if target.exists():
        raise FeatureDocsError(f"refusing to overwrite existing document: {target}")

    existing_documents = discover_documents(repo)
    if any(document.feature_id == feature_id for document in existing_documents):
        raise FeatureDocsError(f"feature ID already exists in another document: {feature_id}")

    index_path = directory / "index.md"
    existing_index = index_path.read_text(encoding="utf-8") if index_path.exists() else None
    if existing_index is not None:
        start_count = existing_index.count(INDEX_START)
        end_count = existing_index.count(INDEX_END)
        if start_count != end_count or start_count > 1:
            raise FeatureDocsError("index contains mismatched or duplicate managed-block markers")

    source = template_path().read_text(encoding="utf-8")
    replacements = {
        "{{FEATURE_TITLE}}": args.title,
        "{{FEATURE_ID}}": feature_id,
        "{{FEATURE_ALIASES}}": ", ".join(aliases),
        "{{LAST_VERIFIED}}": dt.date.today().isoformat(),
        "{{CODE_BASIS}}": git_code_basis(repo),
    }
    rendered = source
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)

    new_document = FeatureDocument(target, rendered, mask_fenced_blocks(rendered), parse_metadata(mask_fenced_blocks(rendered)))
    updated_index = render_index(existing_index, [*existing_documents, new_document])

    directory.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as output:
        output.write(rendered)
    try:
        atomic_write_text(index_path, updated_index)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    print(target)
    print(index_path)
    return 0


def match_score(document: FeatureDocument, query: str) -> int:
    needle = query.casefold().strip()
    if not needle:
        return 1
    feature_id = document.feature_id.casefold()
    title = document.title.casefold()
    aliases = tuple(alias.casefold() for alias in document.aliases)
    if needle == feature_id:
        return 100
    if needle == title:
        return 95
    if needle in aliases:
        return 90
    if needle in feature_id or needle in title or any(needle in alias for alias in aliases):
        return 60
    if needle in document.text.casefold():
        return 20
    return 0


def command_find(args: argparse.Namespace) -> int:
    repo = ensure_repo(args.repo)
    documents = discover_documents(repo)
    matches = [(match_score(doc, args.query or ""), doc) for doc in documents]
    matches = [(score, doc) for score, doc in matches if score > 0]
    matches.sort(key=lambda item: (-item[0], item[1].feature_id, item[1].path.name))
    if not matches:
        print("no matching feature documents", file=sys.stderr)
        return 1
    for score, doc in matches:
        aliases = ", ".join(doc.aliases) or "—"
        status = doc.metadata.get("feature-status", "待确认")
        print(f"{score}\t{doc.feature_id}\t{status}\t{doc.title}\t{aliases}\t{doc.path}")
    return 0


def extract_link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        return target[1 : target.index(">")]
    if " " in target:
        target = target.split(" ", 1)[0]
    return target


def broken_local_links(document: FeatureDocument, repo: Path) -> list[str]:
    broken: list[str] = []
    repository_root = repo.resolve()
    for match in MARKDOWN_LINK_RE.finditer(document.scan_text):
        target = unquote(extract_link_target(match.group(1)))
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        path_part = target.split("#", 1)[0]
        resolved = (document.path.parent / path_part).resolve()
        try:
            resolved.relative_to(repository_root)
        except ValueError:
            broken.append(f"{target} (outside repository)")
            continue
        if path_part and not resolved.exists():
            broken.append(target)
    return broken


def unresolved_regression_phrase(text: str) -> str | None:
    normalized = unicodedata.normalize("NFKC", text)
    compact = re.sub(r"\s+", "", normalized)
    chinese_match = CHINESE_UNRESOLVED_REGRESSION_RE.search(compact)
    if chinese_match:
        return chinese_match.group(0)
    spaced = re.sub(r"\s+", " ", normalized)
    english_match = ENGLISH_UNRESOLVED_REGRESSION_RE.search(spaced)
    return english_match.group(0) if english_match else None


def validate_document(document: FeatureDocument, repo: Path) -> list[str]:
    errors: list[str] = []
    metadata = document.metadata
    metadata_matches = list(METADATA_RE.finditer(document.scan_text))
    metadata_counts: dict[str, int] = {}
    for match in metadata_matches:
        metadata_counts[match.group(1)] = metadata_counts.get(match.group(1), 0) + 1
    for key, count in metadata_counts.items():
        if count > 1:
            errors.append(f"duplicate metadata: {key}")
    for key in REQUIRED_METADATA:
        if key not in metadata:
            errors.append(f"missing metadata: {key}")
        elif key != "feature-aliases" and not metadata[key]:
            errors.append(f"empty metadata: {key}")
    feature_id = metadata.get("feature-id", "")
    if feature_id and not FEATURE_ID_RE.fullmatch(feature_id):
        errors.append("feature-id is not lowercase kebab-case")
    if feature_id and document.path.name != f"{feature_id}.md":
        errors.append(f"filename does not match feature-id {feature_id!r}")
    status = metadata.get("feature-status")
    if status and status not in ALLOWED_STATUSES:
        errors.append(f"unsupported feature-status: {status}")
    verified = metadata.get("last-verified")
    if verified:
        try:
            verified_date = dt.date.fromisoformat(verified)
            if verified_date > dt.date.today():
                errors.append("last-verified cannot be in the future")
        except ValueError:
            errors.append("last-verified must use YYYY-MM-DD")
    for key, value in metadata.items():
        if "|" in value or "\n" in value or "\r" in value:
            errors.append(f"metadata {key} must be a safe single-line value")
    first_heading = re.search(r"^#\s+(.+?)\s*$", document.scan_text, re.MULTILINE)
    if not first_heading:
        errors.append("missing level-one title")
    elif metadata.get("feature-title") and first_heading.group(1) != metadata["feature-title"]:
        errors.append("level-one title does not match feature-title")
    else:
        lines = document.scan_text.splitlines()
        heading_line = next(
            (index for index, line in enumerate(lines) if re.fullmatch(r"#\s+.+?", line)),
            -1,
        )
        following = lines[heading_line + 1 :]
        while following and not following[0].strip():
            following.pop(0)
        expected = tuple(REQUIRED_METADATA)
        observed: list[str] = []
        for line in following:
            match = METADATA_RE.fullmatch(line)
            if not match:
                break
            observed.append(match.group(1))
        if tuple(observed) != expected:
            errors.append("metadata block must be contiguous immediately after the title")
    heading_counts: dict[str, int] = {}
    for heading in REQUIRED_HEADINGS:
        count = len(re.findall(rf"^{re.escape(heading)}\s*$", document.scan_text, re.MULTILINE))
        heading_counts[heading] = count
        if count == 0:
            errors.append(f"missing heading: {heading}")
        elif count > 1:
            errors.append(f"duplicate heading: {heading}")
    document_headings = tuple(
        match.group(0).strip()
        for match in re.finditer(r"^##\s+.+?\s*$", document.scan_text, re.MULTILINE)
    )
    unexpected_headings = [heading for heading in document_headings if heading not in REQUIRED_HEADINGS]
    for heading in unexpected_headings:
        errors.append(f"unexpected level-two heading: {heading}")
    if not unexpected_headings and all(heading_counts[heading] == 1 for heading in REQUIRED_HEADINGS):
        if document_headings != REQUIRED_HEADINGS:
            errors.append("required level-two headings are out of order")

    section_matches = list(re.finditer(r"^##\s+.+?\s*$", document.scan_text, re.MULTILINE))
    sections: dict[str, str] = {}
    for index, match in enumerate(section_matches):
        end = section_matches[index + 1].start() if index + 1 < len(section_matches) else len(document.scan_text)
        heading = match.group(0).strip()
        content = document.scan_text[match.end() : end]
        sections[heading] = content
        visible = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL).strip()
        if heading in REQUIRED_HEADINGS and not visible:
            errors.append(f"empty section: {heading}")

    for section_heading, required_subheadings in REQUIRED_SUBHEADINGS.items():
        content = sections.get(section_heading, "")
        matches_by_subheading: list[tuple[str, re.Match[str]]] = []
        for subheading in required_subheadings:
            matches = list(re.finditer(rf"^{re.escape(subheading)}\s*$", content, re.MULTILINE))
            if len(matches) != 1:
                errors.append(f"{section_heading} must contain exactly one {subheading}")
            else:
                matches_by_subheading.append((subheading, matches[0]))
        if len(matches_by_subheading) == len(required_subheadings):
            positions = [match.start() for _, match in matches_by_subheading]
            if positions != sorted(positions):
                errors.append(f"fixed subheadings are out of order in {section_heading}")
            ordered_matches = sorted(matches_by_subheading, key=lambda item: item[1].start())
            for index, (subheading, match) in enumerate(ordered_matches):
                end = (
                    ordered_matches[index + 1][1].start()
                    if index + 1 < len(ordered_matches)
                    else len(content)
                )
                body = re.sub(r"<!--.*?-->", "", content[match.end() : end], flags=re.DOTALL).strip()
                if not body:
                    errors.append(f"empty fixed subsection: {section_heading} / {subheading}")

    for section_heading, fields in STRUCTURED_SECTION_FIELDS.items():
        content = sections.get(section_heading, "")
        entries = list(re.finditer(r"^###\s+.+?\s*$", content, re.MULTILINE))
        if not entries:
            visible = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL).strip()
            if visible and not visible.startswith("不适用："):
                errors.append(f"{section_heading} must use structured entries or start with 不适用：")
            continue
        for index, entry in enumerate(entries):
            end = entries[index + 1].start() if index + 1 < len(entries) else len(content)
            body = content[entry.end() : end]
            for field in fields:
                count = len(re.findall(rf"^-\s+\*\*{field}\*\*：\s*\S", body, re.MULTILINE))
                if count != 1:
                    title = entry.group(0).strip()
                    errors.append(f"structured entry {title!r} must contain one non-empty **{field}** field")

    test_content = sections.get("## 测试与验证", "")
    regression_heading = re.search(r"^### 用户回归准备\s*$", test_content, re.MULTILINE)
    if regression_heading:
        next_heading = re.search(r"^###\s+.+?\s*$", test_content[regression_heading.end() :], re.MULTILINE)
        regression_end = (
            regression_heading.end() + next_heading.start()
            if next_heading
            else len(test_content)
        )
        regression_body = test_content[regression_heading.end() : regression_end]
        observed_fields = re.findall(
            r"^-\s+\*\*(.+?)\*\*：",
            regression_body,
            re.MULTILINE,
        )
        for field in observed_fields:
            if field not in USER_REGRESSION_FIELDS:
                errors.append(f"user regression preparation contains unexpected field: **{field}**")
        field_matches: list[re.Match[str]] = []
        for field in USER_REGRESSION_FIELDS:
            matches = list(
                re.finditer(
                    rf"^-\s+\*\*{re.escape(field)}\*\*：\s*\S",
                    regression_body,
                    re.MULTILINE,
                )
            )
            if len(matches) != 1:
                errors.append(f"user regression preparation must contain one non-empty **{field}** field")
            else:
                field_matches.append(matches[0])
        if len(field_matches) == len(USER_REGRESSION_FIELDS):
            positions = [match.start() for match in field_matches]
            if positions != sorted(positions):
                errors.append("user regression preparation fields are out of order")
        required_match = re.search(
            r"^-\s+\*\*是否需要用户回归\*\*：\s*(\S.*?)\s*$",
            regression_body,
            re.MULTILINE,
        )
        if required_match and required_match.group(1) not in {"是", "否"}:
            errors.append("**是否需要用户回归** must be exactly 是 or 否")
        unresolved = unresolved_regression_phrase(regression_body)
        if unresolved:
            errors.append(
                f"用户回归准备不能包含未确认内容: {unresolved}; clarify with the user first"
            )

    change_content = sections.get("## 变更记录", "")
    change_entries = list(
        re.finditer(r"^###\s+(\d{4}-\d{2}-\d{2})\s+—\s+.+?\s*$", change_content, re.MULTILINE)
    )
    if not change_entries:
        errors.append("change history must contain a '### YYYY-MM-DD — summary' entry")
    change_dates: list[dt.date] = []
    for index, entry in enumerate(change_entries):
        try:
            change_date = dt.date.fromisoformat(entry.group(1))
            change_dates.append(change_date)
            if change_date > dt.date.today():
                errors.append(f"change-history date cannot be in the future: {entry.group(1)}")
        except ValueError:
            errors.append(f"invalid change-history date: {entry.group(1)}")
        end = change_entries[index + 1].start() if index + 1 < len(change_entries) else len(change_content)
        body = change_content[entry.end() : end]
        for field in CHANGE_FIELDS:
            count = len(re.findall(rf"^-\s+\*\*{field}\*\*：\s*\S", body, re.MULTILINE))
            if count != 1:
                errors.append(f"change-history entry {entry.group(1)} must contain one non-empty **{field}** field")
        status_match = re.search(r"^-\s+\*\*状态\*\*：\s*(\S.*?)\s*$", body, re.MULTILINE)
        if status_match and status_match.group(1) not in CHANGE_STATUSES:
            errors.append(
                f"change-history entry {entry.group(1)} has unsupported status: {status_match.group(1)}"
            )
    if len(change_dates) == len(change_entries) and change_dates != sorted(change_dates, reverse=True):
        errors.append("change-history entries must be sorted by date descending")
    for pattern in PLACEHOLDER_PATTERNS:
        if pattern.search(document.scan_text):
            errors.append(f"unresolved placeholder matching {pattern.pattern!r}")
    for target in broken_local_links(document, repo):
        errors.append(f"broken local Markdown link: {target}")
    return errors


def command_sync_index(args: argparse.Namespace) -> int:
    repo = ensure_repo(args.repo)
    documents = discover_documents(repo)
    if not documents:
        raise FeatureDocsError(f"no feature documents found in {feature_directory(repo)}")
    index_path = feature_directory(repo) / "index.md"
    existing = index_path.read_text(encoding="utf-8") if index_path.exists() else None
    atomic_write_text(index_path, render_index(existing, documents))
    print(index_path)
    return 0


def command_validate(args: argparse.Namespace) -> int:
    repo = ensure_repo(args.repo)
    documents = discover_documents(repo)
    if not documents:
        raise FeatureDocsError(f"no feature documents found in {feature_directory(repo)}")

    all_errors: list[tuple[Path, str]] = []
    by_id: dict[str, list[Path]] = {}
    for document in documents:
        by_id.setdefault(document.feature_id, []).append(document.path)
    for feature_id, paths in by_id.items():
        if not feature_id:
            continue
        if len(paths) > 1:
            for path in paths:
                all_errors.append((path, f"duplicate feature-id: {feature_id}"))

    selected = documents
    if args.feature_id:
        selected = [doc for doc in documents if doc.feature_id == args.feature_id]
        if not selected:
            raise FeatureDocsError(f"feature ID not found: {args.feature_id}")
    for document in selected:
        for error in validate_document(document, repo):
            all_errors.append((document.path, error))
        if args.mode == "fresh":
            for error in fresh_git_errors(document, repo):
                all_errors.append((document.path, error))

    index_path = feature_directory(repo) / "index.md"
    if not index_path.exists():
        all_errors.append((index_path, "missing index"))
    else:
        current = index_path.read_text(encoding="utf-8")
        try:
            expected = render_index(current, documents)
            if current != expected:
                all_errors.append((index_path, "managed index block is stale or inconsistent"))
        except FeatureDocsError as exc:
            all_errors.append((index_path, str(exc)))
        index_doc = FeatureDocument(index_path, current, mask_fenced_blocks(current), {})
        for target in broken_local_links(index_doc, repo):
            all_errors.append((index_path, f"broken local Markdown link: {target}"))

    if all_errors:
        for path, error in all_errors:
            print(f"ERROR\t{path}\t{error}", file=sys.stderr)
        return 1
    scope = args.feature_id or "all feature documents"
    print(f"OK\t{scope}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create, find, and validate docs/features technical documents."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create a feature document and update index")
    init_parser.add_argument("--repo", required=True, help="repository or workspace root")
    init_parser.add_argument("--id", dest="feature_id", required=True, help="lowercase kebab-case ID")
    init_parser.add_argument("--title", required=True, help="human-readable feature title")
    init_parser.add_argument("--aliases", nargs="*", default=[], help="zero or more lookup aliases")
    init_parser.set_defaults(handler=command_init)

    find_parser = subparsers.add_parser("find", help="locate feature documents")
    find_parser.add_argument("--repo", required=True, help="repository or workspace root")
    find_parser.add_argument("--query", help="ID, title, alias, or content query; omit to list all")
    find_parser.set_defaults(handler=command_find)

    validate_parser = subparsers.add_parser("validate", help="validate feature documents and index")
    validate_parser.add_argument("--repo", required=True, help="repository or workspace root")
    validate_parser.add_argument("--id", dest="feature_id", help="validate one feature plus catalog integrity")
    validate_parser.add_argument("--mode", choices=("structural", "fresh"), default="structural")
    validate_parser.set_defaults(handler=command_validate)
    sync_parser = subparsers.add_parser("sync-index", help="rebuild the managed feature index")
    sync_parser.add_argument("--repo", required=True, help="repository or workspace root")
    sync_parser.set_defaults(handler=command_sync_index)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (FeatureDocsError, OSError) as exc:
        print(f"ERROR\t{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
