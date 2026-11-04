#!/usr/bin/env python3
"""Calculate source-risk alignment metrics with deterministic holdout assignment."""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


def assign_split(public_post_id):
    """Return a deterministic split chosen without seeing a user risk score."""
    if not isinstance(public_post_id, str) or not public_post_id.strip():
        raise ValueError("public_post_id must be a non-empty string")
    bucket = int(hashlib.sha256(("xhs-rental-v21|" + public_post_id).encode("utf-8")).hexdigest(), 16) % 5
    return "holdout" if bucket == 0 else "development"


def _weighted_kappa(pairs):
    if not pairs:
        return None
    count = len(pairs)
    actual = Counter(int(user) for user, _ in pairs)
    predicted = Counter(int(model) for _, model in pairs)
    observed = sum(1 - ((user - model) ** 2) / 16 for user, model in pairs) / count
    expected = sum(
        (actual[left] / count) * (predicted[right] / count) * (1 - ((left - right) ** 2) / 16)
        for left in range(1, 6)
        for right in range(1, 6)
    )
    return None if expected == 1 else (observed - expected) / (1 - expected)


def calculate(records, split=None):
    if not isinstance(records, list):
        raise ValueError("input must be a JSON array or JSONL records")
    selected = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"record {index} must be an object")
        if split is None or record.get("split") == split:
            selected.append((index, record))
    pairs, rounds, user_distribution = [], set(), Counter()
    for index, record in selected:
        user_risk, model_risk = record.get("user_risk"), record.get("model_risk")
        if isinstance(user_risk, bool) or not isinstance(user_risk, (int, float)) or not 1 <= user_risk <= 5:
            raise ValueError(f"record {index} user_risk must be between 1 and 5")
        if isinstance(model_risk, bool) or not isinstance(model_risk, (int, float)) or not 1 <= model_risk <= 5:
            raise ValueError(f"record {index} model_risk must be between 1 and 5")
        if record.get("round") is None:
            raise ValueError(f"record {index} requires round")
        rounds.add(str(record["round"]))
        pairs.append((float(user_risk), float(model_risk)))
        user_distribution[int(user_risk)] += 1
    count = len(pairs)
    mae = sum(abs(user - model) for user, model in pairs) / count if count else None
    within_one = sum(abs(user - model) <= 1 for user, model in pairs) / count if count else None
    user_high = sum(user >= 4 for user, _ in pairs)
    predicted_high = sum(model >= 4 for _, model in pairs)
    true_positive = sum(user >= 4 and model >= 4 for user, model in pairs)
    recall = true_positive / user_high if user_high else None
    precision = true_positive / predicted_high if predicted_high else None
    distribution_coverage = all(user_distribution[score] >= 4 for score in range(1, 6))
    kappa = _weighted_kappa(pairs)
    alignment_good = bool(
        count >= 30 and len(rounds) >= 3 and distribution_coverage and mae is not None and mae <= 0.75
        and within_one is not None and within_one >= 0.85 and recall == 1.0 and precision is not None and precision >= 0.5
    )
    return {
        "count": count,
        "rounds": len(rounds),
        "mae": mae,
        "within_one_rate": within_one,
        "high_risk_recall": recall,
        "high_risk_precision": precision,
        "user_risk_distribution": {str(score): user_distribution[score] for score in range(1, 6)},
        "distribution_coverage": distribution_coverage,
        "weighted_kappa": kappa,
        "alignment_good": alignment_good,
    }


def _read_records(path):
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    stripped = text.lstrip()
    if not stripped:
        return []
    if stripped.startswith("["):
        return json.loads(text)
    records = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {line_number}: {exc.msg}") from exc
    return records


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", default="-", help="JSON array/JSONL records, or - for stdin")
    parser.add_argument("--split", help="include only this split, such as holdout")
    parser.add_argument("--assign-split", help="print deterministic split for a public post identifier")
    args = parser.parse_args(argv)
    if args.assign_split:
        print(assign_split(args.assign_split))
        return 0
    try:
        result = calculate(_read_records(args.input), args.split)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
