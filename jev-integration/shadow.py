"""ARCHIVED three-question connectivity probe. Use component_runner for new runs.

No backend writes, no scraping, no geometry generation. The default is offline.
Only a supplied current-pipeline receipt qualifies as a baseline measurement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler

ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT / "questions.json").read_text())
MODEL = "jev-1.13.0"
PRICE_PER_INPUT_MILLION_USD = 0.042  # docs.typesafe.ai/models, 2026-09-20
MAX_REQUEST_TOKENS = 64_000
RESERVE_PER_REQUEST_USD = MAX_REQUEST_TOKENS * PRICE_PER_INPUT_MILLION_USD / 1_000_000
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
STATE_FIELDS = ("incident", "source", "claim", "observations")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def build_request(case):
    if case.get("data_use") != "public_authorized":
        raise ValueError("case_not_authorized_for_external_evaluation")
    if not isinstance(case.get("case_id"), str) or not case["case_id"]:
        raise ValueError("case_id_required")
    if not isinstance(case.get("group_id"), str) or not case["group_id"]:
        raise ValueError("incident_and_source_family_group_required")
    if not all(field in case for field in STATE_FIELDS):
        raise ValueError("incomplete_evidence_export")
    if not isinstance(case["source"], dict) or not isinstance(case["source"].get("text"), str):
        raise ValueError("source_text_required")
    # An explicit allowlist prevents labels, baseline answers and credentials
    # elsewhere in an exported record from being sent to the model.
    state = {field: case[field] for field in STATE_FIELDS}
    payload = {"model": MODEL, "state": state, "questions": QUESTIONS}
    if len(canonical(payload).encode()) > 24_000:
        raise ValueError("request_too_large_do_not_silently_truncate_evidence")
    for key, label in case.get("labels", {}).items():
        if key not in QUESTIONS or label not in QUESTIONS[key]["criteria"]:
            raise ValueError("invalid_reference_label")
    for key, answer in case.get("baseline_answers", {}).items():
        if key not in QUESTIONS or answer not in QUESTIONS[key]["criteria"]:
            raise ValueError("baseline_requires_matching_question_semantics")
    receipt = case.get("baseline_receipt")
    if receipt:
        if not isinstance(receipt, dict) or receipt.get("input_sha256") != digest(state):
            raise ValueError("baseline_receipt_must_match_frozen_input")
        if not receipt.get("artifact_reference") or not receipt.get("source_commit"):
            raise ValueError("baseline_receipt_provenance_required")
        for key in ("latency_ms", "cost_usd"):
            if key in receipt and (not number(receipt[key]) or receipt[key] < 0):
                raise ValueError("invalid_baseline_measurement")
    return payload


def number(value):
    return type(value) in (float, int) and math.isfinite(value)


def validate_response(response):
    if response.get("model") != MODEL:
        raise ValueError("unexpected_model_revision")
    answers = response.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(QUESTIONS):
        raise ValueError("answer_set_mismatch")
    for key, question in QUESTIONS.items():
        answer = answers[key]
        if not isinstance(answer, dict) or answer.get("type") != "choice":
            raise ValueError("invalid_answer_type")
        choices = set(question["criteria"])
        probabilities = answer.get("probabilities")
        if answer.get("choice") not in choices or not isinstance(probabilities, dict):
            raise ValueError("invalid_choice")
        if set(probabilities) != choices:
            raise ValueError("probability_set_mismatch")
        if any(not number(p) or not 0 <= p <= 1 for p in probabilities.values()):
            raise ValueError("invalid_probability")
        if abs(sum(probabilities.values()) - 1) > 0.001:
            raise ValueError("invalid_probability_sum")
        if probabilities[answer["choice"]] + 1e-6 < max(probabilities.values()):
            raise ValueError("choice_is_not_highest_probability")
        if not number(answer.get("confidence")) or not 0 <= answer["confidence"] <= 1:
            raise ValueError("invalid_confidence")
    usage = response.get("usage", {})
    for key in ("input_tokens", "output_tokens"):
        if type(usage.get(key)) is not int or usage[key] < 0:
            raise ValueError("missing_or_invalid_token_usage")
    if usage["input_tokens"] > MAX_REQUEST_TOKENS:
        raise ValueError("usage_exceeds_documented_request_budget")
    return response


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def call_typesafe(payload, api_key):
    raise ValueError("legacy_probe_archived_use_component_runner_with_one_component")


def summarize(records):
    valid = [r for r in records if r["status"] == "ok"]
    output = {"cases": len(records), "successful_requests": len(valid),
              "failed_requests": sum(r["status"] == "error" for r in records),
              "skipped_budget": sum(r["status"] == "budget_exhausted" for r in records),
              "measured_typesafe_cost_usd": sum(r.get("cost_usd", 0) for r in valid),
              "publication_enabled": False, "stages": {}}
    latencies = sorted(r["latency_ms"] for r in valid)
    output["latency_p50_ms"] = statistics.median(latencies) if latencies else None
    output["latency_p95_ms"] = latencies[math.ceil(len(latencies)*.95)-1] if latencies else None
    for stage in QUESTIONS:
        labeled = [r for r in valid if stage in r["labels"]]
        paired = [r for r in labeled if stage in r["baseline_answers"] and r["baseline_receipt"]]
        output["stages"][stage] = {
            "labeled_cases": len(labeled),
            "accuracy": sum(r["response"]["answers"][stage]["choice"] == r["labels"][stage] for r in labeled) / len(labeled) if labeled else None,
            "paired_cases": len(paired),
            "baseline_accuracy_paired": sum(r["baseline_answers"][stage] == r["labels"][stage] for r in paired) / len(paired) if paired else None,
            "typesafe_accuracy_paired": sum(r["response"]["answers"][stage]["choice"] == r["labels"][stage] for r in paired) / len(paired) if paired else None,
            "disagreements": sum(r["baseline_answers"][stage] != r["response"]["answers"][stage]["choice"] for r in paired),
            "brier_score": sum(sum((p - float(option == r["labels"][stage]))**2 for option,p in r["response"]["answers"][stage]["probabilities"].items()) for r in labeled) / len(labeled) if labeled else None,
            "abstentions": sum(r["response"]["answers"][stage]["choice"] in {"uncertain", "insufficient", "abstain"} for r in valid),
        }
    output["limits"] = ["No model or product qualification from synthetic fixtures.",
                        "Agreement with the current pipeline is not ground truth.",
                        "Unknown costs of failed requests remain reserved.",
                        "No baseline latency or cost gain claim without paired measurements."]
    return output


def run(cases, *, execute=False, api_key=None, max_cost_usd=.5, transport=call_typesafe, on_event=None):
    if not 1 <= len(cases) <= 50:
        raise ValueError("one_to_fifty_cases_required")
    if not number(max_cost_usd) or not 0 < max_cost_usd <= .5:
        raise ValueError("experiment_cost_limit_must_be_in_0_to_0_5_usd")
    if execute and not api_key:
        raise ValueError("TYPESAFE_API_KEY_missing_use_local_secret_input")
    if len({c.get("case_id") for c in cases}) != len(cases):
        raise ValueError("duplicate_case_ids")
    requests = [build_request(case) for case in cases]
    records, reserved = [], 0.0
    for case, payload in zip(cases, requests):
        if on_event:
            on_event({"type": "case_started", "case_id": case["case_id"],
                      "mode": "live" if execute else "offline_plan"})
        record = {"case_id": case["case_id"], "group_id": case["group_id"],
                  "fixture_kind": case.get("fixture_kind", "real_evidence"),
                  "request_sha256": digest(payload), "input_sha256": digest(payload["state"]),
                  "labels": case.get("labels", {}),
                  "baseline_answers": case.get("baseline_answers", {}),
                  "baseline_receipt": case.get("baseline_receipt"),
                  "status": "planned", "publication_enabled": False}
        if execute:
            if reserved + RESERVE_PER_REQUEST_USD > max_cost_usd:
                record["status"] = "budget_exhausted"
            else:
                reserved += RESERVE_PER_REQUEST_USD
                started = time.perf_counter()
                try:
                    response = validate_response(transport(payload, api_key))
                    record.update(status="ok", response=response,
                                  cost_usd=response["usage"]["input_tokens"]*PRICE_PER_INPUT_MILLION_USD/1_000_000)
                except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError) as exc:
                    # Do not persist response bodies, headers, URLs or credentials.
                    record.update(status="error", error_type=type(exc).__name__)
                record["latency_ms"] = round((time.perf_counter()-started)*1000, 3)
        records.append(record)
        if on_event:
            on_event({"type": "case_finished", "record": record, "completed": len(records),
                      "total": len(cases), "metrics": summarize(records)})
    report = summarize(records)
    report.update(mode="live" if execute else "offline_plan", model=MODEL,
                  questions_sha256=digest(QUESTIONS),
                  reserved_cost_usd=reserved,
                  projected_max_cost_usd=len(cases)*RESERVE_PER_REQUEST_USD,
                  synthetic_cases=sum(r["fixture_kind"] == "synthetic" for r in records))
    return {"report": report, "records": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-cost-usd", type=float, default=.5)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; preserve previous experiment evidence")
    cases = [json.loads(line) for line in args.cases.read_text().splitlines() if line.strip()]
    result = run(cases, execute=args.execute, api_key=os.environ.get("TYPESAFE_API_KEY"), max_cost_usd=args.max_cost_usd)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        os.chmod(args.output, 0o600)
        stream.write(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)+"\n")
    print(json.dumps(result["report"], indent=2))


if __name__ == "__main__":
    main()
