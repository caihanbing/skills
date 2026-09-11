#!/usr/bin/env python3
"""Create a clean distributable archive for one local skill."""

from __future__ import annotations

import argparse
from pathlib import Path
import zipfile


EXCLUDED_PARTS = {".git", ".DS_Store", "__MACOSX", "__pycache__"}
ALLOWED_TOP_LEVEL = {"SKILL.md", "agents", "assets", "references", "scripts", "tests", "evals"}


def include(path: Path, root: Path) -> bool:
    if path.is_symlink():
        return False
    relative = path.relative_to(root)
    if not relative.parts or relative.parts[0] not in ALLOWED_TOP_LEVEL:
        return False
    return not any(part in EXCLUDED_PARTS or part.endswith(".pyc") for part in relative.parts)


def package(skill_dir: Path, output: Path) -> None:
    root = skill_dir.resolve()
    if not (root / "SKILL.md").is_file():
        raise ValueError("skill directory must contain SKILL.md")
    resolved_output = output.resolve()
    try:
        resolved_output.relative_to(root)
        output_is_inside_skill = True
    except ValueError:
        output_is_inside_skill = False
    if output_is_inside_skill:
        raise ValueError("output archive must be outside the skill directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and include(path, root):
                archive.write(path, Path(root.name) / path.relative_to(root))


def main() -> int:
    parser = argparse.ArgumentParser(description="Package a Skill without local metadata.")
    parser.add_argument("--skill-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    package(Path(args.skill_dir), Path(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
