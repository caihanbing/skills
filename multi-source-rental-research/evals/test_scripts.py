import copy
import json
import sys
import unittest
from datetime import date
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR))

from scripts import calibration_metrics, normalize_candidates, validate_behavioral_evals, validate_discovery, validate_evidence


FIXTURES = json.loads((SKILL_DIR / "evals" / "fixtures.json").read_text(encoding="utf-8"))
BEHAVIORAL_CASES = json.loads((SKILL_DIR / "evals" / "behavioral-cases.json").read_text(encoding="utf-8"))
AS_OF = date(2026, 9, 6)


def _add_fixture_semantics(value):
    if isinstance(value, dict):
        if isinstance(value.get("claims"), list):
            for claim in value["claims"]:
                if isinstance(claim, dict):
                    claim.setdefault("statement", "fixture evidence")
        for nested in value.values():
            _add_fixture_semantics(nested)


_add_fixture_semantics(FIXTURES)


class EvidenceContractTests(unittest.TestCase):
    def test_requires_explicit_v21_schema_and_sources(self):
        result = validate_evidence.validate(FIXTURES["legacy_payload"], AS_OF)
        self.assertFalse(result["valid"])
        self.assertTrue(any("schema_version" in message for message in result["errors"]))

    def test_rejects_incompatible_label_and_source_class(self):
        result = validate_evidence.validate(FIXTURES["broker_as_verified_fact"], AS_OF)
        self.assertFalse(result["valid"])
        self.assertTrue(any("incompatible" in message for message in result["errors"]))

    def test_accepts_user_file_with_operator_provenance(self):
        result = validate_evidence.validate(FIXTURES["user_file_operator_statement"], AS_OF)
        self.assertTrue(result["valid"], result["errors"])

    def test_retrieval_date_alone_never_makes_current_offer_fresh(self):
        result = validate_evidence.validate(FIXTURES["retrieval_only_offer"], AS_OF)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["claims"][0]["freshness_status"], "unknown")

    def test_effective_date_outranks_old_publication_date(self):
        result = validate_evidence.validate(FIXTURES["effective_offer"], AS_OF)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["claims"][0]["freshness_status"], "fresh")

    def test_resolved_conflict_requires_same_scope_field_resolution_claim(self):
        bad = validate_evidence.validate(FIXTURES["resolved_without_evidence"], AS_OF)
        good = validate_evidence.validate(FIXTURES["resolved_with_evidence"], AS_OF)
        self.assertFalse(bad["valid"])
        self.assertTrue(any("resolution" in message for message in bad["errors"]))
        self.assertTrue(good["valid"], good["errors"])

    def test_derived_claims_reject_cycles_and_cross_scope_dependencies(self):
        cyclic = validate_evidence.validate(FIXTURES["derived_cycle"], AS_OF)
        cross_scope = validate_evidence.validate(FIXTURES["derived_cross_scope"], AS_OF)
        self.assertFalse(cyclic["valid"])
        self.assertTrue(any("cycle" in message for message in cyclic["errors"]))
        self.assertFalse(cross_scope["valid"])
        self.assertTrue(any("scope" in message for message in cross_scope["errors"]))

    def test_market_reference_must_use_offer_scope(self):
        result = validate_evidence.validate(FIXTURES["market_reference_project_scope"], AS_OF)
        self.assertFalse(result["valid"])
        self.assertTrue(any("offer_id" in message for message in result["errors"]))

    def test_derived_claim_inherits_most_conservative_dependency_freshness(self):
        result = validate_evidence.validate(FIXTURES["derived_from_stale"], AS_OF)
        self.assertTrue(result["valid"], result["errors"])
        statuses = {claim["id"]: claim["freshness_status"] for claim in result["claims"]}
        self.assertEqual(statuses["derived"], "stale")


class CandidateNormalizationTests(unittest.TestCase):
    def test_emits_high_and_medium_confidence_pairs_without_merging(self):
        result = normalize_candidates.normalize(FIXTURES["candidate_matches"])
        self.assertEqual([record["id"] for record in result["records"]], ["a", "b", "c", "d"])
        pairs = {(entry["left_id"], entry["right_id"]): entry for entry in result["possible_duplicates"]}
        self.assertEqual(pairs[("a", "b")]["confidence"], "high")
        self.assertEqual(pairs[("a", "c")]["confidence"], "medium")
        self.assertNotIn(("a", "d"), pairs)


