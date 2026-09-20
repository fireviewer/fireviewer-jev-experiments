import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import components as c
import component_runner as runner
from shadow import MODEL, digest


def receipt(scope, **extra):
    return dict(input_sha256=digest(scope), source_commit="test-only-revision",
                artifact_reference="test://unit-fixture-not-a-real-run", rule_revision="test-rule-1", **extra)


def case_for(cid):
    state = {k: "Synthetic unit-test text" for k in c.COMPONENTS[cid]["fields"]}
    case = dict(case_id="unit-"+cid, group_id="unit-not-a-benchmark", component_id=cid,
                data_use="public_authorized", fixture_kind="synthetic", semantic_input=state,
                observations=[{"id": "visual-1", "label": "smoke", "box": [1, 2, 3, 4]}])
    if cid == "FV-03":
        case["pair_gate"] = receipt(state, spatial_compatible=True, temporal_compatible=True)
    if cid == "FV-04":
        case["structured_fields"] = {"place": "", "date": "2025-08-06", "provenance": ""}
    if cid == "DS-03":
        case["error_rule_receipt"] = receipt(state, matched=False)
    if cid == "LOC-01":
        case["geocoder_candidates"] = [{"id": "place_a", "description": "Candidate returned by geocoder"}]
        case["geocoder_receipt"] = receipt(case["geocoder_candidates"])
    return case


def response_for(payload, key=None):
    answers = {}
    for qid, q in payload["questions"].items():
        if q["type"] == "noul":
            answers[qid] = {"type": "noul", "noul": .5}
        else:
            keys = list(q["criteria"]) if q["type"] == "choice" else [str(i) for i in range(len(q["criteria"]))]
            answer = {"type": q["type"], "probabilities": {k: float(i == 0) for i, k in enumerate(keys)}, "confidence": 1.0}
            answer[q["type"]] = keys[0] if q["type"] == "choice" else 0.0
            answers[qid] = answer
    return {"model": MODEL, "answers": answers, "usage": {"input_tokens": 100, "output_tokens": 20}}


