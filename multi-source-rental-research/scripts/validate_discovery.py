#!/usr/bin/env python3
"""Validate a conservative DiscoveryLead contract without resolving entities."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


SCHEMA_VERSION = "1.1"
PROVIDER_CLASSES = {"map", "market"}
APPLICABILITY_STATUSES = {"applicable", "not_applicable", "unknown"}
ACCESS_STATUSES = {"accessible", "limited", "unavailable"}
LEAD_KINDS = {"project", "offer"}
PAYLOAD_FIELDS = {"schema_version", "target_location", "target_city", "attempts", "leads"}
ATTEMPT_FIELDS = {
    "id", "provider", "provider_class", "query", "entry_url", "retrieved_at",
    "applicability_status", "applicability_basis", "access_status", "limitation_reason",
}
COMMON_LEAD_FIELDS = {
    "id", "attempt_id", "lead_kind", "candidate_name", "address", "operator",
    "property_type", "locality", "result_url", "resolved_project_id",
}
PROJECT_LEAD_FIELDS = COMMON_LEAD_FIELDS
OFFER_LEAD_FIELDS = COMMON_LEAD_FIELDS | {
    "offer_reference", "room_type", "area", "rent", "listing_id", "availability_signal",
}


def _is_text(value):
    return isinstance(value, str) and bool(value.strip())


def _valid_url(value):
    if not _is_text(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _parse_date(value, field, record_id, as_of, errors):
    if not _is_text(value):
        errors.append(f"{record_id}: {field} must be YYYY-MM-DD")
        return
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        errors.append(f"{record_id}: {field} must be YYYY-MM-DD")
        return
    if parsed > as_of:
        errors.append(f"{record_id}: {field} is after the as-of date")


def _index(items, kind, errors):
    if not isinstance(items, list):
        errors.append(f"{kind} must be an array")
        return {}
    index = {}
    for position, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{kind}[{position}] must be an object")
            continue
        record_id = item.get("id")
        if not _is_text(record_id):
            errors.append(f"{kind}[{position}] has no stable string id")
        elif record_id in index:
            errors.append(f"duplicate {kind} id: {record_id}")
        else:
            index[record_id] = item
    return index


def _required_text(record, field, record_id, errors):
    if not _is_text(record.get(field)):
        errors.append(f"{record_id}: {field} is required")


def _undeclared_fields(record, allowed, record_id, errors):
    unknown = sorted(set(record) - allowed)
    if unknown:
        errors.append(f"{record_id}: undeclared fields: {', '.join(unknown)}")


def validate(payload, as_of=None):
    as_of = as_of or date.today()
    errors = []
    if not isinstance(payload, dict):
        return {"valid": False, "errors": ["input must be an object"], "summary": {}}
    _undeclared_fields(payload, PAYLOAD_FIELDS, "payload", errors)
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}; legacy discovery is not accepted")
    _required_text(payload, "target_location", "payload", errors)
    _required_text(payload, "target_city", "payload", errors)
    attempts = _index(payload.get("attempts"), "attempts", errors)
    leads = _index(payload.get("leads"), "leads", errors)

    for attempt_id, attempt in attempts.items():
        _undeclared_fields(attempt, ATTEMPT_FIELDS, f"attempt {attempt_id}", errors)
        _required_text(attempt, "provider", f"attempt {attempt_id}", errors)
        _required_text(attempt, "query", f"attempt {attempt_id}", errors)
        if attempt.get("provider_class") not in PROVIDER_CLASSES:
            errors.append(f"attempt {attempt_id}: provider_class must be map or market")
        if not _valid_url(attempt.get("entry_url")):
            errors.append(f"attempt {attempt_id}: entry_url must be an http or https URL")
        _parse_date(attempt.get("retrieved_at"), "retrieved_at", f"attempt {attempt_id}", as_of, errors)
        applicability = attempt.get("applicability_status")
        if applicability not in APPLICABILITY_STATUSES:
            errors.append(f"attempt {attempt_id}: invalid applicability_status")
        elif applicability == "not_applicable":
            _required_text(attempt, "applicability_basis", f"attempt {attempt_id}", errors)
        status = attempt.get("access_status")
        if status not in ACCESS_STATUSES:
            errors.append(f"attempt {attempt_id}: invalid access_status")
        elif status in {"limited", "unavailable"}:
            _required_text(attempt, "limitation_reason", f"attempt {attempt_id}", errors)

    for lead_id, lead in leads.items():
        attempt_id = lead.get("attempt_id")
        if not _is_text(attempt_id) or attempt_id not in attempts:
            errors.append(f"lead {lead_id}: attempt_id must reference an attempt")
            continue
        kind = lead.get("lead_kind")
        if kind not in LEAD_KINDS:
            errors.append(f"lead {lead_id}: lead_kind must be project or offer")
            allowed_fields = COMMON_LEAD_FIELDS
        else:
            allowed_fields = PROJECT_LEAD_FIELDS if kind == "project" else OFFER_LEAD_FIELDS
        _undeclared_fields(lead, allowed_fields, f"lead {lead_id}", errors)
        _required_text(lead, "candidate_name", f"lead {lead_id}", errors)
        _required_text(lead, "property_type", f"lead {lead_id}", errors)
        if not _valid_url(lead.get("result_url")):
            errors.append(f"lead {lead_id}: result_url must be an http or https URL")
        resolved_project_id = lead.get("resolved_project_id")
        if resolved_project_id is not None and not _is_text(resolved_project_id):
            errors.append(f"lead {lead_id}: resolved_project_id must be a non-empty string when present")

        attempt = attempts[attempt_id]
        if attempt.get("applicability_status") != "applicable":
            errors.append(f"lead {lead_id}: parent attempt must be applicable")
        if attempt.get("access_status") not in {"accessible", "limited"}:
            errors.append(f"lead {lead_id}: parent attempt must be accessible or limited")
        provider_class = attempt.get("provider_class")
        if kind == "offer":
            if provider_class != "market":
                errors.append(f"lead {lead_id}: offer lead must originate from a market attempt")
            _required_text(lead, "offer_reference", f"lead {lead_id}", errors)
        elif kind == "project" and provider_class == "map" and "rent" in lead:
            errors.append(f"lead {lead_id}: map project lead cannot contain rent")

    resolved_projects = {
        lead.get("resolved_project_id")
        for lead in leads.values()
        if _is_text(lead.get("resolved_project_id"))
    }
    summary = {
        "raw_leads": len(leads),
        "unique_resolved_projects": len(resolved_projects),
        "potential_offer_leads": sum(lead.get("lead_kind") == "offer" for lead in leads.values()),
    }
    return {"valid": not errors, "errors": errors, "summary": summary}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", default="-", help="DiscoveryLead JSON file, or - for stdin")
    parser.add_argument("--as-of", type=date.fromisoformat, help="as-of date (YYYY-MM-DD)")
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        result = validate(json.loads(raw), args.as_of)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"valid": False, "errors": [str(exc)], "summary": {}}
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