class CalibrationTests(unittest.TestCase):
    def test_requires_distribution_coverage_before_alignment_can_pass(self):
        result = calibration_metrics.calculate(FIXTURES["imbalanced_calibration"], "holdout")
        self.assertFalse(result["alignment_good"])
        self.assertFalse(result["distribution_coverage"])

    def test_balanced_holdout_can_pass_and_exposes_weighted_kappa(self):
        result = calibration_metrics.calculate(FIXTURES["balanced_calibration"], "holdout")
        self.assertTrue(result["alignment_good"])
        self.assertTrue(result["distribution_coverage"])
        self.assertIn("weighted_kappa", result)


class BehavioralEvalContractTests(unittest.TestCase):
    def test_frozen_behavioral_cases_are_complete(self):
        result = validate_behavioral_evals.validate(BEHAVIORAL_CASES)
        self.assertTrue(result["valid"], result["errors"])
        self.assertGreaterEqual(result["case_count"], 16)

    def test_contract_marks_prohibited_outcomes_as_critical(self):
        self.assertTrue(BEHAVIORAL_CASES["prohibited_outcomes_are_critical"])

    def test_rejects_case_without_prohibited_outcome(self):
        payload = copy.deepcopy(BEHAVIORAL_CASES)
        payload["cases"][0].pop("prohibited_outcomes")
        result = validate_behavioral_evals.validate(payload)
        self.assertFalse(result["valid"])
        self.assertTrue(any("prohibited_outcomes" in message for message in result["errors"]))

    def test_runner_result_has_required_trace_and_grading_fields(self):
        result = {
            "case_id": "unknown-budget",
            "raw_response": "预算未提供，因此未做预算淘汰。",
            "tool_trace": [],
            "outcomes": {"satisfied": ["record_budget_unknown", "do_not_invent_budget"], "violated": []},
        }
        validation = validate_behavioral_evals.validate_runner_result(BEHAVIORAL_CASES, result)
        self.assertTrue(validation["valid"], validation["errors"])
        self.assertTrue(validation["passed"])
        self.assertEqual(validation["missing_obligations"], [])
        self.assertEqual(validation["critical_violations"], [])

    def test_runner_result_can_be_structurally_valid_but_behaviorally_failed(self):
        result = {
            "case_id": "unknown-budget",
            "raw_response": "我假设你的预算是 6000 元。",
            "tool_trace": [],
            "outcomes": {"satisfied": [], "violated": ["budget_filter_without_budget"]},
        }
        validation = validate_behavioral_evals.validate_runner_result(BEHAVIORAL_CASES, result)
        self.assertTrue(validation["valid"], validation["errors"])
        self.assertFalse(validation["passed"])
        self.assertIn("record_budget_unknown", validation["missing_obligations"])
        self.assertEqual(validation["critical_violations"], ["budget_filter_without_budget"])

    def test_runner_result_rejects_unknown_outcomes_from_a_passing_grade(self):
        result = {
            "case_id": "unknown-budget",
            "raw_response": "预算未提供，因此未做预算淘汰。",
            "tool_trace": [],
            "outcomes": {"satisfied": ["record_budget_unknown", "do_not_invent_budget", "invented_id"], "violated": []},
        }
        validation = validate_behavioral_evals.validate_runner_result(BEHAVIORAL_CASES, result)
        self.assertTrue(validation["valid"], validation["errors"])
        self.assertFalse(validation["passed"])
        self.assertEqual(validation["unknown_outcome_ids"], ["invented_id"])

    def test_place_discovery_cases_cover_adaptive_source_then_precise_xhs_workflow(self):
        cases = {case["id"]: case for case in BEHAVIORAL_CASES["cases"]}
        required = {
            "adaptive-source-expansion": (
                "establish_commute_constraint_before_discovery",
                "require_all_four_sources_before_shortlisting",
            ),
            "partial-discovery-failure": (
                "record_discovery_source_limitation_and_continue",
                "invent_missing_source_results",
            ),
            "precise-project-xhs": (
                "search_xiaohongshu_by_project_identity",
                "substitute_generic_location_posts_for_project_experience",
            ),
            "listing-market-reference": (
                "scope_listing_as_dated_offer_market_reference",
                "upgrade_listing_to_verified_fact_or_renter_experience",
            ),
            "catalog-discovery-expansion": (
                "expand_catalog_radius_transparently",
                "omit_precise_xiaohongshu_search_for_reported_project",
            ),
            "discovery-shortlist-xhs": (
                "apply_p0_before_deep_xiaohongshu_research",
                "deep_search_every_raw_candidate",
            ),
            "scoped-dd-no-discovery-expansion": (
                "research_named_candidates_only",
                "expand_candidate_pool_without_request",
            ),
            "source-absence": (
                "treat_source_absence_as_coverage_evidence",
                "infer_project_or_availability_absence",
            ),
            "weak-xhs-identity": (
                "keep_weak_identity_match_unverified",
                "attach_weak_identity_post_as_project_experience",
            ),
        }
        for case_id, (obligation, prohibited) in required.items():
            self.assertIn(case_id, cases)
            self.assertIn(obligation, cases[case_id]["expected_obligations"])
            self.assertIn(prohibited, cases[case_id]["prohibited_outcomes"])

    def test_candidate_discovery_policy_preserves_source_roles(self):
        workflow = (SKILL_DIR / "references" / "decision-workflow.md").read_text(encoding="utf-8")
        policy = (SKILL_DIR / "references" / "evidence-policy.md").read_text(encoding="utf-8")
        sources = (SKILL_DIR / "references" / "discovery-sources.md").read_text(encoding="utf-8")
        self.assertIn("adaptive", sources)
        self.assertIn("target city", sources)
        self.assertIn("commute constraint", workflow)
        self.assertIn("apply the commute", workflow)
        self.assertIn("项目级精确小红书检索", workflow)
        self.assertIn("identity match", policy)
        self.assertIn("coverage evidence", policy)
        self.assertIn("市场参考", policy)
        self.assertIn("地图发现", policy)

    def test_skill_metadata_uses_broader_multi_source_name(self):
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        agent_config = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertEqual(SKILL_DIR.name, "multi-source-rental-research")
        self.assertIn("name: multi-source-rental-research", skill)
        self.assertIn("$multi-source-rental-research", agent_config)


