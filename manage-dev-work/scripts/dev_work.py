#!/usr/bin/env python3
"""Manage project-local development work items and deterministic gates."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


WORK_ID_RE = re.compile(r"^WORK-(\d{8})-(\d{3})$")
FEATURE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
METADATA_RE = re.compile(
    r"^<!--\s*(work-id|work-title|work-type|work-status|risk-level|feature-ids|created|updated|code-basis|verification-basis):\s*(.*?)\s*-->$",
    re.MULTILINE,
)
STATUSES = {
    "intake",
    "clarified",
    "planned",
    "implementing",
    "verifying",
    "handoff-ready",
    "closed",
    "blocked",
    "cancelled",
    "rolled-back",
}
ALLOWED_TRANSITIONS = {
    "intake": {"clarified", "blocked", "cancelled"},
    "clarified": {"planned", "blocked", "cancelled"},
    "planned": {"implementing", "blocked", "cancelled"},
    "implementing": {"verifying", "blocked", "rolled-back", "cancelled"},
    "verifying": {"implementing", "handoff-ready", "blocked", "rolled-back"},
    "handoff-ready": {"implementing", "closed", "blocked", "rolled-back"},
    "blocked": {"clarified", "cancelled"},
    "rolled-back": {"implementing", "cancelled"},
    "cancelled": set(),
    "closed": set(),
}
WORK_TYPES = {"feature", "bugfix", "change"}
RISK_LEVELS = {"low", "medium", "high"}
RISK_RANK = {"low": 1, "medium": 2, "high": 3}
DEC_STATUSES = {"BLOCKER", "OPEN", "RESOLVED", "DEFERRED"}
RSK_STATUSES = {"OPEN", "MITIGATED", "ACCEPTED", "CLOSED"}
REQ_STATUSES = {"OPEN", "IMPLEMENTED", "VERIFIED", "DEFERRED"}
VER_STATUSES = {"OPEN", "PASS", "FAIL", "SKIPPED"}
REV_STATUSES = {"OPEN", "PASS", "FAIL"}
HIGH_IMPACTS = {"Database", "MQ", "Security", "Concurrency", "Transaction", "Cross-service"}
MEDIUM_IMPACTS = {"API", "Configuration", "Compatibility", "Deployment"}
IMPACT_DIMENSIONS = (
    "Code",
    "API",
    "Database",
    "Configuration",
    "Cache",
    "MQ",
    "Security",
    "Concurrency",
    "Observability",
    "Deployment",
    "Compatibility",
    "Transaction",
    "Performance",
    "Cross-service",
)
MANAGEMENT_DOC_PREFIXES = ("docs/features/", "docs/work-items/", "docs/superpowers/")
REGRESSION_FIELDS = (
    "是否需要用户回归",
    "需更新、部署或重启的服务",
    "无需操作的服务",
    "操作顺序",
    "前置条件",
    "回归步骤与预期结果",
    "用户回归结果",
)
UNRESOLVED_RE = re.compile(r"待确认|待定|未知|不明确|不清楚|TODO|TBD|unknown|pending confirmation|稍后补充", re.IGNORECASE)
INDEX_START = "<!-- manage-dev-work:index:start -->"
INDEX_END = "<!-- manage-dev-work:index:end -->"


class DevWorkError(Exception):
    pass


@dataclass(frozen=True)
class WorkItem:
    path: Path
    text: str
    scan_text: str
    metadata: dict[str, str]

    @property
    def work_id(self) -> str:
        return self.metadata.get("work-id", "")


def work_directory(repo: Path) -> Path:
    return repo / "docs" / "work-items"


def parse_metadata(text: str) -> dict[str, str]:
    return {match.group(1): match.group(2).strip() for match in METADATA_RE.finditer(text)}


def read_work_item(path: Path) -> WorkItem:
    text = path.read_text(encoding="utf-8")
    scan_text = mask_fenced_blocks(text)
    return WorkItem(path=path, text=text, scan_text=scan_text, metadata=parse_metadata(scan_text))


def mask_fenced_blocks(text: str) -> str:
    """Hide fenced Markdown contents while preserving line offsets."""
    lines = text.splitlines(keepends=True)
    masked: list[str] = []
    fence: tuple[str, int] | None = None
    for line in lines:
        marker = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})", line)
        content_end = len(line.rstrip("\r\n"))
        if fence is None and marker:
            fence = (marker.group(1)[0], len(marker.group(1)))
            masked.append(" " * content_end + line[content_end:])
            continue
        if fence is not None:
            closing = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})[ \t]*$", line.rstrip("\r\n"))
            if closing and closing.group(1)[0] == fence[0] and len(closing.group(1)) >= fence[1]:
                fence = None
            masked.append(" " * content_end + line[content_end:])
            continue
        masked.append(line)
    return "".join(masked)


def ensure_repo(value: str | Path) -> Path:
    repo = Path(value).expanduser().resolve()
    if not repo.is_dir():
        raise DevWorkError(f"repository directory does not exist: {repo}")
    return repo


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as output:
            temporary_name = output.name
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


def git_code_basis(repo: Path) -> str:
    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)

    if git("rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
        return "no-git; working-tree=unknown"
    head = git("rev-parse", "--short=12", "HEAD")
    sha = head.stdout.strip() if head.returncode == 0 else "unborn"
    dirty = bool(git("status", "--porcelain").stdout.strip())
    return f"HEAD {sha}; working-tree={'dirty' if dirty else 'clean'}"


def implementation_worktree_digest(repo: Path) -> str | None:
    """Hash changed implementation files while excluding management documents."""
    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)

    if git("rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
        return None
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain", "-z", "--untracked-files=all"],
        capture_output=True,
        check=False,
    )
    entries: list[bytes] = []
    records = status.stdout.split(b"\0")
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if len(record) < 4:
            continue
        state, raw_path = record[:2], record[3:]
        paths = [raw_path]
        if b"R" in state or b"C" in state:
            if index < len(records):
                paths.append(records[index])
                index += 1
        for path_bytes in paths:
            path = path_bytes.decode("utf-8", "surrogateescape")
            if path.startswith(MANAGEMENT_DOC_PREFIXES):
                continue
            absolute = repo / path
            try:
                content = absolute.read_bytes() if absolute.exists() else b""
            except OSError:
                content = b""
            entries.append(state + b"\0" + path_bytes + b"\0" + hashlib.sha256(content).digest())
    digest = hashlib.sha256()
    for entry in sorted(entries):
        digest.update(entry)
        digest.update(b"\n")
    return digest.hexdigest()


def verification_basis(repo: Path) -> str:
    """Return the implementation snapshot used by verification gates."""
    digest = implementation_worktree_digest(repo)
    if digest is None:
        return "no-git; worktree-digest=unknown"
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--short=12", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    sha = head.stdout.strip() if head.returncode == 0 else "unborn"
    return f"HEAD {sha}; worktree-digest sha256:{digest}"


def template_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "work-item-template.md"


def discover_work_items(repo: Path) -> list[WorkItem]:
    directory = work_directory(repo)
    if not directory.exists():
        return []
    return [read_work_item(path) for path in sorted(directory.glob("WORK-*.md"))]


def next_work_id(repo: Path) -> str:
    today = dt.date.today().strftime("%Y%m%d")
    highest = 0
    for item in discover_work_items(repo):
        match = WORK_ID_RE.fullmatch(item.work_id)
        if match and match.group(1) == today:
            highest = max(highest, int(match.group(2)))
    return f"WORK-{today}-{highest + 1:03d}"


def render_index(items: list[WorkItem], existing: str | None) -> str:
    lines = [INDEX_START, "| Work Item | 标题 | 类型 | 风险 | 状态 | Feature | 更新日期 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for item in sorted(items, key=lambda value: value.work_id):
        meta = item.metadata
        lines.append(
            f"| [`{item.work_id}`]({item.path.name}) | {meta.get('work-title', '待确认')} | "
            f"{meta.get('work-type', '待确认')} | {meta.get('risk-level', '待确认')} | "
            f"{meta.get('work-status', '待确认')} | {meta.get('feature-ids', '') or '—'} | "
            f"{meta.get('updated', '待确认')} |"
        )
    lines.append(INDEX_END)
    block = "\n".join(lines)
    if existing is None:
        return "# 研发 Work Item 索引\n\n" + block + "\n"
    starts = existing.count(INDEX_START)
    ends = existing.count(INDEX_END)
    if starts != ends or starts > 1:
        raise DevWorkError("work-item index has mismatched managed markers")
    if starts == 1:
        start = existing.index(INDEX_START)
        end = existing.index(INDEX_END, start) + len(INDEX_END)
        return existing[:start] + block + existing[end:]
    return existing.rstrip() + "\n\n" + block + "\n"


def sync_index(repo: Path) -> Path:
    directory = work_directory(repo)
    index = directory / "index.md"
    existing = index.read_text(encoding="utf-8") if index.exists() else None
    atomic_write(index, render_index(discover_work_items(repo), existing))
    return index


def work_index_errors(repo: Path) -> list[str]:
    index = work_directory(repo) / "index.md"
    if not index.exists():
        return ["work-item index is missing"]
    current = index.read_text(encoding="utf-8")
    try:
        expected = render_index(discover_work_items(repo), current)
    except DevWorkError as exc:
        return [str(exc)]
    return [] if current == expected else ["work-item index is stale or inconsistent"]


def init_work_item(
    repo: str | Path,
    work_id: str | None,
    title: str,
    work_type: str,
    risk: str,
    feature_ids: tuple[str, ...],
) -> Path:
    root = ensure_repo(repo)
    actual_id = work_id or next_work_id(root)
    if not WORK_ID_RE.fullmatch(actual_id):
        raise DevWorkError("work ID must use WORK-YYYYMMDD-NNN")
    if work_type not in WORK_TYPES:
        raise DevWorkError(f"unsupported work type: {work_type}")
    if risk not in RISK_LEVELS:
        raise DevWorkError(f"unsupported risk level: {risk}")
    normalized_features = tuple(value.strip() for value in feature_ids if value.strip())
    if len(normalized_features) != len(set(normalized_features)):
        raise DevWorkError("feature IDs must be unique")
    if any(not FEATURE_ID_RE.fullmatch(value) for value in normalized_features):
        raise DevWorkError("feature IDs must use lowercase kebab-case")
    if any(value in title for value in ("\n", "\r", "-->", "|")):
        raise DevWorkError("title cannot contain newlines, '|', or '-->'")
    target = work_directory(root) / f"{actual_id}.md"
    if target.exists():
        raise DevWorkError(f"refusing to overwrite existing work item: {target}")
    source = template_path().read_text(encoding="utf-8")
    today = dt.date.today().isoformat()
    replacements = {
        "{{WORK_TITLE}}": title,
        "{{WORK_ID}}": actual_id,
        "{{WORK_TYPE}}": work_type,
        "{{RISK_LEVEL}}": risk,
        "{{FEATURE_IDS}}": ", ".join(normalized_features),
        "{{TODAY}}": today,
        "{{CODE_BASIS}}": git_code_basis(root),
    }
    rendered = source
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as output:
        output.write(rendered)
    sync_index(root)
    return target


def section(text: str, heading: str) -> str:
    match = re.search(rf"^{re.escape(heading)}\s*$", text, re.MULTILINE)
    if not match:
        return ""
    next_heading = re.search(r"^##\s+.+?$", text[match.end() :], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    return text[match.end() : end]


def field_value(text: str, field: str) -> str:
    match = re.search(rf"^-\s+\*\*{re.escape(field)}\*\*：\s*(.*?)\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def has_placeholder(value: str) -> bool:
    return not value or "WORK_ITEM:REPLACE" in value or value in {"OPEN", "pending", "待确认"}


def structural_errors(item: WorkItem) -> list[str]:
    errors: list[str] = []
    counts: dict[str, int] = {}
    for match in METADATA_RE.finditer(item.scan_text):
        counts[match.group(1)] = counts.get(match.group(1), 0) + 1
    for key, count in counts.items():
        if count > 1:
            errors.append(f"duplicate metadata: {key}")
    required = ("work-id", "work-title", "work-type", "work-status", "risk-level", "feature-ids", "created", "updated", "code-basis")
    for key in required:
        if key not in item.metadata:
            errors.append(f"missing metadata: {key}")
    title_match = re.search(r"^#\s+.+?\s*$", item.scan_text, re.MULTILINE)
    if title_match:
        lines = item.scan_text.splitlines()
        title_index = next(index for index, line in enumerate(lines) if re.fullmatch(r"#\s+.+?", line))
        following = lines[title_index + 1 :]
        while following and not following[0].strip():
            following.pop(0)
        observed: list[str] = []
        for line in following:
            match = METADATA_RE.fullmatch(line)
            if not match:
                break
            observed.append(match.group(1))
        allowed_orders = (required, required + ("verification-basis",))
        if tuple(observed) not in allowed_orders:
            errors.append("metadata block must be contiguous immediately after the title")
    dates: dict[str, dt.date] = {}
    for key in ("created", "updated"):
        value = item.metadata.get(key, "")
        if not value:
            continue
        try:
            parsed = dt.date.fromisoformat(value)
            dates[key] = parsed
            if parsed > dt.date.today():
                errors.append(f"{key} date cannot be in the future: {value}")
        except ValueError:
            errors.append(f"{key} must use YYYY-MM-DD")
    if "created" in dates and "updated" in dates and dates["created"] > dates["updated"]:
        errors.append("created date cannot be later than updated date")
    if item.work_id and not WORK_ID_RE.fullmatch(item.work_id):
        errors.append("work-id must use WORK-YYYYMMDD-NNN")
    if item.work_id and item.path.name != f"{item.work_id}.md":
        errors.append(f"filename does not match work-id {item.work_id!r}")
    first_heading = re.search(r"^#\s+(.+?)\s*$", item.scan_text, re.MULTILINE)
    if not first_heading:
        errors.append("missing level-one title")
    elif item.metadata.get("work-title") and first_heading.group(1) != item.metadata["work-title"]:
        errors.append("level-one title does not match work-title")
    feature_values = tuple(value.strip() for value in item.metadata.get("feature-ids", "").split(",") if value.strip())
    if len(feature_values) != len(set(feature_values)):
        errors.append("feature IDs must be unique")
    for feature_id in feature_values:
        if not FEATURE_ID_RE.fullmatch(feature_id):
            errors.append(f"invalid feature ID: {feature_id}")
    if item.metadata.get("work-status") not in STATUSES:
        errors.append(f"unsupported work-status: {item.metadata.get('work-status', '')}")
    if item.metadata.get("work-type") not in WORK_TYPES:
        errors.append(f"unsupported work-type: {item.metadata.get('work-type', '')}")
    if item.metadata.get("risk-level") not in RISK_LEVELS:
        errors.append(f"unsupported risk-level: {item.metadata.get('risk-level', '')}")
    required_headings = (
        "## 工作概述", "## 范围与验收", "## 变更影响", "## 决策", "## 风险", "## 实施计划",
        "## 实施记录", "## 验证", "## 代码审查", "## 发布与回滚", "## 用户回归", "## 长期知识提炼", "## Bug Fix 闭环",
    )
    for heading in required_headings:
        count = len(re.findall(rf"^{re.escape(heading)}\s*$", item.scan_text, re.MULTILINE))
        if count == 0:
            errors.append(f"missing heading: {heading}")
        elif count > 1:
            errors.append(f"duplicate heading: {heading}")
    for prefix, allowed, heading in (
        ("DEC", DEC_STATUSES, "## 决策"),
        ("RSK", RSK_STATUSES, "## 风险"),
        ("REQ", REQ_STATUSES, "## 范围与验收"),
        ("VER", VER_STATUSES, "## 验证"),
        ("REV", REV_STATUSES, "## 代码审查"),
    ):
        for block in re.finditer(rf"^### {prefix}-\d+.*?(?=^### {prefix}-|\Z)", section(item.scan_text, heading), re.MULTILINE | re.DOTALL):
            status = field_value(block.group(0), "状态")
            if status not in allowed:
                errors.append(f"unsupported {prefix} status: {status}")
        ids = re.findall(rf"^### ({prefix}-\d+)\b", section(item.scan_text, heading), re.MULTILINE)
        for record_id in sorted({value for value in ids if ids.count(value) > 1}):
            errors.append(f"duplicate {prefix} ID: {record_id}")
    return errors


def canonical_feature_validation_errors(
    repo: Path, feature_ids: tuple[str, ...], validator: str | Path | None
) -> list[str]:
    validator_path = Path(validator).expanduser().resolve() if validator else (
        Path(__file__).resolve().parents[2] / "manage-feature-docs" / "scripts" / "feature_docs.py"
    )
    if not validator_path.exists():
        return [f"canonical Feature Docs validator not found: {validator_path}"]
    git_check = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    mode = "fresh" if git_check.stdout.strip() == "true" else "structural"
    errors: list[str] = []
    for feature_id in feature_ids:
        result = subprocess.run(
            [sys.executable, str(validator_path), "validate-contract", "--repo", str(repo), "--id", feature_id, "--mode", mode],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            messages = (result.stderr or result.stdout).splitlines()
            errors.extend(
                [f"Feature Doc {feature_id}: {message}" for message in messages]
                or [f"Feature Doc {feature_id} failed canonical validation"]
            )
    return errors


def gate_errors(
    item: WorkItem,
    target: str,
    repo: Path | None = None,
    feature_validator: str | Path | None = None,
) -> list[str]:
    errors = structural_errors(item)
    decisions = section(item.scan_text, "## 决策")
    requirements = section(item.scan_text, "## 范围与验收")
    impacts = section(item.scan_text, "## 变更影响")
    plan = section(item.scan_text, "## 实施计划")
    verification = section(item.scan_text, "## 验证")
    review = section(item.scan_text, "## 代码审查")
    release = section(item.scan_text, "## 发布与回滚")
    regression = section(item.scan_text, "## 用户回归")
    knowledge = section(item.scan_text, "## 长期知识提炼")
    bugfix = section(item.scan_text, "## Bug Fix 闭环")
    risk = item.metadata.get("risk-level", "")
    requirement_blocks = list(re.finditer(r"^### REQ-\d+.*?(?=^### REQ-|\Z)", requirements, re.MULTILINE | re.DOTALL))
    verification_blocks = list(re.finditer(r"^### VER-\d+.*?(?=^### VER-|\Z)", verification, re.MULTILINE | re.DOTALL))
    risk_blocks = list(re.finditer(r"^### RSK-\d+.*?(?=^### RSK-|\Z)", section(item.scan_text, "## 风险"), re.MULTILINE | re.DOTALL))

    if target in {"clarified", "planned", "implementing", "verifying", "handoff-ready", "closed"}:
        if re.search(r"^-\s+\*\*状态\*\*：\s*BLOCKER\s*$", decisions, re.MULTILINE):
            errors.append("BLOCKER decision remains")

    if target in {"planned", "implementing", "verifying", "handoff-ready", "closed"}:
        if not requirement_blocks:
            errors.append("planning requires at least one REQ")
        for match in requirement_blocks:
            title = match.group(0).splitlines()[0]
            for field in ("需求", "验收标准"):
                if has_placeholder(field_value(match.group(0), field)):
                    errors.append(f"{title} requires {field}")
        for dimension in IMPACT_DIMENSIONS:
            matches = re.findall(rf"^\|\s*{re.escape(dimension)}\s*\|\s*(.*?)\s*\|$", impacts, re.MULTILINE)
            if len(matches) != 1:
                errors.append(f"impact {dimension} must appear exactly once")
                continue
            value = matches[0]
            if value not in {"affected", "none"}:
                errors.append(f"impact {dimension} must be affected or none")
            elif value == "affected":
                minimum = "high" if dimension in HIGH_IMPACTS else "medium" if dimension in MEDIUM_IMPACTS else "low"
                if RISK_RANK.get(risk, 0) < RISK_RANK[minimum]:
                    errors.append(f"impact {dimension} requires minimum risk {minimum}")
        for match in re.finditer(r"^### DEC-\d+.*?(?=^### DEC-|\Z)", decisions, re.MULTILINE | re.DOTALL):
            body = match.group(0)
            if field_value(body, "状态") == "OPEN" and has_placeholder(field_value(body, "确认路径")):
                errors.append(f"open decision lacks confirmation path: {match.group(0).splitlines()[0]}")
        for match in risk_blocks:
            body = match.group(0)
            if field_value(body, "状态") == "OPEN" and has_placeholder(field_value(body, "确认路径")):
                errors.append(f"open risk lacks confirmation path: {match.group(0).splitlines()[0]}")

    if target in {"implementing", "verifying", "handoff-ready", "closed"}:
        plan_items = re.findall(r"^- \[[ xX]\]\s+\S.*$", plan, re.MULTILINE)
        if not plan_items or "- [ ]" in plan or "WORK_ITEM:REPLACE" in plan:
            errors.append("implementation plan is incomplete")

    if target in {"verifying", "handoff-ready", "closed"}:
        for match in requirement_blocks:
            body = match.group(0)
            if has_placeholder(field_value(body, "实现证据")):
                errors.append(f"requirement {match.group(0).splitlines()[0]} lacks implementation evidence")
            if field_value(body, "状态") not in {"IMPLEMENTED", "VERIFIED", "DEFERRED"}:
                errors.append(f"requirement {match.group(0).splitlines()[0]} is not implemented")

    if target in {"handoff-ready", "closed"}:
        decision_blocks = list(re.finditer(r"^### DEC-\d+.*?(?=^### DEC-|\Z)", decisions, re.MULTILINE | re.DOTALL))
        for match in decision_blocks:
            body = match.group(0)
            status = field_value(body, "状态")
            required_fields = {
                "BLOCKER": ("确认路径",),
                "OPEN": ("确认路径",),
                "RESOLVED": ("决定", "原因", "取舍", "证据"),
                "DEFERRED": ("原因", "确认路径"),
            }.get(status, ())
            for field in required_fields:
                if has_placeholder(field_value(body, field)):
                    errors.append(f"decision {match.group(0).splitlines()[0]} requires {field} for status {status}")
        decision_statuses = {
            re.match(r"^### (DEC-\d+)\b", match.group(0), re.MULTILINE).group(1): field_value(match.group(0), "状态")
            for match in re.finditer(r"^### DEC-\d+.*?(?=^### DEC-|\Z)", decisions, re.MULTILINE | re.DOTALL)
        }
        recorded_basis = item.metadata.get("verification-basis", "")
        current_basis = verification_basis(repo) if repo is not None else ""
        if repo is not None and current_basis.startswith("HEAD "):
            if not recorded_basis or recorded_basis == "pending":
                errors.append("verification basis is missing")
            elif recorded_basis != current_basis:
                errors.append("verification basis does not match current implementation")
        requirement_ids = {
            re.match(r"^### (REQ-\d+)\b", match.group(0), re.MULTILINE).group(1)
            for match in requirement_blocks
        }
        for match in verification_blocks:
            linked = field_value(match.group(0), "关联需求")
            if not linked or linked not in requirement_ids:
                errors.append(f"verification references unknown requirement {linked}")
            status = field_value(match.group(0), "状态")
            if status in {"PASS", "FAIL", "SKIPPED"} and has_placeholder(field_value(match.group(0), "证据")):
                errors.append(f"verification {match.group(0).splitlines()[0]} requires evidence for status {status}")
        for match in requirement_blocks:
            body = match.group(0)
            req_id = re.search(r"REQ-\d+", match.group(0)).group(0)
            status = field_value(body, "状态")
            if status not in {"VERIFIED", "DEFERRED"}:
                errors.append(f"requirement {match.group(0).splitlines()[0]} lacks verification")
            if has_placeholder(field_value(body, "验证证据")):
                errors.append(f"requirement {match.group(0).splitlines()[0]} lacks verification evidence")
            if status == "VERIFIED" and not any(field_value(block.group(0), "关联需求") == req_id and field_value(block.group(0), "状态") == "PASS" for block in verification_blocks):
                errors.append(f"requirement {req_id} requires a PASS VER")
            if status == "DEFERRED":
                basis = field_value(body, "延期依据")
                follow_up = field_value(body, "后续工作")
                if not re.fullmatch(r"DEC-\d+", basis) or not re.fullmatch(r"WORK-\d{8}-\d{3}", follow_up):
                    errors.append(f"deferred requirement {req_id} needs DEC approval and follow-up WORK")
                else:
                    decision_ids = {
                        re.match(r"^### (DEC-\d+)\b", match.group(0), re.MULTILINE).group(1)
                        for match in re.finditer(r"^### DEC-\d+.*?(?=^### DEC-|\Z)", decisions, re.MULTILINE | re.DOTALL)
                    }
                    if basis not in decision_ids:
                        errors.append(f"deferred requirement {req_id} references unknown decision {basis}")
                    elif decision_statuses.get(basis) not in {"RESOLVED", "DEFERRED"}:
                        errors.append(f"deferred requirement {req_id} decision {basis} must be resolved")
                    if repo is not None:
                        follow_up_path = work_directory(repo) / f"{follow_up}.md"
                        if not follow_up_path.exists():
                            errors.append(f"deferred requirement {req_id} references missing follow-up work {follow_up}")
                        else:
                            follow_up_item = read_work_item(follow_up_path)
                            follow_up_errors = structural_errors(follow_up_item)
                            if follow_up_item.work_id != follow_up or follow_up_errors:
                                errors.append(f"deferred requirement {req_id} follow-up work {follow_up} is not a valid Work Item")
                    if follow_up == item.work_id:
                        errors.append(f"deferred requirement {req_id} cannot follow up with itself")
        if "WORK_ITEM:REPLACE" in verification:
            errors.append("verification evidence is incomplete")
        for match in re.finditer(r"^### VER-\d+.*?(?=^### VER-|\Z)", verification, re.MULTILINE | re.DOTALL):
            status = field_value(match.group(0), "状态")
            if status != "PASS":
                errors.append(f"verification {match.group(0).splitlines()[0]} must PASS")
        review_blocks = list(re.finditer(r"^### REV-(\d+).*?(?=^### REV-|\Z)", review, re.MULTILINE | re.DOTALL))
        for match in review_blocks:
            status = field_value(match.group(0), "状态")
            if status in {"PASS", "FAIL"}:
                for field in ("范围", "证据"):
                    if has_placeholder(field_value(match.group(0), field)):
                        errors.append(f"review {match.group(0).splitlines()[0]} requires {field} for status {status}")
        if risk in {"medium", "high"} and review_blocks:
            latest_review = max(review_blocks, key=lambda match: int(re.match(r"^### REV-(\d+)", match.group(0)).group(1)))
            if field_value(latest_review.group(0), "状态") != "PASS":
                errors.append("latest review must pass for medium or high risk")
        elif risk in {"medium", "high"}:
            errors.append("review must pass for medium or high risk")
        if risk == "high":
            if has_placeholder(field_value(release, "发布策略")):
                errors.append("release strategy is required for high risk")
            if has_placeholder(field_value(release, "回滚策略")):
                errors.append("rollback strategy is required for high risk")
        for match in risk_blocks:
            body = match.group(0)
            if field_value(body, "状态") == "OPEN":
                errors.append(f"open risk remains: {match.group(0).splitlines()[0]}")
            status = field_value(body, "状态")
            required_fields = {
                "MITIGATED": ("概率", "影响", "缓解措施", "验证"),
                "ACCEPTED": ("影响", "确认路径", "验证"),
                "CLOSED": ("缓解措施", "验证"),
            }.get(status, ())
            for field in required_fields:
                if has_placeholder(field_value(body, field)):
                    errors.append(f"{match.group(0).splitlines()[0]} requires {field} for status {status}")
        for field in REGRESSION_FIELDS[:-1]:
            if has_placeholder(field_value(regression, field)):
                errors.append(f"user regression handoff lacks {field}")
        if UNRESOLVED_RE.search(regression):
            errors.append("user regression handoff contains unresolved language")
        if field_value(regression, "是否需要用户回归") not in {"是", "否"}:
            errors.append("user regression decision must be 是 or 否")
        if item.metadata.get("work-type") == "bugfix":
            for field in ("症状", "复现", "根因", "失败机制", "修复", "回归保护"):
                if has_placeholder(field_value(bugfix, field)) or field_value(bugfix, field).startswith("不适用"):
                    errors.append(f"bugfix requires {field}")

    if target == "closed":
        needed = field_value(regression, "是否需要用户回归")
        result = field_value(regression, "用户回归结果")
        if needed not in {"是", "否"}:
            errors.append("user regression decision must be 是 or 否")
        if needed == "是" and result != "passed":
            errors.append("user regression must pass before close")
        if needed == "否" and result != "not-required":
            errors.append("no-regression work must record result not-required")
        if has_placeholder(field_value(knowledge, "Feature Docs")):
            errors.append("closure requires Feature Docs evidence")
        if repo is not None:
            feature_ids = tuple(value.strip() for value in item.metadata.get("feature-ids", "").split(",") if value.strip())
            documented_features = tuple(value.strip() for value in field_value(knowledge, "Feature Docs").split(",") if value.strip())
            if feature_ids and documented_features != feature_ids:
                errors.append("Feature Docs evidence must list feature-ids in the same order")
            if feature_ids:
                errors.extend(canonical_feature_validation_errors(repo, feature_ids, feature_validator))
    return errors


def find_work_item(repo: Path, work_id: str) -> WorkItem:
    path = work_directory(repo) / f"{work_id}.md"
    if path.exists():
        return read_work_item(path)
    matches = [item for item in discover_work_items(repo) if item.work_id == work_id]
    if len(matches) == 1:
        return matches[0]
    raise DevWorkError(f"work item not found: {work_id}")


def transition_work_item(
    repo: str | Path, work_id: str, target: str, feature_validator: str | Path | None = None
) -> list[str]:
    root = ensure_repo(repo)
    if target not in STATUSES:
        return [f"unsupported target status: {target}"]
    item = find_work_item(root, work_id)
    current = item.metadata.get("work-status", "")
    errors = []
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        errors.append(f"invalid transition: {current} -> {target}")
    errors.extend(gate_errors(item, target, root, feature_validator))
    if errors:
        return errors
    text = re.sub(r"(<!-- work-status:\s*)(.*?)(\s*-->)", rf"\g<1>{target}\g<3>", item.text, count=1)
    text = re.sub(r"(<!-- updated:\s*)(.*?)(\s*-->)", rf"\g<1>{dt.date.today().isoformat()}\g<3>", text, count=1)
    if target == "verifying":
        text = re.sub(r"(<!-- verification-basis:\s*)(.*?)(\s*-->)", rf"\g<1>{verification_basis(root)}\g<3>", text, count=1)
    atomic_write(item.path, text)
    sync_index(root)
    return []


def validate_work_item(repo: str | Path, work_id: str, gate: str | None = None) -> list[str]:
    root = ensure_repo(repo)
    item = find_work_item(root, work_id)
    errors = gate_errors(item, gate, root) if gate else structural_errors(item)
    if not gate:
        errors.extend(work_index_errors(root))
    return errors


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Create and gate project-local development work items.")
    sub = value.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--repo", required=True)
    init.add_argument("--id")
    init.add_argument("--title", required=True)
    init.add_argument("--type", dest="work_type", required=True, choices=sorted(WORK_TYPES))
    init.add_argument("--risk", required=True, choices=sorted(RISK_LEVELS))
    init.add_argument("--features", nargs="*", default=[])
    status = sub.add_parser("status")
    status.add_argument("--repo", required=True)
    status.add_argument("--id", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--repo", required=True)
    validate.add_argument("--id", required=True)
    validate.add_argument("--gate", choices=sorted(STATUSES))
    transition = sub.add_parser("transition")
    transition.add_argument("--repo", required=True)
    transition.add_argument("--id", required=True)
    transition.add_argument("--to", required=True, choices=sorted(STATUSES))
    transition.add_argument("--feature-validator", help="path to manage-feature-docs/scripts/feature_docs.py")
    close = sub.add_parser("close")
    close.add_argument("--repo", required=True)
    close.add_argument("--id", required=True)
    close.add_argument("--feature-validator", help="path to manage-feature-docs/scripts/feature_docs.py")
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "init":
            path = init_work_item(args.repo, args.id, args.title, args.work_type, args.risk, tuple(args.features))
            print(path)
            return 0
        root = ensure_repo(args.repo)
        if args.command == "status":
            item = find_work_item(root, args.id)
            print(f"{item.work_id}\t{item.metadata.get('work-status')}\t{item.metadata.get('risk-level')}\t{item.metadata.get('work-title')}")
            return 0
        target = "closed" if args.command == "close" else getattr(args, "to", None)
        errors = (
            transition_work_item(root, args.id, target, getattr(args, "feature_validator", None))
            if target
            else validate_work_item(root, args.id, args.gate)
        )
        if errors:
            for error in errors:
                print(f"ERROR\t{error}", file=sys.stderr)
            return 1
        print("OK")
        return 0
    except (DevWorkError, OSError) as error:
        print(f"ERROR\t{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
