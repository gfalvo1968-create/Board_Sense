"""Guarded route for private separate-board testing: no public quota bypass."""
import os
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

import main
from routes import free_usage_gate as gate


def photo_bytes():
    out = BytesIO()
    Image.new("RGB", (80, 80), "green").save(out, format="PNG")
    return out.getvalue()


class MultiBoardTesterRouteTests(unittest.TestCase):
    def setUp(self):
        self.flags = patch.dict(os.environ, {
            "BOARD_SENSE_MULTI_BOARD_PREVIEW": "enabled",
            "BOARD_SENSE_ENV": "staging",
            "RAILWAY_ENVIRONMENT_NAME": "staging",
        })
        self.flags.start()
        self.addCleanup(self.flags.stop)
        self.tester = patch.object(gate, "BOARD_SENSE_TESTER_KEY", "private-in-test-only")
        self.tester.start()
        self.addCleanup(self.tester.stop)

    def post(self, headers=None, data=None):
        with TestClient(main.app) as client:
            return client.post("/analyze-multi", files={"file": (
                "boards.png", photo_bytes() if data is None else data, "image/png"
            )}, headers=headers or {})

    def test_staging_capability_reflects_feature_flag_not_private_secret(self):
        with TestClient(main.app) as client:
            response = client.get("/multi-board-capabilities")
        self.assertTrue(response.json()["tester_preview_enabled"])
        self.assertNotIn("private-in-test-only", response.text)

    def test_production_can_never_enable_preview_even_with_flag(self):
        with patch.dict(os.environ, {"BOARD_SENSE_ENV": "production"}):
            response = self.post(headers={"x-board-sense-tester-key": "private-in-test-only"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["cache-control"], "private, no-store, max-age=0")
        with patch.dict(os.environ, {"RAILWAY_ENVIRONMENT_NAME": "production"}), TestClient(main.app) as client:
            self.assertFalse(client.get("/multi-board-capabilities").json()["tester_preview_enabled"])

    def test_disabled_flag_hides_route(self):
        with patch.dict(os.environ, {"BOARD_SENSE_MULTI_BOARD_PREVIEW": ""}):
            response = self.post(headers={"x-board-sense-tester-key": "private-in-test-only"})
        self.assertEqual(response.status_code, 404)

    def test_missing_and_wrong_tester_keys_cannot_use_multi_board_quota(self):
        with patch.object(main, "analyze_single_or_independent_boards") as analyzer:
            for headers in ({}, {"x-board-sense-tester-key": "wrong"}):
                response = self.post(headers=headers)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.headers["cache-control"], "private, no-store, max-age=0")
                self.assertNotIn("private-in-test-only", response.text)
            analyzer.assert_not_called()

    def test_valid_tester_gets_only_independent_reports_and_temp_upload_is_removed(self):
        seen = []
        reply = {
            "status": "separate_reports",
            "mode": "separate_board_preview",
            "board_count": 2,
            "reports": [
                {"board_index": 1, "provisional_grade": "LOW"},
                {"board_index": 2, "provisional_grade": "MEDIUM"},
            ],
            "combined_grade": None,
            "combined_recovery_economics": None,
        }
        def analyze(path):
            seen.append(Path(path))
            self.assertTrue(Path(path).is_file())
            return reply
        with TemporaryDirectory() as directory, patch.object(main, "IMAGE_DIR", Path(directory)), \
             patch.object(main, "analyze_single_or_independent_boards", side_effect=analyze), \
             patch.object(main, "_claim_or_block", side_effect=AssertionError("Never debit one preview for multiple boards.")):
            response = self.post(headers={"x-board-sense-tester-key": "private-in-test-only"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual([r["provisional_grade"] for r in response.json()["reports"]], ["LOW", "MEDIUM"])
            self.assertIsNone(response.json()["combined_grade"])
            self.assertIsNone(response.json()["combined_recovery_economics"])
            self.assertEqual(list(Path(directory).iterdir()), [], "Private uploaded file must be removed")
        self.assertEqual(len(seen), 1)
        self.assertFalse(seen[0].exists())
        self.assertEqual(response.headers["cache-control"], "private, no-store, max-age=0")
        self.assertNotIn("private-in-test-only", response.text)

    def test_authorized_one_board_uses_standard_shape_not_multi_card(self):
        normal = {
            "status": "success",
            "scan_path": "standard_one_board",
            "grade": "MANUAL REVIEW",
            "confidence": 45,
            "board_type": "General PCB",
            "object_gate": {"mode": "board"},
        }
        with patch.object(main, "analyze_single_or_independent_boards", return_value=normal) as analyze:
            response = self.post(headers={"x-board-sense-tester-key": "private-in-test-only"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["scan_path"], "standard_one_board")
        self.assertEqual(response.json()["grade"], "MANUAL REVIEW")
        self.assertNotIn("reports", response.json())
        analyze.assert_called_once()
        self.assertEqual(response.headers["cache-control"], "private, no-store, max-age=0")

    def test_public_free_one_board_credit_cannot_yield_two_board_reports(self):
        with (
            patch.object(main, "_gate_or_block", return_value=None),
            patch.object(main, "inspect_frame", return_value={
                "status": "MULTIPLE_BOARDS_OR_OVERLAP_SUSPECTED",
                "block_analysis": True,
            }),
            patch.object(main, "_claim_or_block", side_effect=AssertionError("Rejected photo must not consume allowance")) as claim,
            patch.object(main, "analyze_board", side_effect=AssertionError("Never issue a blended grade")) as analyze,
            TestClient(main.app) as client,
        ):
            response = client.post("/analyze", files={"file": (
                "boards.png", photo_bytes(), "image/png"
            )})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["status"], "multi_board_requires_separate_scans")
        self.assertIs(data["credit_consumed"], False)
        self.assertIsNone(data["grade"])
        self.assertEqual(data["reports"], [])
        self.assertIn("one physical board", data["message"].lower())
        self.assertEqual(response.headers["cache-control"], "private, no-store, max-age=0")
        claim.assert_not_called()
        analyze.assert_not_called()

    def test_public_one_board_still_uses_existing_atomic_claim(self):
        from routes.free_usage_gate import GateDecision
        allowance = GateDecision(
            True, "private-hash-not-returned", 1, 1, 0, "2026-11-20", "recorded"
        )
        with (
            patch.object(main, "_gate_or_block", return_value=None),
            patch.object(main, "inspect_frame", return_value={
                "status": "SINGLE_BOARD_NOT_CONTRADICTED",
                "block_analysis": False,
            }),
            patch.object(main, "_claim_or_block", return_value=(allowance, None)) as claim,
            patch.object(main, "analyze_board", return_value={
                "object_gate": {"mode": "board"}, "grade": "MEDIUM", "confidence": 67
            }) as analyze,
            patch.object(main, "build_evidence_packet", return_value={}),
            TestClient(main.app) as client,
        ):
            response = client.post("/analyze", files={"file": (
                "board.png", photo_bytes(), "image/png"
            )})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["grade"], "MEDIUM")
        self.assertEqual(response.json()["free_usage"]["used_today"], 1)
        claim.assert_called_once()
        analyze.assert_called_once()

    def test_invalid_upload_does_not_invoke_analyzer(self):
        with patch.object(main, "analyze_single_or_independent_boards") as analyzer:
            response = self.post(
                headers={"x-board-sense-tester-key": "private-in-test-only"},
                data=b"not-a-png",
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.headers["cache-control"], "private, no-store, max-age=0")
            analyzer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