class DiscoveryContractTests(unittest.TestCase):
    def _payload(self):
        return {
            "schema_version": "1.1",
            "target_location": "Lingzhi Station",
            "target_city": "Shenzhen",
            "attempts": [
                {
                    "id": "a-map",
                    "provider": "amap",
                    "provider_class": "map",
                    "query": "Lingzhi Station apartments",
                    "entry_url": "https://ditu.amap.com/",
                    "retrieved_at": "2026-09-06",
                    "applicability_status": "applicable",
                    "access_status": "accessible",
                },
                {
                    "id": "a-market",
                    "provider": "ke",
                    "provider_class": "market",
                    "query": "Lingzhi Station rental",
                    "entry_url": "https://map.ke.com/",
                    "retrieved_at": "2026-09-06",
                    "applicability_status": "applicable",
                    "access_status": "accessible",
                },
            ],
            "leads": [
                {
                    "id": "l-project",
                    "attempt_id": "a-map",
                    "lead_kind": "project",
                    "candidate_name": "Example Residence",
                    "property_type": "住宅小区",
                    "result_url": "https://ditu.amap.com/example",
                    "resolved_project_id": "p-example",
                },
                {
                    "id": "l-offer",
                    "attempt_id": "a-market",
                    "lead_kind": "offer",
                    "candidate_name": "Example Residence",
                    "property_type": "住宅小区",
                    "result_url": "https://map.ke.com/example-offer",
                    "offer_reference": "listing-1",
                    "rent": 5200,
                    "resolved_project_id": "p-example",
                },
            ],
        }

    def test_accepts_project_and_offer_leads_and_reports_distinct_counts(self):
        result = validate_discovery.validate(self._payload(), AS_OF)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["summary"], {
            "raw_leads": 2,
            "unique_resolved_projects": 1,
            "potential_offer_leads": 1,
        })

    def test_rejects_limited_attempt_without_reason(self):
        payload = self._payload()
        payload["attempts"][0]["access_status"] = "limited"
        result = validate_discovery.validate(payload, AS_OF)
        self.assertFalse(result["valid"])
        self.assertTrue(any("limitation_reason" in error for error in result["errors"]))

    def test_rejects_old_schema_and_non_applicable_or_unavailable_attempt_leads(self):
        old_schema = self._payload()
        old_schema["schema_version"] = "1.0"
        non_applicable = self._payload()
        non_applicable["attempts"][0].update({
            "applicability_status": "not_applicable",
            "applicability_basis": "city unsupported",
            "access_status": "unavailable",
            "limitation_reason": "not attempted",
        })
        unavailable = self._payload()
        unavailable["attempts"][0].update({"access_status": "unavailable", "limitation_reason": "blocked"})
        for payload in (old_schema, non_applicable, unavailable):
            result = validate_discovery.validate(payload, AS_OF)
            self.assertFalse(result["valid"])

    def test_allows_limited_leads_but_rejects_undeclared_lead_fields(self):
        limited = self._payload()
        limited["attempts"][0].update({"access_status": "limited", "limitation_reason": "detail pages blocked"})
        self.assertTrue(validate_discovery.validate(limited, AS_OF)["valid"])
        unknown_field = self._payload()
        unknown_field["leads"][0]["management_fee"] = 300
        result = validate_discovery.validate(unknown_field, AS_OF)
        self.assertFalse(result["valid"])
        self.assertTrue(any("undeclared fields" in error for error in result["errors"]))

    def test_rejects_map_price_and_offer_without_market_reference(self):
        payload = self._payload()
        payload["leads"][0]["rent"] = 5200
        payload["leads"][1].pop("offer_reference")
        result = validate_discovery.validate(payload, AS_OF)
        self.assertFalse(result["valid"])
        self.assertTrue(any("map project lead" in error for error in result["errors"]))
        self.assertTrue(any("offer_reference" in error for error in result["errors"]))


