"""Private response safety checks for the guarded Board Sense preview."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

import main
from routes.free_usage_gate import GateDecision


def decision(reason="free_board_available", allowed=True):
    return GateDecision(
        allowed=allowed,
        visitor_id="internal-hash-must-never-leave-server",
        used_today=0,
        limit=1,
        remaining=1 if allowed else 0,
        day_utc="2026-11-19",
        reason=reason,
    )


def make_photo():
    output = BytesIO()
    Image.new("RGB", (12, 12), "green").save(output, "PNG")
    return output.getvalue()


def private_headers(response):
    assert response.headers["cache-control"] == "private, no-store, max-age=0"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"


class PrivateApiResponseTests(unittest.TestCase):
    def test_quota_json_omits_server_side_visitor_id(self):
        self.assertNotIn("visitor_id", decision().as_dict())
        self.assertNotIn("internal-hash-must-never-leave-server", str(decision().as_dict()))

        with patch.object(main, "check_free_board_allowance", return_value=decision()), TestClient(main.app) as client:
            response = client.get("/free-usage")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("visitor_id", response.json()["free_usage"])
        private_headers(response)

    def test_quota_error_omits_id_and_is_not_cached(self):
        blocked = decision("usage_backend_unavailable", allowed=False)
        with patch.object(main, "check_free_board_allowance", return_value=blocked), TestClient(main.app) as client:
            response = client.get("/free-usage")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("visitor_id", response.json()["free_usage"])
        private_headers(response)

    def test_analyze_report_omits_id_and_does_not_cache_derived_image(self):
        with TemporaryDirectory() as directory:
            with (
                patch.object(main, "IMAGE_DIR", Path(directory)),
                patch.object(main, "_gate_or_block", return_value=None),
                patch.object(main, "_claim_or_block", return_value=(decision(), None)),
                patch.object(main, "analyze_board", return_value={
                    "object_gate": {"mode": "board"},
                    "grade": "MANUAL REVIEW",
                    "board_blueprint": {"available": True, "delivery_mode": "inline_no_store",
                                        "image_url": "data:image/jpeg;base64,YQ=="},
                }),
                patch.object(main, "build_evidence_packet", return_value={}),
                TestClient(main.app) as client,
            ):
                response = client.post(
                    "/analyze",
                    files={"file": ("board.png", make_photo(), "image/png")},
                )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn("visitor_id", response.json()["free_usage"])
            self.assertEqual(response.json()["board_blueprint"]["delivery_mode"], "inline_no_store")
            private_headers(response)

    def test_invalid_uploads_and_old_asset_routes_cannot_be_cached_or_served(self):
        with TestClient(main.app) as client:
            for route in ("/analyze", "/upload", "/analyze-pair", "/analyze-case"):
                with self.subTest(route=route):
                    response = client.post(route, content=b"invalid form")
                    self.assertEqual(response.status_code, 422, response.text)
                    private_headers(response)

            for route in ("/blueprints/nonexistent-test.png", "/multi-board-crops/nonexistent-test.png"):
                self.assertEqual(client.get(route).status_code, 404)

            self.assertEqual(client.get("/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
