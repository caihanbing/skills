#!/usr/bin/env python3
"""Validate versioned rental evidence records and conservative freshness."""

import argparse
import copy
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


SCHEMA_VERSION = "2.2"
LABELS = {"已核实事实", "运营方声明", "市场参考", "小红书租住体验", "推导结果", "未核实"}
SOURCE_CLASSES = {"authority", "operator", "market", "resident"}
LOCATOR_KINDS = {"url", "user_file", "user_message", "document"}
CONFLICT_STATES = {"none", "conflicting", "resolved", "unknown"}
LABEL_SOURCE_CLASSES = {
    "已核实事实": {"authority"},
    "运营方声明": {"operator"},
    "市场参考": {"market"},
    "小红书租住体验": {"resident"},
}
RELATION_FAMILIES = {
    "authority": {"government_registry", "government_notice", "official_public_record", "utility_tariff", "map_route"},
    "operator": {"operator_page", "operator_quote", "landlord_statement", "property_management_notice"},
    "market": {"broker", "listing", "aggregator", "agency_quote"},
    "resident": {"xiaohongshu_renter", "resident_comment", "tenant_interview"},
}
CANONICAL_RELATIONS = {relation for family in RELATION_FAMILIES.values() for relation in family}
FRESHNESS_DAYS = {"current_offer": 30, "discount": 30, "inventory": 30, "fees": 90, "pet_rules": 90, "utilities": 90, "renter_experience": 730}
EVERGREEN_CATEGORIES = {"static_fact", "evergreen"}
NARROW_RELATION_FIELDS = {
    "map_route": {"commute", "commute_time", "distance", "route", "route_distance", "travel_time"},
    "utility_tariff": {"utilities", "utility_tariff"},
}
IDENTITY_MATCHES = {"strong", "medium", "weak"}


def _parse_date(value, field, errors, entity_id):
    if not isinstance(value, str):
        errors.append(f"{entity_id}: {field} must be YYYY-MM-DD")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{entity_id}: {field} must be YYYY-MM-DD")
        return None


def _index(items, kind, errors):
    if not isinstance(items, list):
        errors.append(f"{kind} must be an array")
        return {}
    indexed = {}
    for position, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{kind}[{position}] must be an object")
            continue
        entity_id = item.get("id")
        if not isinstance(entity_id, str) or not entity_id.strip():
            errors.append(f"{kind}[{position}] has no stable string id")
        elif entity_id in indexed:
            errors.append(f"duplicate {kind} id: {entity_id}")
        else:
            indexed[entity_id] = item
    return indexed


def _required_string(record, field, errors, entity_id):
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{entity_id}: {field} is required")
        return None
    return value


def _is_id(value):
    return isinstance(value, str) and bool(value.strip())


def _validate_source(source, as_of, errors):
    source_id = source.get("id", "<missing source>")
    locator = source.get("locator")
    if not isinstance(locator, dict):
        errors.append(f"source {source_id}: locator is required")
    else:
        kind, ref = locator.get("kind"), locator.get("ref")
        if kind not in LOCATOR_KINDS:
            errors.append(f"source {source_id}: invalid locator kind: {kind!r}")
        if not isinstance(ref, str) or not ref.strip():
            errors.append(f"source {source_id}: locator ref is required")
        elif kind == "url":
            parsed = urlparse(ref)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append(f"source {source_id}: url locator must be http or https")
    if source.get("source_class") not in SOURCE_CLASSES:
        errors.append(f"source {source_id}: invalid source_class: {source.get('source_class')!r}")
    relation = _required_string(source, "source_relation", errors, f"source {source_id}")
    source_class = source.get("source_class")
    if relation == "other":
        detail = _required_string(source, "relation_detail", errors, f"source {source_id}")
        if detail in CANONICAL_RELATIONS:
            errors.append(f"source {source_id}: other relation_detail cannot restate a canonical relation")
    elif relation and source_class in RELATION_FAMILIES and relation not in RELATION_FAMILIES[source_class]:
        errors.append(f"source {source_id}: source_class/source_relation incompatible")
    risk = source.get("source_risk")
    if isinstance(risk, bool) or not isinstance(risk, int) or not 1 <= risk <= 5:
        errors.append(f"source {source_id}: source_risk must be an integer from 1 to 5")
    if source.get("retrieved_at") is None:
        errors.append(f"source {source_id}: retrieved_at is required")
    parsed_dates = {}
    for field in ("published_at", "observed_at", "retrieved_at"):
        if source.get(field) is not None:
            parsed = _parse_date(source[field], field, errors, f"source {source_id}")
            if parsed and parsed > as_of:
                errors.append(f"source {source_id}: {field} is after the as-of date")
                parsed = None
            parsed_dates[field] = parsed
    return parsed_dates


