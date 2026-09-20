import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import shadow


def case():
    return {"case_id": "synthetic-1", "group_id": "synthetic-incident-1",
            "fixture_kind": "synthetic", "data_use": "public_authorized",
            "incident": {"name": "test"}, "source": {"text": "Smoke reported"},
            "claim": "Visible flames", "observations": [],
            "labels": {"claim_support": "insufficient"}}


def response():
    answers = {}
    for stage, question in shadow.QUESTIONS.items():
        choices = list(question["criteria"])
        chosen = "insufficient" if stage == "claim_support" else choices[0]
        answers[stage] = {"type": "choice", "choice": chosen, "confidence": .9,
                          "probabilities": {key: float(key == chosen) for key in choices}}
    return {"model": shadow.MODEL, "answers": answers,
            "usage": {"input_tokens": 300, "output_tokens": 100}}


class ShadowTests(unittest.TestCase):
    def test_default_never_calls_network(self):
        result = shadow.run([case()], transport=lambda *_: self.fail("network called"))
        self.assertEqual(result["report"]["successful_requests"], 0)
        self.assertIsNone(result["report"]["stages"]["claim_support"]["accuracy"])

    def test_answer_and_secret_leakage(self):
        value = case()
        value.update(api_key="secret", baseline_answers={"claim_support": "supports"})
        payload = shadow.build_request(value)
        self.assertNotIn("labels", payload["state"])
        self.assertNotIn("baseline_answers", payload["state"])
        self.assertNotIn("secret", shadow.canonical(payload))

    def test_private_evidence_rejected(self):
        value = case()
        value["data_use"] = "private"
        with self.assertRaises(ValueError): shadow.run([value])

    def test_replay_hash_invariant_to_dict_order(self):
        value = case()
        self.assertEqual(shadow.digest(shadow.build_request(value)),
                         shadow.digest(shadow.build_request(dict(reversed(list(value.items()))))))

    def test_missing_key_fails_before_network(self):
        with self.assertRaises(ValueError): shadow.run([case()], execute=True)

    def test_invalid_provider_response_rejected(self):
        for mutate in [lambda r: r.update(model="other"),
                       lambda r: r["answers"].pop("claim_support"),
                       lambda r: r["answers"]["claim_support"].update(choice="invented"),
                       lambda r: r["usage"].update(input_tokens=-1),
                       lambda r: r["answers"]["claim_support"].update(confidence=float("nan")),
                       lambda r: r["answers"]["claim_support"]["probabilities"].update(insufficient=.5)]:
            value = response(); mutate(value)
            with self.assertRaises(ValueError): shadow.validate_response(value)

    def test_low_budget_prevents_request(self):
        result = shadow.run([case()], execute=True, api_key="test", max_cost_usd=.00001,
                            transport=lambda *_: self.fail("budget exceeded"))
        self.assertEqual(result["records"][0]["status"], "budget_exhausted")

    def test_failure_cost_reserved_without_retry_or_error_body(self):
        def fail(*_): raise OSError("private provider body")
        result = shadow.run([case()], execute=True, api_key="test", transport=fail)
        self.assertEqual(result["report"]["reserved_cost_usd"], shadow.RESERVE_PER_REQUEST_USD)
        self.assertNotIn("private provider body", shadow.canonical(result))
        self.assertEqual(result["report"]["failed_requests"], 1)

    def test_no_fabricated_baseline(self):
        value = case(); value["baseline_answers"] = {"claim_support": "supports"}
        result = shadow.run([value], execute=True, api_key="test", transport=lambda *_: response())
        self.assertEqual(result["report"]["stages"]["claim_support"]["paired_cases"], 0)

    def test_paired_comparison_and_brier(self):
        value = case()
        state = {key: value[key] for key in shadow.STATE_FIELDS}
        value.update(baseline_answers={"claim_support": "supports"}, baseline_receipt={
            "input_sha256": shadow.digest(state), "artifact_reference": "synthetic-receipt",
            "source_commit": "synthetic-test"})
        result = shadow.run([value], execute=True, api_key="test", transport=lambda *_: response())
        metrics = result["report"]["stages"]["claim_support"]
        self.assertEqual(metrics["paired_cases"], 1)
        self.assertEqual(metrics["baseline_accuracy_paired"], 0)
        self.assertEqual(metrics["typesafe_accuracy_paired"], 1)
        self.assertEqual(metrics["brier_score"], 0)
        self.assertFalse(result["report"]["publication_enabled"])

    def test_baseline_for_different_input_rejected(self):
        value = case()
        value["baseline_receipt"] = {"input_sha256": "wrong", "artifact_reference": "test", "source_commit": "test"}
        with self.assertRaises(ValueError): shadow.run([value])

    def test_duplicate_cases_and_nan_budget_rejected(self):
        with self.assertRaises(ValueError): shadow.run([case(), case()])
        with self.assertRaises(ValueError): shadow.run([case()], max_cost_usd=float("nan"))


if __name__ == "__main__": unittest.main()
