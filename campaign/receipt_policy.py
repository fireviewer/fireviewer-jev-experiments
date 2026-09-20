"""Acceptance requires source identity and successful runs, not just equal counts."""
def complete_day(expected_ids, items, runs):
    ids = [item.get("input_id") for item in items]
    return (bool(expected_ids) and len(ids) == len(set(ids))
            and set(ids) == set(expected_ids) and bool(runs)
            and all(run.get("status") == "COMPLETED"
                    and run.get("output_status") == "succeeded"
                    and not run.get("validation_errors")
                    and all(model.get("status") == "succeeded"
                            for model in run.get("model_runs", []))
                    for run in runs))