def _scope_key(claim):
    return ("project", claim["project_id"]) if claim.get("project_id") is not None else ("offer", claim.get("offer_id"))


def _source_freshness(claim, source_dates, as_of, errors, warnings):
    claim_id, category = claim.get("id", "<missing claim>"), claim.get("freshness_category")
    if category in EVERGREEN_CATEGORIES:
        return "evergreen"
    if category not in FRESHNESS_DAYS:
        warnings.append(f"claim {claim_id}: freshness is unknown; set freshness_category")
        return "unknown"
    effective = None
    if claim.get("effective_at") is not None:
        effective = _parse_date(claim["effective_at"], "effective_at", errors, f"claim {claim_id}")
        if effective and effective > as_of:
            errors.append(f"claim {claim_id}: effective_at is after the as-of date")
            effective = None
    anchor = effective or source_dates.get("observed_at") or source_dates.get("published_at")
    if anchor is None:
        warnings.append(f"claim {claim_id}: freshness is unknown because no effective, observed, or published date is recorded")
        return "unknown"
    status = "fresh" if (as_of - anchor).days <= FRESHNESS_DAYS[category] else "stale"
    if status == "stale":
        warnings.append(f"claim {claim_id}: stale {category} evidence")
    return status


def _most_conservative(statuses):
    if not statuses or "unknown" in statuses:
        return "unknown"
    if "stale" in statuses:
        return "stale"
    if "fresh" in statuses:
        return "fresh"
    return "evergreen"


