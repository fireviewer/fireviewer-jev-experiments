"""One-component textual experiments. No backend or image/geometry writes.

An export and its imported receipts are not an attestation of a full pipeline
execution. Failure, abstention and budget exhaustion always leave the current
pipeline in charge. This runner writes advisory receipts only.
"""
import argparse
import json
import os
import statistics
import time
from pathlib import Path
from urllib.request import Request, build_opener

import components
from shadow import (MODEL, ENDPOINT, MAX_REQUEST_TOKENS, RESERVE_PER_REQUEST_USD,
                    PRICE_PER_INPUT_MILLION_USD, NoRedirect, canonical, digest, number)


def probability(value):
    return number(value) and 0 <= value <= 1


def validate_response(response, questions):
    if not isinstance(response, dict) or response.get("model") != MODEL:
        raise ValueError("unexpected_model_revision")
    answers = response.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(questions):
        raise ValueError("answer_set_mismatch")
    clean = {}
    for key, question in questions.items():
        answer = answers[key]
        kind = question["type"]
        if not isinstance(answer, dict) or answer.get("type") != kind:
            raise ValueError("invalid_answer_type")
        if kind == "noul":
            if not probability(answer.get("noul")):
                raise ValueError("invalid_noul")
            clean[key] = {"type": kind, "noul": answer["noul"]}
            continue
        probs = answer.get("probabilities")
        choices = set(question["criteria"]) if kind == "choice" else {str(i) for i in range(len(question["criteria"]))}
        if not isinstance(probs, dict) or set(probs) != choices or any(not probability(v) for v in probs.values()):
            raise ValueError("invalid_probability_set")
        if abs(sum(probs.values()) - 1) > .001 or not probability(answer.get("confidence")):
            raise ValueError("invalid_probability_sum_or_confidence")
        if kind == "choice":
            value = answer.get("choice")
            if value not in choices or probs[value] + 1e-6 < max(probs.values()):
                raise ValueError("invalid_choice")
        else:
            value = answer.get("score")
            if not number(value) or not 0 <= value <= len(choices)-1:
                raise ValueError("invalid_score")
            if abs(value - sum(int(k)*p for k, p in probs.items())) > .002:
                raise ValueError("score_not_probability_weighted")
        clean[key] = {"type": kind, kind: value, "probabilities": probs, "confidence": answer["confidence"]}
    usage = response.get("usage", {})
    if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("input_tokens", "output_tokens")):
        raise ValueError("invalid_usage")
    if usage["input_tokens"] > MAX_REQUEST_TOKENS:
        raise ValueError("usage_exceeds_request_budget")
    return {"model": MODEL, "answers": clean, "usage": {k: usage[k] for k in ("input_tokens", "output_tokens")}}


