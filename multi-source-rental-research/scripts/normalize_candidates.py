#!/usr/bin/env python3
"""Flag conservative, pairwise rental-candidate duplicate leads without merging."""

import argparse
import difflib
import json
import sys
import unicodedata
from pathlib import Path


def _normalized(value):
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(char for char in text if not char.isspace() and not unicodedata.category(char).startswith("P"))


def _similarity(left, right):
    return difflib.SequenceMatcher(None, _normalized(left), _normalized(right)).ratio()


def normalize(payload):
    candidates = payload.get("candidates") if isinstance(payload, dict) else payload
    if not isinstance(candidates, list):
        raise ValueError("input must be a JSON array or an object with a candidates array")
    records = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise ValueError(f"candidate at index {index} must be an object")
        record = dict(candidate)
        record["id"] = record.get("id", index)
        record["normalized_name"] = _normalized(record.get("name"))
        record["normalized_address"] = _normalized(record.get("address"))
        record["normalized_operator"] = _normalized(record.get("operator"))
        record["normalized_property_type"] = _normalized(record.get("property_type"))
        record["normalized_locality"] = _normalized(record.get("locality"))
        records.append(record)

    possible_duplicates = []
    for index, left in enumerate(records):
        for right in records[index + 1 :]:
            name_similarity = _similarity(left.get("name"), right.get("name"))
            same_type = bool(left["normalized_property_type"] and left["normalized_property_type"] == right["normalized_property_type"])
            same_address = bool(left["normalized_address"] and left["normalized_address"] == right["normalized_address"])
            same_operator = bool(left["normalized_operator"] and left["normalized_operator"] == right["normalized_operator"])
            same_locality = bool(left["normalized_locality"] and left["normalized_locality"] == right["normalized_locality"])
            confidence, reasons = None, []
            if same_address and same_type and name_similarity >= 0.80:
                confidence, reasons = "high", ["same_normalized_address", "same_property_type", "similar_name"]
            elif same_operator and same_type and same_locality and name_similarity >= 0.55:
                confidence, reasons = "medium", ["same_operator", "same_property_type", "same_locality", "similar_name"]
            if confidence:
                possible_duplicates.append({
                    "left_id": left["id"],
                    "right_id": right["id"],
                    "confidence": confidence,
                    "reasons": reasons,
                    "name_similarity": round(name_similarity, 3),
                })
    return {"records": records, "possible_duplicates": possible_duplicates, "merge_performed": False}


def _read_json(path):
    return json.load(sys.stdin) if path == "-" else json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", default="-", help="JSON file, or - for stdin")
    args = parser.parse_args(argv)
    try:
        result = normalize(_read_json(args.input))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
