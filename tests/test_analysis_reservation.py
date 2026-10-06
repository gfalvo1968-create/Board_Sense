"""Exercise real HTTP upload validation and atomic allowance ordering."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from io import BytesIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

import main
from routes import free_usage_gate as gate, grade, irm_core


def photo():
    out = BytesIO()
    Image.new("RGB", (3, 3), "green").save(out, "PNG")
    return ("board.png", out.getvalue(), "image/png")


class AnalysisReservationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(TemporaryDirectory()))
        self.images = root / "data" / "Images"
        self.usage_file = root / "usage.json"
        self.stack.enter_context(patch.dict(os.environ, {"RAILWAY_ENVIRONMENT_NAME": "", "BOARD_SENSE_VISITOR_SALT": "test-salt"}))
        for module, name, value in [(main, "IMAGE_DIR", self.images), (grade, "IMAGE_DIR", self.images),
                                    (gate, "USAGE_FILE", self.usage_file), (gate, "BOARD_SENSE_ENV", "development"),
                                    (gate, "BOARD_SENSE_TESTER_KEY", ""), (gate, "DAILY_FREE_BOARD_LIMIT", 1)]:
            self.stack.enter_context(patch.object(module, name, value))
        self.stack.enter_context(patch.object(gate, "_supabase_ready", return_value=False))
        # Let every contender pass the non-consuming preview check. The actual
        # claim must still allow only one request to reach analysis.
        preview = gate.GateDecision(True, "preview", 0, 1, 1, gate._utc_day(), "free_board_available")
        self.stack.enter_context(patch.object(main, "check_free_board_allowance", return_value=preview))
        self.stack.enter_context(patch.object(grade, "check_free_board_allowance", return_value=preview))
        self.stack.enter_context(patch.object(main, "build_evidence_packet", return_value={}))
        self.stack.enter_context(patch.object(main, "load_reference_data"))

        def analyze(path):
            self.assertTrue(Path(path).is_file())
            usage = json.loads(self.usage_file.read_text())
            counts = [r["boards"] for r in usage["days"][gate._utc_day()].values()]
            self.assertEqual(counts, [1], "claim must exist before analysis")
            return {"grade": "MEDIUM", "confidence": 70, "board_type": "Test Board"}

        self.analyzer = self.stack.enter_context(patch.object(main, "analyze_board", side_effect=analyze))
        self.stack.enter_context(patch.object(grade, "analyze_board", self.analyzer))

    def post(self, path, files, data=None, headers=None):
        with TestClient(main.app) as client:
            return client.post(path, files=files, data=data or {}, headers=headers or {})

    def test_all_analysis_routes_reserve_before_any_view(self):
        cases = [("/analyze", [("file", photo())], 1),
                 ("/upload", [("file", photo())], 1),
                 ("/analyze-spike-pair", [("context", photo()), ("closeup", photo())], 2),
                 ("/analyze-pair", [("side_a", photo()), ("side_b", photo())], 2),
                 ("/analyze-case", [("files", photo()), ("files", photo())], 2)]
        self.stack.enter_context(patch.object(main, "reconcile_case", return_value={}))
        self.stack.enter_context(patch.object(main, "reconcile_pair", return_value={}))
        self.stack.enter_context(patch.object(main, "guard_pair", return_value={}))
        for path, files, count in cases:
            with self.subTest(path=path):
                self.usage_file.unlink(missing_ok=True)
                self.analyzer.reset_mock()
                r = self.post(path, files)
                self.assertEqual(r.status_code, 200, r.text)
                self.assertEqual(r.json()["free_usage"]["used_today"], 1)
                self.assertEqual(self.analyzer.call_count, count)
                self.assertEqual(list(self.images.iterdir()), [])

    def test_simultaneous_requests_cannot_run_extra_analysis(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            replies = list(pool.map(lambda _: self.post("/analyze", [("file", photo())]), range(8)))
        self.assertEqual(sorted(r.status_code for r in replies), [200] + [429] * 7)
        self.assertEqual(self.analyzer.call_count, 1)
        self.assertEqual(list(self.images.iterdir()), [])
        r = self.post("/analyze", [("file", photo())], headers={"User-Agent": "Changed Browser"})
        self.assertEqual(r.status_code, 429)
        self.assertEqual(self.analyzer.call_count, 1)

    def test_invalid_last_view_never_claims_or_analyzes(self):
        r = self.post("/analyze-case", [("files", photo()), ("files", ("bad.png", b"not an image", "image/png"))])
        self.assertEqual(r.status_code, 400)
        self.assertFalse(self.usage_file.exists())
        self.analyzer.assert_not_called()
        self.assertEqual(list(self.images.iterdir()), [])

    def test_bad_economics_are_rejected_before_analysis(self):
        for invalid in ("-1", "nan", "inf"):
            r = self.post("/analyze-case", [("files", photo()), ("files", photo())], {"full_recovery_value": invalid})
            self.assertEqual(r.status_code, 422, r.text)
        self.analyzer.assert_not_called()
        self.assertFalse(self.usage_file.exists())

    def test_multiple_boards_halt_without_extra_reports_or_economics(self):
        blocked = {"status": "case_identity_failed", "same_board_verification": {
            "status": "MULTIPLE_BOARDS_DETECTED", "block_reconciliation": True}}
        self.stack.enter_context(patch.object(main, "reconcile_case", return_value=blocked))
        economics = self.stack.enter_context(patch.object(main, "compare_paths"))
        r = self.post("/analyze-case", [("files", photo()), ("files", photo())], {"operator_same_board_confirmation": "true"})
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertEqual(payload["mode"], "multi_photo_identity_blocked")
        self.assertEqual(payload["free_usage"]["used_today"], 1)
        self.assertIn("separate case", payload["case_warning"])
        self.assertNotIn("multi_board_material_report", payload["combined"])
        self.assertEqual(self.analyzer.call_count, 2)
        economics.assert_not_called()


class PrivateSourceTests(unittest.TestCase):
    def test_anonymous_and_tester_requests_cannot_read_or_write_contacts(self):
        with patch.dict(os.environ, {"BOARD_SENSE_IRM_ADMIN_KEY": "a" * 40}), \
                patch.object(irm_core, "load_sources", side_effect=AssertionError("private read")), \
                TestClient(main.app) as client:
            self.assertEqual(client.get("/irm/sources").status_code, 401)
            self.assertEqual(client.get("/irm/sources", headers={"x-board-sense-tester-key": "a" * 40}).status_code, 401)
            self.assertEqual(client.post("/irm/save-source", json={"name": "private"}).status_code, 401)

    def test_source_records_are_disabled_until_admin_key_is_configured(self):
        with patch.dict(os.environ, {"BOARD_SENSE_IRM_ADMIN_KEY": ""}), TestClient(main.app) as client:
            self.assertEqual(client.get("/irm/sources").status_code, 503)

    def test_separate_admin_can_read_contacts(self):
        with patch.dict(os.environ, {"BOARD_SENSE_IRM_ADMIN_KEY": "a" * 40}), \
                patch.object(irm_core, "load_sources", return_value=[]), TestClient(main.app) as client:
            r = client.get("/irm/sources", headers={"Authorization": "Bearer " + "a" * 40})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["sources"], [])
