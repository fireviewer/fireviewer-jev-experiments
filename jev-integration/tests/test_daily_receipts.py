import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/"campaign"))
from receipt_policy import complete_day

class DailyReceiptTests(unittest.TestCase):
    def test_success_requires_exact_source_identity(self):
        runs=[{"status":"COMPLETED", "output_status":"succeeded", "model_runs":[{"status":"succeeded"}]}]
        self.assertTrue(complete_day(["a","b"], [{"input_id":"a"},{"input_id":"b"}], runs))
        self.assertFalse(complete_day(["a","b"], [{"input_id":"a"},{"input_id":"a"}], runs))
        self.assertFalse(complete_day(["a","b"], [{"input_id":"a"},{"input_id":"c"}], runs))
    def test_cancelled_or_failed_model_never_completes_day(self):
        for run in [{"status":"CANCELLED","output_status":"succeeded"},
                    {"status":"COMPLETED","output_status":"failed"},
                    {"status":"COMPLETED","output_status":"succeeded","model_runs":[{"status":"failed"}]}]:
            self.assertFalse(complete_day(["a"],[{"input_id":"a"}],[run]))