class ValidatorHardeningTests(unittest.TestCase):
    def test_rejects_v21_evidence_after_strict_v22_migration(self):
        payload = copy.deepcopy(FIXTURES["effective_offer"])
        payload["schema_version"] = "2.1"
        result = validate_evidence.validate(payload, AS_OF)
        self.assertFalse(result["valid"])
        self.assertTrue(any("2.2" in message for message in result["errors"]))

    def test_restricts_narrow_authority_relations_to_compatible_fields(self):
        map_route = copy.deepcopy(FIXTURES["effective_offer"])
        map_route["sources"][0].update({"source_class": "authority", "source_relation": "map_route"})
        map_route["claims"][0].update({"label": "已核实事实", "field": "management_fee"})
        utility = copy.deepcopy(FIXTURES["effective_offer"])
        utility["sources"][0].update({"source_class": "authority", "source_relation": "utility_tariff"})
        utility["claims"][0].update({"label": "已核实事实", "field": "building_age"})
        for payload in (map_route, utility):
            result = validate_evidence.validate(payload, AS_OF)
            self.assertFalse(result["valid"])
            self.assertTrue(any("field is incompatible" in message for message in result["errors"]))

        allowed = copy.deepcopy(FIXTURES["effective_offer"])
        allowed["sources"][0].update({"source_class": "authority", "source_relation": "map_route"})
        allowed["claims"][0].update({"label": "已核实事实", "field": "commute"})
        self.assertTrue(validate_evidence.validate(allowed, AS_OF)["valid"])

    def test_requires_non_weak_identity_match_for_xiaohongshu_renter_experience(self):
        missing = copy.deepcopy(FIXTURES["effective_offer"])
        missing["sources"][0].update({"source_class": "resident", "source_relation": "xiaohongshu_renter"})
        missing["claims"][0].update({"label": "小红书租住体验", "field": "noise"})
        weak = copy.deepcopy(missing)
        weak["claims"][0].update({"identity_match": "weak", "identity_basis": ["project_name"]})
        medium = copy.deepcopy(missing)
        medium["claims"][0].update({"identity_match": "medium", "identity_basis": ["project_name", "district"]})
        for payload in (missing, weak):
            result = validate_evidence.validate(payload, AS_OF)
            self.assertFalse(result["valid"])
            self.assertTrue(any("identity" in message for message in result["errors"]))
        self.assertTrue(validate_evidence.validate(medium, AS_OF)["valid"])

    def test_rejects_claim_without_value_or_statement(self):
        payload = copy.deepcopy(FIXTURES["retrieval_only_offer"])
        payload["claims"][0].pop("statement")
        result = validate_evidence.validate(payload, AS_OF)
        self.assertFalse(result["valid"])
        self.assertTrue(any("semantic payload" in message for message in result["errors"]))

    def test_rejects_source_class_relation_mismatch(self):
        payload = copy.deepcopy(FIXTURES["effective_offer"])
        payload["sources"][0]["source_class"] = "authority"
        payload["sources"][0]["source_relation"] = "broker"
        payload["claims"][0]["label"] = "已核实事实"
        result = validate_evidence.validate(payload, AS_OF)
        self.assertFalse(result["valid"])
        self.assertTrue(any("source_class/source_relation" in message for message in result["errors"]))

    def test_rejects_self_and_unresolved_resolution_evidence(self):
        self_resolution = copy.deepcopy(FIXTURES["resolved_with_evidence"])
        self_resolution["claims"][0]["resolution"]["resolved_by_claim_ids"] = ["c1"]
        unresolved = copy.deepcopy(FIXTURES["resolved_with_evidence"])
        unresolved["claims"][1]["conflict_state"] = "conflicting"
        for payload in (self_resolution, unresolved):
            result = validate_evidence.validate(payload, AS_OF)
            self.assertFalse(result["valid"])
            self.assertTrue(any("resolution" in message for message in result["errors"]))

    def test_malformed_reference_ids_return_errors_not_exceptions(self):
        derived = copy.deepcopy(FIXTURES["derived_from_stale"])
        derived["claims"][1]["derived_from"] = [{"id": "base"}]
        resolution = copy.deepcopy(FIXTURES["resolved_with_evidence"])
        resolution["claims"][0]["resolution"]["resolved_by_claim_ids"] = [{"id": "c2"}]
        malformed_offer = copy.deepcopy(FIXTURES["effective_offer"])
        malformed_offer["offers"][0]["project_id"] = {"id": "p1"}
        for payload in (derived, resolution, malformed_offer):
            result = validate_evidence.validate(payload, AS_OF)
            self.assertFalse(result["valid"])
            self.assertTrue(result["errors"])

    def test_rejects_cycles_between_resolution_claims(self):
        payload = copy.deepcopy(FIXTURES["resolved_with_evidence"])
        first, second = payload["claims"]
        for claim in (first, second):
            claim["conflict_state"] = "resolved"
            claim["conflict_group_id"] = "fees-p1"
        first["resolution"]["resolved_by_claim_ids"] = ["c2"]
        second["resolution"] = {"rationale": "other claim", "resolved_by_claim_ids": ["c1"]}
        result = validate_evidence.validate(payload, AS_OF)
        self.assertFalse(result["valid"])
        self.assertTrue(any("resolution cycle" in message for message in result["errors"]))

    def test_malformed_claim_id_returns_validation_error_not_exception(self):
        payload = copy.deepcopy(FIXTURES["effective_offer"])
        payload["claims"][0]["id"] = {"bad": "id"}
        result = validate_evidence.validate(payload, AS_OF)
        self.assertFalse(result["valid"])
        self.assertTrue(result["errors"])

    def test_rejects_empty_collection_semantic_values(self):
        for value in ([], {}):
            payload = copy.deepcopy(FIXTURES["effective_offer"])
            payload["claims"][0].pop("statement")
            payload["claims"][0]["value"] = value
            result = validate_evidence.validate(payload, AS_OF)
            self.assertFalse(result["valid"])
            self.assertTrue(any("semantic payload" in message for message in result["errors"]))

    def test_other_relation_cannot_restate_a_canonical_relation(self):
        payload = copy.deepcopy(FIXTURES["effective_offer"])
        payload["sources"][0]["source_class"] = "authority"
        payload["sources"][0]["source_relation"] = "other"
        payload["sources"][0]["relation_detail"] = "broker"
        payload["claims"][0]["label"] = "已核实事实"
        result = validate_evidence.validate(payload, AS_OF)
        self.assertFalse(result["valid"])
        self.assertTrue(any("canonical relation" in message for message in result["errors"]))


if __name__ == "__main__":
    unittest.main()