def _validate_derived_graph(claims, claim_index, offers, errors):
    graph = {}
    for claim in claims:
        if not isinstance(claim, dict) or claim.get("label") != "推导结果":
            continue
        claim_id, dependencies = claim.get("id", "<missing claim>"), claim.get("derived_from")
        if not _is_id(claim_id):
            continue
        if not isinstance(dependencies, list) or not dependencies:
            errors.append(f"claim {claim_id}: derived_from is required for 推导结果")
            continue
        graph[claim_id] = []
        for dependency_id in dependencies:
            if not _is_id(dependency_id):
                errors.append(f"claim {claim_id}: derived_from IDs must be non-empty strings")
                continue
            dependency = claim_index.get(dependency_id)
            if dependency is None:
                errors.append(f"claim {claim_id}: derived_from claim is missing: {dependency_id!r}")
                continue
            graph[claim_id].append(dependency_id)
            if claim.get("project_id") is not None:
                compatible = dependency.get("project_id") == claim.get("project_id")
            else:
                parent_project = offers.get(claim.get("offer_id"), {}).get("project_id")
                compatible = dependency.get("offer_id") == claim.get("offer_id") or dependency.get("project_id") == parent_project
            if not compatible:
                errors.append(f"claim {claim_id}: derived dependency has incompatible scope: {dependency_id}")
    visiting, visited = set(), set()

    def visit(node):
        if node in visiting:
            errors.append(f"claim {node}: derived_from cycle detected")
            return
        if node in visited:
            return
        visiting.add(node)
        for child in graph.get(node, []):
            if child in graph:
                visit(child)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def _validate_resolution_graph(claims, claim_index, errors):
    graph = {}
    for claim in claims:
        if not isinstance(claim, dict) or claim.get("conflict_state") != "resolved":
            continue
        claim_id = claim.get("id")
        resolution = claim.get("resolution")
        if not _is_id(claim_id) or not isinstance(resolution, dict):
            continue
        graph[claim_id] = []
        resolved_by = resolution.get("resolved_by_claim_ids")
        if not isinstance(resolved_by, list):
            continue
        for other_id in resolved_by:
            if not _is_id(other_id):
                continue
            other = claim_index.get(other_id)
            if other and other.get("conflict_state") == "resolved":
                graph[claim_id].append(other_id)

    visiting, visited = set(), set()

    def visit(node):
        if node in visiting:
            errors.append(f"claim {node}: resolution cycle detected")
            return
        if node in visited:
            return
        visiting.add(node)
        for child in graph.get(node, []):
            if child in graph:
                visit(child)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def validate(payload, as_of=None):
    as_of, errors, warnings = as_of or date.today(), [], []
    if not isinstance(payload, dict):
        return {"valid": False, "errors": ["input must be an object"], "warnings": [], "claims": []}
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}; legacy evidence is not accepted")
    projects = _index(payload.get("projects"), "projects", errors)
    offers = _index(payload.get("offers"), "offers", errors)
    sources = _index(payload.get("sources"), "sources", errors)
    claims_input = payload.get("claims")
    claim_index = _index(claims_input, "claims", errors)
    claims = copy.deepcopy(claims_input) if isinstance(claims_input, list) else []
    source_dates = {source_id: _validate_source(source, as_of, errors) for source_id, source in sources.items()}
    for offer_id, offer in offers.items():
        if not _is_id(offer.get("project_id")):
            errors.append(f"offer {offer_id}: project_id must be a non-empty string")
        elif offer.get("project_id") not in projects:
            errors.append(f"offer {offer_id}: referenced project_id is missing: {offer.get('project_id')!r}")
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        claim_id, project_id, offer_id = claim.get("id", "<missing claim>"), claim.get("project_id"), claim.get("offer_id")
        if int(project_id is not None) + int(offer_id is not None) != 1:
            errors.append(f"claim {claim_id}: exactly one of project_id or offer_id is required")
        elif project_id is not None and not _is_id(project_id):
            errors.append(f"claim {claim_id}: project_id must be a non-empty string")
        elif offer_id is not None and not _is_id(offer_id):
            errors.append(f"claim {claim_id}: offer_id must be a non-empty string")
        elif project_id is not None and project_id not in projects:
            errors.append(f"claim {claim_id}: referenced project_id is missing: {project_id!r}")
        elif offer_id is not None and offer_id not in offers:
            errors.append(f"claim {claim_id}: referenced offer_id is missing: {offer_id!r}")
        _required_string(claim, "field", errors, f"claim {claim_id}")
        value = claim.get("value")
        has_value = value is not None
        if isinstance(value, str):
            has_value = bool(value.strip())
        elif isinstance(value, (list, tuple, dict, set)):
            has_value = bool(value)
        has_statement = isinstance(claim.get("statement"), str) and bool(claim["statement"].strip())
        if not has_value and not has_statement:
            errors.append(f"claim {claim_id}: semantic payload requires value or statement")
        label = claim.get("label")
        if label not in LABELS:
            errors.append(f"claim {claim_id}: invalid label: {label!r}")
        conflict_state = claim.get("conflict_state")
        if conflict_state not in CONFLICT_STATES:
            errors.append(f"claim {claim_id}: invalid conflict_state: {conflict_state!r}")
        elif conflict_state == "conflicting":
            warnings.append(f"claim {claim_id}: conflict remains unresolved")
        source_id = claim.get("source_id")
        if label == "推导结果":
            if source_id is not None:
                errors.append(f"claim {claim_id}: 推导结果 must use derived_from instead of source_id")
        elif label != "未核实":
            source = sources.get(source_id) if _is_id(source_id) else None
            if source is None:
                errors.append(f"claim {claim_id}: source_id is required and must exist")
            elif label in LABEL_SOURCE_CLASSES and source.get("source_class") not in LABEL_SOURCE_CLASSES[label]:
                errors.append(f"claim {claim_id}: label/source_class incompatible")
            elif source.get("source_relation") in NARROW_RELATION_FIELDS and claim.get("field") not in NARROW_RELATION_FIELDS[source["source_relation"]]:
                errors.append(f"claim {claim_id}: field is incompatible with source_relation {source['source_relation']}")
        elif source_id is not None and (not _is_id(source_id) or source_id not in sources):
            errors.append(f"claim {claim_id}: source_id references a missing source")
        if label == "市场参考" and offer_id is None:
            errors.append(f"claim {claim_id}: 市场参考 must be scoped to exactly one offer_id")
        if label == "小红书租住体验":
            identity_match = claim.get("identity_match")
            identity_basis = claim.get("identity_basis")
            if identity_match not in IDENTITY_MATCHES:
                errors.append(f"claim {claim_id}: identity_match must be strong, medium, or weak")
            elif identity_match == "weak":
                errors.append(f"claim {claim_id}: weak identity_match cannot support 小红书租住体验")
            if not isinstance(identity_basis, list) or not identity_basis or not all(_is_id(item) for item in identity_basis):
                errors.append(f"claim {claim_id}: identity_basis must be a non-empty string array")
        if conflict_state == "resolved":
            resolution = claim.get("resolution")
            if not isinstance(claim.get("conflict_group_id"), str) or not claim["conflict_group_id"].strip():
                errors.append(f"claim {claim_id}: resolved conflict requires conflict_group_id")
            if not isinstance(resolution, dict):
                errors.append(f"claim {claim_id}: resolved conflict requires resolution")
            else:
                resolved_by = resolution.get("resolved_by_claim_ids")
                if not isinstance(resolved_by, list) or not resolved_by:
                    errors.append(f"claim {claim_id}: resolution requires resolved_by_claim_ids")
                if not isinstance(resolution.get("rationale"), str) or not resolution["rationale"].strip():
                    errors.append(f"claim {claim_id}: resolution requires rationale")
                for resolution_id in resolved_by or []:
                    if not _is_id(resolution_id):
                        errors.append(f"claim {claim_id}: resolution IDs must be non-empty strings")
                        continue
                    if resolution_id == claim_id:
                        errors.append(f"claim {claim_id}: resolution cannot reference itself")
                        continue
                    other = claim_index.get(resolution_id)
                    if other is None:
                        errors.append(f"claim {claim_id}: resolution claim is missing: {resolution_id!r}")
                    elif _scope_key(other) != _scope_key(claim) or other.get("field") != claim.get("field"):
                        errors.append(f"claim {claim_id}: resolution claim must share scope and field")
                    elif other.get("conflict_state") == "conflicting" or other.get("label") == "未核实":
                        errors.append(f"claim {claim_id}: resolution claim must be resolved evidence")
    _validate_resolution_graph(claims, claim_index, errors)
    _validate_derived_graph(claims, claim_index, offers, errors)
    status_cache, calculating = {}, set()

    def claim_status(claim_id):
        if not _is_id(claim_id):
            return "unknown"
        if claim_id in status_cache:
            return status_cache[claim_id]
        if claim_id in calculating:
            return "unknown"
        calculating.add(claim_id)
        claim = claim_index.get(claim_id, {})
        if claim.get("label") == "推导结果":
            dependencies = claim.get("derived_from") if isinstance(claim.get("derived_from"), list) else []
            status = _most_conservative([claim_status(dep) for dep in dependencies if _is_id(dep) and dep in claim_index])
        else:
            source_id = claim.get("source_id")
            status = _source_freshness(claim, source_dates.get(source_id, {}) if _is_id(source_id) else {}, as_of, errors, warnings)
        calculating.remove(claim_id)
        status_cache[claim_id] = status
        return status

    for claim in claims:
        if isinstance(claim, dict):
            claim["freshness_status"] = claim_status(claim.get("id"))
    return {"valid": not errors, "errors": errors, "warnings": warnings, "claims": claims}


def _read_json(path):
    return json.load(sys.stdin) if path == "-" else json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", default="-", help="V2.2 JSON file, or - for stdin")
    parser.add_argument("--as-of", type=date.fromisoformat, help="freshness date (YYYY-MM-DD)")
    args = parser.parse_args(argv)
    try:
        result = validate(_read_json(args.input), args.as_of)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"valid": False, "errors": [str(exc)], "warnings": [], "claims": []}
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