def call_typesafe(payload, api_key):
    request = Request(ENDPOINT, canonical(payload).encode(),
                      {"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}, method="POST")
    with build_opener(NoRedirect()).open(request, timeout=30) as stream:
        raw = stream.read(256001)
    if len(raw) > 256000:
        raise ValueError("response_too_large")
    return json.loads(raw)


def validate_annotations(case, questions):
    for name in ("labels", "baseline_answers"):
        values = case.get(name, {})
        if not isinstance(values, dict) or set(values) - set(questions):
            raise ValueError("annotations_require_same_component_semantics")
        for key, value in values.items():
            if value is None:  # human-indeterminate cases remain in the corpus
                continue
            q = questions[key]
            if q["type"] == "choice":
                valid = isinstance(value, str) and value in q["criteria"]
            elif q["type"] == "noul":
                valid = type(value) is bool if name == "labels" else (type(value) is bool or probability(value))
            else:
                valid = number(value) and 0 <= value <= len(q["criteria"])-1
            if not valid:
                raise ValueError("invalid_" + name)


def validate_baseline(case, payload, component_id):
    receipt = case.get("baseline_receipt")
    if receipt is None:
        return None
    identity = components.comparison_identity(case, payload, component_id)
    if not isinstance(receipt, dict) or receipt.get("comparison_sha256") != digest(identity):
        raise ValueError("baseline_must_match_component_questions_input_and_frozen_context")
    if receipt.get("measurement_scope") != "component" or receipt.get("component_id") != component_id:
        raise ValueError("baseline_latency_cost_must_cover_same_component_only")
    if not all(isinstance(receipt.get(k), str) and receipt[k] for k in ("artifact_reference", "source_commit", "method")):
        raise ValueError("baseline_provenance_required")
    for key in ("latency_ms", "cost_usd"):
        if key in receipt and (not number(receipt[key]) or receipt[key] < 0):
            raise ValueError("invalid_baseline_measurement")
    if set(case.get("baseline_answers", {})) != set(payload["questions"]):
        raise ValueError("baseline_requires_complete_component_answers")
    return identity


def summarize(records):
    valid = [r for r in records if r["status"] == "ok"]
    paired = [r for r in valid if r["baseline_receipt"] and r["fixture_kind"] != "synthetic"]
    metrics = {}
    for key, q in (records[0]["questions"].items() if records else []):
        labeled = [r for r in paired if r["labels"].get(key) is not None and r["baseline_answers"].get(key) is not None]
        metric = {"paired_labeled_cases": len(labeled), "kind": q["type"]}
        if q["type"] == "choice":
            metric.update(
                baseline_accuracy=sum(r["baseline_answers"][key] == r["labels"][key] for r in labeled)/len(labeled) if labeled else None,
                jev_accuracy=sum(r["response"]["answers"][key]["choice"] == r["labels"][key] for r in labeled)/len(labeled) if labeled else None)
        else:
            field = q["type"]
            metric.update(metric="brier" if field == "noul" else "mean_squared_error",
                baseline_error=sum((r["baseline_answers"][key]-r["labels"][key])**2 for r in labeled)/len(labeled) if labeled else None,
                jev_error=sum((r["response"]["answers"][key][field]-r["labels"][key])**2 for r in labeled)/len(labeled) if labeled else None)
        metrics[key] = metric
    latencies = sorted(r["latency_ms"] for r in valid)
    return {"cases": len(records), "successful_requests": len(valid),
            "failed_requests": sum(r["status"] == "error" for r in records),
            "rule_skips": sum(r["status"] == "rule_applies" for r in records),
            "synthetic_cases": sum(r["fixture_kind"] == "synthetic" for r in records),
            "paired_export_cases": len(paired), "metrics": metrics,
            "latency_p50_ms": statistics.median(latencies) if latencies else None,
            "measured_typesafe_cost_usd": sum(r.get("cost_usd", 0) for r in valid),
            "full_pipeline_executed": False, "publication_enabled": False,
            "qualification": "export_experiment_only_not_full_pipeline_benchmark"}


def run(cases, *, component_id=None, execute=False, api_key=None, max_cost_usd=.5,
        transport=call_typesafe, on_event=None):
    if not isinstance(cases, list) or not 1 <= len(cases) <= 50 or any(not isinstance(c, dict) for c in cases):
        raise ValueError("one_to_fifty_export_cases_required_not_a_daily_corpus_limit")
    if not isinstance(component_id, str) or component_id not in components.COMPONENTS:
        raise ValueError("one_known_component_id_required")
    if not number(max_cost_usd) or not 0 < max_cost_usd <= .5:
        raise ValueError("cost_limit_must_be_in_0_to_0_5_usd")
    prepared = [components.prepare(case, component_id) for case in cases]
    if len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("duplicate_case_ids")
    for case, (payload, _) in zip(cases, prepared):
        validate_annotations(case, payload["questions"])
        validate_baseline(case, payload, component_id)
    if execute and not api_key:
        raise ValueError("TYPESAFE_API_KEY_missing")
    records, reserved = [], 0.0
    for case, (payload, skip) in zip(cases, prepared):
        if on_event:
            on_event({"type": "case_started", "case_id": case["case_id"], "component_id": component_id})
        record = {"case_id": case["case_id"], "group_id": case["group_id"],
                  "component_id": component_id, "revision": components.REVISION,
                  "fixture_kind": case.get("fixture_kind", "real_evidence"),
                  "request_sha256": digest(payload), "input_sha256": digest(payload["state"]),
                  "questions": payload["questions"], "questions_sha256": digest(payload["questions"]),
                  "labels": case.get("labels", {}), "baseline_answers": case.get("baseline_answers", {}),
                  "baseline_receipt": case.get("baseline_receipt"),
                  "frozen_context": case.get("frozen_context"),
                  "status": "planned", "binding_status": "export_adapter_only",
                  "publication_enabled": False,
                  "sidecar": {"scope": "textual_advice_only", "raw_observations_changed": False,
                              "vision_can_be_skipped": False, "action": "keep_current_pipeline"}}
        if skip:
            record.update(status="rule_applies", rule_reason=skip)
        elif execute:
            if reserved + RESERVE_PER_REQUEST_USD > max_cost_usd:
                record["status"] = "budget_exhausted"
            else:
                reserved += RESERVE_PER_REQUEST_USD
                started = time.perf_counter()
                try:
                    response = validate_response(transport(payload, api_key), payload["questions"])
                    record.update(status="ok", response=response,
                                  cost_usd=response["usage"]["input_tokens"]*PRICE_PER_INPUT_MILLION_USD/1e6)
                    record["sidecar"]["judgments"] = response["answers"]
                    if component_id == "FV-04":
                        record["sidecar"]["suggested_message"] = components.MESSAGES[response["answers"]["message"]["choice"]]
                    if component_id == "LOC-01":
                        record["sidecar"]["suggested_candidate_id"] = response["answers"]["place"]["choice"]
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    record.update(status="error", error_type=type(exc).__name__)
                record["latency_ms"] = round((time.perf_counter()-started)*1000, 3)
        records.append(record)
        if on_event:
            on_event({"type": "case_finished", "record": record, "completed": len(records), "total": len(cases)})
    report = summarize(records)
    report.update(component_id=component_id, revision=components.REVISION, model=MODEL,
                  mode="live" if execute else "offline_plan", reserved_cost_usd=reserved,
                  projected_max_cost_usd=sum(skip is None for _, skip in prepared)*RESERVE_PER_REQUEST_USD)
    return {"report": report, "records": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("--component", required=True, choices=components.COMPONENTS)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("preserve_previous_receipts")
    cases = [json.loads(line) for line in args.cases.read_text().splitlines() if line.strip()]
    result = run(cases, component_id=args.component, execute=args.execute, api_key=os.environ.get("TYPESAFE_API_KEY"))
    with open(args.output, "x", opener=lambda p, f: os.open(p, f, 0o600)) as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(result["report"], ensure_ascii=False))
