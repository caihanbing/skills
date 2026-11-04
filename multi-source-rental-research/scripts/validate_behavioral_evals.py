#!/usr/bin/env python3
"""Validate frozen, runner-independent behavioral evaluation contracts."""

import argparse
import json
import sys
from pathlib import Path


REQUIRED_CASE_FIELDS = ("id", "prompt", "available_evidence", "expected_obligations", "prohibited_outcomes")
RUNNER_RESULT_FIELDS = ("case_id", "raw_response", "tool_trace", "outcomes")


def validate(payload):
    errors = []
    if not isinstance(payload, dict):
        return {"valid": False, "errors": ["input must be an object"], "case_count": 0}
    if payload.get("format_version") != "1.0":
        errors.append("format_version must be '1.0'")
    if payload.get("prohibited_outcomes_are_critical") is not True:
        errors.append("prohibited_outcomes_are_critical must be true")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        return {"valid": False, "errors": errors + ["cases must be an array"], "case_count": 0}
    seen = set()
    for index, case in enumerate(cases):
        prefix = f"case {index}"
        if not isinstance(case, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        for field in REQUIRED_CASE_FIELDS:
            value = case.get(field)
            if field == "available_evidence":
                if not isinstance(value, list):
                    errors.append(f"{prefix}: available_evidence must be an array")
            elif field in {"expected_obligations", "prohibited_outcomes"}:
                if not isinstance(value, list) or not value:
                    errors.append(f"{prefix}: {field} must be a non-empty array")
            elif not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}: {field} must be a non-empty string")
        case_id = case.get("id")
        if isinstance(case_id, str) and case_id in seen:
            errors.append(f"duplicate case id: {case_id}")
        elif isinstance(case_id, str):
            seen.add(case_id)
    return {"valid": not errors, "errors": errors, "case_count": len(cases)}


def validate_runner_result(contract, result):
    contract_validation = validate(contract)
    errors = list(contract_validation["errors"])
    if not isinstance(result, dict):
        return {
            "valid": False,
            "passed": False,
            "errors": errors + ["runner result must be an object"],
            "missing_obligations": [],
            "critical_violations": [],
            "unknown_outcome_ids": [],
        }
    cases = {case.get("id"): case for case in contract.get("cases", []) if isinstance(case, dict)}
    case_ids = set(cases)
    for field in RUNNER_RESULT_FIELDS:
        if field not in result:
            errors.append(f"runner result: {field} is required")
    if result.get("case_id") not in case_ids:
        errors.append("runner result: case_id must reference a contract case")
    if not isinstance(result.get("raw_response"), str):
        errors.append("runner result: raw_response must be a string")
    if not isinstance(result.get("tool_trace"), list):
        errors.append("runner result: tool_trace must be an array")
    outcomes = result.get("outcomes")
    satisfied, violated = [], []
    if not isinstance(outcomes, dict):
        errors.append("runner result: outcomes must be an object")
    else:
        for field in ("satisfied", "violated"):
            if not isinstance(outcomes.get(field), list):
                errors.append(f"runner result: outcomes.{field} must be an array")
            elif not all(isinstance(item, str) and item.strip() for item in outcomes[field]):
                errors.append(f"runner result: outcomes.{field} entries must be non-empty strings")
        if isinstance(outcomes.get("satisfied"), list):
            satisfied = outcomes["satisfied"]
        if isinstance(outcomes.get("violated"), list):
            violated = outcomes["violated"]
    case = cases.get(result.get("case_id"))
    expected = case.get("expected_obligations", []) if isinstance(case, dict) else []
    prohibited = case.get("prohibited_outcomes", []) if isinstance(case, dict) else []
    satisfied_set, violated_set = set(satisfied), set(violated)
    missing_obligations = [obligation for obligation in expected if obligation not in satisfied_set]
    critical_violations = [outcome for outcome in prohibited if outcome in violated_set]
    known_outcomes = set(expected) | set(prohibited)
    unknown_outcome_ids = sorted((satisfied_set | violated_set) - known_outcomes)
    valid = not errors
    return {
        "valid": valid,
        "passed": bool(valid and not missing_obligations and not critical_violations and not unknown_outcome_ids),
        "errors": errors,
        "missing_obligations": missing_obligations,
        "critical_violations": critical_violations,
        "unknown_outcome_ids": unknown_outcome_ids,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="behavioral-cases JSON file")
    args = parser.parse_args(argv)
    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = validate(payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"valid": False, "errors": [str(exc)], "case_count": 0}
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