class ComponentTests(unittest.TestCase):
    def test_all_twelve_contracts_and_typed_responses_are_isolated(self):
        self.assertEqual(len(c.catalog()), 12)
        for cid in c.COMPONENTS:
            with self.subTest(cid=cid):
                case = case_for(cid)
                original = copy.deepcopy(case)
                payload, skip = c.prepare(case, cid)
                self.assertIsNone(skip)
                result = runner.run([case], component_id=cid, execute=True, api_key="unit", transport=response_for)
                row = result["records"][0]
                self.assertEqual(row["status"], "ok")
                self.assertEqual(case, original)
                self.assertEqual(set(row["response"]["answers"]), set(c.COMPONENTS[cid]["questions"]))
                self.assertEqual(row["sidecar"]["action"], "keep_current_pipeline")
                self.assertFalse(row["sidecar"]["raw_observations_changed"])
                self.assertFalse(row["sidecar"]["vision_can_be_skipped"])
                self.assertFalse(result["report"]["full_pipeline_executed"])
                self.assertEqual(result["report"]["paired_export_cases"], 0)

    def test_no_component_or_mixed_component_rejected_before_any_call(self):
        for cid in (None, ["FV-01", "FV-02"], "vision"):
            with self.assertRaises(ValueError):
                runner.run([case_for("FV-01")], component_id=cid)
        with self.assertRaises(ValueError):
            runner.run([case_for("FV-01"), case_for("FV-02")], component_id="FV-01")
        case = case_for("FV-01")
        case["changed_components"] = ["FV-01", "FV-02"]
        with self.assertRaises(ValueError): c.prepare(case, "FV-01")

    def test_only_explicit_text_projection_sent_no_raw_vision_labels_or_secrets(self):
        case = case_for("LOC-02")
        case.update(api_key="should-not-leak", labels={"claim_conflict": True}, image_base64="not-for-jev")
        payload, _ = c.prepare(case, "LOC-02")
        self.assertEqual(set(payload["state"]), set(c.COMPONENTS["LOC-02"]["fields"]))
        for forbidden in ("should-not-leak", "not-for-jev", "visual-1"):
            self.assertNotIn(forbidden, json.dumps(payload))
        for key, value in (("text", {"pixels": "nested"}), ("coordinates", [1, 2]), ("reference_text", "data:image/png;base64,AAAA")):
            bad = copy.deepcopy(case)
            bad["semantic_input"][key] = value
            with self.assertRaises(ValueError): c.prepare(bad, "LOC-02")

    def test_spatiotemporal_gates_are_required_and_not_recomputed_by_jev(self):
        case = case_for("FV-03")
        case.pop("pair_gate")
        with self.assertRaises(ValueError): c.prepare(case, "FV-03")
        case = case_for("FV-03")
        case["pair_gate"]["temporal_compatible"] = False
        result = runner.run([case], component_id="FV-03", execute=True, api_key="unit", transport=lambda *_: self.fail("must not call"))
        self.assertEqual(result["records"][0]["status"], "rule_applies")
        case["semantic_input"]["left_text"] = "Changed evidence"
        with self.assertRaises(ValueError): c.prepare(case, "FV-03")

    def test_form_code_selects_missing_fields_and_templates_only(self):
        case = case_for("FV-04")
        payload, _ = c.prepare(case, "FV-04")
        self.assertEqual(set(payload["questions"]["message"]["criteria"]), {"place", "provenance", "human_review"})
        case["structured_fields"] = dict(place="here", date="then", provenance="witness")
        self.assertEqual(c.prepare(case, "FV-04")[1], "no_missing_field")

    def test_known_license_absence_and_error_rules_do_not_call_jev(self):
        cases = [case_for("DS-02"), case_for("DS-03")]
        cases[0]["semantic_input"]["license_text"] = ""
        cases[1]["error_rule_receipt"]["matched"] = True
        for case in cases:
            result = runner.run([case], component_id=case["component_id"], execute=True, api_key="unit", transport=lambda *_: self.fail("must not call"))
            self.assertEqual(result["report"]["reserved_cost_usd"], 0)

    def test_geocoder_candidate_only_no_coordinate_or_unknown_id(self):
        case = case_for("LOC-01")
        payload, _ = c.prepare(case, "LOC-01")
        bad = response_for(payload)
        bad["answers"]["place"]["choice"] = "invented-place"
        with self.assertRaises(ValueError): runner.validate_response(bad, payload["questions"])
        case["geocoder_candidates"][0]["coordinates"] = [43, 2]
        with self.assertRaises(ValueError): c.prepare(case, "LOC-01")

    def test_failure_and_budget_preserve_current_pipeline_and_no_error_body(self):
        def fail(*_): raise TimeoutError("private-secret-message")
        case = case_for("LOC-02")
        result = runner.run([case], component_id="LOC-02", execute=True, api_key="unit", transport=fail)
        self.assertEqual(result["records"][0]["status"], "error")
        self.assertNotIn("private-secret-message", json.dumps(result))
        self.assertEqual(result["records"][0]["sidecar"]["action"], "keep_current_pipeline")
        result = runner.run([case], component_id="LOC-02", execute=True, api_key="unit", max_cost_usd=.0001, transport=lambda *_: self.fail("must not call"))
        self.assertEqual(result["records"][0]["status"], "budget_exhausted")

    def test_pairing_requires_same_component_full_frozen_context_and_measurement_scope(self):
        case = case_for("FV-01")
        payload, _ = c.prepare(case, "FV-01")
        case["frozen_context"] = {k: digest(k) for k in ("corpus_sha256", "vision_artifacts_sha256", "pipeline_config_sha256", "prior_state_sha256", "arrival_batch_sha256")}
        case["changed_components"] = ["FV-01"]
        identity = c.comparison_identity(case, payload, "FV-01")
        case["baseline_answers"] = {"topic": "indeterminate", "useful_text": .5}
        case["baseline_receipt"] = dict(component_id="FV-01", measurement_scope="component", comparison_sha256=digest(identity), artifact_reference="test://fake", source_commit="unit", method="fixture")
        runner.run([case], component_id="FV-01")
        for key in case["frozen_context"]:
            changed = copy.deepcopy(case)
            changed["frozen_context"][key] = "f"*64
            with self.assertRaises(ValueError): runner.run([changed], component_id="FV-01")
        case["baseline_receipt"]["measurement_scope"] = "whole_pipeline"
        with self.assertRaises(ValueError): runner.run([case], component_id="FV-01")

    def test_invalid_noul_score_and_extra_fields_are_not_accepted_as_actions(self):
        for cid, qid, field, invalid in (("FV-03", "same_case", "noul", float("nan")), ("DS-04", "review_priority", "score", 1.2)):
            payload, _ = c.prepare(case_for(cid), cid)
            result = response_for(payload)
            result["answers"][qid][field] = invalid
            with self.assertRaises(ValueError): runner.validate_response(result, payload["questions"])
        payload, _ = c.prepare(case_for("FV-01"), "FV-01")
        result = response_for(payload)
        result["publish"] = True
        result["answers"]["topic"]["discard_image"] = True
        self.assertNotIn("discard_image", json.dumps(runner.validate_response(result, payload["questions"])))
        result["model"] = "unknown"
        with self.assertRaises(ValueError): runner.validate_response(result, payload["questions"])

    def test_empty_text_is_retained_and_missing_api_key_is_explicit(self):
        case = case_for("FV-01")
        case["semantic_input"] = {}
        result = runner.run([case], component_id="FV-01")
        self.assertEqual(result["records"][0]["status"], "planned")
        self.assertFalse(result["records"][0]["sidecar"]["vision_can_be_skipped"])
        with self.assertRaises(ValueError): runner.run([case], component_id="FV-01", execute=True)


if __name__ == "__main__": unittest.main()
